#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Pose
from soa_interfaces.action import MoveToPose, Gripper

GRIPPER_OPEN = 1.0
GRIPPER_CLOSED = -0.16 # not fully closed

class PickByPosition(Node):
    def __init__(self):
        super().__init__('pick_by_position')
        self.pose_client = ActionClient(self, MoveToPose, 'move_to_pose')
        self.gripper_client = ActionClient(self, Gripper, 'gripper_command')
    
    def move_to(self, pose, label=""):
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
    
    def control_gripper(self, position, label=""):
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
    
    def run(self, x, y, z, qx, qy, qz, qw):
        approach_z = z + 0.15
        
        def make_pose(px, py, pz):
            pose = Pose()
            pose.position.x = px
            pose.position.y = py
            pose.position.z = pz
            # Use provided orientation
            pose.orientation.x = qx
            pose.orientation.y = qy
            pose.orientation.z = qz
            pose.orientation.w = qw
            return pose
        
        # 1. Hover above
        if not self.move_to(make_pose(x, y, approach_z), "hover above"):
            return
        
        # 2. Open gripper
        if not self.control_gripper(GRIPPER_OPEN, "open"):
            return
        
        # 3. Descend to object
        if not self.move_to(make_pose(x, y, z), "descend"):
            return
        
        # 4. Grasp
        if not self.control_gripper(GRIPPER_CLOSED, "grasp"):
            return
        
        # 5. Lift
        self.move_to(make_pose(x, y, approach_z), "lift")

def main():
    rclpy.init()
    import sys
    
    if len(sys.argv) < 8:
        print("Usage: ros2 run soa_apps pick_by_position <x> <y> <z> <qx> <qy> <qz> <qw>")
        return
    
    x, y, z = map(float, sys.argv[1:4])
    qx, qy, qz, qw = map(float, sys.argv[4:8])
    
    node = PickByPosition()
    node.run(x, y, z, qx, qy, qz, qw)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()