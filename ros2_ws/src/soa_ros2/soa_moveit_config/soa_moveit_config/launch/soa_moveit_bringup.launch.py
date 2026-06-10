"""Launch MoveIt with the real SOA follower arm.

Hardware (ros2_control + controllers) runs in the global namespace so MoveIt's default
action client paths (/arm_controller/follow_joint_trajectory, /gripper_controller/gripper_cmd)
match the server paths directly — no remapping required.

A dedicated MoveIt RSP (no frame_prefix) subscribes to /joint_states published by the
global-namespace joint_state_broadcaster, and publishes base_link, shoulder_link, …
TF frames matching the SRDF virtual joint definition.

Usage:
    ros2 launch soa_moveit_config soa_moveit_bringup.launch.py
    ros2 launch soa_moveit_config soa_moveit_bringup.launch.py cameras:=true
"""

import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from moveit_configs_utils import MoveItConfigsBuilder

from soa_bringup.calibration_loader import load_arm_calibration

JOINTS = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']


def _calib_xacro_args(calib: dict) -> list:
    """Return flat list of xacro 'key:=value' strings for calibration data."""
    args = []
    for j in JOINTS:
        args += [f' {j}_id:=', str(calib[j]['id']),
                 f' {j}_offset:=', str(calib[j]['offset'])]
    return args


def launch_setup(context, *args, **kwargs):
    cameras       = context.launch_configurations['cameras']
    leader        = context.launch_configurations['leader']
    arm_ns        = context.launch_configurations['arm_ns'].strip('/')
    params_fn     = context.launch_configurations['params_file']
    launch_moveit = context.launch_configurations['launch_moveit'] == 'true'

    moveit_config = (
        MoveItConfigsBuilder('soa', package_name='soa_moveit_config')
        .to_moveit_configs()
    )
    launch_pkg = moveit_config.package_path

    bringup_share = get_package_share_directory('soa_bringup')
    description_share = get_package_share_directory('soa_description')
    moveit_share = get_package_share_directory('soa_moveit_config')

    # Load hardware parameters — use override params_file when arm_ns is set
    params_file = os.path.join(bringup_share, 'config', params_fn)
    with open(params_file) as f:
        hw = yaml.safe_load(f)['/**']['ros__parameters']
    follower_params = hw['follower']

    # Helpers for namespace-aware node configuration
    # When arm_ns is set, hardware nodes run under that namespace so controller
    # paths become /<arm_ns>/arm_controller/... which MoveIt resolves correctly.
    ns_kwargs     = {'namespace': arm_ns} if arm_ns else {}
    cm_path       = f'/{arm_ns}/controller_manager' if arm_ns else '/controller_manager'
    cm_switch_srv = f'/{arm_ns}/controller_manager/switch_controller' if arm_ns else '/controller_manager/switch_controller'
    frame_prefix  = f'{arm_ns}/' if arm_ns else ''
    base_link     = f'{arm_ns}/base_link' if arm_ns else 'base_link'

    # Load per-joint calibration offsets and servo IDs
    follower_calib = load_arm_calibration(
        follower_params['calibration_dir'],
        follower_params['id'],
    )

    # Generate URDF with correct serial port and calibration (needed by ros2_control hardware)
    xacro_file = os.path.join(description_share, 'urdf', 'soa.urdf.xacro')
    follower_urdf_cmd = Command([
        FindExecutable(name='xacro'), ' ',
        xacro_file,
        ' usb_port:=', follower_params['usb_port'],
        ' leader_mode:=false',
        ' use_sim:=false',
        *_calib_xacro_args(follower_calib),
    ])
    hw_robot_description = {
        'robot_description': ParameterValue(follower_urdf_cmd, value_type=str)
    }

    controllers_yaml = os.path.join(moveit_share, 'config', 'moveit_controllers_hw.yaml')
    ros2_control_node = Node(
        package='controller_manager',
        executable='ros2_control_node',
        output='screen',
        parameters=[hw_robot_description, controllers_yaml],
        **ns_kwargs,
    )

    # Spawners: when namespaced, point explicitly at the namespaced controller_manager.
    def _spawner(*args_list):
        return Node(
            package='controller_manager',
            executable='spawner',
            arguments=list(args_list) + (['--controller-manager', cm_path] if arm_ns else []),
            output='screen',
            **ns_kwargs,
        )

    spawner_jsb         = _spawner('joint_state_broadcaster')
    spawner_arm         = _spawner('arm_controller')
    spawner_gripper     = _spawner('gripper_controller')
    spawner_arm_fwd     = _spawner('arm_fwd_controller', '--inactive')
    spawner_gripper_fwd = _spawner('gripper_fwd_controller', '--inactive')

    controller_switcher = Node(
        package='soa_functions',
        executable='controller_switcher',
        name='controller_switcher',
        output='screen',
        parameters=[{
            'initial_mode': 'jtc',
            'cm_service': cm_switch_srv,
        }],
        **ns_kwargs,
    )

    # RSP: frame_prefix isolates TF frames per arm when arm_ns is set.
    rsp_params = dict(moveit_config.robot_description)
    if frame_prefix:
        rsp_params['frame_prefix'] = frame_prefix
    moveit_rsp = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[rsp_params],
        **ns_kwargs,
    )

    # Static TF: world -> base_link (or world -> <arm_ns>/base_link).
    # For the default arm use the generated virtual-joint launch; for named
    # namespaces publish the transform directly so frame names are correct.
    if arm_ns:
        static_tf = Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='world_base_tf',
            arguments=['0', '0', '0', '0', '0', '0', 'world', base_link],
            output='screen',
        )
    else:
        static_tf = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                str(launch_pkg / 'launch/static_virtual_joint_tfs.launch.py')
            ),
        )

    camera_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='camera_base_tf',
        arguments=[
            '0.0392', '0.1131', '0.3051',
            '0.6355', '-0.6305', '0.1935', '-0.4015',
            'overhead_camoverhead_cam_color_optical_frame',
            base_link,
        ],
        output='screen',
    )

    # Secondary arms (arm_ns set) suppress all monitoring publishers so they
    # don't conflict with the primary arm's RViz / planning scene.
    move_group_params = {
        'allow_trajectory_execution': True,
        'monitor_dynamics': False,
        'publish_robot_description_semantic': not bool(arm_ns),
        'publish_planning_scene':             not bool(arm_ns),
        'publish_geometry_updates':           not bool(arm_ns),
        'publish_state_updates':              not bool(arm_ns),
        'publish_transforms_updates':         not bool(arm_ns),
    }
    move_group = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        output='screen',
        parameters=[moveit_config.to_dict(), move_group_params],
        additional_env={'DISPLAY': os.environ.get('DISPLAY', '')},
        **ns_kwargs,
    )

    # RViz only makes sense for the primary arm (no namespace).
    rviz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            str(launch_pkg / 'launch/moveit_rviz.launch.py')
        ),
    )

    actions = [
        ros2_control_node,
        spawner_jsb,
        RegisterEventHandler(OnProcessExit(target_action=spawner_jsb, on_exit=[spawner_arm])),
        RegisterEventHandler(OnProcessExit(target_action=spawner_arm, on_exit=[spawner_gripper])),
        spawner_arm_fwd,
        spawner_gripper_fwd,
        controller_switcher,
        moveit_rsp,
        static_tf,
        camera_static_tf,
    ]

    if launch_moveit:
        actions.append(move_group)
        # RViz only for the primary arm to avoid duplicate windows.
        if not arm_ns:
            actions.append(rviz)

    if leader == 'true':
        leader_params = hw['leader']

        try:
            leader_calib = load_arm_calibration(
                leader_params['calibration_dir'],
                leader_params['id'],
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f'[soa_moveit_bringup] Leader calibration not found.\n{e}\n'
                'Run LeRobot calibration and update soa_params.yaml with the correct path.'
            )

        leader_controllers_yaml = os.path.join(
            description_share, 'config', 'leader_controllers.yaml'
        )

        leader_urdf_cmd = Command([
            FindExecutable(name='xacro'), ' ',
            xacro_file,
            ' usb_port:=', leader_params['usb_port'],
            ' leader_mode:=true',
            ' use_sim:=false',
            *_calib_xacro_args(leader_calib),
        ])
        leader_robot_description = {
            'robot_description': ParameterValue(leader_urdf_cmd, value_type=str)
        }

        leader_cm = Node(
            package='controller_manager',
            executable='ros2_control_node',
            namespace='leader',
            output='screen',
            parameters=[leader_robot_description, leader_controllers_yaml],
        )

        leader_rsp = Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            namespace='leader',
            output='screen',
            parameters=[leader_robot_description, {'frame_prefix': 'leader/'}],
        )

        leader_jsb_spawner = Node(
            package='controller_manager',
            executable='spawner',
            arguments=['joint_state_broadcaster',
                       '--controller-manager', '/leader/controller_manager'],
            output='screen',
        )

        leader_static_tf = Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='leader_world_tf',
            arguments=['0', '0', '0', '0', '0', '0', 'world', 'leader/base_link'],
            output='screen',
        )

        teleop_node = Node(
            package='soa_teleop',
            executable='teleop_node',
            name='teleop_node',
            output='screen',
        )

        actions += [leader_cm, leader_rsp, leader_jsb_spawner,
                    leader_static_tf, teleop_node]

    if cameras == 'true':
        camera_config = context.launch_configurations['camera_config']
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(bringup_share, 'launch', 'include', 'cameras.launch.py')
            ),
            launch_arguments={'config_file': camera_config}.items(),
        ))

    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'cameras',
            default_value='true',
            description='Launch camera nodes alongside the arm hardware.',
        ),
        DeclareLaunchArgument(
            'leader',
            default_value='false',
            description='Launch the leader arm hardware and teleop node alongside MoveIt.',
        ),
        DeclareLaunchArgument(
            'arm_ns',
            default_value='',
            description='Namespace for all hardware nodes (e.g. "arm2"). '
                        'Leave empty for the primary arm.',
        ),
        DeclareLaunchArgument(
            'params_file',
            default_value='soa_params.yaml',
            description='Params filename inside soa_bringup/config/ '
                        '(e.g. soa_params_arm2.yaml).',
        ),
        DeclareLaunchArgument(
            'camera_config',
            default_value='soa_cameras.yaml',
            description='Camera config filename inside soa_bringup/config/ '
                        '(e.g. soa_cameras_arm2.yaml).',
        ),
        DeclareLaunchArgument(
            'launch_moveit',
            default_value='true',
            description='Launch move_group and RViz. Set false for secondary arms '
                        'to avoid two move_group instances crashing RViz.',
        ),
        OpaqueFunction(function=launch_setup),
    ])
