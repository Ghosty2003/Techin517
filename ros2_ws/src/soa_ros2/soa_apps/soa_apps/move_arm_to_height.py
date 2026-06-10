#!/usr/bin/env python3
"""
Move the SOA arm end-effector to a target (x, y, z) position.

Prerequisites:
    ros2 launch soa_moveit_config soa_moveit_bringup.launch.py
    ros2 run soa_functions move_to_pose_server
    ros2 run soa_functions gripper_server

Run (default parameters):
    ros2 run soa_apps move_arm_to_height

Run with custom target:
    ros2 run soa_apps move_arm_to_height --ros-args \
        -p target_x:=0.2 -p target_y:=0.0 -p target_z:=0.3
"""

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from geometry_msgs.msg import Pose
from soa_interfaces.action import MoveToPose


class MoveArmToHeight(Node):

    def __init__(self):
        super().__init__('move_arm_to_height')

        self.declare_parameter('target_x', 0.2)
        self.declare_parameter('target_y', 0.0)
        self.declare_parameter('target_z', 0.3)
        # Gripper-down orientation: 180° around Y → (x=0, y=1, z=0, w=0)
        self.declare_parameter('orient_x', 0.0)
        self.declare_parameter('orient_y', 1.0)
        self.declare_parameter('orient_z', 0.0)
        self.declare_parameter('orient_w', 0.0)

        self._pose_client = ActionClient(self, MoveToPose, 'move_to_pose')

    def send_pose_goal(self, pose: Pose, label: str = '') -> bool:
        """Send a MoveToPose goal and block until the result is received."""
        goal = MoveToPose.Goal()
        goal.target_pose = pose

        self.get_logger().info(
            f'Sending pose goal ({label}): '
            f'pos=({pose.position.x:.4f}, {pose.position.y:.4f}, {pose.position.z:.4f}) '
            f'ori=({pose.orientation.x:.4f}, {pose.orientation.y:.4f}, '
            f'{pose.orientation.z:.4f}, {pose.orientation.w:.4f})'
        )

        self._pose_client.wait_for_server()

        future = self._pose_client.send_goal_async(
            goal,
            feedback_callback=self._pose_feedback_callback,
        )
        rclpy.spin_until_future_complete(self, future)

        goal_handle = future.result()
        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error(f'Pose goal rejected ({label})')
            return False

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result().result
        if result.success:
            self.get_logger().info(f'Pose goal succeeded ({label}): {result.message}')
        else:
            self.get_logger().error(f'Pose goal failed ({label}): {result.message}')
        return result.success

    def _pose_feedback_callback(self, feedback_msg):
        self.get_logger().info(
            f'Distance to goal: {feedback_msg.feedback.distance_to_goal:.4f} m'
        )

    def run(self):
        pose = Pose()
        pose.position.x    = self.get_parameter('target_x').get_parameter_value().double_value
        pose.position.y    = self.get_parameter('target_y').get_parameter_value().double_value
        pose.position.z    = self.get_parameter('target_z').get_parameter_value().double_value
        pose.orientation.x = self.get_parameter('orient_x').get_parameter_value().double_value
        pose.orientation.y = self.get_parameter('orient_y').get_parameter_value().double_value
        pose.orientation.z = self.get_parameter('orient_z').get_parameter_value().double_value
        pose.orientation.w = self.get_parameter('orient_w').get_parameter_value().double_value

        self.get_logger().info(
            f'Moving arm to: x={pose.position.x:.3f}, '
            f'y={pose.position.y:.3f}, z={pose.position.z:.3f}'
        )
        self.send_pose_goal(pose, label='target height')


def main(args=None):
    rclpy.init(args=args)

    node = MoveArmToHeight()
    try:
        node.run()
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
