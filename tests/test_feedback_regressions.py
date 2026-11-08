"""Regressions from v0.1.1 user feedback. Constructed observations, not human acceptance."""

import math
from dataclasses import replace

import pytest
from test_interaction import armed_blade, blade_frame, casting, frame, mirror_frame, open_mirror, run
from test_tracking_and_diagnostics import hand, observations

from mirror_moon.control import IntensityController
from mirror_moon.domain import Shape
from mirror_moon.features import FeatureExtractor
from mirror_moon.geometry import blade_combo


def test_support_is_free_after_first_cast_and_lowering_caster_ends_session():
    engine = casting()
    states, _ = run(engine, 0.7, 2.0, support=(300.0, 650.0))
    assert states[-1].state == "CAST" and states[-1].intensity > 0
    states, _ = run(engine, 2.025, 3.0, support=(300.0, 650.0), caster=(850.0, 650.0))
    assert states[-1].state == "OFF" and states[-1].visibility == 0


def test_grip_recent_hand_then_pose_only_can_complete_and_boost_above_100():
    engine = casting()
    engine.update(frame(0.70, support=(630.0, 330.0)))
    engine.update(frame(0.80, support=(750.0, 350.0)))
    states, events = run(engine, 0.85, 1.15, support=(750.0, 350.0), support_hand=False)
    assert states[-1].state == "OVERDRIVE" and states[-1].intensity > 1.0
    assert [e.kind for e in events] == ["overdrive"]


def test_unseen_support_cannot_create_new_grip():
    engine = casting()
    run(engine, 0.70, 1.5, support=(300.0, 550.0), support_hand=False)
    states, events = run(engine, 1.525, 2.2, support=(750.0, 350.0), support_hand=False)
    assert all(s.state != "OVERDRIVE" for s in states) and not events


def test_long_unrecognized_cast_hand_stops_output_but_keeps_ring():
    engine = casting()
    states, _ = run(engine, 0.7, 2.0, cast_shape=Shape.UNKNOWN)
    assert states[-1].state == "READY"
    assert states[-1].intensity == 0.0 and states[-1].visibility == 1.0


def test_no_frame_gap_cannot_resume_or_create_grip_on_first_reacquisition():
    engine = casting()
    view, events = engine.update(frame(2.0, support=(750.0, 350.0)))
    assert view.state == "CAST" and view.intensity <= 1.0 and not events
    assert not engine.neutral_required


def test_foreshortened_forearm_can_confirm_only_after_observed_approach():
    engine = casting()
    views = []
    for i in range(24):
        t = 0.7 + i * 0.05
        progress = min(1.0, i / 7)
        f = frame(t, support=(500.0 + progress * 330.0, 300.0 + progress * 50.0))
        f = replace(f, arms=(f.arms[0], replace(f.arms[1], elbow=(830.0, 350.0))))
        view, _ = engine.update(f)
        views.append(view)
    assert views[-1].state == "OVERDRIVE" and views[-1].intensity > 1.0


def test_neutral_works_with_hands_out_of_image_and_observed_lower_elbows():
    engine = casting()
    engine.update(frame(0.7), mode="blade")
    for i in range(16):
        f = frame(0.75 + i * 0.05)
        f = replace(
            f,
            arms=tuple(
                replace(
                    a,
                    elbow=(a.elbow[0], 470.0),
                    wrist=(a.wrist[0], 800.0),
                    hand_valid=False,
                    shape=Shape.UNKNOWN,
                )
                for a in f.arms
            ),
        )
        engine.update(f)
    assert not engine.neutral_required


def test_close_distinct_hands_are_not_globally_suppressed():
    extractor = FeatureExtractor()
    hands, pose = observations()
    for index, x in enumerate((610.0, 670.0)):
        hands.hand_landmarks[index] = hand(x, 400.0, 1280, 720)
        pose.pose_landmarks[0][15 + index].x = x / 1280
    f = extractor.extract(hands, pose, 1280, 720, 0.0, 0)
    assert all(a.hand_valid for a in f.arms)


def test_weak_pose_elbow_does_not_discard_observed_hand():
    hands, pose = observations()
    pose.pose_landmarks[0][13].visibility = 0.1
    f = FeatureExtractor().extract(hands, pose, 1280, 720, 0.0, 0)
    assert f.arm("left").hand_valid and f.arm("left").angle is None


def test_intensity_rejects_single_spike_limits_jitter_and_tracks_a_real_step():
    c = IntensityController()
    for i in range(20):
        c.update(110.0, i * 0.1)
    before = c.value
    spike = c.update(179.0, 2.0)
    assert abs(spike - before) < 0.03
    values = [c.update(110.0 + math.sin(i) * 8.0, 2.1 + i * 0.1) for i in range(20)]
    assert max(values) - min(values) < 0.12
    for i in range(15):
        c.update(170.0, 4.1 + i * 0.1)
    assert c.value > 0.95
    for i in range(15):
        c.update(None, 5.6 + i * 0.1)
    assert c.value == 0 and not c.reliable


def test_each_caster_uses_its_own_calibration_and_reset_preserves_it():
    engine = casting()
    engine.circle.profiles = {"right": (100.0, 135.0), "left": (65.0, 175.0)}
    states, _ = run(engine, 0.7, 2.0, angle=140.0)
    assert states[-1].intensity > 0.98
    engine.reset(2.1)
    assert engine.circle.profiles["left"] == (65.0, 175.0)


@pytest.mark.parametrize("step", [0.10, 0.13, 0.16])
def test_held_arming_is_stable_then_real_low_rate_swing_emits_once(step):
    engine = armed_blade()
    for i in range(15):
        view, events = engine.update(blade_frame(0.3 + i * step, (400.0, 250.0)))
        assert view.state == "ARMED" and not events
    start = 0.3 + 14 * step
    events = []
    for i in range(1, 5):
        _, emitted = engine.update(blade_frame(start + i * step, (400.0 + i * 90.0, 250.0)))
        events.extend(emitted)
    assert [e.kind for e in events] == ["slash"]


def test_blade_reacquisition_cannot_bridge_a_missing_hand():
    engine = armed_blade()
    missing = blade_frame(0.25, (420.0, 250.0))
    missing = replace(missing, arms=tuple(replace(a, hand_valid=False) for a in missing.arms))
    engine.update(missing)
    for i in range(8):
        _, events = engine.update(blade_frame(0.35 + i * 0.05, (700.0, 250.0)))
        assert not events


def test_observed_fast_close_can_shatter_while_hands_still_separated():
    engine = open_mirror()
    events = []
    for t, d in ((0.9, 1.6), (1.03, 1.25), (1.16, 0.60)):
        _, emitted = engine.update(mirror_frame(t, d))
        events.extend(emitted)
    assert [e.kind for e in events] == ["shatter"]


def test_reacquired_mirror_hand_jump_has_no_closing_velocity():
    engine = open_mirror()
    engine.update(mirror_frame(0.80, 1.6))
    engine.update(mirror_frame(0.9, 0.6, both=False))
    _, events = engine.update(mirror_frame(1.0, 0.6))
    assert not events


@pytest.mark.parametrize(
    "segment,expected",
    [
        (((2.0, 1.0), (0.0, 1.0)), "double"),
        (((0.0, 1.0), (2.0, 1.0)), "slash"),
        (((3.0, 0.0), (3.0, 2.0)), "slash"),
        (((1.0, -1.0), (1.0, 1.0)), "cross"),
    ],
)
def test_combo_requires_reverse_parallel_or_actual_intersection(segment, expected):
    assert blade_combo((0.0, 0.0), (2.0, 0.0), *segment) == expected
