# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Task-specific curriculum callbacks for the soa_lab environment."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from isaaclab.envs.mdp.curriculums import modify_term_cfg

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


def expand_pose_range(
    env: "ManagerBasedRLEnv",
    env_ids: Sequence[int],
    data: dict,
    pose_range: dict,
    num_steps: int,
):
    """Override a `pose_range` dict once training passes `num_steps`.

    Intended as the `modify_fn` of `modify_term_cfg` when the address points
    at an event term's ``params["pose_range"]`` entry.
    """
    if env.common_step_counter > num_steps:
        return pose_range
    return modify_term_cfg.NO_CHANGE


def expand_position_range(
    env: "ManagerBasedRLEnv",
    env_ids: Sequence[int],
    data: tuple[float, float],
    position_range: tuple[float, float],
    num_steps: int,
):
    """Override a tuple-typed ``position_range`` once training passes ``num_steps``.

    Intended as the ``modify_fn`` of ``modify_term_cfg`` when the address points
    at an event term's ``params["position_range"]`` entry that holds a
    ``(min, max)`` tuple (e.g. ``reset_joints_by_offset``). Use one curriculum
    entry per stage to ramp the randomization amplitude upward in steps.
    """
    if env.common_step_counter > num_steps:
        return position_range
    return modify_term_cfg.NO_CHANGE


def set_offset_range(
    env: "ManagerBasedRLEnv",
    env_ids: Sequence[int],
    data: dict,
    offset_range: dict,
    num_steps: int,
):
    """Override an ``offset_range`` dict once training passes ``num_steps``.

    Intended as the `modify_fn` of `modify_term_cfg` when the address points at
    a command term's ``offset_range`` attribute (e.g. randomizing the goal
    height above the tracked object by sampling a z-noise range per env).
    """
    if env.common_step_counter > num_steps:
        return offset_range
    return modify_term_cfg.NO_CHANGE


def set_observation_noise(
    env: "ManagerBasedRLEnv",
    env_ids: Sequence[int],
    data,
    noise,
    num_steps: int,
):
    """Replace an observation term's ``noise`` cfg once training passes ``num_steps``.

    Intended as the ``modify_fn`` of ``modify_term_cfg`` when the address points
    at an observation term's ``noise`` attribute. Use one curriculum entry per
    stage to ramp noise upward in steps.
    """
    if env.common_step_counter > num_steps:
        return noise
    return modify_term_cfg.NO_CHANGE


def set_dr_params(
    env: "ManagerBasedRLEnv",
    env_ids: Sequence[int],
    data: dict,
    params_update: dict,
    num_steps: int,
):
    """Merge ``params_update`` into a target ``params`` dict once training passes ``num_steps``.

    Intended as the ``modify_fn`` of ``modify_term_cfg`` when the address points
    at an event term's full ``params`` dict (e.g.
    ``events.randomize_arm_actuator_gains.params``) and you need to update
    multiple sub-keys at once — for instance, widening stiffness and damping
    distribution ranges together. Other keys (asset_cfg, operation,
    distribution, ...) are preserved.
    """
    if env.common_step_counter > num_steps:
        merged = dict(data)
        merged.update(params_update)
        return merged
    return modify_term_cfg.NO_CHANGE
