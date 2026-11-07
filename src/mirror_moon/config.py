"""Initial thresholds in seconds, shoulder widths and degrees; require human tuning."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    summon_hold: float = 0.22
    summon_animation: float = 0.15
    cast_hold: float = 0.10
    stop_fist: float = 0.10
    stop_lowered: float = 0.22
    transfer_window: float = 1.1
    grip_hold: float = 0.20
    grip_enter: float = 0.30
    grip_exit: float = 0.43
    lost_grace: float = 0.45
    depth_hold: float = 0.15
    depth_fade: float = 0.25
    fade_time: float = 0.35
    neutral_hold: float = 0.30
    max_gap: float = 0.35
    blade_prepare: float = 0.15
    blade_min_time: float = 0.08
    blade_max_time: float = 0.90
    blade_span: float = 0.48
    blade_speed: float = 1.6
    blade_recovery: float = 0.25
    blade_pose_bridge: float = 0.20
    mirror_seed: float = 0.20
    mirror_min_age: float = 0.35
    mirror_shatter_speed: float = 1.8
    mirror_lost: float = 0.35
    mirror_close_distance: float = 0.28
    mirror_close_hold: float = 0.30
    mirror_geometry_bridge: float = 0.20
    control_hold: float = 0.35
    control_fade: float = 0.50
    gesture_hold: float = 0.15
    fire_unlock: float = 2.0
    fire_unlock_dropout: float = 0.28
    fire_loss_hold: float = 1.0
    fire_loss_fade: float = 0.65
    fire_palm_down: float = 0.45
    gesture_max_age: float = 0.18
    water_palm_offset: float = 0.05
    water_grip_hold: float = 0.18
    water_launch_speed: float = 4.5
    water_spring: float = 65.0
    water_damping: float = 13.0
    water_gravity: float = 1.8
    clap_distance: float = 0.24
    clap_speed: float = 0.9


DEFAULTS = Thresholds()
