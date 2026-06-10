#!/usr/bin/env python3
"""grasp_sequencer.py

Orchestrates bimanual grasping: monitors YOLO detections and runs
hover_to_object + go_to_poses for each arm in priority order.

  Left arm:  tape → pen → plier
  Right arm: screwdriver → scissor

Each arm runs its own daemon thread that loops:
  1. Wait for arm state machine to be IDLE
  2. Find highest-priority object visible in YOLO
  3. Run hover_to_object subprocess (blocking)
  4. Wait for state machine to enter GRASPING then return to IDLE
  5. Run go_to_poses with the CSV for that specific object (optional)
  6. Repeat

Prerequisites (must be running):
  bi_soa_moveit_bringup (hardware + MoveIt + controller_switchers)
  move_to_pose_server, gripper_server per arm
  rosetta_client (left + right)
  grasp_state_machine (left + right) with run_go_to_poses:=false
  YOLO detection publishing to /yolo/detections_3d
"""

import datetime
import os
import subprocess
import threading
import time

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile

from std_msgs.msg import String
from yolo_msgs.msg import DetectionArray


class GraspSequencer(Node):

    def __init__(self):
        super().__init__('grasp_sequencer')

        # Priority sequences (comma-separated, highest priority first)
        self.declare_parameter('left_sequence',  'tape,pen,plier')
        self.declare_parameter('right_sequence', 'screwdriver,scissor')

        # Arm namespaces (must match arm_ns used in state machines)
        self.declare_parameter('left_arm_ns',  'left')
        self.declare_parameter('right_arm_ns', 'right')

        # hover_to_object position offsets — left arm
        self.declare_parameter('left_x_offset', 0.0)
        self.declare_parameter('left_y_offset', 0.0)
        self.declare_parameter('left_z_offset', 0.0)

        # TF transform for left arm (camera is calibrated to right_base_link)
        self.declare_parameter('left_tf_source_frame', 'base_link')
        self.declare_parameter('left_tf_target_frame', 'left_base_link')

        # hover_to_object position offsets — right arm
        self.declare_parameter('right_x_offset', 0.0)
        self.declare_parameter('right_y_offset', -0.05)
        self.declare_parameter('right_z_offset', 0.0)

        # Base directory for go_to_poses CSVs.
        # Path is constructed as: {csv_base_dir}/{arm}_{object}.csv
        # e.g. /home/ubuntu/techin517/left_pen.csv, right_scissor.csv
        # If the file does not exist, go_to_poses is skipped for that object.
        self.declare_parameter('csv_base_dir', '/home/ubuntu/techin517')

        # Shared gripper timing for go_to_poses
        self.declare_parameter('left_gripper_close_at',  '9')
        self.declare_parameter('left_gripper_open_at',   '7')
        self.declare_parameter('right_gripper_close_at', '0')
        self.declare_parameter('right_gripper_open_at',  '7')

        # Gripper positions used during go_to_poses (radians)
        # 1.7453 = fully open, -0.1745 = fully closed
        self.declare_parameter('left_gripper_open_position',   1.0)
        self.declare_parameter('right_gripper_open_position',  1.0)
        self.declare_parameter('left_gripper_close_position',  -0.0)
        self.declare_parameter('right_gripper_close_position', -0.0)

        # Set False to skip home-return between grasps entirely
        self.declare_parameter('run_go_to_poses', True)

        # State machine ~/state topic names
        # Must match node names given to grasp_state_machine instances.
        self.declare_parameter('left_state_topic',  '/left_grasp_state_machine/state')
        self.declare_parameter('right_state_topic', '/right_grasp_state_machine/state')

        # Detection parameters
        self.declare_parameter('detection_window_s',  2.0)
        self.declare_parameter('min_detection_score', 0.5)

        # Comma-separated list of left-arm objects that pause the right arm
        # while the left arm is actively working on them (hover → grasp → return).
        # Example: 'tape' means right arm waits whenever left arm picks up tape.
        self.declare_parameter('right_pause_on_left', 'tape')

        # Parsed sequences
        self._left_sequence  = [
            c.strip() for c in self.get_parameter('left_sequence').value.split(',') if c.strip()
        ]
        self._right_sequence = [
            c.strip() for c in self.get_parameter('right_sequence').value.split(',') if c.strip()
        ]

        self._detection_window = self.get_parameter('detection_window_s').value
        self._min_score        = self.get_parameter('min_detection_score').value
        self._run_go_to_poses  = self.get_parameter('run_go_to_poses').value

        # Which arm owns each object (derived from sequences)
        self._arm_of: dict[str, str] = {}
        for cls in self._left_sequence:
            self._arm_of[cls] = 'left'
        for cls in self._right_sequence:
            self._arm_of[cls] = 'right'

        # Detection cache: {class_name: (best_score, last_seen_timestamp)}
        self._detections: dict[str, tuple[float, float]] = {}
        self._det_lock = threading.Lock()

        # Current arm states — updated by subscription callbacks
        self._arm_state: dict[str, str] = {'left': 'IDLE', 'right': 'IDLE'}

        # Active target per arm — set when hover starts, cleared after return finishes
        self._active_target: dict[str, str | None] = {'left': None, 'right': None}

        # Parse right_pause_on_left into a set for fast lookup
        self._right_pause_on_left: set[str] = {
            t.strip() for t in self.get_parameter('right_pause_on_left').value.split(',') if t.strip()
        }

        # YOLO subscription
        self.create_subscription(DetectionArray, '/yolo/detections_3d', self._on_detection, 10)

        # Arm state subscriptions (TRANSIENT_LOCAL — receive last published value on connect)
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(
            String,
            self.get_parameter('left_state_topic').value,
            lambda msg: self._on_state('left', msg),
            qos,
        )
        self.create_subscription(
            String,
            self.get_parameter('right_state_topic').value,
            lambda msg: self._on_state('right', msg),
            qos,
        )

        # File logger
        log_path = os.path.join(
            self.get_parameter('csv_base_dir').value, 'log.txt'
        )
        self._log_file = open(log_path, 'a')
        self._log(f'=== GraspSequencer started ===')

        # Launch per-arm dispatch threads
        for arm in ('left', 'right'):
            threading.Thread(target=self._arm_loop, args=(arm,), daemon=True).start()

        self.get_logger().info(
            f"GraspSequencer ready.\n"
            f"  Left  sequence: {self._left_sequence}\n"
            f"  Right sequence: {self._right_sequence}\n"
            f"  run_go_to_poses: {self._run_go_to_poses}\n"
            f"  right_pause_on_left: {self._right_pause_on_left}"
        )

    # ------------------------------------------------------------------ #
    #  ROS callbacks                                                       #
    # ------------------------------------------------------------------ #

    def _on_detection(self, msg: DetectionArray):
        now = time.time()
        # Per frame: keep only the largest-bbox detection per class (above threshold)
        best_in_frame: dict[str, tuple[float, float]] = {}  # cls → (score, area)
        for det in msg.detections:
            if det.score < self._min_score:
                continue
            cls  = det.class_name.lower()
            area = det.bbox.size.x * det.bbox.size.y
            prev = best_in_frame.get(cls)
            if prev is None or area > prev[1]:
                best_in_frame[cls] = (det.score, area)

        with self._det_lock:
            for cls, (score, _) in best_in_frame.items():
                prev = self._detections.get(cls)
                best = max(score, prev[0]) if prev is not None else score
                self._detections[cls] = (best, now)

    def _log(self, msg: str):
        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        line = f'[{ts}] {msg}\n'
        self._log_file.write(line)
        self._log_file.flush()

    def _on_state(self, arm: str, msg: String):
        prev = self._arm_state[arm]
        self._arm_state[arm] = msg.data
        if prev != msg.data:
            target = self._active_target.get(arm) or 'none'
            self.get_logger().info(f"[{arm}] State: {prev} → {msg.data}")
            self._log(f"[{arm}] state={msg.data} target={target}")

    # ------------------------------------------------------------------ #
    #  Per-arm dispatch loop (runs in daemon thread)                      #
    # ------------------------------------------------------------------ #

    def _arm_loop(self, arm: str):
        sequence = self._left_sequence if arm == 'left' else self._right_sequence
        self.get_logger().info(f"[{arm}] Dispatch loop started. Sequence: {sequence}")

        # Track objects that failed hover this cycle so we skip them and try the next
        skip: set[str] = set()

        while rclpy.ok():
            # 1. Wait for arm to be IDLE
            self._wait_for_state(arm, 'IDLE')

            # 1b. Right arm: pause if left arm is actively working on a blocking object
            if arm == 'right' and self._active_target.get('left') in self._right_pause_on_left:
                self.get_logger().info(
                    f"[right] Pausing — left arm is running '{self._active_target['left']}'"
                )
                while rclpy.ok() and self._active_target.get('left') in self._right_pause_on_left:
                    time.sleep(0.3)
                self.get_logger().info("[right] Resuming — left arm blocking object cleared.")
                continue

            # 2. Find highest-priority object currently visible in YOLO (skipping failures)
            target = self._find_target(sequence, skip)
            if target is None:
                if skip:
                    self.get_logger().info(
                        f"[{arm}] No reachable targets visible (skipped: {skip}). Clearing skip list."
                    )
                    skip.clear()
                time.sleep(0.3)
                continue

            self.get_logger().info(f"[{arm}] Target selected: '{target}'")
            self._active_target[arm] = target
            self._log(f"[{arm}] state=HOVERING target={target}")

            # 3. Run hover_to_object (blocking subprocess)
            if not self._run_hover(arm, target):
                self.get_logger().warn(
                    f"[{arm}] Hover failed for '{target}' — skipping to next in sequence."
                )
                self._log(f"[{arm}] state=HOVER_FAILED target={target}")
                self._active_target[arm] = None
                skip.add(target)
                continue

            # Hover succeeded — clear the skip list for next round
            skip.clear()
            self._log(f"[{arm}] state=HOVER_DONE target={target}")

            # 4. Wait for state machine to enter GRASPING, then return to IDLE
            if not self._wait_for_state(arm, 'GRASPING', timeout=20.0):
                self.get_logger().warn(
                    f"[{arm}] State machine did not enter GRASPING within 20s after hover."
                )
                self._log(f"[{arm}] state=GRASPING_TIMEOUT target={target}")
            self._wait_for_state(arm, 'IDLE')
            self.get_logger().info(f"[{arm}] Grasp complete for '{target}'.")
            self._log(f"[{arm}] state=GRASP_DONE target={target}")

            # 5. Return arm to home position using this object's CSV.
            # RETURNING state blocks the loop from starting a new grasp cycle
            # until the trajectory finishes.
            if self._run_go_to_poses:
                self._arm_state[arm] = 'RETURNING'
                self.get_logger().info(f"[{arm}] State: IDLE → RETURNING")
                self._log(f"[{arm}] state=RETURNING target={target}")
                self._run_return(arm, target)
                self._arm_state[arm] = 'IDLE'
                self.get_logger().info(f"[{arm}] State: RETURNING → IDLE")
                self._log(f"[{arm}] state=IDLE target=none")

            self._active_target[arm] = None
            time.sleep(1.0)

    def _find_target(self, sequence: list, skip: set = None) -> str | None:
        now = time.time()
        with self._det_lock:
            for cls in sequence:
                if skip and cls in skip:
                    continue
                entry = self._detections.get(cls)
                if entry and (now - entry[1]) <= self._detection_window:
                    return cls
        return None

    def _wait_for_state(self, arm: str, target: str, timeout: float = None, poll: float = 0.2) -> bool:
        deadline = time.time() + timeout if timeout is not None else None
        while rclpy.ok():
            if self._arm_state[arm] == target:
                return True
            if deadline is not None and time.time() > deadline:
                return False
            time.sleep(poll)
        return False

    # ------------------------------------------------------------------ #
    #  Subprocess helpers                                                  #
    # ------------------------------------------------------------------ #

    def _run_hover(self, arm: str, target: str) -> bool:
        p = self.get_parameter

        if arm == 'left':
            ns  = p('left_arm_ns').value
            cmd = [
                'ros2', 'run', 'soa_apps', 'hover_to_object', target,
                '--ros-args',
                '--remap', f'__node:=hover_to_object_{arm}',
                '-p', f'arm_ns:={ns}',
                '-p', f'x_offset:={p("left_x_offset").value}',
                '-p', f'y_offset:={p("left_y_offset").value}',
                '-p', f'z_offset:={p("left_z_offset").value}',
            ]
            src = p('left_tf_source_frame').value
            tgt = p('left_tf_target_frame').value
            if src and tgt:
                cmd += [
                    '-p', f'tf_source_frame:={src}',
                    '-p', f'tf_target_frame:={tgt}',
                ]
        else:
            ns  = p('right_arm_ns').value
            cmd = [
                'ros2', 'run', 'soa_apps', 'hover_to_object', target,
                '--ros-args',
                '--remap', f'__node:=hover_to_object_{arm}',
                '-p', f'arm_ns:={ns}',
                '-p', f'x_offset:={p("right_x_offset").value}',
                '-p', f'y_offset:={p("right_y_offset").value}',
                '-p', f'z_offset:={p("right_z_offset").value}',
            ]

        self.get_logger().info(f"[{arm}] hover_to_object: {' '.join(cmd)}")
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            self.get_logger().error(
                f"[{arm}] hover_to_object failed (code {result.returncode}) for '{target}':\n{result.stderr.strip()}"
            )
        return result.returncode == 0

    def _run_return(self, arm: str, target: str):
        import os
        p = self.get_parameter

        base_dir = p('csv_base_dir').value
        csv = os.path.join(base_dir, f'{arm}_{target}.csv')

        if not os.path.isfile(csv):
            self.get_logger().info(f"[{arm}] No CSV found at '{csv}' — skipping go_to_poses.")
            return

        ns        = p('left_arm_ns').value  if arm == 'left' else p('right_arm_ns').value
        clat      = p('left_gripper_close_at').value if arm == 'left' else p('right_gripper_close_at').value
        olat      = p('left_gripper_open_at').value  if arm == 'left' else p('right_gripper_open_at').value
        open_pos  = p('left_gripper_open_position').value  if arm == 'left' else p('right_gripper_open_position').value
        close_pos = p('left_gripper_close_position').value if arm == 'left' else p('right_gripper_close_position').value

        cmd = [
            'ros2', 'run', 'soa_apps', 'go_to_poses',
            '--ros-args',
            '--remap', f'__node:=go_to_poses_{arm}',
            '-p', f'csv_path:={csv}',
            '-p', f'gripper_close_at:={clat}',
            '-p', f'gripper_open_at:={olat}',
            '-p', f'gripper_open_position:={open_pos}',
            '-p', f'gripper_close_position:={close_pos}',
        ]
        if ns:
            cmd += ['-p', f'arm_ns:={ns}']

        self.get_logger().info(f"[{arm}] Returning to home via '{target}' CSV: {csv}")
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            self.get_logger().error(
                f"[{arm}] go_to_poses failed (code {result.returncode}) for '{target}':\n{result.stderr.strip()}"
            )


def main(args=None):
    rclpy.init(args=args)
    node = GraspSequencer()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
