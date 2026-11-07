"""Synthetic acceptance for the explicitly requested v0.3.1 tuning, not human results."""

from dataclasses import replace

from test_interaction import casting, frame, mirror_frame, open_mirror, overdrive

from mirror_moon.control import IntensityController
from mirror_moon.domain import Shape
from mirror_moon.pipeline import Controls


def test_requested_134_default_reaches_full_strength_in_controller_and_session():
    controller, engine = IntensityController(), casting()
    for i in range(40):
        t = 0.7 + i * 0.05
        value = controller.update(134.0, t)
        view, _ = engine.update(frame(t, angle=134.0))
    assert Controls().extended == 134.0
    assert value == view.intensity == 1.0 and view.state == "CAST"


def test_raised_pose_caster_and_body_translation_keep_overdrive_then_total_loss_stops():
    engine = overdrive()
    for i in range(80):
        t, dx, dy = 1.025 + i * 0.05, i * 1.5, i * 0.3
        f = frame(t, angle=134.0, support=(750.0, 350.0))
        arms = tuple(
            replace(
                a,
                shoulder=(a.shoulder[0] + dx, a.shoulder[1] + dy),
                elbow=(a.elbow[0] + dx, a.elbow[1] + dy),
                wrist=(a.wrist[0] + dx, a.wrist[1] + dy),
                hand_valid=a.side == "left",
                shape=a.shape if a.side == "left" else Shape.UNKNOWN,
            )
            for a in f.arms
        )
        view, _ = engine.update(replace(f, chest=(500.0 + dx, 300.0 + dy), arms=arms))
        assert view.state == "OVERDRIVE"
    assert view.intensity > 1.0
    for i in range(1, 30):
        view, _ = engine.update(frame(t + i * 0.05, valid=False))
    assert view.state == "OFF" and view.intensity == 0.0


def test_open_mirror_survives_six_tenths_of_reliable_pose_geometry():
    engine = open_mirror()
    for i in range(1, 13):
        f = mirror_frame(0.75 + i * 0.05, 1.6)
        f = replace(f, arms=(f.arms[0], replace(f.arms[1], hand_valid=False, shape=Shape.UNKNOWN)))
        view, events = engine.update(f)
        assert view.state == "MANIPULATING" and not events
    view, events = engine.update(mirror_frame(1.40, 1.6))
    assert view.state == "MANIPULATING" and not events


def test_requested_moderate_visible_closing_speed_shatters_before_palms_overlap():
    engine, events = open_mirror(), []
    for i in range(12):
        view, emitted = engine.update(mirror_frame(0.8 + i * 0.06, 1.6 - 1.5 * i * 0.06))
        events.extend(emitted)
    assert [e.kind for e in events] == ["shatter"] and view.state == "SHATTER"


def test_same_moderate_close_with_unseen_hand_never_shatters():
    engine, events = open_mirror(), []
    for i in range(12):
        _, emitted = engine.update(mirror_frame(0.8 + i * 0.06, 1.6 - 1.5 * i * 0.06, both=False))
        events.extend(emitted)
    assert not any(e.kind == "shatter" for e in events)
