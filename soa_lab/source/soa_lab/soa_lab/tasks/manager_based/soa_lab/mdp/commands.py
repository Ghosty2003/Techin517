from __future__ import annotations

from collections.abc import Sequence
from dataclasses import MISSING, field
from typing import TYPE_CHECKING

import torch

from isaaclab.assets import Articulation, RigidObject
from isaaclab.managers import CommandTerm, CommandTermCfg
from isaaclab.markers import VisualizationMarkers, VisualizationMarkersCfg
from isaaclab.markers.config import POSITION_GOAL_MARKER_CFG
from isaaclab.utils import configclass
from isaaclab.utils.math import combine_frame_transforms, sample_uniform, subtract_frame_transforms

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedEnv


class ObjectRelativePoseCommand(CommandTerm):
    """3-DOF position goal in the robot base frame.

    Goal = object position at the most recent resample + a fixed body-frame offset.
    There is no orientation component; the command is a pure position target.
    """

    cfg: "ObjectRelativePoseCommandCfg"

    def __init__(self, cfg: "ObjectRelativePoseCommandCfg", env: "ManagerBasedEnv"):
        super().__init__(cfg, env)

        self.robot: Articulation = env.scene[cfg.asset_name]
        self.body_idx = self.robot.find_bodies(cfg.body_name)[0][0]
        self.object: RigidObject = env.scene[cfg.object_name]

        self.pos_command_b = torch.zeros(self.num_envs, 3, device=self.device)
        self.pos_command_w = torch.zeros_like(self.pos_command_b)

        self.metrics["position_error"] = torch.zeros(self.num_envs, device=self.device)

    def __str__(self) -> str:
        msg = "ObjectRelativePoseCommand:\n"
        msg += f"\tCommand dimension: {tuple(self.command.shape[1:])}\n"
        msg += f"\tResampling time range: {self.cfg.resampling_time_range}\n"
        return msg

    @property
    def command(self) -> torch.Tensor:
        """The desired position command in the robot base frame. Shape is (num_envs, 3)."""
        return self.pos_command_b

    def _resample_command(self, env_ids: Sequence[int]):
        obj_pos_w = self.object.data.root_pos_w[env_ids, :3]
        root_pos_w = self.robot.data.root_state_w[env_ids, :3]
        root_quat_w = self.robot.data.root_state_w[env_ids, 3:7]
        obj_pos_b, _ = subtract_frame_transforms(root_pos_w, root_quat_w, obj_pos_w)
        offset_b = torch.as_tensor(self.cfg.offset, device=self.device, dtype=torch.float32)
        # per-env uniform noise from cfg.offset_range (missing axes -> no noise)
        range_list = [self.cfg.offset_range.get(k, (0.0, 0.0)) for k in ("x", "y", "z")]
        ranges = torch.tensor(range_list, device=self.device, dtype=torch.float32)
        noise = sample_uniform(ranges[:, 0], ranges[:, 1], (len(env_ids), 3), device=self.device)
        self.pos_command_b[env_ids] = obj_pos_b + offset_b + noise

    def _update_metrics(self):
        self.pos_command_w[:], _ = combine_frame_transforms(
            self.robot.data.root_pos_w,
            self.robot.data.root_quat_w,
            self.pos_command_b,
        )
        self.metrics["position_error"] = torch.norm(
            self.pos_command_w - self.robot.data.body_pos_w[:, self.body_idx], dim=-1
        )

    def _update_command(self):
        pass

    def _set_debug_vis_impl(self, debug_vis: bool):
        if debug_vis:
            if not hasattr(self, "goal_pose_visualizer"):
                self.goal_pose_visualizer = VisualizationMarkers(self.cfg.goal_pose_visualizer_cfg)
                self.current_pose_visualizer = VisualizationMarkers(self.cfg.current_pose_visualizer_cfg)
            self.goal_pose_visualizer.set_visibility(True)
            self.current_pose_visualizer.set_visibility(True)
        else:
            if hasattr(self, "goal_pose_visualizer"):
                self.goal_pose_visualizer.set_visibility(False)
                self.current_pose_visualizer.set_visibility(False)

    def _debug_vis_callback(self, event):
        if not self.robot.is_initialized:
            return
        self.goal_pose_visualizer.visualize(translations=self.pos_command_w)
        body_pos_w = self.robot.data.body_pos_w[:, self.body_idx]
        self.current_pose_visualizer.visualize(translations=body_pos_w)


@configclass
class ObjectRelativePoseCommandCfg(CommandTermCfg):
    """Config for :class:`ObjectRelativePoseCommand`."""

    class_type: type = ObjectRelativePoseCommand

    asset_name: str = MISSING
    """Robot scene entity name (used to resolve base frame and body)."""

    body_name: str = MISSING
    """Body name within the robot (used for the position-error metric and current-pose marker)."""

    object_name: str = MISSING
    """Scene entity name of the object whose position is tracked at each resample."""

    offset: tuple[float, float, float] = (0.0, 0.0, 0.1)
    """Offset added to the object's position, in the robot base frame (meters)."""

    offset_range: dict[str, tuple[float, float]] = field(default_factory=dict)
    """Per-axis uniform noise added to ``offset`` on each resample. Keys: 'x', 'y', 'z'.
    Missing keys default to (0.0, 0.0) — no noise on that axis. Sampled per-env per-resample."""

    goal_pose_visualizer_cfg: VisualizationMarkersCfg = POSITION_GOAL_MARKER_CFG.replace(
        prim_path="/Visuals/Command/goal_position"
    )
    current_pose_visualizer_cfg: VisualizationMarkersCfg = POSITION_GOAL_MARKER_CFG.replace(
        prim_path="/Visuals/Command/body_position"
    )
