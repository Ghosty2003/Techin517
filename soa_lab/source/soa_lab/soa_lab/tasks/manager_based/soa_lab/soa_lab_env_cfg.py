# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import math

import isaaclab.sim as sim_utils
from isaaclab.assets import (
    ArticulationCfg,
    AssetBaseCfg,
    RigidObjectCfg,
)
from isaaclab.utils.noise import AdditiveGaussianNoiseCfg as Gnoise
from isaaclab.utils.noise import AdditiveUniformNoiseCfg as Unoise
from isaaclab.sim.spawners.from_files.from_files_cfg import UsdFileCfg
from isaaclab.sim.schemas.schemas_cfg import RigidBodyPropertiesCfg
from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab.managers import CurriculumTermCfg as CurrTerm
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sensors import ContactSensorCfg
from isaaclab.sensors.frame_transformer.frame_transformer_cfg import (
    FrameTransformerCfg,
    OffsetCfg,
)
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR

from isaaclab.markers.config import FRAME_MARKER_CFG  # isort: skip

from soa_lab.robots import SO_ARM101_CFG

import soa_lab.tasks.manager_based.soa_lab.mdp as mdp


# Marker used for FrameTransformer visualization.
# Kept at module scope so @configclass doesn't turn it into a scene field.
_EE_FRAME_MARKER_CFG = FRAME_MARKER_CFG.copy()
_EE_FRAME_MARKER_CFG.markers["frame"].scale = (0.05, 0.05, 0.05)
_EE_FRAME_MARKER_CFG.prim_path = "/Visuals/FrameTransformer"


##
# Scene definition
##


@configclass
class SoaLabSceneCfg(InteractiveSceneCfg):
    """Configuration for a cart-pole scene."""

    # ground plane
    ground = AssetBaseCfg(
        prim_path="/World/ground",
        spawn=sim_utils.GroundPlaneCfg(size=(1000.0, 1000.0)),
    )

    # lights
    dome_light = AssetBaseCfg(
        prim_path="/World/DomeLight",
        spawn=sim_utils.DomeLightCfg(color=(0.9, 0.9, 0.9), intensity=500.0),
    )

    # robot
    robot: ArticulationCfg = SO_ARM101_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")

    # contact sensor on every robot link. GPU PhysX does not support
    # filter_prim_paths_expr against the ground plane, so the sensor reports
    # net contact forces from all sources — the reward term below narrows the
    # body list to links that should never contact anything in normal operation.
    contact_forces: ContactSensorCfg = ContactSensorCfg(
        prim_path="{ENV_REGEX_NS}/Robot/.*",
        history_length=3,
        update_period=0.0,
    )

    # end effector frame
    ee_frame: FrameTransformerCfg = FrameTransformerCfg(
        prim_path="{ENV_REGEX_NS}/Robot/base_link",
        debug_vis=True,
        visualizer_cfg=_EE_FRAME_MARKER_CFG,
        target_frames=[
            FrameTransformerCfg.FrameCfg(
                prim_path="{ENV_REGEX_NS}/Robot/gripper_link",
                name="end_effector",
                offset=OffsetCfg(
                    pos=[-0.0079, -0.000218121, -0.0981274],
                    rot=[0.0, 0.0, 1.0, 0.0],
                ),
            ),
        ],
    )

    # cube
    object: RigidObjectCfg = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Object",
        init_state=RigidObjectCfg.InitialStateCfg(pos=[0.26, 0.0, 0.015], rot=[1, 0, 0, 0]),
        spawn=UsdFileCfg(
            usd_path=f"{ISAAC_NUCLEUS_DIR}/Props/Blocks/DexCube/dex_cube_instanceable.usd",
            scale=(0.3, 0.3, 0.3),
            rigid_props=RigidBodyPropertiesCfg(
                solver_position_iteration_count=16,
                solver_velocity_iteration_count=1,
                max_angular_velocity=1000.0,
                max_linear_velocity=1000.0,
                max_depenetration_velocity=5.0,
                disable_gravity=False,
            ),
        ),
    )


##
# MDP settings
##


@configclass
class CommandsCfg:
    """Command terms for the MDP."""

    object_pose = mdp.ObjectRelativePoseCommandCfg(
        asset_name="robot",
        body_name=["gripper_link"],
        object_name="object",
        offset=(0.0, 0.0, 0.05),
        resampling_time_range=(8.0, 8.0),
        debug_vis=True,
    )


@configclass
class ActionsCfg:
    """Action specifications for the MDP."""

    arm_action = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=["shoulder_.*", "elbow_flex", "wrist_.*"],
        scale=0.5,
        use_default_offset=True,
    )
    gripper_action = mdp.BinaryJointPositionActionCfg(
        asset_name="robot",
        joint_names=["gripper"],
        open_command_expr={"gripper": 1.0},
        close_command_expr={"gripper": -0.2},
    )


@configclass
class ObservationsCfg:
    """Observation specifications for the MDP."""

    @configclass
    class PolicyCfg(ObsGroup):
        """Observations for policy group."""

        # observation terms (order preserved)
        joint_pos = ObsTerm(func=mdp.joint_pos_rel, noise=Unoise(n_min=-0.005, n_max=0.005))
        joint_vel = ObsTerm(func=mdp.joint_vel_rel, noise=Unoise(n_min=-0.05, n_max=0.05))
        object_position = ObsTerm(func=mdp.object_position_in_robot_root_frame, noise=Gnoise(std=0.001))
        target_object_position = ObsTerm(func=mdp.generated_commands, params={"command_name": "object_pose"})
        ee_position = ObsTerm(func=mdp.ee_position_in_robot_root_frame, noise=Gnoise(std=0.002))
        actions = ObsTerm(func=mdp.last_action, history_length=3)

        def __post_init__(self) -> None:
            self.enable_corruption = True
            self.concatenate_terms = True

    # observation groups
    policy: PolicyCfg = PolicyCfg()


@configclass
class EventCfg:
    """Configuration for events."""

    reset_all = EventTerm(func=mdp.reset_scene_to_default, mode="reset")

    reset_object_position = EventTerm(
        func=mdp.reset_root_state_uniform,
        mode="reset",
        params={
            "pose_range": {"x": (-0.05, 0.05), "y": (-0.05, 0.05), "z": (0.0, 0.0)},
            "velocity_range": {},
            "asset_cfg": SceneEntityCfg("object", body_names="Object"),
        },
    )

    reset_robot_joints = EventTerm(
        func=mdp.reset_joints_by_offset,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot"),
            "position_range": (-0.1, 0.1),
            "velocity_range": (0.0, 0.0),
        },
    )

    arm_disturbances = EventTerm(
        func=mdp.apply_external_force_torque,
        mode="interval",
        interval_range_s=(0.5, 1.5),
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=".*"),
            "force_range": (-1.0, 1.0),
            "torque_range": (-0.5, 0.5),
        },
    )


@configclass
class RewardsCfg:
    """Reward terms for the MDP."""
    reaching_object = RewTerm(func=mdp.object_ee_distance, params={"std": 0.1}, weight=1.0)

    lifting_object = RewTerm(func=mdp.object_is_lifted, params={"minimal_height": 0.016}, weight=1.0)

    object_goal_tracking = RewTerm(
        func=mdp.object_goal_distance,
        params={"std": 0.3, "minimal_height": 0.02, "command_name": "object_pose"},
        weight=16.0,
    )

    object_goal_tracking_fine_grained = RewTerm(
        func=mdp.object_goal_distance,
        params={"std": 0.05, "minimal_height": 0.02, "command_name": "object_pose"},
        weight=5.0,
    )

    # ee_upright = RewTerm(
    #     func=mdp.ee_frame_upright,
    #     params={"std": 0.5},
    #     weight=1.0,
    # )

    ee_upright_penalty = RewTerm(
        func=mdp.ee_frame_downward_penalty,
        weight=-20.0,
    )

    # action penalty
    action_rate = RewTerm(func=mdp.action_rate_l2, weight=-1e-4)

    joint_vel = RewTerm(
        func=mdp.joint_vel_l2,
        weight=-1e-4,
        params={"asset_cfg": SceneEntityCfg("robot")},
    )

    undesired_arm_contact = RewTerm(
        func=mdp.undesired_contacts,
        weight=-20.0,
        params={
            "sensor_cfg": SceneEntityCfg(
                "contact_forces",
                body_names=[
                    "shoulder_link",
                    "upper_arm_link",
                    "lower_arm_link",
                    "wrist_link",
                ],
            ),
            "threshold": 1.0,
        },
    )


@configclass
class TerminationsCfg:
    """Termination terms for the MDP."""

    time_out = DoneTerm(func=mdp.time_out, time_out=True)

    object_dropping = DoneTerm(
        func=mdp.root_height_below_minimum, params={"minimum_height": -0.05, "asset_cfg": SceneEntityCfg("object")}
    )


@configclass
class CurriculumCfg:
    """Curriculum terms for the MDP."""

    action_rate = CurrTerm(
        func=mdp.modify_reward_weight, params={"term_name": "action_rate", "weight": -1e-1, "num_steps": 10000}
    )

    joint_vel = CurrTerm(
        func=mdp.modify_reward_weight, params={"term_name": "joint_vel", "weight": -1e-1, "num_steps": 10000}
    )

    object_spawn_range_1 = CurrTerm(
        func=mdp.modify_term_cfg,
        params={
            "address": "events.reset_object_position.params.pose_range",
            "modify_fn": mdp.expand_pose_range,
            "modify_params": {
                "pose_range": {
                    "x": (-0.03, 0.03),
                    "y": (-0.03, 0.03),
                    "z": (0.0, 0.0),
                },
                "num_steps": 10_000,
            },
        },
    )

    object_spawn_range_2 = CurrTerm(
        func=mdp.modify_term_cfg,
        params={
            "address": "events.reset_object_position.params.pose_range",
            "modify_fn": mdp.expand_pose_range,
            "modify_params": {
                "pose_range": {
                    "x": (-0.04, 0.04),
                    "y": (-0.04, 0.04),
                    "z": (0.0, 0.0),
                },
                "num_steps": 20_000,
            },
        },
    )

    goal_offset_range = CurrTerm(
        func=mdp.modify_term_cfg,
        params={
            "address": "commands.object_pose.offset_range",
            "modify_fn": mdp.set_offset_range,
            "modify_params": {
                "offset_range": {"z": (-0.1, 0.1)},
                "num_steps": 15_000,
            },
        },
    )

    object_spawn_range_3 = CurrTerm(
        func=mdp.modify_term_cfg,
        params={
            "address": "events.reset_object_position.params.pose_range",
            "modify_fn": mdp.expand_pose_range,
            "modify_params": {
                "pose_range": {"x": (-0.07, 0.07), "y": (-0.07, 0.07), "z": (0.0, 0.0)},
                "num_steps": 35_000,
            },
        },
    )


##
# Environment configuration
##


@configclass
class SoaLabEnvCfg(ManagerBasedRLEnvCfg):
    """Configuration for the lifting environment."""
    
    # Scene settings
    scene: SoaLabSceneCfg = SoaLabSceneCfg(num_envs=4096, env_spacing=2.5)
    # Basic settings
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    commands: CommandsCfg = CommandsCfg()
    # MDP settings
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    events: EventCfg = EventCfg()
    curriculum: CurriculumCfg = CurriculumCfg()

    def __post_init__(self):
        """Post initialization."""
        # general settings
        self.decimation = 2
        self.episode_length_s = 5.0
        self.viewer.eye = (2.5, 2.5, 1.5)
        # simulation settings
        self.sim.dt = 0.01  # 100Hz
        self.sim.render_interval = self.decimation

        self.sim.physx.bounce_threshold_velocity = 0.2
        self.sim.physx.bounce_threshold_velocity = 0.01
        self.sim.physx.gpu_found_lost_aggregate_pairs_capacity = 1024 * 1024 * 4
        self.sim.physx.gpu_total_aggregate_pairs_capacity = 16 * 1024
        self.sim.physx.friction_correlation_distance = 0.00625
