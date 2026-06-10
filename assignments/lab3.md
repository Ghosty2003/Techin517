# Lab 3: MoveIt Forward Kinematics

Over the next series of labs, we will learn about classic arm control, or "motion planning".  
Industrial arms are one of the oldest types of robots, dating back to the 1960s.  
It is well understood how to make a robot arm move to accurately move to different positions.  
Given this, we will consider the tradeoffs between classical and learned controls.  
This lab focuses on "forward kinematics", where we control each robot arm joint directly.  


## Learning Objectives

- Develop a ROS service to save joint states.
- Control the SO101 using forward kinematics.
- Develop layers of controls to build capabilities and abstractions for higher-level control.


## Given

- [MoveIt2](https://github.com/moveit/moveit2)  
    MoveIt is a general solution for classic motion planning.  
    This allows for using many types of planners with nearly any type of robot manipulator.  
    MoveIt includes many of the tools you need including obstacle avoidance, orientation constraints, camera integration, and more.  

- [pymoveit2](https://github.com/AndrejOrsula/pymoveit2)  
    MoveIt is typically programmed with C++.  
    It has a python interface, but it requires building the package from source, which can take hours and an unreasonable amount of RAM.  
    We'll use this open-source package to quickly build with python.

- [soa_moveit_config]()  
    Most robot arms you will use provide functions for motion planning.  
    It's rare that you will need to configure this yourself from scratch.  
    Also, MoveIt's setup documentation is lacking; refer to examples online if you ever need to setup yourself.  


## TODO

1. Develop the `save_joint_states` service in the `soa_functions` package.

2. Save a handful of poses to pick a cube using teleoperation.  
    Launch `soa_bringup.launch.py` with the `leader:=true` argument.  
    Call your `save_joint_states` service from the command line to save poses while picking up a cube.  
    A rough sequence might be:  
    - start position  
    - overhead position  
    - pick position  
    - retract position  
    - move to place position

3. Complete the `move_to_joint_states_server` in `soa_functions`.

4. Complete `go_to_joint_states.py` in `soa_apps`.

5. Run your new `go_to_joint_states` app with the csv of joint states you recorded earlier.  
    Launch the robot arm with MoveIt:
    ```bash
    ros2 launch soa_moveit_config soa_moveit_bringup.launch.py
    ```
    Note how this launch file starts with the joint trajectory controller.  
    Film a demo of the robot copying your actions.


## Deliverables

1. Submit your code for the `save_joint_states` service.

2. Submit a link to the official ros2 humble documentation definition of the joint states message type.

3. Copy the contents of your joint states csv file into your report.

4. Submit your code for the `move_to_joint_states_server`.

5. Submit your code for the `go_to_joint_states` app.

6. Submit a link to the video of the arm moving to your joint positions.

7. Write a short paragraph discussing which applications are well suited for forward kinematics.  
    **Do not use AI.**  
    What are the strengths of controlling the joints directly?  
    What are the weaknesses?


## FAQ

**Q:** Why do the arm and gripper move differently in the `go_to_joint_states` app?  
    Is it posisble to make them move together?  
**A:** Both servers use pymoveit2's execute() method, which sends planned trajectories to MoveGroup's execute_trajectory action.  
This action capability in the move_group node serializes all trajectory executions.


## Resources

History of robot arms from different robot companies:  
[Universal Robots](https://www.universal-robots.com/blog/inventor-of-the-robot-arm-and-its-continued-development/)  
[Robots.com](https://www.robots.com/articles/industrial-robot-history)  
[Augmentus](https://www.augmentus.tech/blogs/the-history-of-robotic-arms/)

[Official MoveIt2 Documentation](https://moveit.picknik.ai/main/index.html)  
MoveIt is an extremely useful library for generally controlling all types of robot manipulators.  
This library includes many tools for different planner, obstacle avoidance, sensor integration, and much more.

[AutomaticAddison's guide for creating a MoveIt config package](https://automaticaddison.com/how-to-configure-moveit-2-for-a-simulated-robot-arm/)  
MoveIt's documentation is sometimes lacking so finding community guides can often be a huge help.  

[Pymoveit2 documentation](https://docs.ros.org/en/humble/p/pymoveit2/index.html)  
This is an unofficial package for interfacing with MoveIt using python.  
MoveIt has an official python package, but it has to be built from source to work with ROS2 Humble.  
