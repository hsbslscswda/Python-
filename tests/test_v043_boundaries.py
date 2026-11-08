"""Observed-sequence regressions for the user-authorized v0.4.3 rules."""

from dataclasses import replace

import pytest
from test_interaction import mirror_frame, open_mirror
from test_seated_spells import hand_frame, water_ball

from mirror_moon.domain import Shape
from mirror_moon.fire import Fire


def dropped(t):
    f = mirror_frame(t, 1.0, both=False)
    return replace(
        f,
        arms=tuple(
            replace(
                a,
                hand_valid=False,
                upper_valid=True,
                elbow=(a.shoulder[0], 500.0),
                wrist=(a.shoulder[0], 820.0),
            )
            for a in f.arms
        ),
    )


@pytest.mark.parametrize("kind", ["mirror", "water"])
def test_downward_exit_requires_uninterrupted_observed_030_seconds(kind):
    obj = open_mirror() if kind == "mirror" else water_ball()
    for t in (0.85, 0.95, 1.05):
        obj.update(dropped(t))
    obj.update(mirror_frame(1.10, 1.6))
    for t in (1.15, 1.25, 1.35, 1.44):
        view, _ = obj.update(dropped(t))
        assert view.state not in ("CLOSING", "OFF")
    view, _ = obj.update(dropped(1.46))
    assert view.state in ("CLOSING", "OFF")


@pytest.mark.parametrize("kind", ["mirror", "water"])
def test_unknown_body_does_not_become_a_downward_exit(kind):
    obj = open_mirror() if kind == "mirror" else water_ball()
    for i in range(15):
        view, _ = obj.update(replace(dropped(0.85 + i * 0.1), valid=False))
        assert view.state not in ("CLOSING", "OFF", "IDLE")


@pytest.mark.parametrize("kind", ["mirror", "water"])
def test_missing_input_gap_cannot_finish_downward_exit(kind):
    obj = open_mirror() if kind == "mirror" else water_ball()
    obj.update(dropped(0.85))
    obj.update(dropped(1.0))
    view, _ = obj.update(dropped(3.0))
    assert view.state not in ("CLOSING", "OFF", "IDLE")


def test_partial_fist_pauses_without_erasing_observed_unlock_or_counting_time():
    fire = Fire()
    fire.update(hand_frame(0))
    for i in range(1, 11):
        fire.update(hand_frame(i * 0.1, Shape.FIST, None))
    accumulated = fire.hands["left"].unlock_seconds
    for i in range(11, 22):
        f = hand_frame(i * 0.1, Shape.FIST, None)
        fire.update(replace(f, arms=(replace(f.arms[0], openness=0.28), f.arms[1])))
        assert fire.hands["left"].unlock_seconds == accumulated
        assert not fire.hands["left"].unlocked
    fire.update(hand_frame(2.2, Shape.FIST, None))
    assert fire.hands["left"].unlock_seconds == accumulated
    assert not fire.hands["right"].unlocked


@pytest.mark.parametrize("radius", [0.075, 0.35])
def test_launch_starts_at_exact_levitated_center_after_resizing(radius):
    w = water_ball()
    w.radius = radius
    f = hand_frame(0.6, Shape.OPEN, None, normal=(0, 0, -1))
    view, _ = w.update(f)
    center, scale = w.project(w.position, f)
    center = (center[0], center[1] - max(20.0, radius * scale * 1.25))
    w._launch_orb(f.arms[0], center, scale, f.timestamp)
    projected, _ = w.project(w.shots[-1].position, f)
    assert projected == pytest.approx(center)


def test_other_support_never_changes_single_hand_anchor_or_size():
    w = water_ball()
    radius = w.radius
    for i in range(15):
        f = hand_frame(0.6 + i * 0.05, Shape.OPEN, Shape.OTHER)
        a = replace(f.arms[0], palm=(450, 300), wrist=(450, 300))
        b = replace(f.arms[1], palm=(650 + i * 8, 300), wrist=(650 + i * 8, 300))
        view, events = w.update(replace(f, arms=(a, b)))
        assert view.state == "HELD" and not w.scaling and not events
        assert w.radius == radius


@pytest.mark.parametrize("kind", ["mirror", "water"])
def test_low_but_in_frame_occlusion_is_not_an_out_of_frame_drop(kind):
    obj = open_mirror() if kind == "mirror" else water_ball()
    for i in range(12):
        f = dropped(0.85 + i * 0.05)
        f = replace(f, arms=tuple(replace(a, wrist=(a.wrist[0], 640.0)) for a in f.arms))
        view, _ = obj.update(f)
        assert view.state not in ("CLOSING", "OFF", "IDLE")


def test_water_wide_scaling_never_snaps_to_single_hand_or_oscillates():
    w = water_ball()
    centers_x = []
    for i in range(28):
        t = 0.6 + i * 0.04
        half_span = 60.0 + i * 10.0
        shape_b = Shape.OTHER if i in (10, 11, 18, 19) else Shape.OPEN
        f = hand_frame(t, Shape.OPEN, shape_b, valid=True)
        a = replace(
            f.arms[0],
            palm=(640.0 - half_span, 320.0),
            wrist=(640.0 - half_span, 320.0),
            normal=(1.0, 0.0, 0.0),
            upper_valid=True,
        )
        b = replace(
            f.arms[1],
            palm=(640.0 + half_span, 320.0),
            wrist=(640.0 + half_span, 320.0),
            normal=(-1.0, 0.0, 0.0),
            upper_valid=True,
        )
        view, events = w.update(replace(f, arms=(a, b)))
        assert not any(e[0] == "water_launch" for e in events)
        if i >= 4:
            assert w.scaling and view.state == "SCALING"
            centers_x.append(view.objects[0].center[0])
    assert w.radius > 0.30
    assert all(abs(cx - 640.0) < 48.0 for cx in centers_x[-10:])


def test_water_palm_forward_and_sideways_launch_translate_horizontally():
    w = water_ball()
    for i in range(6):
        t = 0.6 + i * 0.05
        f = hand_frame(t, Shape.OPEN, None, valid=True)
        a = replace(
            f.arms[0],
            shoulder=(420.0, 260.0),
            elbow=(510.0, 300.0),
            wrist=(680.0, 300.0),
            palm=(700.0, 300.0),
            normal=(0.75, -0.10, -0.65),
            upper_valid=True,
            tracked=True,
        )
        bx = 520.0 if i == 0 else 665.0
        b = replace(
            f.arms[1],
            shoulder=(400.0, 265.0),
            elbow=(520.0, 320.0),
            wrist=(bx, 308.0),
            palm=None,
            hand_valid=False,
            upper_valid=True,
            tracked=True,
        )
        _, events = w.update(replace(f, arms=(a, b)))
    assert len(w.shots) == 1
    shot = w.shots[0]
    assert shot.velocity[0] > 2.5
    assert abs(shot.velocity[1]) < 0.45

    w2 = water_ball()
    f0 = hand_frame(0.6, Shape.OPEN, None, valid=True, normal=(0.0, -1.0, 0.0))
    w2.update(f0)
    center, scale = w2.project(w2.position, f0)
    w2._launch_orb(f0.arms[0], center, scale, 0.6, f0)
    shot2 = w2.shots[-1]
    assert abs(shot2.velocity[1]) < 0.45 and (shot2.velocity[0] ** 2 + shot2.velocity[2] ** 2) ** 0.5 > 4.0


def test_water_never_auto_respawns_after_launch_or_relaxed_other_hand():
    w = water_ball()
    f0 = hand_frame(0.6, Shape.OPEN, None, valid=True, normal=(0.0, 0.0, -1.0))
    w.update(f0)
    center, scale = w.project(w.position, f0)
    w._launch_orb(f0.arms[0], center, scale, 0.6, f0)
    assert not w.has_orb

    for t in (0.9, 1.2, 1.6, 2.5, 4.8):
        view, events = w.update(hand_frame(t, Shape.OPEN, None, valid=True))
        assert not w.has_orb
        assert not any(o.kind == 1 for o in view.objects)
        assert not any(e[0] == "water_open" for e in events)

    for t, sh in [(5.2, Shape.FIST), (5.4, Shape.FIST), (5.6, Shape.OTHER), (5.8, Shape.OTHER)]:
        view, events = w.update(hand_frame(t, sh, None, valid=True))
        assert not w.has_orb and not any(e[0] == "water_open" for e in events)

    for t, sh in [(6.0, Shape.FIST), (6.2, Shape.FIST), (6.35, Shape.OPEN), (6.55, Shape.OPEN)]:
        view, events = w.update(hand_frame(t, sh, None, valid=True))
    assert w.enabled and w.has_orb and w.radius == 0.075
    assert any(o.kind == 1 for o in view.objects)


def test_sideways_torso_rotation_produces_frontal_facing_yaw():
    from types import SimpleNamespace as NS

    from test_tracking_and_diagnostics import observations

    from mirror_moon.features import FeatureExtractor

    hands, pose = observations()
    ext = FeatureExtractor()
    frontal = ext.extract(hands, pose, 1280, 720, 0.0, 0)
    assert frontal.body_yaw == 0.0

    for step in range(1, 8):
        hands_s, pose_s = observations()
        ps = pose_s.pose_landmarks[0]
        ws = pose_s.pose_world_landmarks[0]
        ps[11] = NS(**vars(ps[11]))
        ps[12] = NS(**vars(ps[12]))
        ps[0] = NS(**vars(ps[0]))
        ws[11] = NS(**vars(ws[11]))
        ws[12] = NS(**vars(ws[12]))
        ps[11].x = 0.45
        ps[12].x = 0.55
        ps[12].visibility = 0.42
        ps[0].x = 0.43
        ws[11].z = -0.14
        ws[12].z = 0.14
        ws[11].x = -0.09
        ws[12].x = 0.09
        sideways = ext.extract(hands_s, pose_s, 1280, 720, step * 0.05, step)
    assert sideways.body_yaw is not None and sideways.body_yaw > 0.48
