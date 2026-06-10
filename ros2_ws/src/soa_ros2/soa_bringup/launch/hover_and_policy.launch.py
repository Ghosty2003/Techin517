from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, PushRosNamespace


def _arm_nodes(side: str, move_group: str, joint_prefix: str) -> GroupAction:
    """Return a namespaced group of hover+policy nodes for one arm.

    Args:
        side:         ROS namespace — 'left' or 'right'.
        move_group:   MoveIt planning group name — 'left_arm' or 'right_arm'.
        joint_prefix: URDF joint name prefix — 'left_' or 'right_'.
    """
    return GroupAction(actions=[
        PushRosNamespace(side),
        Node(
            package='soa_apps',
            executable='object_detector_node',
            name='object_detector',
            output='screen',
            parameters=[{
                'target_objects': ['screwdriver', 'pen', 'apple', 'orange'],
                'confidence_threshold': 0.5,
            }],
        ),
        Node(
            package='soa_apps',
            executable='hover_above_object',
            name='hover_controller',
            output='screen',
            parameters=[{
                'hover_height': LaunchConfiguration('hover_height'),
                'target_object': LaunchConfiguration('target_object'),
                'policy_name': LaunchConfiguration('policy_name'),
                'move_group': move_group,
                'joint_prefix': joint_prefix,
            }],
        ),
        Node(
            package='soa_apps',
            executable='policy_controller_stub',
            name='policy_controller',
            output='screen',
            parameters=[{
                'policy_checkpoint': LaunchConfiguration('policy_checkpoint'),
                'use_visual_feedback': True,
            }],
        ),
    ])


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('target_object', default_value='screwdriver'),
        DeclareLaunchArgument('hover_height', default_value='0.15'),
        DeclareLaunchArgument('policy_name', default_value='pick_policy'),
        DeclareLaunchArgument('policy_checkpoint', default_value='/path/to/policy.pth'),

        _arm_nodes(side='left',  move_group='left_arm',  joint_prefix='left_'),
        _arm_nodes(side='right', move_group='right_arm', joint_prefix='right_'),
    ])
