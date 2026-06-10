#!/usr/bin/env python3
"""
Execute a fixed sequence of end-effector poses and gripper commands.

Poses are loaded from a CSV file saved by the save_pose service
(columns: x, y, z, qx, qy, qz, qw).  Gripper commands are interleaved
in the SEQUENCE list defined below.

Prerequisites:
    # 1. Launch the MoveIt stack:
    ros2 launch soa_moveit_config soa_moveit_bringup.launch.py

    # 2. Start the action servers:
    ros2 run soa_functions move_to_pose_server
    ros2 run soa_functions gripper_server

    # 3. Run this app (default CSV path):
    ros2 run soa_apps go_to_poses

    # Or with a custom CSV path:
    ros2 run soa_apps go_to_poses --ros-args -p csv_path:=/path/to/poses.csv
"""

import csv

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from geometry_msgs.msg import Pose
from soa_interfaces.action import Gripper, MoveToPose

# ---------------------------------------------------------------------------
# Gripper state definitions
# ---------------------------------------------------------------------------

GRIPPER_OPEN   =  1.7453  # fully open  — GRIPPER_TICK_MAX (3122)
GRIPPER_CLOSED = -0.1745  # fully closed — GRIPPER_TICK_MIN (1597)


DEFAULT_CSV_PATH = '/home/ubuntu/techin517/poses_scissor.csv'


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def load_poses(path: str) -> list[Pose]:
    """Load saved poses from a CSV file into a list of geometry_msgs/Pose.

    CSV columns (written by save_pose service):
        x, y, z, qx, qy, qz, qw

    Args:
        path: Filesystem path to the CSV file.

    Returns:
        List of Pose messages, one per CSV row (header excluded).
    """
    poses = []
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pose = Pose()
            pose.position.x    = float(row['x'])
            pose.position.y    = float(row['y'])
            pose.position.z    = float(row['z'])
            pose.orientation.x = float(row['qx'])
            pose.orientation.y = float(row['qy'])
            pose.orientation.z = float(row['qz'])
            pose.orientation.w = float(row['qw'])
            poses.append(pose)
    return poses


# ---------------------------------------------------------------------------
# ROS2 node
# ---------------------------------------------------------------------------

class GoToPoses(Node):

    def __init__(self):
        super().__init__('go_to_poses')

        self.declare_parameter('csv_path', DEFAULT_CSV_PATH)
        self.declare_parameter('gripper_close_at', 0)
        self.declare_parameter('gripper_open_at',  7)
        self.declare_parameter('gripper_open_position',  GRIPPER_OPEN)
        self.declare_parameter('gripper_close_position', GRIPPER_CLOSED)
        # arm_ns: set to match the arm namespace (e.g. "arm2") so action
        # clients reach the right move_to_pose / gripper_command servers.
        self.declare_parameter('arm_ns', '')

        arm_ns = self.get_parameter('arm_ns').value.strip('/')

        def _action(name: str) -> str:
            return f'/{arm_ns}/{name}' if arm_ns else name

        self._pose_client    = ActionClient(self, MoveToPose, _action('move_to_pose'))
        self._gripper_client = ActionClient(self, Gripper,    _action('gripper_command'))

    # ------------------------------------------------------------------
    # Pose goal
    # ------------------------------------------------------------------

    def send_pose_goal(self, pose: Pose, label: str = '') -> bool:
        """Send a MoveToPose goal and block until the result is received.

        Args:
            pose:  Target end-effector pose in base_link frame.
            label: Optional string logged alongside the goal for tracing.

        Returns:
            True if the action server reported success, False otherwise.
        """
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
        if not goal_handle.accepted:
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

    # ------------------------------------------------------------------
    # Gripper goal
    # ------------------------------------------------------------------

    def send_gripper_goal(self, target_position: float, label: str = '') -> bool:
        """Send a Gripper goal and block until the result is received.

        Args:
            target_position: Target gripper joint position in radians.
                             Use GRIPPER_OPEN or GRIPPER_CLOSED.
            label: Optional string logged alongside the goal for tracing.

        Returns:
            True if the action server reported success, False otherwise.
        """
        goal = Gripper.Goal()
        goal.target_position = target_position

        self.get_logger().info(
            f'Sending gripper goal ({label}): position={target_position:.4f} rad'
        )

        self._gripper_client.wait_for_server()

        future = self._gripper_client.send_goal_async(
            goal,
            feedback_callback=self._gripper_feedback_callback,
        )
        rclpy.spin_until_future_complete(self, future)

        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error(f'Gripper goal rejected ({label})')
            return False

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result().result
        if result.success:
            self.get_logger().info(f'Gripper goal succeeded ({label}): {result.message}')
        else:
            self.get_logger().error(f'Gripper goal failed ({label}): {result.message}')
        return result.success

    # ------------------------------------------------------------------
    # Feedback callbacks
    # ------------------------------------------------------------------

    def _pose_feedback_callback(self, feedback_msg):
        """Log distance-to-goal feedback from the MoveToPose action server."""
        self.get_logger().info(
            f'Pose feedback — distance to goal: '
            f'{feedback_msg.feedback.distance_to_goal:.4f} m'
        )

    def _gripper_feedback_callback(self, feedback_msg):
        """Log current position feedback from the Gripper action server."""
        self.get_logger().info(
            f'Gripper feedback — current position: '
            f'{feedback_msg.feedback.current_position:.4f} rad'
        )

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    def run(self):
        """Load all poses from CSV and visit them in order.

        Gripper is closed before the pose at gripper_close_at index,
        and opened before the pose at gripper_open_at index.
        Set either parameter to "" to skip that gripper action.
        """
        csv_path = self.get_parameter('csv_path').get_parameter_value().string_value

        def _parse(param: str):
            raw = str(self.get_parameter(param).value).strip()
            return {int(x) for x in raw.split(',') if x.strip()} if raw else set()

        close_at = _parse('gripper_close_at')
        open_at  = _parse('gripper_open_at')
        open_pos  = self.get_parameter('gripper_open_position').value
        close_pos = self.get_parameter('gripper_close_position').value

        self.get_logger().info(
            f'Loading poses from: {csv_path} | '
            f'close before={sorted(close_at)} open before={sorted(open_at)} | '
            f'open_pos={open_pos:.4f} close_pos={close_pos:.4f}'
        )

        poses = load_poses(csv_path)
        self.get_logger().info(f'Loaded {len(poses)} pose(s)')
        self.get_logger().info('=== Starting go_to_poses sequence ===')

        for i, pose in enumerate(poses):
            self.get_logger().info(f'--- Pose {i + 1}/{len(poses)} ---')

            if i in close_at:
                if not self.send_gripper_goal(close_pos, label=f'close before pose[{i}]'):
                    self.get_logger().warn(f'Gripper close failed at pose {i} — continuing.')
            elif i in open_at:
                if not self.send_gripper_goal(open_pos, label=f'open before pose[{i}]'):
                    self.get_logger().warn(f'Gripper open failed at pose {i} — continuing.')

            if not self.send_pose_goal(pose, label=f'pose[{i}]'):
                self.get_logger().error(f'Pose {i} failed. Aborting sequence.')
                return

        self.get_logger().info('=== go_to_poses sequence complete ===')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(args=None):
    rclpy.init(args=args)

    node = GoToPoses()
    try:
        node.run()
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
