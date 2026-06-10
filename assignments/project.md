# TECHIN 517 Spring 2026 Class Project

## Learning Objectives

- Gain experience using cutting edge techniques for robot learning
- Develop a smart, general robot application for an area of robotics your team is passionate about: healthcare, agriculture, home, food, manufacturing, etc.
- Design and run quantitative experiments to evaluate a general robotic system


## Project Requirements

- Develop a "general robotics" application for bi-manual SO101 robot arms
- Incorporate machine learning, computer vision, and classical techniques to accomplish your application
- Collect quantitative metrics on your system's performance


## TODO

- Join a team: you are not allowed to team up with anyone you worked with last quarter
- Choose a concept or category of tasks to iterate on
- Review existing demos and research online
- Discuss application with teaching team
- Begin with the most basic version of your application
    - For example: If your application is to fold clothes, start by folding a hand towel once
- Continue developing features, gathering training data, and training models to increase the robustness of your system
- Present your progress to the class
- Incorporate feedback
- Present your final results

**Schedule**

|  Week | TODO | Deliverable |
| - | - | - |
| 1 | Choose a team<br>Choose an application | Add team to class spreadsheet |
| 2 | Research chosen application<br>Have concept approved by teaching team | **Teaching team check-in** |
| 3 | Gather training data<br>Train VLA<br>Evaluate performance | **In-class presentation 1** |
| 4 | Continue developing your application<br>Address feedback from presentations
| 5 |
| 6 |
| 7 | | **In-class presentation 2** |
| 8 |
| 9 | The project should be done by now<br>Leave time to measure results, document, and practice your presentation | 
| 10 |
| 11 | | **Final presentation** |


**Presentations**

- Teaching team check-in:
    - Discuss your application
    - Present your research
        - How far have other people gone?
        - Do the examples come from hobbyist, researchers, or a company?
        - What challenges do you anticipate based on your research?  
    - Present an initial development plan:
        - How are you going to start?
        - How far would you like to get before the end of the quarter?
        - How do you plan to address the evaluation considerations?
- In-class presentation 1:
    - Present your plan
    - Train the most basic version of your application  
    - Show a demo video of progress so far
    - Present evidence of what each team member has done so far
    - Explain what each team member will do next
    - Describe your goals for the next 2 presentation
    - Stick to time limit
- In-class presentation 2:
    - Demonstrate progress based on feedback from the first presentation
    - Show a demo video of progress so far
    - Present evidence of what each team member has done so far
    - Explain what you plan to measure to evaluate quantitative success
    - Describe your goal for the final presentation
    - Stick to time limit
- Final presentation:
    - Perform a live demo
    - Explain your system architecture
    - Explain how you handled challenges and improved your system
    - Present your quantitative results
    - Address the evaluation considerations below
    - Contributions from all team members
    - Stick to time limit


### Evaluation

Your project will be evaluated based on the following priorities:

1. Does your system meet the project requirements?
2. Can your system preform your application?
3. Can it perform the application safely?
    - Does it avoid harming people?
    - Does it avoid damaging the robot?
    - Does it avoid damaging the environment and any objects it interacts with?
4. Is it robust?
    - Can it perform the application multiple times?
    - What is the success rate?
    - How long can your system operate before it needs to be reset or maintained?
5. How well does it generalize?
    - Does your application work with related objects?
    - Does it work in different lighting conditions?
    - What happens if there are random objects in the scene?
    - Does your application work in related environments?

**Quantitative Results**

During the second in-class presentation, you will be asked to justify how you quantitaively evaluate your project.  
The teaching team will give you feedback and suggestions about your plan during the presentation.  
Every team will need to design a series of experiments to quantitatively evaluate your project.  
Experiments should measure:

- Accuracy: What percentage of the time does the robot succeed in the task
- Timing: How long does the robot take to accomplish the task
- The variance of one meaningful parameter for your project, e.g.
    - The type(s) of objects you interact with
    - Lighting conditions
    - How messy the workspace is
    - Human interference
    - Etc.

Your experiment plan for the second presentation should include:  

- A clear definition of success: a clear, binary definition, e.g. "the towel is folded with edges aligned within 3cm"
- Termination criteria: a what point is failure decided, e.g. safety stop, object dropped, timeout
- Starting state: how does the robot begin each trial
- Reset proceedure: steps to return the environment to the starting state

You must test a minimum of 3 states of your project.  
You must run at least 10 trials per state tested.  
This requires at least 30 trial runs of your project.  
For each trial, you should record:

- Trial number 
- State label (which of the 3 states are you testing)
- Success / failure
- Task completion time
- Failure mode if applicable (e.g. "timeout", "object dropped", etc.)
- Any notable observations

Your quantitative results report in your Github repo should include:

- Mean and standard deviations of timings across successful trials
- Success rate
- Failure mode analysis: categorize failures into types
- The raw data in a csv file
- At least one bar chart or table showing success rate across conditions


## Final Deliverables

- A short video demo of your robot performing its application
- Upload your model(s) to Huggingface
- Github repo containing the following:
    - A .devcontainer with a Dockerfile and devcontainer.json purpose made for your project and your dependencies  
    Theoretically, anyone who downloads your repo should be able to use your robot using your container environment
    - All of your customized code required to use the robot
    - Quantitative results data
    - Contributions from all team members
    - A LICENSE file that complies with all dependencies' licenses
    - A README.md file with:
        - A short explanation of your project
        - A link to your video demo
        - Report and visualizations about your quantitative results
        - Setup instructions, including installation instructions of any dependencies, and a link to download your pre-trained model(s)
        - Usage instructions
- Return all materials


## FAQ

**Q:** What methods should we focus on? (VLA, classical motion planning, RL)?  
**A:** Start by training a demo using the tutorial from lerobot.  
Afterwards you may use any methods necessary.  
The lab schedule will not train you on RL until near the end of the quarter, but you are always welcome to work ahead.

**Q:** We couldn't get enough time with the arms to complete our project, can we still get the full grade?  
**A:** You need to manage your time to complete on-time.  
Please be considerate to your fellow class-mates and use the class spreadsheet to schedule time with the 5090 desktops.  
Consider training your models on your personal devices overnight to reduce reliance on school resources.  

**Q:** Do we have to use 2 arms?  
**A:** Your project must meet all project requirements.

**Q:** Can we change the hardware?  
**A:** Multiple teams need to share these robot arms.  
Therefore, you can potentially add hardware and external tools if your project requires.  
You must be able to rapidly return the robot to its base configuration to allow other teams to use it.

**Q:** How do I record and train with 2 arms?  
**A:** There are very few examples online using 2 arms with lerobot.  
Below are some example commands to get you started.  
Note how the train command sets the batch size, chunk size, and action steps.  
**You will need the 5090 desktops to train for your project.**
```bash
lerobot-record \
    --robot.type=bi_so100_follower \
    --robot.left_arm_port=/dev/ttyACM2 \
    --robot.right_arm_port=/dev/ttyACM3 \
    --robot.id=bi_soa_follower \
    --teleop.type=bi_so100_leader \
    --teleop.left_arm_port=/dev/ttyACM0 \
    --teleop.right_arm_port=/dev/ttyACM1 \
    --teleop.id=bi_soa_leader \
    --robot.cameras="{ left: {type: opencv, index_or_path: 8, width: 1920, height: 1080, fps: 30, fourcc: MJPG}, right: {type: opencv, index_or_path: 6, width: 1920, height: 1080, fps: 30, fourcc: MJPG}, overhead: {type: intelrealsense, serial_number_or_name: 349622072267, width: 640, height: 480, fps: 30} }" \
    --display_data=false \
    --dataset.repo_id=${HF_USER}/bi_test1 \
    --dataset.num_episodes=10 \
    --dataset.single_task="move the cube to the right" \
    --dataset.push_to_hub=False \
    --dataset.episode_time_s=30 \
    --dataset.reset_time_s=30 \
    --play_sounds=false
```
```bash
lerobot-train \
    --dataset.repo_id=${HF_USER}/bi_test1 \
    --policy.type=act \
    --output_dir=outputs/train/act_bi_test1 \
    --job_name=act_bi_test1 \
    --policy.device=cuda \
    --wandb.enable=false \
    --policy.repo_id=${HF_USER}/bi_test1 \
    --batch_size=2 \
    --policy.chunk_size=50 \
    --policy.n_action_steps=50
```


## Resources

[Physical Intelligence's Website](https://www.pi.website/)  
[Physical Intelligence's YouTube Chanel](https://www.youtube.com/@PhysicalIntelligence/videos)  
Physical Intelligence (pi) is a cutting edge, YC-backed, startup developing VLA models for general robotics.  
Their YouTube chanel features many impressive demos that are similar to the goal of this project.  
Given that they have far more resources, you are not expected to be able to replicate their results fully, but their work can still serve as inspiration to help you scope your project.

[NVIDIA Isaac GR00T](https://developer.nvidia.com/isaac/gr00t)  
[Actually useful GR00T tutorials](https://www.youtube.com/playlist?list=PLV3OXZIciyneoSHLTuS42_rvXXIj6wDQC)  
GR00T is NVIDIA's VLA model for general robotics.  
It has integrations with their other systems like Isaac Lab, Cosmos, and Isaac ROS.  
Their documentation is lacking and frustrating, so it is recommended to begin with a different VLA model until your requirements necessitate GR00T's features.

**Project Examples**
- [Making espresso coffee](https://www.youtube.com/watch?v=iG2fHqa6ohk)
- [Folding laundry](https://www.youtube.com/watch?v=Oa19cq_MxE0)
- [Scanning and sorting objects](https://www.youtube.com/shorts/i2JHWBzwPcs)
- [Folding boxes](https://www.youtube.com/shorts/MY-_ehZJ884)
- [Making a burger](https://www.youtube.com/watch?v=oDJuD95Sua0)
- [Making matcha tea](https://www.youtube.com/watch?v=FEa4-pXqAoE&t=2s)
- [Playing in the dirt](https://www.linkedin.com/posts/isaac-blankenau_ros2-lerobot-robotlearning-activity-7387233936571056128-kPhn)
- [Lamps that fold laundry](https://www.hello-lume.com/)