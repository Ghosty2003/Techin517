#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import PoseStamped
from yolov8_msgs.msg import DetectionArray
from cv_bridge import CvBridge
import numpy as np
from tf2_ros import TransformListener, Buffer
import tf2_geometry_msgs

class ObjectDetectorNode(Node):
    def __init__(self):
        super().__init__('object_detector_node')
        
        # Parameters
        self.declare_parameter('target_objects', ['screwdriver', 'pen', 'apple', 'orange'])
        self.declare_parameter('confidence_threshold', 0.5)
        
        self.target_objects = self.get_parameter('target_objects').value
        self.confidence_threshold = self.get_parameter('confidence_threshold').value
        
        # TF2 for coordinate transformations
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # Publishers
        self.pose_pub = self.create_publisher(
            PoseStamped, 
            '/detected_object_pose', 
            10
        )
        
        # Subscribers
        self.detection_sub = self.create_subscription(
            DetectionArray,
            '/yolo/detections',
            self.detection_callback,
            10
        )
        
        self.depth_sub = self.create_subscription(
            Image,
            '/camera/depth/image_rect_raw',
            self.depth_callback,
            10
        )
        
        self.bridge = CvBridge()
        self.latest_depth = None
        
        # Camera intrinsics (Realsense D435i default values - adjust if needed)
        self.fx = 616.0  # focal length x
        self.fy = 616.0  # focal length y
        self.cx = 320.0  # principal point x
        self.cy = 240.0  # principal point y
        
        self.get_logger().info(f'Looking for objects: {self.target_objects}')
        self.get_logger().info(f'Confidence threshold: {self.confidence_threshold}')
        
    def depth_callback(self, msg):
        """Store latest depth image"""
        try:
            self.latest_depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
        except Exception as e:
            self.get_logger().error(f'Failed to convert depth image: {e}')
        
    def detection_callback(self, msg):
        """Process YOLO detections"""
        if self.latest_depth is None:
            return
            
        for detection in msg.detections:
            class_name = detection.class_name
            confidence = detection.score
            
            # Check if this is one of our target objects with sufficient confidence
            if class_name in self.target_objects and confidence >= self.confidence_threshold:
                self.get_logger().info(f'Detected {class_name} (confidence: {confidence:.2f})')
                
                # Get 3D position from depth
                pose = self.get_3d_pose(detection, class_name)
                
                if pose is not None:
                    # Publish the pose
                    self.pose_pub.publish(pose)
                    self.get_logger().info(
                        f'📍 {class_name} position in base_link: '
                        f'x={pose.pose.position.x:.3f}, '
                        f'y={pose.pose.position.y:.3f}, '
                        f'z={pose.pose.position.z:.3f}'
                    )
    
    def get_3d_pose(self, detection, class_name):
        """Convert 2D bounding box + depth to 3D pose in base_link frame"""
        try:
            # Get bounding box center
            bbox = detection.bbox
            center_x = int(bbox.center.position.x)
            center_y = int(bbox.center.position.y)
            
            # Sample depth in a small region around center (more robust)
            window_size = 5
            y_min = max(0, center_y - window_size)
            y_max = min(self.latest_depth.shape[0], center_y + window_size)
            x_min = max(0, center_x - window_size)
            x_max = min(self.latest_depth.shape[1], center_x + window_size)
            
            depth_region = self.latest_depth[y_min:y_max, x_min:x_max]
            
            # Filter out zeros and use median for robustness
            valid_depths = depth_region[depth_region > 0]
            if len(valid_depths) == 0:
                self.get_logger().warn(f'No valid depth for {class_name}')
                return None
                
            depth = np.median(valid_depths) / 1000.0  # Convert mm to meters
            
            if depth == 0 or np.isnan(depth) or depth > 3.0:  # Sanity check
                self.get_logger().warn(f'Invalid depth measurement: {depth}')
                return None
            
            # Convert pixel coordinates to 3D camera frame
            x_cam = (center_x - self.cx) * depth / self.fx
            y_cam = (center_y - self.cy) * depth / self.fy
            z_cam = depth
            
            # Create pose in camera optical frame
            pose_cam = PoseStamped()
            pose_cam.header.frame_id = 'camera_color_optical_frame'
            pose_cam.header.stamp = self.get_clock().now().to_msg()
            pose_cam.pose.position.x = x_cam
            pose_cam.pose.position.y = y_cam
            pose_cam.pose.position.z = z_cam
            pose_cam.pose.orientation.w = 1.0
            
            # Transform to base_link frame
            try:
                transform = self.tf_buffer.lookup_transform(
                    'base_link',
                    'camera_color_optical_frame',
                    rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=1.0)
                )
                
                # Transform the pose
                pose_base = tf2_geometry_msgs.do_transform_pose(pose_cam, transform)
                
                return pose_base
                
            except Exception as e:
                self.get_logger().warn(f'TF transform failed: {e}')
                return None
                
        except Exception as e:
            self.get_logger().error(f'Error computing 3D pose: {e}')
            return None

def main(args=None):
    rclpy.init(args=args)
    node = ObjectDetectorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()