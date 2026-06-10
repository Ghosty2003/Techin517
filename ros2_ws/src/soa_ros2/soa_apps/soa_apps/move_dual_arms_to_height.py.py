#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from pymoveit2 import MoveIt2
from pymoveit2.robots import ur5
import threading

class MoveDualArmsToHeight(Node):
    def __init__(self):
        super().__init__('move_dual_arms_to_height')
        
        # LEFT ARM Parameters
        self.declare_parameter('left_x', 0.3)
        self.declare_parameter('left_y', 0.2)   # Left side (positive Y)
        self.declare_parameter('left_z', 0.3)
        
        # RIGHT ARM Parameters  
        self.declare_parameter('right_x', 0.3)
        self.declare_parameter('right_y', -0.2)  # Right side (negative Y)
        self.declare_parameter('right_z', 0.3)
        
        # Arm namespaces
        self.declare_parameter('left_arm_namespace', 'left_arm')
        self.declare_parameter('right_arm_namespace', 'right_arm')
        
        # Movement mode
        self.declare_parameter('move_simultaneously', True)  # Move both at same time
        
        # Get parameters
        self.left_x = self.get_parameter('left_x').value
        self.left_y = self.get_parameter('left_y').value
        self.left_z = self.get_parameter('left_z').value
        
        self.right_x = self.get_parameter('right_x').value
        self.right_y = self.get_parameter('right_y').value
        self.right_z = self.get_parameter('right_z').value
        
        self.left_arm_ns = self.get_parameter('left_arm_namespace').value
        self.right_arm_ns = self.get_parameter('right_arm_namespace').value
        self.move_simultaneously = self.get_parameter('move_simultaneously').value
        
        # Initialize MoveIt2 for LEFT ARM
        self.moveit2_left_arm = MoveIt2(
            node=self,
            joint_names=[
                f'{self.left_arm_ns}_shoulder_pan_joint',
                f'{self.left_arm_ns}_shoulder_lift_joint',
                f'{self.left_arm_ns}_elbow_joint',
                f'{self.left_arm_ns}_wrist_1_joint',
                f'{self.left_arm_ns}_wrist_2_joint',
                f'{self.left_arm_ns}_wrist_3_joint'
            ],
            base_link_name=f'{self.left_arm_ns}_base_link',
            end_effector_name=f'{self.left_arm_ns}_tool0',
            group_name=self.left_arm_ns,
        )
        
        # Initialize MoveIt2 for RIGHT ARM
        self.moveit2_right_arm = MoveIt2(
            node=self,
            joint_names=[
                f'{self.right_arm_ns}_shoulder_pan_joint',
                f'{self.right_arm_ns}_shoulder_lift_joint',
                f'{self.right_arm_ns}_elbow_joint',
                f'{self.right_arm_ns}_wrist_1_joint',
                f'{self.right_arm_ns}_wrist_2_joint',
                f'{self.right_arm_ns}_wrist_3_joint'
            ],
            base_link_name=f'{self.right_arm_ns}_base_link',
            end_effector_name=f'{self.right_arm_ns}_tool0',
            group_name=self.right_arm_ns,
        )
        
        # Status tracking
        self.left_complete = False
        self.right_complete = False
        
        self.print_info()
        
    def print_info(self):
        """Print movement information"""
        self.get_logger().info('='*60)
        self.get_logger().info('🦾🦾 DUAL ARM MOVEMENT CONTROLLER 🦾🦾')
        self.get_logger().info('='*60)
        self.get_logger().info(f'LEFT ARM target position:')
        self.get_logger().info(f'  X (forward/back): {self.left_x} m')
        self.get_logger().info(f'  Y (left/right):   {self.left_y} m')
        self.get_logger().info(f'  Z (height):       {self.left_z} m')
        self.get_logger().info('-'*60)
        self.get_logger().info(f'RIGHT ARM target position:')
        self.get_logger().info(f'  X (forward/back): {self.right_x} m')
        self.get_logger().info(f'  Y (left/right):   {self.right_y} m')
        self.get_logger().info(f'  Z (height):       {self.right_z} m')
        self.get_logger().info('-'*60)
        self.get_logger().info(f'Movement mode: {"SIMULTANEOUS" if self.move_simultaneously else "SEQUENTIAL"}')
        self.get_logger().info('='*60)
    
    def move_left_arm(self):
        """Move left arm to target position"""
        try:
            self.get_logger().info('🦾 LEFT ARM: Starting movement...')
            
            self.moveit2_left_arm.move_to_pose(
                position=[self.left_x, self.left_y, self.left_z],
                quat_xyzw=[0.0, 1.0, 0.0, 0.0],  # Gripper pointing down
                cartesian=False
            )
            
            self.get_logger().info('⏳ LEFT ARM: Moving to position...')
            self.moveit2_left_arm.wait_until_executed()
            
            self.get_logger().info('✅ LEFT ARM: Movement complete!')
            self.left_complete = True
            return True
            
        except Exception as e:
            self.get_logger().error(f'❌ LEFT ARM: Movement failed: {str(e)}')
            self.left_complete = False
            return False
    
    def move_right_arm(self):
        """Move right arm to target position"""
        try:
            self.get_logger().info('🦾 RIGHT ARM: Starting movement...')
            
            self.moveit2_right_arm.move_to_pose(
                position=[self.right_x, self.right_y, self.right_z],
                quat_xyzw=[0.0, 1.0, 0.0, 0.0],  # Gripper pointing down
                cartesian=False
            )
            
            self.get_logger().info('⏳ RIGHT ARM: Moving to position...')
            self.moveit2_right_arm.wait_until_executed()
            
            self.get_logger().info('✅ RIGHT ARM: Movement complete!')
            self.right_complete = True
            return True
            
        except Exception as e:
            self.get_logger().error(f'❌ RIGHT ARM: Movement failed: {str(e)}')
            self.right_complete = False
            return False
    
    def move_both_arms_simultaneously(self):
        """Move both arms at the same time using threads"""
        self.get_logger().info('🚀 Starting SIMULTANEOUS movement of both arms...')
        
        # Create threads for each arm
        left_thread = threading.Thread(target=self.move_left_arm)
        right_thread = threading.Thread(target=self.move_right_arm)
        
        # Start both threads
        left_thread.start()
        right_thread.start()
        
        # Wait for both to complete
        left_thread.join()
        right_thread.join()
        
        return self.left_complete and self.right_complete
    
    def move_both_arms_sequentially(self):
        """Move arms one after another"""
        self.get_logger().info('🚀 Starting SEQUENTIAL movement (left first, then right)...')
        
        # Move left arm first
        left_success = self.move_left_arm()
        
        if not left_success:
            self.get_logger().error('Left arm failed, skipping right arm')
            return False
        
        # Then move right arm
        right_success = self.move_right_arm()
        
        return left_success and right_success
    
    def move_to_positions(self):
        """Main function to move both arms"""
        if self.move_simultaneously:
            success = self.move_both_arms_simultaneously()
        else:
            success = self.move_both_arms_sequentially()
        
        return success

def main(args=None):
    rclpy.init(args=args)
    
    node = MoveDualArmsToHeight()
    
    # Allow time for initialization
    rclpy.spin_once(node, timeout_sec=2.0)
    
    # Execute movement
    success = node.move_to_positions()
    
    if success:
        node.get_logger().info('='*60)
        node.get_logger().info('✨✨ MISSION ACCOMPLISHED! ✨✨')
        node.get_logger().info(f'LEFT ARM at: ({node.left_x}, {node.left_y}, {node.left_z})')
        node.get_logger().info(f'RIGHT ARM at: ({node.right_x}, {node.right_y}, {node.right_z})')
        node.get_logger().info('='*60)
        node.get_logger().info('Press Ctrl+C to exit')
        rclpy.spin(node)
    else:
        node.get_logger().error('='*60)
        node.get_logger().error('❌ MISSION FAILED!')
        node.get_logger().error('='*60)
    
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()