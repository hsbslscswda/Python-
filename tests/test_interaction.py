import math
from dataclasses import replace

import pytest

from mirror_moon.domain import Arm, Event, Features, Shape
from mirror_moon.geometry import OneEuro, angle3, crossing, distance, segment_distance
from mirror_moon.interaction import Engine
from mirror_moon.transport import EventJournal, Latest


def frame(
    t,
    support=(500.0, 300.0),
    cast_shape=Shape.OPEN,
    angle=130.0,
    valid=True,
    support_tracked=True,
    support_hand=True,
    caster=(850.0, 350.0),
    scale=200.0,
):
    arms = (
        Arm("left", (400.0, 250.0), (300.0, 340.0), support, Shape.FIST, support_tracked, support_hand, 95.0),
        Arm("right", (600.0, 250.0), (650.0, 350.0), caster, cast_shape, valid, valid, angle),
    )
    return Features(t, round(t * 1000), 1280, 720, (500.0, 300.0), scale, arms, valid)


def run(engine, start, end, step=0.025, **kwargs):
    states, events = [], []
    for i in range(round((end - start) / step) + 1):
        v, e = engine.update(frame(round(start + i * step, 5), **kwargs))
        states.append(v)
        events.extend(e)
    return states, events


def casting():
    engine = Engine()
    states, _ = run(engine, 0.0, 0.65)
    assert states[-1].state == "CAST"
    return engine


def overdrive():
    engine = casting()
    engine.update(frame(0.70, support=(630.0, 330.0)))
    states, _ = run(engine, 0.725, 1.0, support=(750.0, 350.0))
    assert states[-1].state == "OVERDRIVE"
    return engine


def test_zero_intensity_keeps_summoned_circle():
    engine = casting()
    states, _ = run(engine, 0.7, 3.0, angle=75.0)
    assert states[-1].state == "CAST"
    assert states[-1].visibility == 1.0
    assert states[-1].intensity == 0.0


def test_fist_stop_keeps_ready_circle():
    engine = casting()
    states, _ = run(engine, 0.7, 1.0, cast_shape=Shape.FIST)
    assert states[-1].state == "READY"
    assert states[-1].intensity == 0.0
    assert states[-1].visibility == 1.0


def test_transfer_precedes_leaving_chest_cancellation_and_migrates():
    engine = overdrive()
    states, _ = run(engine, 1.025, 1.5, support=(750.0, 350.0))
    assert states[-1].migration > 0.95
    assert distance(states[-1].center, (850.0, 350.0)) < 1.0


def test_return_to_chest_restores_cast_and_migration():
    engine = overdrive()
    states, _ = run(engine, 1.025, 1.5)
    assert states[-1].state == "CAST"
    assert states[-1].migration < 0.01


def test_releasing_support_restores_normal_cast_with_free_support():
    engine = overdrive()
    states, _ = run(engine, 1.025, 2.2, support=(1000.0, 650.0))
    assert any(s.state == "RETURN" for s in states)
    assert states[-1].state == "CAST"
    assert 0 < states[-1].intensity <= 1.0


def test_stop_during_overdrive_never_continues_output():
    engine = overdrive()
    states, _ = run(engine, 1.025, 1.3, support=(750.0, 350.0), cast_shape=Shape.FIST)
    assert states[-1].state == "READY"
    assert states[-1].intensity == 0.0


def test_missing_support_can_hold_briefly_but_not_forever():
    engine = overdrive()
    states, _ = run(engine, 1.025, 1.15, support=(750.0, 350.0), support_tracked=False, support_hand=False)
    assert states[-1].state == "OVERDRIVE"
    states, _ = run(engine, 1.175, 1.6, support=(750.0, 350.0), support_tracked=False, support_hand=False)
    assert any(s.state == "RETURN" for s in states)
    assert states[-1].state == "CAST" and states[-1].intensity <= 1.0


def test_long_pose_loss_cancels_and_does_not_resummon():
    engine = casting()
    states, _ = run(engine, 0.7, 1.7, valid=False)
    assert states[-1].state == "OFF"
    assert states[-1].intensity == 0.0


def test_depth_loss_fades_without_changing_algorithm():
    engine = casting()
    states, _ = run(engine, 0.7, 2.4, angle=None)
    assert states[0].intensity > 0.0
    assert states[-1].intensity == 0.0
    assert states[-1].visibility == 1.0


def test_duplicate_and_rewound_timestamp_are_safe():
    engine = casting()
    first, _ = engine.update(frame(0.7))
    duplicate, e = engine.update(frame(0.7, valid=False))
    assert duplicate == first and not e
    rewound, e = engine.update(frame(0.1))
    assert rewound.state == "OFF" and not e


def test_mode_switch_clears_input_and_requires_neutral_delay():
    engine = casting()
    view, events = engine.update(frame(0.7), mode="mirror")
    assert view.state == "OFF" and not events
    assert not engine.blade.history
    view, _ = engine.update(frame(0.8), mode="circle")
    assert view.state == "OFF"


def test_left_and_right_roles_are_symmetric_and_remain_locked():
    engine = Engine()
    for i in range(30):
        f = frame(i * 0.025)
        a, b = f.arms
        # Swap anatomical sides, preserving body geometry and intentional support pose.
        f = replace(f, arms=(replace(b, side="left"), replace(a, side="right")))
        view, _ = engine.update(f)
    assert view.support == "right" and view.caster == "left" and view.state == "CAST"


def mirror_frame(t, d, both=True):
    f = frame(t)
    arms = tuple(
        replace(
            a,
            shape=Shape.OPEN,
            wrist=(500.0 + (-1 if i == 0 else 1) * d * 100.0, 300.0),
            hand_valid=both or i == 0,
        )
        for i, a in enumerate(f.arms)
    )
    return replace(f, arms=arms)


def open_mirror():
    engine = Engine()
    engine.mode = "mirror"
    for i in range(11):
        engine.update(mirror_frame(i * 0.025, 0.4))
    for i in range(1, 21):
        view, _ = engine.update(mirror_frame(0.25 + i * 0.025, 1.6))
    assert view.state == "MANIPULATING"
    return engine


def test_slow_mirror_close_does_not_shatter():
    engine = open_mirror()
    events = []
    for i in range(1, 101):
        view, e = engine.update(mirror_frame(0.75 + i * 0.025, 1.6 - i * 0.014))
        events.extend(e)
    for i in range(1, 17):
        view, e = engine.update(mirror_frame(3.25 + i * 0.025, 0.2))
        events.extend(e)
    assert all(e.kind != "shatter" for e in events)
    assert view.state in ("CLOSING", "IDLE")


def test_fast_mirror_close_freezes_exactly_once():
    engine = open_mirror()
    events = []
    for i, d in enumerate((1.5, 1.2, 0.8, 0.3, 0.25, 0.22)):
        _, e = engine.update(mirror_frame(0.8 + i * 0.025, d))
        events.extend(e)
    assert [e.kind for e in events].count("shatter") == 1


def test_missing_hand_never_becomes_a_clap():
    engine = open_mirror()
    events = []
    for i in range(1, 31):
        _, e = engine.update(mirror_frame(0.75 + i * 0.025, 0.1, both=False))
        events.extend(e)
    assert all(e.kind != "shatter" for e in events)


def test_unopened_mirror_cannot_shatter():
    engine = Engine()
    engine.mode = "mirror"
    events = []
    for i, d in enumerate((2.0, 1.5, 0.8, 0.3, 0.2)):
        _, e = engine.update(mirror_frame(i * 0.025, d))
        events.extend(e)
    assert not events


def blade_frame(t, wrist, chest_x=500.0):
    f = frame(t, caster=wrist)
    delta = chest_x - 500.0
    return replace(
        f,
        chest=(chest_x, 300.0),
        arms=tuple(
            replace(
                a,
                shoulder=(a.shoulder[0] + delta, a.shoulder[1]),
                elbow=(a.elbow[0] + delta, a.elbow[1]),
                wrist=(a.wrist[0] + delta, a.wrist[1]),
            )
            for a in f.arms
        ),
    )


def armed_blade():
    engine = Engine()
    engine.mode = "blade"
    for i in range(8):
        view, _ = engine.update(blade_frame(i * 0.025, (400.0, 250.0)))
    assert view.state == "ARMED"
    return engine


def test_intentional_slash_emits_once():
    engine = armed_blade()
    events = []
    for i in range(1, 12):
        _, e = engine.update(blade_frame(0.175 + i * 0.025, (400.0 + i * 22.0, 250.0)))
        events.extend(e)
    assert [e.kind for e in events] == ["slash"]


def test_second_cut_only_becomes_cross_when_actual_segments_intersect():
    engine = armed_blade()
    events = []
    for i in range(1, 10):
        _, e = engine.update(blade_frame(0.175 + i * 0.025, (400.0 + i * 22.0, 250.0)))
        events.extend(e)
    for i in range(1, 13):
        _, e = engine.update(blade_frame(0.4 + i * 0.025, (550.0, 310.0)))
        events.extend(e)
    for i in range(1, 9):
        _, e = engine.update(blade_frame(0.725 + i * 0.025, (550.0 - i * 20.0, 310.0 - i * 20.0)))
        events.extend(e)
    assert [e.kind for e in events] == ["slash", "cross"]


@pytest.mark.parametrize("step", [0.02, 0.033333, 0.05])
def test_transfer_approach_is_time_based_at_different_update_rates(step):
    engine = Engine()
    states = []
    for i in range(round(1.5 / step)):
        t = i * step
        progress = max(0.0, min(1.0, (t - 0.7) / 0.3))
        view, _ = engine.update(frame(t, support=(500.0 + 250.0 * progress, 300.0 + 50.0 * progress)))
        states.append(view.state)
    assert "TRANSFER" in states and states[-1] == "OVERDRIVE"


@pytest.mark.parametrize("scenario", ["stationary", "body_move", "jump", "gap", "wave"])
def test_blade_negative_inputs(scenario):
    engine = armed_blade() if scenario != "wave" else Engine()
    engine.mode = "blade"
    events = []
    for i in range(1, 30):
        t = 0.175 + i * 0.025
        wrist = (400.0 + math.sin(i) * 2.0, 250.0)
        shift = 0.0
        if scenario == "body_move":
            shift = i * 20.0
        elif scenario == "jump":
            wrist = (1100.0, 250.0)
        elif scenario == "gap":
            t += 1.0
            wrist = (900.0, 250.0)
        elif scenario == "wave":
            wrist = (900.0 + math.sin(i) * 60.0, 160.0)
        _, e = engine.update(blade_frame(t, wrist, 500.0 + shift))
        events.extend(e)
    assert not events


def test_parallel_is_not_cross_and_true_cross_is_detected():
    assert not crossing((0, 0), (2, 0), (2, 0), (0, 0))
    assert crossing((0, 0), (2, 2), (0, 2), (2, 0))


def test_geometric_degeneracy_and_filter_reset():
    assert angle3((0, 0, 0), (0, 0, 0), (1, 0, 0)) is None
    assert angle3((-1, 0, 0), (0, 0, 0), (1, 0, 0)) == 180.0
    assert segment_distance((1, 1), (0, 0), (0, 0)) == (math.sqrt(2), -1.0)
    f = OneEuro()
    assert f(10.0, 0.0) == 10.0
    assert f(20.0, 1.0) == 20.0
    assert f(30.0, 0.1) == 30.0


def test_events_survive_overwritten_snapshots_and_acknowledge_once():
    latest, journal = Latest(), EventJournal(2)
    event = Event(1, "slash", 1, 1.0)
    journal.publish(event)
    for i in range(50):
        latest.publish(i)
    assert latest.read()[1] == 49
    assert journal.consume(1.0) == (event,)
    assert journal.consume(1.0) == ()
    journal.publish(replace(event, event_id=2))
    journal.publish(replace(event, event_id=3))
    with pytest.raises(BufferError):
        journal.publish(replace(event, event_id=4))
    assert len(journal.consume(1.0)) == 2


def test_event_expiration_is_counted():
    journal = EventJournal()
    journal.publish(Event(1, "slash", 1, 0.0))
    assert not journal.consume(5.0)
    assert journal.expired == 1


def test_duplicate_events_are_idempotent_at_journal_boundary():
    journal = EventJournal()
    event = Event(1, "slash", 1, 0.0)
    journal.publish(event)
    journal.publish(event)
    assert journal.consume(0.0) == (event,)
    journal.publish(event)
    assert not journal.consume(0.0)


def test_manual_switch_does_not_require_lowered_hands():
    engine = casting()
    engine.update(frame(0.7), mode="blade")
    for i in range(1, 50):
        view, _ = engine.update(frame(0.7 + i * 0.025))
    assert not engine.neutral_required and view.mode == "blade" and view.state == "IDLE"
    for i in range(1, 20):
        f = frame(2.0 + i * 0.025)
        f = replace(f, arms=tuple(replace(a, wrist=(a.wrist[0], 650.0), shape=Shape.OTHER) for a in f.arms))
        engine.update(f)
    assert not engine.neutral_required


def test_occlusion_after_partial_fast_close_never_generates_shatter():
    engine = open_mirror()
    events = []
    # Stop while still separated: new observed-proximity rule may fire before hands touch.
    for i, d in enumerate((1.6, 1.4, 1.1, 0.8)):
        _, e = engine.update(mirror_frame(0.8 + i * 0.025, d))
        events.extend(e)
    for i in range(1, 9):
        _, e = engine.update(mirror_frame(0.875 + i * 0.025, 0.1, both=False))
        events.extend(e)
    assert not any(e.kind == "shatter" for e in events)


@pytest.mark.parametrize("step", [0.02, 0.033333, 0.05])
def test_temporal_sampling_and_resolution_invariance(step):
    engine = Engine()
    for i in range(round(0.7 / step)):
        f = frame(i * step)
        factor = 0.5
        f = replace(
            f,
            width=640,
            height=360,
            chest=(250.0, 150.0),
            scale=100.0,
            arms=tuple(
                replace(
                    a,
                    shoulder=tuple(v * factor for v in a.shoulder),
                    elbow=tuple(v * factor for v in a.elbow),
                    wrist=tuple(v * factor for v in a.wrist),
                )
                for a in f.arms
            ),
        )
        view, _ = engine.update(f)
    assert view.state == "CAST"
