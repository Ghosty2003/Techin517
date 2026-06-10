# Lab 2: Lerobot Ex ROS

Lerobot is a great system for quickly training VLA models.  
However, it directly occupies the camera and motor ports, which disables rapid switching to other control systems.  
If you want to use lerobot with "classical" ros-based controls, you first have to disable lerobot.  
This causes the motors to lose power and collapse.  
In this lab, we will use the [rosetta](https://github.com/iblnkn/rosetta) group of ros packages to run lerobot policies through ros2_control.  
This allows us to seamlessly switch between multiple policies and classical control systems.


## Learning Objectives

- Convert the output of lerobot policies into ros2_control signals
- Run lerobot policies on the physical robot using ros2_control
- Develop a ROS service for switching controllers.


## Given

- [Rosetta ROS Packages](https://github.com/iblnkn/rosetta)  
    These packages do the heavy lifting interfacing lerobot policies with ROS.  
    You could use these packages to train VLA models for any ROS-compatible robot.

- [ros2_control](https://github.com/ros-controls/ros2_control) and [controllers](https://docs.ros.org/en/humble/Tutorials/Beginner-CLI-Tools/Understanding-ROS2-Services/Understanding-ROS2-Services.html)  
    ROS provides many different controllers and tools for managing them.  
    In this lab we will use ForwardCommandControllers for lerobot policies, and JointTrajectoryControllers for classic motion planning.


## TODO

1. Complete the rosetta contract for the SO101 robot arm in `soa_ros2/soa_bringup/rosetta_contracts`

2. Run your lerobot policy from lab 1 on a physical arm using ROS and the rosetta package.
    Read through the [deploying policies section](https://github.com/iblnkn/rosetta?tab=readme-ov-file#deploying-policies) of the rosetta documentation to understand how to use the policy server.  
    In one terminal, bring-up your robot.  
    In a second terminal, start the rosetta policy server.  
    In a thrid terminal, send a goal to the policy server to complete the action you trained on.  
    Note: the documentation says to use `/rosetta_client/run_policy`, but it actually works with `/run_policy`.

3. Develop a ROS service for hot-swapping controllers.  
    We need to switch controllers because lerobot policies works best with forward command controllers while classic motion planning works best with joint trajectory controllers.  
    Both of these controllers are started in the `soa_bringup` launch files; one starts as active, the other as inactive.

    Try switching between the controllers in the command line first.  
    Refer to the [ros2_control cli documentation](https://control.ros.org/humble/doc/ros2_control/ros2controlcli/doc/userdoc.html) to learn how.

    In the package `soa_functions`, complete all the TODOs in the file `controller_switcher.py`.  
    We will use the `soa_functions` package to build capabilities throughout the quarter.  
    Refer to the [ROS service tutorial](https://docs.ros.org/en/humble/Tutorials/Beginner-CLI-Tools/Understanding-ROS2-Services/Understanding-ROS2-Services.html) for more information.  
    The service is defined in the `soa_interfaces` package, which is included in the `soa_functions package.xml`  


## Deliverables

1. Copy your rosetta contract into your lab report.

2. Link a video of your lerobot policy running through ros2.  
    Show your ros2 terminal and the robot running autonomously.

3. Submit the command(s) used to switch controllers from the command line

4. Write a short paragraph discussing why you may want to use different controllers.  
    **Do not use AI.**  
    Read about the different controllers we're using and discuss their trade-offs.  
    Speculate why forward command controllers might be better for rosetta while joint trajectory controllers might be better for classical control.  


## FAQ

**Q:** Why are we using "namespaces" with all the arm topics?  
**A:** Namespaces are useful for distinguishing similar nodes.  
    This is helpful for separating multiple robots like leader/followers, left/right arms, etc.  
    You can read a bit more about them [here](https://docs.ros.org/en/humble/Tutorials/Intermediate/Launch/Using-ROS2-Launch-For-Large-Projects.html#namespaces). 

**Q:** Nothing appears when I run `ros2 control list_controllers`, why?  
**A:** Make sure to use the controller_manager in the namespace of your arm,  
    e.g. `ros2 control list_controllers --controller-manager /follower/controller_manager`


## Resources

[Lerobot async inference server documentation](https://huggingface.co/docs/lerobot/async)  
Rosetta runs its policy server using lerobot's built-in server system.  
This could theoretically allow you run the policy on a separate powerful computer if you wanted to deploy the arms (or another robot) as a mobile system with less computing power.  

[Structured VLA reading list by MilkClouds on Github](https://github.com/MilkClouds/awesome-vla-study)  
Compilation of resources for learning all about different Vision Language Action models.

[Other packages for using the SO101 arm with ROS](https://github.com/stars/htchr/lists/so101)  
As an open-source projects, there are no standards for using these technologies together.  
Instead, you get many examples that you can use as inspiration for your system(s).  
