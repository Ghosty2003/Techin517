#!/usr/bin/env python3
"""Grasp state machine: IDLE → GRASPING → IDLE.

Listens for /hover_done published by hover_to_object once the arm is
positioned above the target. On receipt:
  1. Publishes state = GRASPING
  2. Switches hardware controllers from JTC (MoveIt) to FCC (Rosetta)
  3. Sends RunPolicy goal to the Rosetta client
  4. When policy finishes, switches back to JTC and publishes state = IDLE

Prerequisites (must already be running):
    ros2 launch soa_moveit_config soa_moveit_bringup.launch.py
    ros2 launch rosetta rosetta_client_launch.py ...
    ros2 run soa_apps hover_to_object <class_name>

Run:
    ros2 run soa_apps grasp_state_machine --ros-args \\
        -p policy_action:=/rosetta_client/run_policy \\
        -p controller_switch_service:=/controller_switcher/switch_controller \\
        -p prompt:="grasp object"
"""

import enum
import subprocess
import threading

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile

from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState, GetState
from std_msgs.msg import String

from rosetta_interfaces.action import RunPolicy
from soa_interfaces.srv import SwitchController


class State(enum.Enum):
    IDLE     = "IDLE"
    GRASPING = "GRASPING"


class GraspStateMachineNode(Node):

    def __init__(self):
        super().__init__("grasp_state_machine")

        self.declare_parameter("policy_action",             "/run_policy")
        self.declare_parameter("controller_switch_service", "/controller_switcher/switch_controller")
        self.declare_parameter("prompt",                    "grasp object")
        self.declare_parameter("policy_timeout_s",          10.0)
        self.declare_parameter("csv_path",                  "/home/ubuntu/techin517/poses_scissor.csv")
        self.declare_parameter("hover_done_topic",          "/hover_done")
        self.declare_parameter("gripper_close_at",          "0")
        self.declare_parameter("gripper_open_at",           "7")
        self.declare_parameter("arm_ns",                    "")
        self.declare_parameter("run_go_to_poses",           True)
        # Per-object policy override: "object:action_path,object2:action_path2"
        # e.g. "plier:/rosetta_client_left_plier/run_policy"
        # Objects not listed use the default policy_action.
        self.declare_parameter("policy_action_map",         "")

        policy_action          = self.get_parameter("policy_action").value
        switch_srv             = self.get_parameter("controller_switch_service").value
        self._prompt           = self.get_parameter("prompt").value
        self._policy_timeout   = self.get_parameter("policy_timeout_s").value
        self._csv_path         = self.get_parameter("csv_path").value
        self._hover_done_topic = self.get_parameter("hover_done_topic").value
        self._gripper_close_at  = self.get_parameter("gripper_close_at").value
        self._gripper_open_at   = self.get_parameter("gripper_open_at").value
        self._arm_ns            = self.get_parameter("arm_ns").value
        self._run_go_to_poses   = self.get_parameter("run_go_to_poses").value

        self._cb = ReentrantCallbackGroup()

        # Parse policy_action_map → {object_name: action_path}
        self._policy_action_map: dict[str, str] = {}
        map_str = self.get_parameter("policy_action_map").value.strip()
        if map_str:
            for entry in map_str.split(','):
                parts = entry.strip().split(':', 1)
                if len(parts) == 2:
                    self._policy_action_map[parts[0].strip().lower()] = parts[1].strip()

        # Default policy client + one per mapped object
        self._default_policy_action = policy_action
        self._policy_clients: dict[str, ActionClient] = {
            policy_action: ActionClient(self, RunPolicy, policy_action, callback_group=self._cb)
        }
        for obj, action in self._policy_action_map.items():
            if action not in self._policy_clients:
                self._policy_clients[action] = ActionClient(
                    self, RunPolicy, action, callback_group=self._cb
                )
            self.get_logger().info(f"  policy_action_map: {obj} → {action}")

        # Convenience: keep the default client accessible for backwards compat
        self._policy_client = self._policy_clients[policy_action]

        # Current object being grasped (set from hover_done, used to select policy)
        self._current_object: str = ''

        # Controller switcher service client
        self._switch_client = self.create_client(SwitchController, switch_srv,
                                                 callback_group=self._cb)

        # Publish current state (TRANSIENT_LOCAL so late subscribers get it)
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._state_pub = self.create_publisher(String, "~/state", qos)

        # Subscribe to hover_done signal from hover_to_object
        self.create_subscription(String, self._hover_done_topic, self._on_hover_done, 10,
                                 callback_group=self._cb)

        self._state = State.IDLE
        self._state_lock = threading.Lock()
        self._goal_handle = None
        self._timeout_timer: threading.Timer | None = None
        self._publish_state()

        self.get_logger().info(
            f"State machine ready. Waiting for /hover_done ...\n"
            f"  policy_action={policy_action}\n"
            f"  switch_service={switch_srv}\n"
            f"  prompt='{self._prompt}'\n"
            f"  policy_timeout={self._policy_timeout}s"
        )

    # ------------------------------------------------------------------
    # /hover_done callback
    # ------------------------------------------------------------------

    def _on_hover_done(self, msg: String):
        with self._state_lock:
            if self._state != State.IDLE:
                self.get_logger().warn("Received /hover_done but not in IDLE — ignoring.")
                return
            self._state = State.GRASPING  # claim the state before releasing lock

        # Extract object name from hover_done payload: "object,x,y,z,..."
        parts = msg.data.split(',')
        self._current_object = parts[0].strip().lower() if parts else ''

        self.get_logger().info(f"[hover_done] {msg.data} — starting grasp sequence.")
        threading.Thread(target=self._grasping_thread, daemon=True).start()

    # ------------------------------------------------------------------
    # GRASPING sequence (runs in a background thread to avoid blocking
    # the executor and to get proper timeouts on async calls)
    # ------------------------------------------------------------------

    def _grasping_thread(self):
        self._publish_state()

        self.get_logger().info("[GRASPING] Switching controllers to FCC (forward) ...")
        if not self._switch_controller("forward"):
            self.get_logger().error("Controller switch to FCC failed — aborting grasp.")
            self._return_to_idle()
            return
        self.get_logger().info("[GRASPING] Controller switch to FCC succeeded.")

        # Select policy action based on detected object; fall back to default
        selected_action = self._policy_action_map.get(self._current_object,
                                                       self._default_policy_action)
        self._policy_client = self._policy_clients[selected_action]
        # action = '/{node_name}/run_policy' → namespace prefix = '/{node_name}'
        # node full path = '/{node_name}/rosetta_client' (name set in rosetta_client_launch.py)
        _ns_prefix = '/'.join(selected_action.rstrip('/').split('/')[:-1])
        self._lifecycle_node = f'{_ns_prefix}/rosetta_client'
        self.get_logger().info(
            f"[GRASPING] Object='{self._current_object}' → policy action='{selected_action}'"
        )
        self.get_logger().info(f"[GRASPING] Lifecycle node resolved to: '{self._lifecycle_node}'")

        # Check action server availability before sending goal
        self.get_logger().info(f"[GRASPING] Waiting for action server '{selected_action}' ...")
        server_ready = self._policy_client.wait_for_server(timeout_sec=5.0)
        if not server_ready:
            self.get_logger().error(
                f"[GRASPING] Action server '{selected_action}' NOT available after 5s — aborting. "
                f"Check that rosetta_client_node is running and the action name matches."
            )
            self._return_to_idle()
            return
        self.get_logger().info(f"[GRASPING] Action server '{selected_action}' is available.")

        self.get_logger().info(f"[GRASPING] Sending RunPolicy goal with prompt='{self._prompt}' ...")

        goal = RunPolicy.Goal()
        goal.prompt = self._prompt

        accepted_event = threading.Event()
        _result = [None, None]  # [goal_handle, exception]

        def _on_accepted(future):
            self.get_logger().info("[GRASPING] send_goal_async callback fired.")
            try:
                _result[0] = future.result()
                self.get_logger().info(
                    f"[GRASPING] Goal response received — accepted={_result[0].accepted}"
                )
            except Exception as e:
                _result[1] = e
                self.get_logger().error(f"[GRASPING] send_goal_async raised exception: {e}")
            accepted_event.set()

        future = self._policy_client.send_goal_async(
            goal, feedback_callback=self._on_policy_feedback
        )
        self.get_logger().info("[GRASPING] send_goal_async called — waiting up to 15s for acceptance ...")
        future.add_done_callback(_on_accepted)

        if not accepted_event.wait(timeout=15.0):
            self.get_logger().error(
                "[GRASPING] Policy goal acceptance timed out after 15s — the action server "
                "did not respond. Verify ros2 action list shows the action and the node is active."
            )
            self._return_to_idle()
            return
        self.get_logger().info("[GRASPING] Acceptance event received.")

        if _result[1] is not None:
            self.get_logger().error(f"Policy goal send failed: {_result[1]} — aborting.")
            self._return_to_idle()
            return

        goal_handle = _result[0]
        if not goal_handle.accepted:
            self.get_logger().warn("Policy goal rejected — attempting to re-activate rosetta...")
            if self._reactivate_rosetta():
                # retry once after re-activation
                accepted_event.clear()
                _result[0] = _result[1] = None
                future = self._policy_client.send_goal_async(
                    goal, feedback_callback=self._on_policy_feedback
                )
                future.add_done_callback(_on_accepted)
                if not accepted_event.wait(timeout=15.0):
                    self.get_logger().error("Policy goal retry timed out — aborting.")
                    self._return_to_idle()
                    return
                goal_handle = _result[0]
                if goal_handle is None or not goal_handle.accepted:
                    self.get_logger().error("Policy goal rejected after re-activation — aborting.")
                    self._return_to_idle()
                    return
            else:
                self.get_logger().error("Policy goal rejected and re-activation failed — aborting.")
                self._return_to_idle()
                return

        self._goal_handle = goal_handle
        self._timeout_timer = threading.Timer(self._policy_timeout, self._on_policy_timeout)
        self._timeout_timer.start()
        self.get_logger().info(
            f"[GRASPING] Policy running — will stop in {self._policy_timeout:.0f}s."
        )

        goal_handle.get_result_async().add_done_callback(self._on_grasp_done)

    def _on_policy_feedback(self, feedback_msg):
        fb = feedback_msg.feedback
        self.get_logger().info(
            f"[GRASPING] actions={fb.published_actions} queue={fb.queue_depth} {fb.status}"
        )

    def _on_policy_timeout(self):
        self.get_logger().info("[GRASPING] Timeout reached — cancelling policy and returning to IDLE.")
        if self._goal_handle is not None:
            self._goal_handle.cancel_goal_async()
            self._goal_handle = None
        # Return to IDLE immediately — don't wait for _on_grasp_done which may never fire
        # if rosetta doesn't acknowledge the cancellation.
        self._return_to_idle()

    def _on_grasp_done(self, future):
        # Cancel the timeout timer if the policy finished before it fired
        if self._timeout_timer is not None:
            self._timeout_timer.cancel()
            self._timeout_timer = None
        self._goal_handle = None

        try:
            result = future.result().result
            if result.success:
                self.get_logger().info(f"[GRASPING] Policy succeeded: {result.message}")
            else:
                self.get_logger().warn(f"[GRASPING] Policy ended: {result.message}")
        except Exception as e:
            self.get_logger().warn(f"[GRASPING] Could not read policy result: {e}")

        self._return_to_idle()

    def _return_to_idle(self):
        with self._state_lock:
            if self._state == State.IDLE:
                return  # already returned (timeout and _on_grasp_done raced)
            self._state = State.IDLE
        self._switch_controller("jtc")
        self._publish_state()
        self.get_logger().info("[IDLE] Controllers back to JTC. Ready for next /hover_done.")
        if self._run_go_to_poses:
            threading.Thread(target=self._run_go_to_poses_subprocess, daemon=True).start()

    def _run_go_to_poses_subprocess(self):
        cmd = [
            'ros2', 'run', 'soa_apps', 'go_to_poses',
            '--ros-args',
            '-p', f'csv_path:={self._csv_path}',
            '-p', f'gripper_close_at:={self._gripper_close_at}',
            '-p', f'gripper_open_at:={self._gripper_open_at}',
        ]
        if self._arm_ns:
            cmd += ['-p', f'arm_ns:={self._arm_ns}']
        self.get_logger().info(f"[IDLE] Launching go_to_poses with csv_path={self._csv_path}")
        proc = subprocess.run(cmd, capture_output=False)
        if proc.returncode != 0:
            self.get_logger().error(f"go_to_poses exited with code {proc.returncode}")

    # ------------------------------------------------------------------
    # Rosetta lifecycle re-activation
    # ------------------------------------------------------------------

    def _call_lifecycle_transition(self, transition_id: int) -> bool:
        client = self.create_client(ChangeState, f'{self._lifecycle_node}/change_state',
                                    callback_group=self._cb)
        if not client.wait_for_service(timeout_sec=3.0):
            self.get_logger().error(f"Lifecycle change_state not available for {self._lifecycle_node}")
            return False
        req = ChangeState.Request()
        req.transition.id = transition_id
        future = client.call_async(req)
        done = threading.Event()
        future.add_done_callback(lambda _: done.set())
        if not done.wait(timeout=5.0):
            return False
        result = future.result()
        return result is not None and result.success

    def _reactivate_rosetta(self) -> bool:
        # Check current lifecycle state
        get_client = self.create_client(GetState, f'{self._lifecycle_node}/get_state',
                                        callback_group=self._cb)
        if get_client.wait_for_service(timeout_sec=3.0):
            future = get_client.call_async(GetState.Request())
            done = threading.Event()
            future.add_done_callback(lambda _: done.set())
            if done.wait(timeout=3.0) and future.result():
                state_id = future.result().current_state.id
                self.get_logger().info(
                    f"Rosetta lifecycle state id={state_id} — attempting activate."
                )
                # UNCONFIGURED (1) → configure first
                if state_id == 1:
                    if not self._call_lifecycle_transition(Transition.TRANSITION_CONFIGURE):
                        self.get_logger().error("Rosetta configure failed.")
                        return False
        return self._call_lifecycle_transition(Transition.TRANSITION_ACTIVATE)

    # ------------------------------------------------------------------
    # Controller switch
    # ------------------------------------------------------------------

    def _switch_controller(self, mode: str) -> bool:
        if not self._switch_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error("controller_switcher service not available.")
            return False

        req = SwitchController.Request()
        req.controller_type = mode

        future = self._switch_client.call_async(req)
        done = threading.Event()
        future.add_done_callback(lambda _: done.set())
        if not done.wait(timeout=10.0):
            self.get_logger().error("controller_switcher call timed out.")
            return False

        res = future.result()
        if res is None:
            self.get_logger().error("controller_switcher returned no result.")
            return False
        if res.success:
            self.get_logger().info(f"Controller switched to '{res.current_controller}'.")
        else:
            self.get_logger().error(f"Controller switch to '{mode}' failed.")
        return res.success

    # ------------------------------------------------------------------

    def _publish_state(self):
        msg = String()
        msg.data = self._state.value
        self._state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = GraspStateMachineNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
