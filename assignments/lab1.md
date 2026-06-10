# Lab 1: Lerobot Ex Machina

In this quarter, we will survey AI in robotics with robot arms.  
We will use the [SO101 arm](https://github.com/TheRobotStudio/SO-ARM100) to explore imitation learning, classical motion planning, computer vision, and reinforcement learning.  
The first step is to assemble the arms, configure the working environment, and train your first VLA!  

Many of the labs for this course assume you have a GPU that works with Nvidia technologies.  
If you do not, please use the desktops in the robotics lab area.  
Not all of the systems we will use this quarter require Linux and ROS.  
You are encouraged to keep your training data stored in the cloud or on external storage in order to train lerobot models on your own devices.  
This gives you the assurance that no one will interrupt the training on a public desktop, and opens up school resources for other students to use.  
To install lerobot on your own device, follow the [conda instructions given on the Huggingface website](https://huggingface.co/docs/lerobot/en/installation).

| OS | Lerobot | ROS | Isaac Sim |
| - | - | - | - |
| Linux | yes | yes | yes |
| Mac | yes | no | no |
| Windows | yes | no | yes |


## Learning Objectives

- Assemble and calibrate a robot arm.
- Configure a Docker container to develop the arm with ROS, lerobot, and GPUs.
- Train your first vision-language-action policy.


## Given

- [Docker](https://www.docker.com/) and [devcontainers](https://code.visualstudio.com/docs/devcontainers/containers)  
    Modern computing runs in containers.  
    Without Docker, we would spend weeks dealing with minor version errors trying to install everything on everyone's disparate systems.  
    Collaboration and deployment would be far more difficult.

- [Lerobot](https://github.com/huggingface/lerobot)  
    Huggingface has done incredible work developing a system for using many types of Vision-Language-Action (VLA) models on many types of robots.  
    Without this, we would need the entire quarter to replicate these results.  
    With lerobot, we can use VLAs to quickly develop and deploy intelligent robot systems.  

- [SO101 Robot Arm](https://github.com/TheRobotStudio/SO-ARM100)  
    The Robot Studio and a large community of open-source developers have already integrated this affordable arm into all the cutting-edge systems we will learn about this quarter, democratizing robot education.


## TODO

**As a project team**

1. Collect a robot arm kit from the instructors.  
Fill out the included packing slip to confirm you received all necessary parts.  

2. Follow the [instructions](https://huggingface.co/docs/lerobot/en/so101) to assemble your arm while you discuss your project.  

**Individually**

1. Clone this repo with the following command:
    ```bash
    git clone --recursive https://github.com/GIXLabs/TECHIN517.git
    ```
    The `--rescursive` option also clones the included dependencies.  
    The scripts in this repo will not work properly without them.  

2. Configure your Docker install to work with Nvidia GPUs:  
Run the following command to make sure your GPU drivers are installed:  
    ```bash
    nvidia-smi
    ```  
    This should print information about your GPU, otherwise you will need to install the right drivers.  
    Next you will need to install [Nvidia's container toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
    Follow the instructions for Debian / Ubuntu.  
    Make sure that you can run the sample workload on the second page.

3. Fill out the partial [Dockerfile](/docker/INCOMPLETE_Dockerfile):  
    Follow the `TODO` comments in the file.  
    You should not need to modify the `devcontainer.json` or `setup.sh` files.  
    Your `Dockerfile` should work with these other configurations to create a working dev environment.  
    We will use a separate container to use Isaac Sim later.  

4. Follow the [instructions](https://huggingface.co/docs/lerobot/en/so101) to configure and calibrate the arms:  
    Use the name on the side of the robot for the calibration name.  
    Calibrate the arm at its "0" position.  
    Especially note how the gripper is orthogonal to the motor:  
    ![calibration_pose](/assets/so101_calibration_L-pose.png)

5. Read through [LeRobot's tutorial](https://huggingface.co/docs/lerobot/il_robots) on imitation learning:  
    Follow [the guide to teleoperate using a camera](https://huggingface.co/docs/lerobot/cameras#setup-cameras).  
    Use both the wrist-mounted camera and the overhead depth camera.  

6. Train an ACT policy using 30 examples and run inference:  
    We highly recommend recording a couple episodes before going for all 30 to ensure everything is working properly.  
    We highly recommend recording with the following argument to avoid additional setup:
    ```bash
    --dataset.push_to_hub=False \
    --display_data=False
    ```
    **You can train lerobot policies using your mac by following the [standard lerobot conda installation guide](https://huggingface.co/docs/lerobot/en/installation)**  
    By training with your personal device, you can let other students use the school computers.  
    Highly recommend training with the following argument to avoid additional setup:
    ```bash
    --push_to_hub=false
    ```
    **Plan for training to take a few hours**  
    We will be training many policies this quarter.  
    By using your personal device(s) instead of school computers, you can train overnight and sleep easy knowing that no one will interfere with the process.  
    Record a video of running your policy trained with 30 examples.  
    Lerobot has [many tools](https://huggingface.co/docs/lerobot/en/using_dataset_tools) for editing datasets if you need to remove an episode, or if you want to record in batches and merge them later.  

7. Save your training dataset and trained policy for later:  
    We highly recommend using a large external hard drive or your school Google drive for all of the data and models this quarter.


## Deliverables 

1. Return the packing slip that came with the kit with everyone's name to confirm you received all the necessary parts.  

2. Submit your Dockerfile.

3. Upload your arms calibration to the course Google Drive to share with the class.   
Any time you need to use a new arm, you should be able to download the calibration.  
If you need to update the calibration at any point, make sure to update the file in the drive as well. 

4. Submit your video of running inference after training with 30 examples.

5. Write a short paragraph discussing the trade-offs of using VLAs.  
    **Do not use AI**  
    What are they good for?  
    What are they bad at?  
    How might you mitigate shortcomings?  
    What was your experience like training a policy?  
    How do you imagine these policies scaling to work in the real world?


## FAQ

**Q:** I have a GPU but `nvidia-smi` doesn't print anything, how do I install the drivers?  
**A:** Open the "Software and Updates" program and look for drivers under the "Additional Drivers" section.  

**Q:** My motors aren't working, why?  
**A:** You might need to update the motor's firmware.  
Refer to [the documentation](https://huggingface.co/docs/lerobot/feetech) for a guide on how to do so.  

**Q:** When I try to calibrate an arm it errors out and says it's out of bounds, what do I do?  
**A:** Unplug both power and data from the motor driver board. Plug them back in and try again.

**Q:** The motor position values jump when trying to calibrate the arm, then the arm jumps when teleoping the robot, why?  
**A:** Try calibrating the robot again, only move one joint at a time slowly.

**Q:** When I try to record an example it says the camera times-out even though the camera works during teleoperation?  
**A:** Check out [this Github issue](https://github.com/huggingface/lerobot/issues/1675).  
You should be able to record examples at 30fps with the given cameras.  

**Q:** The lerobot-record script hangs at the end, why won't it finish?  
**A:** Your container might not be able to launch the Rerun GUI, record with `--display_data=false` to avoid startup/shutdown issues.  


## Resources

[Dockefile Keywords List](https://docs.docker.com/reference/dockerfile/)  
As you modify the given Dockerfile, checkout this list to see what the keywords do.  

[Docker for Robotics YouTube Playlist by Articulated Robotics](https://www.youtube.com/playlist?list=PLunhqkrRNRhaqt0UfFxxC_oj7jscss2qe)  
Environment management is extremely important for robotics development!  
We would run into infinitely more issues if all students installed these workspaces onto their own host machines.  
This lab requires you to modify a Dockerfile because understanding Docker genuinely makes development so much easier.  

[Seeed Studios Wiki Guide for the SO101](https://github.com/Seeed-Studio/wiki-documents/blob/docusaurus-version/docs/Robotics/Robot_Kits/Lerobot/Lerobot_SO100Arm.md)

[Best practices for recording imitation learning demonstrations from NVIDIA](https://www.youtube.com/watch?v=f7Wo9AFUR9U)

[Full tutorial on robot learning by Huggingface](https://huggingface.co/spaces/lerobot/robot-learning-tutorial)  
Full write-up covering classical robots, reinforcement learning, imitation learning, and general robot policies.  
This paper is a great introduction for quickly learning about this field of research.  
The citations in this paper would be a good start for your literature review this quarter.  
