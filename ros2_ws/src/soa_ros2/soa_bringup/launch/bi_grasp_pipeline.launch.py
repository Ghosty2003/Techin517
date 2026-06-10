"""bi_grasp_pipeline.launch.py

Full bimanual grasp pipeline launch file.

Starts everything needed for YOLO-driven sequential object grasping on
top of the hardware/MoveIt bringup.

Prerequisites (must already be running before this launch):
  ros2 launch bi_soa_moveit_config bi_soa_moveit_bringup.launch.py cameras:=true

What this launches:
  Per arm (left + right):
    - move_to_pose_server  (MoveIt cartesian motion)
    - gripper_server       (MoveIt gripper control)
    - grasp_state_machine  (IDLE → GRASPING → IDLE lifecycle)

  Two rosetta clients:
    - rosetta_client_right  (scissors policy, port 8080)
    - rosetta_client_left   (pen policy, port 8081)

  One orchestrator:
    - grasp_sequencer  (YOLO-driven priority dispatch with per-object go_to_poses CSVs)

Note: controller_switcher nodes are already started by bi_soa_moveit_bringup.

Grasping sequences (override via left_sequence / right_sequence args):
  Left arm:  tape → pen → plier   (highest priority first)
  Right arm: screwdriver → scissor

Usage:
  ros2 launch soa_bringup bi_grasp_pipeline.launch.py

Override model or CSV paths:
  ros2 launch soa_bringup bi_grasp_pipeline.launch.py \\
      right_model:=/path/to/right_model \\
      scissor_csv:=/home/ubuntu/techin517/right_scissor.csv

Run without home-return between grasps:
  ros2 launch soa_bringup bi_grasp_pipeline.launch.py run_go_to_poses:=false
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


# ---------------------------------------------------------------------------
# Paths resolved at import time
# ---------------------------------------------------------------------------
_BRINGUP_SHARE = get_package_share_directory('soa_bringup')
_ROSETTA_SHARE = get_package_share_directory('rosetta')

_RIGHT_CONTRACT = os.path.join(_BRINGUP_SHARE, 'rosetta_contracts', 'bi_soa_right_arm_contract.yaml')
_LEFT_CONTRACT  = os.path.join(_BRINGUP_SHARE, 'rosetta_contracts', 'bi_soa_left_arm_contract.yaml')
_ROSETTA_PARAMS = os.path.join(_ROSETTA_SHARE, 'params', 'rosetta_client.yaml')

_DEFAULT_RIGHT_MODEL = '/home/ubuntu/techin517/outputs/train/pick_up_right_scissors/checkpoints/100000/pretrained_model'
_DEFAULT_LEFT_MODEL  = '/home/ubuntu/techin517/outputs/train/pick_up_left_pen/checkpoints/100000/pretrained_model'


# ---------------------------------------------------------------------------
# Helper: IncludeLaunchDescription for rosetta_client_launch.py
# ---------------------------------------------------------------------------
def _rosetta_node(node_name: str, contract: str, model: str, server_address: str):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(_ROSETTA_SHARE, 'launch', 'rosetta_client_launch.py')
        ),
        launch_arguments={
            'node_name':               node_name,
            'contract_path':           contract,
            'pretrained_name_or_path': model,
            'server_address':          server_address,
            'params_file':             _ROSETTA_PARAMS,
            'configure':               'true',
            'activate':                'true',
        }.items(),
    )


# ---------------------------------------------------------------------------
# OpaqueFunction build (needs context to resolve LaunchConfigurations)
# ---------------------------------------------------------------------------
def launch_setup(context, *args, **kwargs):
    def cfg(name):
        return LaunchConfiguration(name).perform(context)

    right_model  = cfg('right_model')
    left_model   = cfg('left_model')
    right_port   = cfg('right_rosetta_port')
    left_port    = cfg('left_rosetta_port')
    run_gtp        = cfg('run_go_to_poses')
    policy_timeout = cfg('policy_timeout_s')
    left_seq            = cfg('left_sequence')
    right_seq           = cfg('right_sequence')
    right_pause_on_left = cfg('right_pause_on_left')
    max_reach      = float(cfg('max_reach'))
    csv_base_dir   = cfg('csv_base_dir')
    left_x_offset  = float(cfg('left_x_offset'))
    left_y_offset  = float(cfg('left_y_offset'))
    left_z_offset  = float(cfg('left_z_offset'))
    right_x_offset = float(cfg('right_x_offset'))
    right_y_offset = float(cfg('right_y_offset'))
    right_z_offset = float(cfg('right_z_offset'))
    left_gripper_open_pos    = float(cfg('left_gripper_open_position'))
    right_gripper_open_pos   = float(cfg('right_gripper_open_position'))
    left_gripper_close_pos   = float(cfg('left_gripper_close_position'))
    right_gripper_close_pos  = float(cfg('right_gripper_close_position'))
    left_gripper_close_at    = cfg('left_gripper_close_at')
    right_gripper_close_at   = cfg('right_gripper_close_at')
    left_gripper_open_at     = cfg('left_gripper_open_at')
    right_gripper_open_at    = cfg('right_gripper_open_at')

    # t=0s: arm servers (fast to start, MoveIt needs a moment anyway)
    arm_servers = [
        Node(
            package='soa_functions',
            executable='move_to_pose_server',
            name='move_to_pose_server_right',
            output='screen',
            parameters=[{
                'ns':             'right',
                'move_group':     'right_arm',
                'joint_prefix':   'right_',
                'base_link_name': 'right_base_link',
                'max_reach':      max_reach,
            }],
        ),
        Node(
            package='soa_functions',
            executable='gripper_server',
            name='gripper_server_right',
            output='screen',
            parameters=[{
                'ns':             'right',
                'move_group':     'right_gripper',
                'joint_prefix':   'right_',
                'base_link_name': 'right_base_link',
            }],
        ),
        Node(
            package='soa_functions',
            executable='move_to_pose_server',
            name='move_to_pose_server_left',
            output='screen',
            parameters=[{
                'ns':             'left',
                'move_group':     'left_arm',
                'joint_prefix':   'left_',
                'base_link_name': 'left_base_link',
                'max_reach':      max_reach,
            }],
        ),
        Node(
            package='soa_functions',
            executable='gripper_server',
            name='gripper_server_left',
            output='screen',
            parameters=[{
                'ns':             'left',
                'move_group':     'left_gripper',
                'joint_prefix':   'left_',
                'base_link_name': 'left_base_link',
            }],
        ),
    ]

    # t=3s: rosetta clients (GPU model loading takes a few seconds)
    rosetta_nodes = TimerAction(
        period=3.0,
        actions=[
            _rosetta_node(
                node_name='rosetta_client_right',
                contract=_RIGHT_CONTRACT,
                model=right_model,
                server_address=f'127.0.0.1:{right_port}',
            ),
            _rosetta_node(
                node_name='rosetta_client_left',
                contract=_LEFT_CONTRACT,
                model=left_model,
                server_address=f'127.0.0.1:{left_port}',
            ),
        ],
    )

    # t=6s: state machines (wait for rosetta to be loading)
    state_machines = TimerAction(
        period=6.0,
        actions=[
            Node(
                package='soa_apps',
                executable='grasp_state_machine',
                name='right_grasp_state_machine',
                output='screen',
                parameters=[{
                    'policy_action':             '/rosetta_client_right/run_policy',
                    'controller_switch_service': '/right/controller_switcher/switch_controller',
                    'hover_done_topic':          '/right/hover_done',
                    'arm_ns':                    'right',
                    'policy_timeout_s':          float(policy_timeout),
                    'run_go_to_poses':           False,
                }],
            ),
            Node(
                package='soa_apps',
                executable='grasp_state_machine',
                name='left_grasp_state_machine',
                output='screen',
                parameters=[{
                    'policy_action':             '/rosetta_client_left/run_policy',
                    'controller_switch_service': '/left/controller_switcher/switch_controller',
                    'hover_done_topic':          '/left/hover_done',
                    'arm_ns':                    'left',
                    'policy_timeout_s':          float(policy_timeout),
                    'run_go_to_poses':           False,
                }],
            ),
        ],
    )

    actions = arm_servers + [rosetta_nodes, state_machines]

    # t=10s: sequencer (wait for arm servers + state machines to be ready)
    actions.append(TimerAction(
        period=10.0,
        actions=[
            Node(
                package='soa_apps',
                executable='grasp_sequencer',
                name='grasp_sequencer',
                output='screen',
                parameters=[{
                    'left_sequence':          left_seq,
                    'right_sequence':         right_seq,
                    'right_pause_on_left':    right_pause_on_left,
                    'left_arm_ns':            'left',
                    'right_arm_ns':           'right',
                    'left_x_offset':          left_x_offset,
                    'left_y_offset':          left_y_offset,
                    'left_z_offset':          left_z_offset,
                    'right_x_offset':         right_x_offset,
                    'right_y_offset':         right_y_offset,
                    'right_z_offset':         right_z_offset,
                    'left_tf_source_frame':   'base_link',
                    'left_tf_target_frame':   'left_base_link',
                    # CSVs resolved dynamically: {csv_base_dir}/{arm}_{object}.csv
                    'csv_base_dir':           csv_base_dir,
                    'left_gripper_close_at':       left_gripper_close_at,
                    'left_gripper_open_at':        left_gripper_open_at,
                    'right_gripper_close_at':      right_gripper_close_at,
                    'right_gripper_open_at':       right_gripper_open_at,
                    'left_gripper_open_position':   left_gripper_open_pos,
                    'right_gripper_open_position':  right_gripper_open_pos,
                    'left_gripper_close_position':  left_gripper_close_pos,
                    'right_gripper_close_position': right_gripper_close_pos,
                    'run_go_to_poses':        run_gtp.lower() in ('true', '1', 'yes'),
                    'left_state_topic':       '/left_grasp_state_machine/state',
                    'right_state_topic':      '/right_grasp_state_machine/state',
                }],
            ),
        ],
    ))

    return actions


def generate_launch_description():
    return LaunchDescription([
        # Model paths
        DeclareLaunchArgument(
            'right_model',
            default_value=_DEFAULT_RIGHT_MODEL,
            description='Path to right arm policy checkpoint (pick_up_right_scissors)',
        ),
        DeclareLaunchArgument(
            'left_model',
            default_value=_DEFAULT_LEFT_MODEL,
            description='Path to left arm policy checkpoint (pick_up_left_pen)',
        ),
        # Rosetta server ports
        DeclareLaunchArgument(
            'right_rosetta_port',
            default_value='8080',
            description='Port for right arm Rosetta policy server',
        ),
        DeclareLaunchArgument(
            'left_rosetta_port',
            default_value='8081',
            description='Port for left arm Rosetta policy server',
        ),
        # Policy timeout
        DeclareLaunchArgument(
            'policy_timeout_s',
            default_value='10.0',
            description='Seconds before policy is force-stopped per grasp attempt',
        ),
        # Objects on the left arm that pause the right arm while active
        DeclareLaunchArgument(
            'right_pause_on_left',
            default_value='',
            description='Comma-separated left-arm objects that pause right arm dispatch while active',
        ),
        # Grasping sequences
        DeclareLaunchArgument(
            'left_sequence',
            default_value='tape,pen,plier',
            description='Left arm object priority order (comma-separated, highest priority first)',
        ),
        DeclareLaunchArgument(
            'right_sequence',
            default_value='screwdriver,scissor',
            description='Right arm object priority order (comma-separated, highest priority first)',
        ),
        # Directory containing go_to_poses CSVs, named {arm}_{object}.csv
        # e.g. left_pen.csv, right_scissor.csv — missing files are silently skipped
        DeclareLaunchArgument(
            'csv_base_dir',
            default_value='/home/ubuntu/techin517',
            description='Directory containing go_to_poses CSVs ({arm}_{object}.csv)',
        ),
        # Max reach for move_to_pose_server (both arms share the same limit)
        DeclareLaunchArgument(
            'max_reach',
            default_value='0.55',
            description='Maximum XYZ distance (m) from base_link the arm may reach',
        ),
        # Gripper pose indices (0-based) and positions during go_to_poses return trajectory
        # 1.7453 = fully open, -0.1745 = fully closed
        DeclareLaunchArgument('left_gripper_close_at',        default_value='0',      description='Left gripper close pose index (0-based)'),
        DeclareLaunchArgument('right_gripper_close_at',       default_value='0',      description='Right gripper close pose index (0-based)'),
        DeclareLaunchArgument('left_gripper_open_at',         default_value='7',      description='Left gripper open pose index (0-based)'),
        DeclareLaunchArgument('right_gripper_open_at',        default_value='7',      description='Right gripper open pose index (0-based)'),
        DeclareLaunchArgument('left_gripper_open_position',   default_value='1.3',    description='Left gripper open position in radians for go_to_poses'),
        DeclareLaunchArgument('right_gripper_open_position',  default_value='1.3',    description='Right gripper open position in radians for go_to_poses'),
        DeclareLaunchArgument('left_gripper_close_position',  default_value='-0.1745', description='Left gripper close position in radians for go_to_poses'),
        DeclareLaunchArgument('right_gripper_close_position', default_value='-0.1745', description='Right gripper close position in radians for go_to_poses'),
        # Per-arm hover offsets (meters, applied before TF transform)
        DeclareLaunchArgument('left_x_offset',  default_value='0.0',  description='Left arm hover X offset (m)'),
        DeclareLaunchArgument('left_y_offset',  default_value='0.0',  description='Left arm hover Y offset (m)'),
        DeclareLaunchArgument('left_z_offset',  default_value='0.0',  description='Left arm hover Z offset (m), negative = lower'),
        DeclareLaunchArgument('right_x_offset', default_value='0.0',  description='Right arm hover X offset (m)'),
        DeclareLaunchArgument('right_y_offset', default_value='-0.1', description='Right arm hover Y offset (m)'),
        DeclareLaunchArgument('right_z_offset', default_value='0.0',  description='Right arm hover Z offset (m), negative = lower'),
        # go_to_poses toggle
        DeclareLaunchArgument(
            'run_go_to_poses',
            default_value='true',
            description='Run go_to_poses after each grasp to return arm to home position',
        ),
        OpaqueFunction(function=launch_setup),
    ])
