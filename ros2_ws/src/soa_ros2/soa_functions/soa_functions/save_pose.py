#!/usr/bin/env python3
"""Save pose service node.

Provides the /follower/save_pose service (soa_interfaces/srv/SaveJointStates)
to capture the current gripper_link pose in the base_link frame using tf2_ros,
and optionally append it to a CSV file for later replay.

Can be run standalone:
    ros2 run soa_functions save_pose

Call the service:
    ros2 service call /follower/save_pose soa_interfaces/srv/SaveJointStates \
        "{csv_path: '/home/ubuntu/techin517/poses.csv'}"

Services:
    /follower/save_pose (soa_interfaces/srv/SaveJointStates)
        request:  csv_path — path to CSV file
        response: success, message

Subscriptions:
    none (uses tf2 lookup instead)
"""

import csv
import os

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

import tf2_ros
from tf2_ros import TransformException

from soa_interfaces.srv import SaveJointStates


class SavePoseNode(Node):

    def __init__(self):
        super().__init__('save_pose')

        self._cb_group = ReentrantCallbackGroup()

        # TF2 buffer and listener
        self._tf_buffer = tf2_ros.Buffer()
        self._tf_listener = tf2_ros.TransformListener(
            self._tf_buffer,
            self,
            spin_thread=False,
        )

        self.create_service(
            SaveJointStates,
            '/follower/save_pose',
            self._handle_save_pose,
            callback_group=self._cb_group,
        )

        self.get_logger().info('SavePose service ready.')

    def _handle_save_pose(self, req, res):
        """Handle the /follower/save_pose service request.

        Looks up the current gripper_link pose in base_link frame via tf2
        and optionally writes it to a CSV file.

        Args:
            req (SaveJointStates.Request): Service request containing:
                csv_path (str): Filesystem path to the target CSV file.
            res (SaveJointStates.Response): Service response to populate.

        Returns:
            SaveJointStates.Response: Populated response with:
                success (bool): True if pose was captured and written.
        """
        # Look up transform: gripper_link expressed in base_link frame
        try:
            transform = self._tf_buffer.lookup_transform(
                'follower/base_link',
                'follower/gripper_link',
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=2.0),
            )
        except TransformException as e:
            self.get_logger().error(f'Could not get transform: {e}')
            res.success = False
            return res

        # Extract position and orientation
        pos = transform.transform.translation
        rot = transform.transform.rotation

        self.get_logger().info(
            f'Pose — position: ({pos.x:.4f}, {pos.y:.4f}, {pos.z:.4f}), '
            f'orientation: ({rot.x:.4f}, {rot.y:.4f}, {rot.z:.4f}, {rot.w:.4f})'
        )

        res.success = True

        if req.csv_path:
            try:
                self._append_to_csv(req.csv_path, pos, rot)
            except OSError as e:
                self.get_logger().error(f'Failed to write CSV: {e}')
                res.success = False

        return res

    def _append_to_csv(self, path: str, pos, rot) -> None:
        """Append a single row of pose data to a CSV file.

        If the file does not yet exist, a header row is written first.
        Each subsequent call appends one data row.

        Args:
            path (str): Filesystem path to the target CSV file.
            pos: translation (x, y, z)
            rot: rotation (x, y, z, w)

        Returns:
            None

        Raises:
            OSError: If the file cannot be opened or written to.
        """
        file_exists = os.path.exists(path)

        with open(path, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['x', 'y', 'z', 'qx', 'qy', 'qz', 'qw'])
            writer.writerow([
                pos.x, pos.y, pos.z,
                rot.x, rot.y, rot.z, rot.w,
            ])

        self.get_logger().info(f'Pose saved to {path}')


def main(args=None):
    rclpy.init(args=args)
    node = SavePoseNode()
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