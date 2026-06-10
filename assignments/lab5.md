# Lab 5: Hand-eye Coordination

Now that we know how to accurately move the robot arm, we need methods for understanding the robot's environment to decide where to move to perform real tasks.  
There are large bodies of work for understanding the world with computer vision.  
In this lab, we will learn how to calibrate and coordinate computer vision with robot arms.


## Learning Objectives

- Calibrate arms and cameras to work together.
- Control robot arms using information from cameras.
- Attempt to pick arbitrary objects using poses from YOLO 3D.


## Given

- [ros2_handeye_calibration](https://github.com/GIXLabs/ros2_handeye_calibration)  
    If you search "ros2 hand-eye calibration", there are many example repos available.  
    Most of them do essentially the same thing, finding relationships between aruco codes and robot frames.  

- [yolo_ros](https://github.com/mgonzs13/yolo_ros)  
    We will use the same ros2 yolo package as last quarter to quickly estimate positions of various objects 


## TODO

1. Use the `ros2_handeye_calibration` package to calibrate the arm with the Realsense D435i depth camera.  
    Review the documentation for the package on their `README` file.  
    This package can perform "eye-on-base" or "eye-in-hand" calibration.  
    We will use "eye-on-base" to find the rigid connection between the Realsense camera and the robot's base.  
    Later, you can use "eye-in-hand" calibration to refine the pose of the wrist camera to the gripper.

    - Begin by launching the arm with rviz and teleop.
    - Configure and launch the `aruco_cube_tracker` from `aruco_tracker_ros2`.
    - Place an aruco cube in the robot's gripper.
    - Confirm the cube is being tracked with the debug image in rviz.
    - Use the leader arm to teleop the arm to 20+ poses across a wide range of positions and orientations in the camera's view, call the calibration service when the arm settles to use that pose for calibration.
    - After a few service calls, the calibration system will print its latest estimation of the camera's pose in the robot's base_frame.
    - Confirm the estimation is correct by running:
        ```bash
        ros2 run tf2_ros static_transform_publisher --x <X> --y <Y> --z <Z> --qx <QX> --qy <QY> --qz <QZ> --qw <QW> --frame-id <robots_base_frame>   --child-frame-id <cameras_frame>
        ```
    - Once this looks correct, add the necessary code to publish the transformation using the `soa_bringup.launch.py` script. Reference the [TF documentation](https://docs.ros.org/en/humble/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Broadcaster-Py.html) to learn more.

2. Write a new application called `pick_by_position.py` app in `soa_apps`.  
    This app should take a position as an argument.  
    The script should follow the sequence:
    - Move above the object
    - Open the gripper
    - Move down to pick the object
    - Close the gripper (not all the way)
    - Lift the object

3. Use the `pick_by_position` app to pick the cube, using the position `aruco_cube_position`.  
    Record a video demo.  

4. Use the `pick_by_position` app to pick a **fake** piece of fruit, using the position from the yolo3D topic.  
    Record a video demo.  


## Deliverables

1. Submit your code for `pick_by_pose.py`.

2. Link to your video demo picking the aruco cube.  

3. Link to your video demo picking the fruit.

4. Write a paragraph discussing classic motion planning versus learning-based control.  
    **Do not use AI.**  
    How do the different systems handle manipulating arbitrary objects?  
    What are the data requirements for manipulating with classic versus learned control?  
    How do classic and learned control compare for non-manipulation end-effectors (e.g. milling, drilling, sensing, spraying, sanding, etc.)?  


## FAQ

**Q:** Calibration accuracy doesn't seem to be very good, how can it be improved?  
**A:** Calibration depends on the accuracy of aruco detection, try increasing the camera's resolution, or taping a single large aruco code to the gripper and launch `aruco_code_tracker` instead.


## Resources

[MoveIt Hand-Eye Calibration](https://moveit.github.io/moveit_tutorials/doc/hand_eye_calibration/hand_eye_calibration_tutorial.html)  
    MoveIt has built-in functions for hand-eye calibration, but it doesn't seem to have been updated since ROS 1.

[MIT Kiss Matcher](https://github.com/MIT-SPARK/KISS-Matcher)  
    If you have a CAD file of the objects you are trying to pick, it's easy to generate a point cloud from that file.  
    From there, you can segment the points of an object from the Realsense output, and match that to your CAD file to find the pose of the object.

[Nvidia's Foundation Pose](https://nvlabs.github.io/FoundationPose/)  
    This system uses a 3D representation of objects to infer the pose of objects.  
    As demoed, these poses can be used to accurately manipulate objects.  
    There are many systems for 6-dof pose estimation that compete on the [BOP leaderboard](https://bop.felk.cvut.cz/leaderboards/pose-estimation-unseen-bop23/core-datasets/)
