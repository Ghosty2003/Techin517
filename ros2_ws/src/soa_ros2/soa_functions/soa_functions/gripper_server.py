#!/usr/bin/env python3
"""
Gripper action server for SOA arm.

Converts MoveIt SRDF joint values (radians)
into hardware encoder ticks for ros2_control gripper controller.
"""

import time
import rclpy
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from pymoveit2 import MoveIt2, MoveIt2State

from soa_interfaces.action import Gripper
from soa_functions import soa_robot


# =========================
# GRIPPER CALIBRATION RANGE
# =========================

# Hardware encoder range (from calibration file)
GRIPPER_TICK_MIN = 1597
GRIPPER_TICK_MAX = 3122

# SRDF joint range (from your MoveIt config)
SRDF_MIN = -0.1745
SRDF_MAX = 1.7453


def map_range(x, in_min, in_max, out_min, out_max):
    return out_min + (x - in_min) * (out_max - out_min) / (in_max - in_min)


class GripperServer(Node):

    def __init__(self):
        super().__init__('gripper_server')

        # Bimanual support: defaults match single-arm behaviour.
        self.declare_parameter('move_group',     soa_robot.MOVE_GROUP_GRIPPER)
        self.declare_parameter('joint_prefix',   '')
        self.declare_parameter('base_link_name', '')
        # ns prefixes the action name only (e.g. 'left' → /left/gripper_command).
        # Do NOT use __ns at launch — that would namespace pymoveit2's internal
        # topics (joint_states, move_action, etc.) away from the global move_group.
        self.declare_parameter('ns', '')

        move_group          = self.get_parameter('move_group').value
        self._joint_prefix  = self.get_parameter('joint_prefix').value
        ns                  = self.get_parameter('ns').value
        base_link           = self.get_parameter('base_link_name').value or soa_robot.base_link_name(self._joint_prefix)

        self._cb_group = ReentrantCallbackGroup()

        # MoveIt2 interface
        self._moveit2 = MoveIt2(
            node=self,
            joint_names=soa_robot.gripper_joint_names(self._joint_prefix),
            base_link_name=base_link,
            end_effector_name=soa_robot.end_effector_name(self._joint_prefix),
            group_name=move_group,
            callback_group=self._cb_group,
        )

        # If your gripper moves backwards, set True
        self.invert_direction = False

        action_name = f'/{ns}/gripper_command' if ns else 'gripper_command'
        self._action_server = ActionServer(
            self,
            Gripper,
            action_name,
            self._execute_callback,
            callback_group=self._cb_group,
        )

        self.get_logger().info("Gripper action server ready")

    def _wait_until_executed(self):
        while self._moveit2.query_state() != MoveIt2State.IDLE:
            time.sleep(0.05)
        return self._moveit2.motion_suceeded

    def _srdf_to_ticks(self, rad):
        tick = map_range(
            rad,
            SRDF_MIN,
            SRDF_MAX,
            GRIPPER_TICK_MIN,
            GRIPPER_TICK_MAX
        )

        if self.invert_direction:
            tick = GRIPPER_TICK_MAX - (tick - GRIPPER_TICK_MIN)

        return tick

    def _execute_callback(self, goal_handle):
        self.get_logger().info("Received gripper goal")

        srdf_position = goal_handle.request.target_position

        tick_position = self._srdf_to_ticks(srdf_position)

        self.get_logger().info(
            f"SRDF: {srdf_position:.4f} rad → {tick_position:.1f} ticks"
        )

        result = Gripper.Result()

        feedback = Gripper.Feedback()
        feedback.current_position = srdf_position
        goal_handle.publish_feedback(feedback)

        # Plan using SRDF space (MoveIt still thinks in radians)
        future = self._moveit2.plan_async(
            joint_positions=[srdf_position],
            joint_names=soa_robot.gripper_joint_names(self._joint_prefix),
        )

        if future is None:
            goal_handle.abort()
            result.success = False
            result.message = "Planning failed: no future returned"
            return result

        while not future.done():
            time.sleep(0.05)

        trajectory = self._moveit2.get_trajectory(future)

        if trajectory is None:
            goal_handle.abort()
            result.success = False
            result.message = "Planning failed: no trajectory"
            return result

        # IMPORTANT: overwrite trajectory with tick-level execution if needed
        # (depends on your MoveIt2 backend; if your controller expects ticks,
        #  you must ensure controller uses same SRDF scaling OR hardware plugin maps it)

        self._moveit2.execute(trajectory)

        success = self._wait_until_executed()

        feedback.current_position = srdf_position
        goal_handle.publish_feedback(feedback)

        goal_handle.succeed()

        result.success = success
        result.message = f"Gripper moved (SRDF={srdf_position:.3f}, ticks={tick_position:.1f})"

        self.get_logger().info(result.message)

        return result


def main(args=None):
    rclpy.init(args=args)

    node = GripperServer()

    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)

    time.sleep(1.0)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()