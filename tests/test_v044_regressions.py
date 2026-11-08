"""Constructed boundaries, not human gesture-success measurements."""

from dataclasses import replace

import pytest
from test_seated_spells import hand_frame, water_ball

from mirror_moon.domain import Shape


def bracket(t, support=Shape.OPEN, valid=True, unequal_depth=False):
    f = hand_frame(t, Shape.OPEN, support, valid=valid)
    a = replace(f.arms[0], wrist=(400, 320), palm=(400, 320), normal=(1, 0, 0), palm_scale=40)
    b = replace(
        f.arms[1],
        wrist=(800, 320),
        palm=(800, 320),
        normal=(-1, 0, 0),
        palm_scale=80 if unequal_depth else 40,
    )
    return replace(f, arms=(a, b))


def scaling(valid=True, unequal_depth=False):
    w = water_ball()
    for i in range(20):
        w.update(bracket(0.6 + i * 0.04, valid=valid, unequal_depth=unequal_depth))
    assert w.scaling
    return w


def test_other_cannot_renew_the_022_second_resize_grace():
    w = scaling()
    strict_until = w.scaling_grace_until
    for i in range(15):
        w.update(bracket(1.4 + i * 0.04, Shape.OTHER))
    assert w.scaling_grace_until == strict_until
    assert not w.scaling and w.pinch_span is None


def test_short_support_dropout_holds_measured_midpoint_not_owner():
    w = scaling()
    x_before = w.project(w.position, bracket(1.4))[0][0]
    radius = w.radius
    for i in range(4):
        f = bracket(1.4 + i * 0.04)
        a = replace(f.arms[0], wrist=(240, 320), palm=(240, 320))
        b = replace(f.arms[1], hand_valid=False, shape=Shape.UNKNOWN, tracked=False, upper_valid=False)
        w.update(replace(f, arms=(a, b)))
        assert w.scaling and w.radius == radius
    assert abs(w.project(w.position, f)[0][0] - x_before) < 8


def test_hand_only_scaling_is_screen_midpoint_even_with_unequal_palm_depths():
    w = scaling(valid=False, unequal_depth=True)
    for i in range(25):
        f = bracket(1.4 + i * 0.04, valid=False, unequal_depth=True)
        w.update(f)
    assert w.project(w.position, f)[0][0] == pytest.approx(600, abs=3)


def test_reopen_requires_new_post_cooldown_fist_and_fresh_explicit_open():
    w = water_ball()
    f = hand_frame(0.6, Shape.OPEN, None, normal=(0, 0, -1))
    w.update(f)
    center, scale = w.project(w.position, f)
    w._launch_orb(f.arms[0], center, scale, 0.6, f)
    for t, shape in (
        (0.7, Shape.FIST),
        (0.9, Shape.FIST),
        (1.1, Shape.OPEN),
        (1.3, Shape.OPEN),
        (1.5, Shape.OPEN),
    ):
        view, events = w.update(hand_frame(t, shape, None))
        assert not w.has_orb and not any(e[0] == "water_open" for e in events)
    for t in (1.6, 1.8):
        w.update(hand_frame(t, Shape.FIST, None))
    for t in (1.9, 2.1):
        f = hand_frame(t, Shape.OPEN, None)
        f = replace(f, arms=(replace(f.arms[0], openness=0.44), f.arms[1]))
        w.update(f)
        assert not w.has_orb
    # An expired fist cannot summon an orb after an observation gap.
    for t in (4.2, 4.4):
        w.update(hand_frame(t, Shape.OPEN, None))
        assert not w.has_orb


def test_low_confidence_pose_alone_cannot_synthesize_a_wrist_tap():
    w = water_ball()
    for i in range(8):
        f = hand_frame(0.6 + i * 0.05, Shape.OPEN, None, valid=True)
        a = replace(f.arms[0], upper_valid=True, elbow=(400, 300))
        b = replace(
            f.arms[1],
            hand_valid=False,
            upper_valid=True,
            tracked=True,
            wrist_confidence=0.1,
            palm=None,
            wrist=(a.wrist[0] + 4, a.wrist[1]),
        )
        _, events = w.update(replace(f, arms=(a, b)))
        assert not w.shots and not any(e[0] == "water_launch" for e in events)


@pytest.mark.parametrize("sign", [-1, 1])
def test_cold_start_sideways_does_not_poison_frontal_reference(sign):
    from types import SimpleNamespace as NS

    from test_tracking_and_diagnostics import observations

    from mirror_moon.features import FeatureExtractor

    ext = FeatureExtractor()
    for step in range(10):
        hands, pose = observations()
        ps, ws = pose.pose_landmarks[0], pose.pose_world_landmarks[0]
        for idx in (0, 11, 12):
            ps[idx] = NS(**vars(ps[idx]))
        for idx in (11, 12):
            ws[idx] = NS(**vars(ws[idx]))
        ps[11].x, ps[12].x, ps[0].x = 0.45, 0.55, 0.5 - sign * 0.07
        ws[11].x, ws[12].x = -0.09, 0.09
        ws[11].z, ws[12].z = -sign * 0.14, sign * 0.14
        f = ext.extract(hands, pose, 1280, 720, step * 0.05, step)
    assert ext.reference_scale is None
    assert 0.48 < sign * f.body_yaw <= 1.08
