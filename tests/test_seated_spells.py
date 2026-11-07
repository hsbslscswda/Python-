"""Constructed time/landmark cases; these are not human success-rate measurements."""

from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from test_interaction import casting, frame, mirror_frame, open_mirror
from test_tracking_and_diagnostics import observations

from mirror_moon.domain import Shape
from mirror_moon.features import FeatureExtractor
from mirror_moon.fire import Fire
from mirror_moon.interaction import Engine
from mirror_moon.water import Shot, Water


def hand_frame(t, left=Shape.OPEN, right=Shape.OPEN, valid=False, normal=(0.0, -1.0, 0.0)):
    f = frame(t)
    return replace(
        f,
        valid=valid,
        arms=tuple(
            replace(
                a,
                shape=shape,
                palm=a.wrist,
                palm_scale=50,
                normal=normal,
                shape_age=0,
                hand_valid=shape is not None,
                openness=0.0 if shape == Shape.FIST else 1.0,
            )
            for a, shape in zip(f.arms, (left, right))
        ),
    )


def unlocked_fire():
    fire = Fire()
    fire.update(hand_frame(0))
    for i in range(1, 45):
        fire.update(hand_frame(i * 0.05, Shape.FIST, None))
    return fire


def water_ball():
    w = Water()
    for t, shape in [(0, Shape.FIST), (0.2, Shape.FIST), (0.3, Shape.OPEN), (0.5, Shape.OPEN)]:
        view, _ = w.update(hand_frame(t, shape, None))
    assert w.enabled
    return w


def test_fire_requires_full_two_seconds_and_reopen_not_body():
    fire = Fire()
    fire.update(hand_frame(0))
    for i in range(1, 39):
        view, _ = fire.update(hand_frame(i * 0.05, Shape.FIST, None))
        assert view.state == "LOCKED"
    fire.update(hand_frame(2.2, Shape.FIST, None))
    fire.update(hand_frame(2.3, Shape.OPEN, None))
    view, events = fire.update(hand_frame(2.5, Shape.OPEN, None))
    assert view.state == "BURNING" and len(view.objects) == 1
    assert [e[0] for e in events] == ["ignite"]
    _, events = fire.update(hand_frame(2.7, Shape.OPEN, None))
    assert not events


def test_unobserved_time_gap_cannot_count_as_two_seconds_of_fist():
    fire = Fire()
    fire.update(hand_frame(0))
    fire.update(hand_frame(0.2, Shape.FIST, None))
    view, events = fire.update(hand_frame(3, Shape.FIST, None))
    assert view.state == "LOCKED" and not events


def test_fire_loss_is_not_fist_and_reacquisition_keeps_same_flame():
    fire = unlocked_fire()
    fire.update(hand_frame(2.3, Shape.OPEN, None))
    view, _ = fire.update(hand_frame(2.5, Shape.OPEN, None))
    born = fire.hands["left"].born
    view, _ = fire.update(hand_frame(2.8, None, None))
    assert len(view.objects) == 1
    view, events = fire.update(hand_frame(3.0, Shape.UNKNOWN, None))
    assert len(view.objects) == 1 and fire.hands["left"].born == born and not events
    view, _ = fire.update(hand_frame(5.0, None, None))
    assert not view.objects


@pytest.mark.parametrize("shape", [Shape.OTHER, Shape.PINCH, Shape.UNKNOWN])
def test_fire_non_fist_categories_never_extinguish_as_fist(shape):
    fire = unlocked_fire()
    fire.update(hand_frame(2.3, Shape.OPEN, None))
    fire.update(hand_frame(2.5, Shape.OPEN, None))
    for i in range(10):
        view, _ = fire.update(hand_frame(2.6 + i * 0.1, shape, None))
    assert len(view.objects) == 1


def test_fire_down_confirmation_and_independent_two_hands():
    fire = Fire()
    fire.update(hand_frame(0))
    for i in range(1, 46):
        fire.update(hand_frame(i * 0.05, Shape.FIST, Shape.FIST))
    fire.update(hand_frame(2.4))
    view, _ = fire.update(hand_frame(2.6))
    assert len(view.objects) == 2
    f = hand_frame(2.7)
    f = replace(f, arms=(replace(f.arms[0], normal=(0, 1, 0)), f.arms[1]))
    view, _ = fire.update(f)
    assert len(view.objects) == 2
    view, _ = fire.update(replace(f, timestamp=2.9))
    assert len(view.objects) == 1


def test_fire_partial_fist_shrinks_without_treating_it_as_full_fist():
    fire = unlocked_fire()
    fire.update(hand_frame(2.3, Shape.OPEN, None))
    full, _ = fire.update(hand_frame(2.5, Shape.OPEN, None))
    f = hand_frame(2.6, Shape.FIST, None)
    f = replace(f, arms=(replace(f.arms[0], openness=0.4), f.arms[1]))
    fire.update(f)
    view, _ = fire.update(replace(f, timestamp=3.0))
    assert 0 < view.objects[0].radius < full.objects[0].radius


def test_water_any_orientation_survives_long_total_loss_and_frame_gap():
    w = water_ball()
    for t in (1, 3, 10, 100):
        view, events = w.update(hand_frame(t, None, None))
        assert view.visibility == 1 and view.objects and not events


@pytest.mark.parametrize("normal", [(0, -1, 0), (0, 0, -1), (1, 0, 0)])
def test_water_model_places_nearest_edge_five_cm_from_palm_not_center(normal):
    import math

    w = Water()
    f = hand_frame(0, normal=normal)
    a = f.arms[0]
    z = w.camera(f) * 0.08 / a.palm_scale
    palm = ((a.palm[0] - f.width / 2) * z / w.camera(f), (a.palm[1] - f.height / 2) * z / w.camera(f), z)
    assert math.dist(w.target(a, f), palm) - w.radius == pytest.approx(0.05)


def test_water_only_deliberate_clap_ends_session():
    w = water_ball()
    for t, d in [(1, 0.8), (1.1, 0.5), (1.2, 0.15)]:
        f = mirror_frame(t, d)
        f = replace(
            f,
            arms=tuple(
                replace(a, palm=a.wrist, normal=(1 if i == 0 else -1, 0, 0)) for i, a in enumerate(f.arms)
            ),
        )
        view, events = w.update(f)
    assert not w.enabled and view.state == "OFF" and [e[0] for e in events] == ["water_close"]


def test_water_clap_occlusion_requires_preobserved_opposing_approach_and_current_wrists():
    w = water_ball()
    for t, d in [(1, 0.8), (1.1, 0.5), (1.2, 0.1)]:
        f = mirror_frame(t, d)
        f = replace(
            f,
            arms=tuple(
                replace(
                    a,
                    palm=a.wrist,
                    normal=(1 if i == 0 else -1, 0, 0),
                    hand_valid=t < 1.2,
                    upper_valid=True,
                    wrist_confidence=0.9,
                )
                for i, a in enumerate(f.arms)
            ),
        )
        view, events = w.update(f)
    assert view.state == "OFF" and [e[0] for e in events] == ["water_close"]


def test_water_expansion_clears_clap_candidate_before_later_occlusion():
    w = water_ball()
    for t, d in [(1, 0.8), (1.1, 0.5), (1.15, 0.7), (1.2, 0.1)]:
        f = mirror_frame(t, d)
        f = replace(
            f,
            arms=tuple(
                replace(
                    a,
                    palm=a.wrist,
                    normal=(1 if i == 0 else -1, 0, 0),
                    hand_valid=t < 1.2,
                    upper_valid=True,
                    wrist_confidence=0.9,
                )
                for i, a in enumerate(f.arms)
            ),
        )
        _, events = w.update(f)
    assert w.enabled and not events


def test_water_inertia_perspective_and_camera_impact():
    w = water_ball()
    f = hand_frame(0.6, Shape.OPEN, None)
    before = w.position.copy()
    a = replace(f.arms[0], wrist=(800, 300), palm=(800, 300))
    w.update(replace(f, arms=(a, f.arms[1])))
    assert before[0] < w.position[0] < w.target(a, f)[0]
    near = w.project([0, 0, 1], f)[1]
    far = w.project([0, 0, 3], f)[1]
    assert near == pytest.approx(far * 3)
    w.shots = [Shot([0, 0, 0.4], [0, 0, -4], 0.08, 0.6, 1)]
    view, events = w.update(hand_frame(0.7, None, None))
    assert any(o.kind == 3 for o in view.objects) and any(e[0] == "water_hit" for e in events) and w.enabled


def test_water_hits_other_detected_person_estimated_volume_once():
    w = water_ball()
    f = hand_frame(0.6, None, None, valid=True)
    focal = w.camera(f)
    z = focal * 0.4 / 200
    w.shots = [Shot([0, 0, z], [0, 0, 0], 0.08, 0.5, 1)]
    f = replace(f, people=((500, 200, 800, 600, 200),))
    _, events = w.update(f)
    assert [e[0] for e in events] == ["water_hit"]
    _, events = w.update(replace(f, timestamp=0.7))
    assert not events


def test_low_rate_water_trajectory_cannot_tunnel_through_other_person_depth_plane():
    w = water_ball()
    f = hand_frame(0.7, None, None, valid=True)
    z = w.camera(f) * 0.4 / 200
    w.shots = [Shot([0, 0, z + 0.6], [0, 0, -8], 0.08, 0.5, 1)]
    _, events = w.update(replace(f, people=((500, 200, 800, 600, 200),)))
    assert any(e[0] == "water_hit" for e in events)


def test_water_opposed_palms_resize_without_accidental_launch():
    w = water_ball()
    for i in range(20):
        f = hand_frame(0.6 + i * 0.05)
        a = replace(f.arms[0], palm=(450, 300), wrist=(450, 300), normal=(1, 0, 0))
        b = replace(f.arms[1], palm=(550 + i * 4, 300), wrist=(550 + i * 4, 300), normal=(-1, 0, 0))
        view, events = w.update(replace(f, arms=(a, b)))
        assert not any(e[0] == "water_launch" for e in events)
    assert w.enabled and w.radius > 0.10


def test_water_occluded_support_can_finish_observed_grip_with_current_pose():
    w = water_ball()
    f = hand_frame(0.6, valid=True, normal=(0, 0, -1))
    w.update(f)
    for t in (0.7, 0.8, 0.95):
        a = replace(f.arms[0], wrist=(500, 300), palm=(500, 300), upper_valid=True)
        b = replace(f.arms[1], wrist=(490, 300), palm=None, hand_valid=False, upper_valid=True)
        view, events = w.update(replace(f, timestamp=t, arms=(a, b)))
    assert any(e[0] == "water_launch" for e in events) or w.shots


def test_mirror_offscreen_pose_and_total_loss_keep_last_mirror_no_shatter():
    e = open_mirror()
    f = mirror_frame(0.85, 5)
    f = replace(f, arms=tuple(replace(a, hand_valid=False, tracked=False, upper_valid=True) for a in f.arms))
    view, events = e.update(f)
    assert view.visibility == 1 and view.radius > 0 and not events
    f = replace(f, timestamp=30, valid=False, arms=tuple(replace(a, upper_valid=False) for a in f.arms))
    view, events = e.update(f)
    assert view.visibility == 1 and not events
    view, events = e.update(mirror_frame(30.1, 0.3))
    assert not events


def test_hand_only_extraction_and_other_person_owner_continuity():
    hands, pose = observations()
    empty = NS(pose_landmarks=[], pose_world_landmarks=[])
    f = FeatureExtractor().extract(hands, empty, 1280, 720, 0, 0)
    assert not f.valid and all(a.hand_valid and a.palm for a in f.arms)
    assert all(a.source == "HAND_ONLY" for a in f.arms)
    ext = FeatureExtractor()
    ext.extract(hands, pose, 1280, 720, 0, 0)
    second = [NS(**vars(p)) for p in pose.pose_landmarks[0]]
    for p in second:
        p.x += 0.3
    multi = NS(
        pose_landmarks=[second, pose.pose_landmarks[0]],
        pose_world_landmarks=[pose.pose_world_landmarks[0]] * 2,
    )
    f = ext.extract(hands, multi, 1280, 720, 0.1, 1)
    assert len(f.people) == 1 and f.arm("left").hand_valid


def test_neck_height_summon_and_manual_switch_do_not_need_lowered_hands():
    e = Engine()
    for i in range(25):
        view, _ = e.update(frame(i * 0.04, support=(480, 130)))
    assert view.state == "CAST"
    e.update(frame(1.1), mode="water")
    assert not e.neutral_required and not e.water.enabled


def test_horizontal_neck_arm_summons_without_tight_fist_and_partial_palm_casts():
    e = Engine()
    for i in range(30):
        f = frame(i * 0.04, cast_shape=Shape.OTHER, support=(470, 140))
        f = replace(f, arms=(replace(f.arms[0], shape=Shape.OTHER, elbow=(330, 140)), f.arms[1]))
        view, _ = e.update(f)
    assert view.state == "CAST" and view.intensity > 0


def test_long_capture_gap_cannot_create_grip_but_keeps_circle():
    e = casting()
    view, events = e.update(frame(8, support=(750, 350)))
    assert view.state == "CAST" and not events and not e.neutral_required


def test_water_pause_freezes_instead_of_ending_and_fire_reset_clears():
    e = Engine()
    e.mode = "water"
    e.water = water_ball()
    e.view = e.water.update(hand_frame(0.6, None, None))[0]
    before = list(e.water.position)
    e.update(hand_frame(100, None, None), paused=True)
    assert e.water.enabled and e.water.position == before and e.view.visibility == 1
    e.update(hand_frame(101, None, None), cancel=True)
    assert not e.water.enabled
    e.fire = unlocked_fire()
    e.mode = "fire"
    e.update(hand_frame(102), paused=True)
    assert not e.fire.hands["left"].unlocked


def test_water_lowered_support_does_not_resize_or_end_session():
    w = water_ball()
    for i in range(6):
        f = hand_frame(0.6 + i * 0.05, valid=True)
        a = replace(f.arms[0], palm=(450, 300), wrist=(450, 300), normal=(1, 0, 0), upper_valid=True)
        b = replace(f.arms[1], palm=(620, 300), wrist=(620, 300), normal=(-1, 0, 0), upper_valid=True)
        w.update(replace(f, arms=(a, b)))
    locked_radius = w.radius
    for i in range(1, 10):
        f = hand_frame(0.9 + i * 0.05, valid=True)
        a = replace(f.arms[0], palm=(450, 300), wrist=(450, 300), normal=(1, 0, 0), upper_valid=True)
        b = replace(
            f.arms[1],
            shoulder=(620, 200),
            palm=(620, 640),
            wrist=(620, 640),
            elbow=(620, 420),
            normal=(-1, 0, 0),
            upper_valid=True,
        )
        w.update(replace(f, arms=(a, b)))
    assert abs(w.radius - locked_radius) < 0.015
    assert w.enabled and not w.shots


def test_water_wrist_tap_with_perpendicular_normal_launches():
    w = water_ball()
    for i, x in enumerate((650, 500, 495, 495, 495)):
        f = hand_frame(0.6 + i * 0.06, valid=True)
        a = replace(f.arms[0], wrist=(480, 300), palm=(480, 300), normal=(0, 0, -1), upper_valid=True)
        b = replace(f.arms[1], wrist=(x, 300), palm=(x, 300), normal=(-1, 0, 0), upper_valid=True)
        _, events = w.update(replace(f, arms=(a, b)))
    assert w.shots


def test_fire_short_dropout_preserves_two_second_fist_unlock():
    fire = Fire()
    fire.update(hand_frame(0))
    for i in range(1, 28):
        fire.update(hand_frame(i * 0.05, Shape.FIST, None))
    fire.update(hand_frame(1.45, None, None))
    fire.update(hand_frame(1.50, None, None))
    for i in range(31, 48):
        fire.update(hand_frame(i * 0.05, Shape.FIST, None))
    assert fire.hands["left"].unlocked


def test_mirror_lowered_arms_without_hands_preserves_session():
    e = open_mirror()
    for i in range(1, 10):
        f = mirror_frame(0.85 + i * 0.05, 1.5, both=False)
        arms = tuple(
            replace(
                a,
                hand_valid=False,
                upper_valid=True,
                elbow=(a.shoulder[0], 390.0),
                wrist=(a.shoulder[0], 640.0),
            )
            for a in f.arms
        )
        view, _ = e.update(replace(f, valid=True, arms=arms))
    assert view.state not in ("CLOSING", "SHATTER", "IDLE")
    assert view.visibility == 1 and not _


def test_water_body_only_lowered_arms_cannot_end_session():
    w = water_ball()
    for i in range(12):
        f = hand_frame(0.6 + i * 0.1, None, None, valid=True)
        arms = tuple(
            replace(
                a,
                shoulder=(a.wrist[0], 200),
                elbow=(a.wrist[0], 420),
                wrist=(a.wrist[0], 640),
                upper_valid=True,
            )
            for a in f.arms
        )
        view, events = w.update(replace(f, arms=arms))
        assert w.enabled and view.visibility == 1 and not events


def test_water_owner_loss_does_not_transfer_ball_to_other_hand():
    w = water_ball()
    view, events = w.update(hand_frame(0.6, None, Shape.OPEN))
    assert w.owner == view.caster == "left" and not events


def test_water_single_hand_fast_move_is_not_an_unrequested_launch_gesture():
    w = water_ball()
    for t, x in [(0.8, 450), (1.0, 450), (1.05, 900), (1.10, 450)]:
        f = hand_frame(t, Shape.OPEN, None, normal=(0, 0, -1))
        a = replace(f.arms[0], palm=(x, 300), wrist=(x, 300))
        _, events = w.update(replace(f, arms=(a, f.arms[1])))
        assert not w.shots and not events


def test_water_slow_opposed_palms_do_not_launch_instead_of_resizing():
    w = water_ball()
    spans = list(range(160, 49, -10)) + [50] * 6
    for i, span in enumerate(spans):
        f = hand_frame(0.6 + i * 0.1)
        a = replace(f.arms[0], palm=(450, 300), wrist=(450, 300), normal=(1, 0, 0))
        b = replace(f.arms[1], palm=(450 + span, 300), wrist=(450 + span, 300), normal=(-1, 0, 0))
        _, events = w.update(replace(f, arms=(a, b)))
        assert not w.shots and not events and w.enabled


@pytest.mark.parametrize("unknown", [None, Shape.UNKNOWN])
def test_fire_unlock_pauses_uncertain_samples_without_counting_recovery_gap(unknown):
    fire = Fire()
    fire.update(hand_frame(0))
    for i in range(1, 11):
        fire.update(hand_frame(i * 0.1, Shape.FIST, None))
    fire.update(hand_frame(1.1, unknown, None))
    fire.update(hand_frame(1.2, unknown, None))
    for i in range(11):
        _, events = fire.update(hand_frame(1.25 + i * 0.1, Shape.FIST, None))
        assert not fire.hands["left"].unlocked and not events
    _, events = fire.update(hand_frame(2.35, Shape.FIST, None))
    assert fire.hands["left"].unlocked and [e[0] for e in events] == ["fire_unlock"]
    _, events = fire.update(hand_frame(2.45, Shape.FIST, None))
    assert not events
