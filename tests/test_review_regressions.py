"""Synthetic reproductions of the review's verifiable conditions, not human validation."""

from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from test_interaction import armed_blade, blade_frame, casting, frame, mirror_frame, open_mirror
from test_tracking_and_diagnostics import observations

from mirror_moon.control import IntensityController, fit_calibration
from mirror_moon.features import FeatureExtractor
from mirror_moon.mirror_texture import mirror_texture


def test_unknown_low_confidence_arm_cannot_steal_the_only_hand():
    hands, pose = observations(only_right=True)
    pose.pose_landmarks[0][15].visibility = 0.1
    pose.pose_landmarks[0][16].x = 750 / 1280
    f = FeatureExtractor().extract(hands, pose, 1280, 720, 0.0, 0)
    assert f.arm("right").hand_valid and not f.arm("left").hand_valid


def test_recent_single_hand_identity_survives_pose_and_category_uncertainty():
    e = FeatureExtractor()
    hands, pose = observations(only_right=True)
    e.extract(hands, pose, 1280, 720, 0.0, 0)
    hands.handedness = [[NS(category_name="Left", score=0.9)]]
    for i in (15, 16):
        pose.pose_landmarks[0][i].visibility = 0.1
    f = e.extract(hands, pose, 1280, 720, 0.08, 1)
    assert f.arm("right").hand_valid and not f.arm("left").hand_valid


def test_small_mirror_can_expand_again_without_instant_close():
    e = open_mirror()
    # Slow changes never reach a shatter velocity.
    t = 0.75
    for i in range(1, 27):
        t += 0.08
        e.update(mirror_frame(t, 1.6 - i * 0.05))
    view, events = e.update(mirror_frame(t + 0.08, 0.26))
    assert view.state == "MANIPULATING" and not events
    view, events = e.update(mirror_frame(t + 0.16, 0.45))
    assert view.state == "MANIPULATING" and not events


def test_mirror_can_rotate_continuously_beyond_ninety_degrees():
    import math

    e = open_mirror()
    for i in range(1, 14):
        angle = math.radians(i * 10)
        f = mirror_frame(0.75 + i * 0.08, 1.4)
        arms = tuple(
            replace(a, wrist=(500 + sign * 140 * math.cos(angle), 300 + sign * 140 * math.sin(angle)))
            for a, sign in zip(f.arms, (-1, 1))
        )
        view, _ = e.update(replace(f, arms=arms))
    assert view.mirror_angle > math.pi / 2


def test_short_reliable_pose_bridge_preserves_blade_origin_but_requires_hand_return():
    e = armed_blade()
    f = blade_frame(0.26, (450.0, 250.0))
    f = replace(f, arms=(f.arms[0], replace(f.arms[1], hand_valid=False)))
    _, events = e.update(f)
    assert not events
    _, events = e.update(blade_frame(0.36, (550.0, 250.0)))
    assert [x.kind for x in events] == ["slash"]


def test_transfer_has_partial_visual_migration_before_confirmation():
    e = casting()
    for t, support in ((0.7, (630.0, 330.0)), (0.8, (720.0, 350.0))):
        e.update(frame(t, support=support))
    view, _ = e.update(frame(0.85, support=(730.0, 350.0)))
    assert view.state == "TRANSFER" and 0.0 < view.migration < 1.0


def test_pose_only_blade_motion_never_emits_even_when_tracking_is_confident():
    e = armed_blade()
    for i in range(1, 10):
        f = blade_frame(0.175 + i * 0.05, (400.0 + i * 40.0, 250.0))
        f = replace(f, arms=(f.arms[0], replace(f.arms[1], hand_valid=False)))
        _, events = e.update(f)
        assert not events


def test_expanding_mirror_cannot_reuse_previous_closing_peak():
    e = open_mirror()
    for t, d in ((0.85, 1.6), (0.95, 1.1), (1.05, 0.75), (1.15, 0.82), (1.25, 0.85)):
        _, events = e.update(mirror_frame(t, d))
        assert not events


def test_compressed_personal_calibration_is_accepted_only_when_stable():
    endpoints = fit_calibration([100.0] * 15, [121.0] * 15)
    assert endpoints == (100.0, 121.0)
    c = IntensityController()
    for i in range(20):
        c.update(121.0, i * 0.07, *endpoints)
    assert c.value == 1.0
    assert fit_calibration([80.0, 120.0] * 8, [101.0, 141.0] * 8) is None
    assert fit_calibration([100.0] * 6, [121.0] * 6) is None


def test_uncalibrated_120_degrees_is_not_declared_fully_extended():
    c = IntensityController()
    for i in range(30):
        c.update(120.0, i * 0.07)
    assert 0.0 < c.value < 1.0


def test_frozen_folded_image_is_bounded_independent_and_keeps_its_pattern():
    import numpy as np

    y, x = np.mgrid[:180, :320]
    rgb = np.stack((x % 256, y % 256, (x + y) % 256), axis=-1).astype("uint8")
    normal = mirror_texture(rgb, (160.0, 90.0), 60.0, 0.4, False, 100.0, 10.0)
    folded = mirror_texture(rgb, (160.0, 90.0), 60.0, 0.4, True, 100.0, 10.0)
    before = folded.copy()
    assert not np.array_equal(normal, folded)
    rgb[:] = 0
    assert np.array_equal(before, folded) and not folded.flags.writeable
    large = mirror_texture(rgb, (160.0, 90.0), 2000.0, 0.0, True, 100.0, 10.0)
    assert large.shape[0] <= 768 and large.shape[1] <= 1024


def test_screen_translation_is_not_body_yaw():
    hands, pose = observations()
    first = FeatureExtractor().extract(hands, pose, 1280, 720, 0.0, 0)
    for p in pose.pose_landmarks[0]:
        p.x += 0.05
    second = FeatureExtractor().extract(hands, pose, 1280, 720, 0.07, 1)
    assert first.body_yaw == second.body_yaw == 0.0


def test_unobserved_low_confidence_arm_is_not_a_tracked_skeleton_ghost():
    hands, pose = observations(only_right=True)
    pose.pose_landmarks[0][15] = NS(**vars(pose.pose_landmarks[0][16]))
    pose.pose_landmarks[0][15].visibility = 0.26
    f = FeatureExtractor().extract(hands, pose, 1280, 720, 0.0, 0)
    assert not f.arm("left").tracked and f.arm("right").hand_valid


@pytest.mark.parametrize("step", [1 / 30, 1 / 15, 1 / 10])
def test_demo_mirror_reset_and_second_prepare_survive_sampling_phase(step):
    from mirror_moon.demo import sample
    from mirror_moon.interaction import Engine

    e = Engine()
    states, events = set(), []
    for i in range(int(12 / step)):
        elapsed = step * 0.4 + i * step
        _, f = sample(elapsed, 100 + elapsed, i, "mirror")
        view, emitted = e.update(f, "mirror")
        states.add(view.state)
        events.extend(emitted)
    assert "CLOSING" in states and "FOLDING" in states
    assert [e.kind for e in events].count("mirror_open") >= 2
    assert [e.kind for e in events].count("shatter") == 1


def test_shatter_event_retains_folded_image_mapping_and_body_scale():
    import math

    e = open_mirror()
    for i in range(1, 8):
        f = mirror_frame(0.75 + i * 0.08, 1.6)
        f = replace(
            f,
            arms=tuple(
                replace(a, wrist=(500 + sign * 160 * math.cos(0.7), 300 + sign * 160 * math.sin(0.7)))
                for a, sign in zip(f.arms, (-1, 1))
            ),
        )
        view, _ = e.update(f)
    assert view.folded
    events = []
    for t, d in ((1.39, 1.5), (1.47, 1.1), (1.55, 0.6)):
        _, emitted = e.update(mirror_frame(t, d))
        events.extend(emitted)
    assert len(events) == 1 and events[0].folded and events[0].body_scale == 200.0


@pytest.mark.parametrize("hz", [10, 60])
def test_slow_grip_approach_history_covers_seconds_at_both_input_rates(hz):
    e = casting()
    for i in range(int(3 * hz)):
        t = 0.7 + i / hz
        y = 254.0 + min(2.2, i / hz) * 20.0
        view, _ = e.update(frame(t, support=(750.0, y)))
    assert view.state == "OVERDRIVE"


@pytest.mark.parametrize("hz", [15, 240])
def test_blade_motion_span_does_not_disappear_into_a_fixed_frame_cap(hz):
    e = armed_blade()
    events = []
    for i in range(1, int(0.4 * hz) + 1):
        elapsed = i / hz
        _, emitted = e.update(blade_frame(0.175 + elapsed, (400.0 + 340.0 * elapsed, 250.0)))
        events.extend(emitted)
    assert [x.kind for x in events] == ["slash"]
