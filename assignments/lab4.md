# Lab 4: Pose Goals & Obstacle Avoidance

Forward kinematics is useful and reliable when you know the exact joint-states of your goal position.  
It's far more common that you only have a goal pose where you want the robot end-effector to go.  
In this case, we use "inverse kinematic" solvers to find joint positions for a given end-effector pose.  
Most industrial robot arms have at least 6 Degrees-Of-Freedom (dof) which allows them to move to any arbitrary 6-dof pose within its workspace.  
The SO101 arm is only 5-dof, significantly limiting the reachable poses.  


## Learning Objectives

- Control the SO101 using inverse kinematics.
- Include environment constraints in motion planning.


## Given

- [MoveIt Included Planners](https://moveit.ai/documentation/planners/)  
    MoveIt provides integrations with many planners for inverse kinematics.  
    The default planner is the [Open Motion Planning Library](https://ompl.kavrakilab.org/)

- [MoveIt Planning Scene](https://moveit.picknik.ai/main/doc/tutorials/planning_around_objects/planning_around_objects.html)  
    MoveIt includes tools for planning around obstacles.  
    In this lab, we will use the planning scene to control for the table.  
    Your project should expand on these capabilities to control for other obstacles in your scene.  


## TODO

1. Creat a new action in the `soa_interfaces` packages called `MoveToPose.action`.  
    Make sure to add the new action to the `CMakeLists.txt` file so it compiles.  
    The action should be defined as:  
    ```
    # Goal: target pose for the end effector
    geometry_msgs/Pose target_pose
    ---
    # Result
    bool success
    string message
    ---
    # Feedback
    float64 distance_to_goal
    ```

2. Complete the `move_to_pose_server` in `soa_functions`.

3. Complete `planning_scene` in `soa_functions`.

4. Try to move the robot arm through the table in Rviz when using your planning scene.  
    Launch MoveIt, start your planning scene in a second terminal.  
    Use the planning marker in Rviz to bring the robot arm through the table.  
    The robot arm should turn red showing that it isn't possible.  

5. Create a new service called `save_pose.py` in the `soa_functions` package.  
    Reference the `save_joint_states` service from last week.  
    Instead of saving individual joint positions, use [tf2_ros](https://docs.ros.org/en/humble/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Listener-Py.html) to save the position (x, y, z), and orientation (x, y, z, w) of the "gripper_link" in the "base_link" frame.  
    Save the pose to a .csv in the same way you saved the joint states.

6. Create a new app called `go_to_poses` in `soa_apps`.  
    Since the poses in the csv file do not container gripper information, you will need to control the gripper separately.  
    Define open and closed gripper states for manipulating the aruco cube, e.g.:  
    ```python
    GRIPPER_OPEN = 1.7453
    GRIPPER_CLOSED = 0.1   
    ```
    You will need to intermix these commands with your saved poses.  
    You can code this however you like; we propose loading the poses from the csv file and creating a sequence that the `run` function should follow, e.g.:  
    ```python
    SEQUENCE = [
        ('pose', pose_index=0),
        ('pose', pose_index=1),
        ('gripper', GRIPPER_OPEN),
        ('pose', pose_index=2),
        ('gripper', GRIPPER_CLOSED),
        ('pose',    pose_index=3),
    ]
    ```
    The overall flow of the application would then be something like:  
    ```python
    # imports

    # gripper state definitions

    # sequence definition

    def load_poses(path: str) -> list:
        """
        load saved poses from a csv file (accessed by the path)
        into a list, so that poses can be referenced by index by the sequence
        """

    class GoToPoses(Node):
        def __init__(self):
            """
            initialize a ros node
            declare the csv file path as a ros parameter
            initialize the MoveToPose action client
            initialize the Gripper action client
            """
        
        def send_pose_goal(self, pose: Pose) -> bool:
            """use the MoveToPose action client to move the arm"""
        
        def send_gripper_goal(self, target_position: float) -> bool:
            """use the Gripper action client to move the gripper"""
        
        def _pose_feedback_callback(self, feedback_msg):
            """handle feedback from the inverse kinematic action server"""
        
        def _gripper_feedback_callback(self, feedback_msg):
            """handle feedback from the gripper action server"""
        
        def run(self):
            """
            load the saved poses from the csv file
            execute the sequence defined above
            """
        
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
    ```

    You would then run this by:
    1. launching the soa_moveit bringup
    2. starting the move to pose action server
    3. starting the gripper action server
    4. running the go_to_pose app


## Deliverables

1. Submit your code for `move_to_pose_server`.

2. Submit your code for `load_planning_scene`.

3. Submit a screenshot of the robot arm turning red when intersecting with the planning scene in Rviz.

4. Submit your code for `save_poses.py`.

5. Submit your code for `go_to_poses.py`.

6. Submit a link to a video of the robot arm lifting the aruco cube using your `go_to_poses` app.

7. Write a paragraph discussing forward versus inverse kinematics.  
    **Do not use AI.**  
    In what circumstances would you use each type?  


## FAQ

## Resources

- [Pymoveit2 Example Scripts](https://github.com/AndrejOrsula/pymoveit2/tree/main/examples)

- [MoveIt Obstacle Avoidance Tutorial by Automated Addison](https://www.youtube.com/watch?v=NzknK_SRDjk)