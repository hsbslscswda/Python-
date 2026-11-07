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


DEFAULTS = Thresholds()
