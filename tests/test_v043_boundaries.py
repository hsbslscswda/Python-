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
