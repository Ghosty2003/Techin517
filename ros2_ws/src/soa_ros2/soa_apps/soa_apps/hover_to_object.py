#!/usr/bin/env python3
"""
hover_to_object.py

Subscribes to /yolo/detections_3d, finds the target object class,
averages 3 detections, hovers above the object, then publishes to
/hover_done topic for state machine handoff.

Usage:
    ros2 run soa_apps hover_to_object <class_name>
Example:
    ros2 run soa_apps hover_to_object scissors
    ros2 run soa_apps hover_to_object tape
"""

import sys
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Pose, PointStamped
from std_msgs.msg import String
from yolo_msgs.msg import DetectionArray
from soa_interfaces.action import MoveToPose, Gripper
import tf2_ros
import tf2_geometry_msgs  # noqa: F401 — registers PointStamped transform support

HOVER_HEIGHT = 0.2   # meters above object
GRIPPER_OPEN = 0.8
NUM_SAMPLES = 3       # number of detections to average
MIN_SCORE = 0.35      # minimum confidence score to accept detection

# Calibration offsets (meters, applied in base_link frame).
# Tune these if the hover is consistently off-center.
# Positive X_OFFSET shifts hover forward; positive Y_OFFSET shifts hover left.
X_OFFSET = -0.05
Y_OFFSET = 0.0
Z_OFFSET = 0.0


class HoverToObject(Node):
    def __init__(self, target_class: str):
        super().__init__('hover_to_object')

        self.declare_parameter('arm_ns', '')
        self.declare_parameter('hover_height', HOVER_HEIGHT)
        self.declare_parameter('x_offset', X_OFFSET)
        self.declare_parameter('y_offset', Y_OFFSET)
        self.declare_parameter('z_offset', Z_OFFSET)
        # TF transform: if set, detected positions are transformed from
        # tf_source_frame → tf_target_frame before being used.
        # Example for left arm when camera is calibrated to right_base_link:
        #   -p tf_source_frame:=right_base_link -p tf_target_frame:=left_base_link
        self.declare_parameter('tf_source_frame', '')
        self.declare_parameter('tf_target_frame', '')

        arm_ns             = self.get_parameter('arm_ns').value.strip('/')
        self._hover_height = self.get_parameter('hover_height').value
        self._x_offset     = self.get_parameter('x_offset').value
        self._y_offset     = self.get_parameter('y_offset').value
        self._z_offset     = self.get_parameter('z_offset').value
        self._tf_source    = self.get_parameter('tf_source_frame').value
        self._tf_target    = self.get_parameter('tf_target_frame').value

        if self._tf_source and self._tf_target:
            self._tf_buffer   = tf2_ros.Buffer()
            self._tf_listener = tf2_ros.TransformListener(self._tf_buffer, self)
            self.get_logger().info(
                f"TF transform enabled: {self._tf_source} → {self._tf_target}"
            )
        else:
            self._tf_buffer = None

        self.target_class = target_class.lower()
        self.get_logger().info(
            f"Looking for: '{self.target_class}'"
            + (f" (arm_ns='{arm_ns}')" if arm_ns else '')
        )

        self.detections = []  # collected (x, y, z) samples

        # Resolve action/topic names — absolute when arm_ns is set
        def _topic(name: str) -> str:
            return f'/{arm_ns}/{name}' if arm_ns else name

        # Action clients
        self.pose_client = ActionClient(self, MoveToPose, _topic('move_to_pose'))
        self.gripper_client = ActionClient(self, Gripper, _topic('gripper_command'))

        # Publisher: notify state machine when hover is done
        self._hover_done_topic = f'/{arm_ns}/hover_done' if arm_ns else '/hover_done'
        self.hover_done_pub = self.create_publisher(String, self._hover_done_topic, 10)

        # Subscriber: YOLO 3D detections
        self.detection_sub = self.create_subscription(
            DetectionArray,
            '/yolo/detections_3d',
            self.detection_callback,
            10
        )

        self.get_logger().info(
            f"Waiting for {NUM_SAMPLES} detections of '{self.target_class}'..."
        )

    # ------------------------------------------------------------------ #
    #  YOLO callback                                                       #
    # ------------------------------------------------------------------ #
    def detection_callback(self, msg: DetectionArray):
        if len(self.detections) >= NUM_SAMPLES:
            return

        # Find best detection of target class (highest confidence)
        best_det = None
        best_score = 0.0

        for det in msg.detections:
            if det.class_name.lower() != self.target_class:
                continue
            if det.score > best_score:
                best_score = det.score
                best_det = det

        if best_det is None:
            return

        # Reject low confidence detections
        if best_score < MIN_SCORE:
            self.get_logger().warn(
                f"Rejecting detection - score {best_score:.3f} below {MIN_SCORE}"
            )
            return

        pos = best_det.bbox3d.center.position

        # Skip zero detections (no depth data)
        if pos.x == 0.0 and pos.y == 0.0 and pos.z == 0.0:
            self.get_logger().warn("Skipping zero detection")
            return

        # Positions already in base_link frame from detect_3d_node
        x = pos.x + self._x_offset
        y = pos.y + self._y_offset
        z = pos.z + self._z_offset

        self.detections.append((x, y, z))

        self.get_logger().info(
            f"Sample {len(self.detections)}/{NUM_SAMPLES}: "
            f"x={x:.3f}, y={y:.3f}, z={z:.3f} "
            f"(score={best_score:.3f})"
        )

    # ------------------------------------------------------------------ #
    #  Action helpers                                                      #
    # ------------------------------------------------------------------ #
    def move_to(self, pose: Pose, label: str = "") -> bool:
        self.pose_client.wait_for_server()
        goal = MoveToPose.Goal()
        goal.target_pose = pose
        self.get_logger().info(f"Moving ({label})")
        future = self.pose_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Pose goal rejected")
            return False
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        return result_future.result().result.success

    def control_gripper(self, position: float, label: str = "") -> bool:
        self.gripper_client.wait_for_server()
        goal = Gripper.Goal()
        goal.target_position = position
        self.get_logger().info(f"Gripper ({label})")
        future = self.gripper_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Gripper goal rejected")
            return False
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        return result_future.result().result.success

    # ------------------------------------------------------------------ #
    #  Main logic                                                          #
    # ------------------------------------------------------------------ #
    def run(self):
        # Wait until we have enough samples
        self.get_logger().info("Collecting detections...")
        while rclpy.ok() and len(self.detections) < NUM_SAMPLES:
            rclpy.spin_once(self, timeout_sec=0.1)

        if len(self.detections) < NUM_SAMPLES:
            self.get_logger().error("Not enough detections collected!")
            return

        # Average position
        x = sum(d[0] for d in self.detections) / NUM_SAMPLES
        y = sum(d[1] for d in self.detections) / NUM_SAMPLES
        z = sum(d[2] for d in self.detections) / NUM_SAMPLES

        self.get_logger().info(
            f"Averaged position ({self._tf_source or 'detection frame'}): "
            f"x={x:.3f}, y={y:.3f}, z={z:.3f}"
        )

        # Transform to target frame if configured
        if self._tf_buffer is not None:
            try:
                pt = PointStamped()
                pt.header.frame_id = self._tf_source
                pt.header.stamp = self.get_clock().now().to_msg()
                pt.point.x = x
                pt.point.y = y
                pt.point.z = z
                transformed = self._tf_buffer.transform(pt, self._tf_target, timeout=rclpy.duration.Duration(seconds=2.0))
                x = transformed.point.x
                y = transformed.point.y
                z = transformed.point.z
                self.get_logger().info(
                    f"Transformed to {self._tf_target}: x={x:.3f}, y={y:.3f}, z={z:.3f}"
                )
            except Exception as e:
                self.get_logger().error(f"TF transform failed: {e} — using original position")

        hover_z = z + self._hover_height

        # Build hover pose - gripper ALWAYS pointing straight down
        hover_pose = Pose()
        hover_pose.position.x = x
        hover_pose.position.y = y
        hover_pose.position.z = hover_z
        hover_pose.orientation.x = 0.0
        hover_pose.orientation.y = 0.0
        hover_pose.orientation.z = 0.0
        hover_pose.orientation.w = 1.0

        # Open gripper before hovering
        self.control_gripper(GRIPPER_OPEN, "open before hover")

        # Move to hover position
        success = self.move_to(hover_pose, f"hover above {self.target_class}")

        if success:
            self.get_logger().info(f"Hover complete! Publishing {self._hover_done_topic}")
            msg = String()
            msg.data = (
                f"{self.target_class},"
                f"{x:.4f},{y:.4f},{z:.4f},"
                f"0.0,0.0,0.0,1.0"
            )
            for _ in range(5):
                self.hover_done_pub.publish(msg)
                rclpy.spin_once(self, timeout_sec=0.1)

            self.get_logger().info(f"Published: {msg.data}")
        else:
            self.get_logger().error("Failed to reach hover position!")


def main():
    rclpy.init()

    if len(sys.argv) < 2:
        print("Usage: ros2 run soa_apps hover_to_object <class_name>")
        print("Example classes: screwdriver, scissors, pen, tape, pliers")
        rclpy.shutdown()
        return

    target_class = sys.argv[1]
    node = HoverToObject(target_class)

    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()