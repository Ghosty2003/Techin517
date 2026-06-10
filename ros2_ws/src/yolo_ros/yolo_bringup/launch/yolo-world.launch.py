# Copyright (C) 2023 Miguel Ángel González Santamarta
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import os
from launch import LaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.actions import (
    IncludeLaunchDescription,
    ExecuteProcess,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():

    # Define your custom classes here
    classes = "['screwdriver', 'scissors', 'pen', 'tape', 'pliers']"

    return LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(
                        get_package_share_directory("yolo_bringup"),
                        "launch",
                        "yolo.launch.py",
                    )
                ),
                launch_arguments={
                    "model_type": "World",
                    "model": LaunchConfiguration("model", default="yolov8s-worldv2.pt"),
                    "tracker": LaunchConfiguration("tracker", default="bytetrack.yaml"),
                    "device": LaunchConfiguration("device", default="cuda:0"),
                    "enable": LaunchConfiguration("enable", default="True"),
                    "threshold": LaunchConfiguration("threshold", default="0.3"),
                    # 3D detection settings
                    "use_3d": LaunchConfiguration("use_3d", default="True"),
                    "input_image_topic": LaunchConfiguration(
                        "input_image_topic",
                        default="/static_camera/overhead_cam/color/image_raw"
                    ),
                    "input_depth_topic": LaunchConfiguration(
                        "input_depth_topic",
                        default="/static_camera/overhead_cam/aligned_depth_to_color/image_raw"
                    ),
                    "input_depth_info_topic": LaunchConfiguration(
                        "input_depth_info_topic",
                        default="/static_camera/overhead_cam/aligned_depth_to_color/camera_info"
                    ),
                    "depth_image_units_divisor": LaunchConfiguration(
                        "depth_image_units_divisor", default="1000"
                    ),
                    "target_frame": LaunchConfiguration(
                        "target_frame", default="base_link"
                    ),
                    "image_reliability": LaunchConfiguration(
                        "image_reliability", default="1"
                    ),
                    "namespace": LaunchConfiguration("namespace", default="yolo"),
                }.items(),
            ),

            # Auto-set classes after node starts (wait 5 seconds for node to activate)
            TimerAction(
                period=5.0,
                actions=[
                    ExecuteProcess(
                        cmd=[
                            "ros2", "service", "call",
                            "/yolo/set_classes",
                            "yolo_msgs/srv/SetClasses",
                            f"{{classes: {classes}}}",
                        ],
                        output="screen",
                    )
                ],
            ),
        ]
    )