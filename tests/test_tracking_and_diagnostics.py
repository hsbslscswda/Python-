import json
from dataclasses import asdict
from types import SimpleNamespace as NS

import pytest

from mirror_moon.diagnostics import Recorder, decode_features
from mirror_moon.domain import Shape
from mirror_moon.tracking import FeatureExtractor, classify


def hand(cx, cy, width, height, folded=False):
    points = [(cx, cy)] * 21
    for x, base, joint, tip in ((-30, 5, 6, 8), (-10, 9, 10, 12), (10, 13, 14, 16), (30, 17, 18, 20)):
        points[base] = (cx + x, cy - 40)
        points[joint] = (cx + x, cy - 65)
        points[tip] = (cx + x, cy - 15 if folded else cy - 105)
    points[4] = (cx + 70, cy - 25)
    return [NS(x=x / width, y=y / height) for x, y in points]


def observations(labels=("Left", "Right"), only_right=False, shoulder_pixels=240):
    w, h = 1280, 720
    pose = [NS(x=0.5, y=0.5, z=0.0, visibility=1.0, presence=1.0) for _ in range(33)]
    for i, xy in {
        11: (520, 220),
        12: (520 + shoulder_pixels, 220),
        13: (420, 350),
        14: (860, 350),
        15: (400, 400),
        16: (900, 400),
        23: (550, 600),
        24: (750, 600),
    }.items():
        pose[i] = NS(x=xy[0] / w, y=xy[1] / h, z=0.0, visibility=1.0, presence=1.0)
    world = [NS(x=0.0, y=0.0, z=0.0) for _ in range(33)]
    for i, xyz in {
        11: (-0.2, 0, 0),
        12: (0.2, 0, 0),
        13: (-0.4, 0.2, 0),
        14: (0.4, 0.2, 0),
        15: (-0.5, 0.45, 0),
        16: (0.5, 0.45, 0),
    }.items():
        world[i] = NS(x=xyz[0], y=xyz[1], z=xyz[2])
    hands = [hand(400, 400, w, h), hand(900, 400, w, h)]
    handedness = [[NS(category_name=label)] for label in labels]
    if only_right:
        hands, handedness = hands[1:], handedness[1:]
    return NS(hand_landmarks=hands, handedness=handedness), NS(
        pose_landmarks=[pose], pose_world_landmarks=[world]
    )


def test_labels_flipping_does_not_swap_anatomical_roles():
    extractor = FeatureExtractor()
    hands, pose = observations()
    first = extractor.extract(hands, pose, 1280, 720, 0.0, 0)
    hands, pose = observations(("Right", "Left"))
    second = extractor.extract(hands, pose, 1280, 720, 0.033, 1)
    assert first.arm("left").wrist == second.arm("left").wrist == (400.0, 400.0)
    assert first.arm("right").wrist == second.arm("right").wrist == (900.0, 400.0)


def test_missing_support_retains_pose_fallback_without_role_reassignment():
    hands, pose = observations(only_right=True)
    features = FeatureExtractor().extract(hands, pose, 1280, 720, 0.0, 0)
    assert features.arm("left").source == "POSE_FALLBACK"
    assert features.arm("left").shape == Shape.UNKNOWN
    assert features.arm("right").source == "HAND_POSE"


def test_ambiguous_crossed_wrists_produce_unknown_hands():
    hands, pose = observations()
    pose.pose_landmarks[0][15] = pose.pose_landmarks[0][16]
    hands.hand_landmarks[0] = hands.hand_landmarks[1]
    features = FeatureExtractor().extract(hands, pose, 1280, 720, 0.0, 0)
    assert not any(a.hand_valid for a in features.arms)


def test_sideways_scale_is_rejected():
    hands, pose = observations(shoulder_pixels=30)
    f = FeatureExtractor().extract(hands, pose, 1280, 720, 0.0, 0)
    assert not f.valid and f.scale > 0.0


def test_degenerate_world_bones_are_unknown_and_finite():
    hands, pose = observations()
    pose.pose_world_landmarks[0] = [NS(x=0.0, y=0.0, z=0.0) for _ in range(33)]
    f = FeatureExtractor().extract(hands, pose, 1280, 720, 0.0, 0)
    assert all(a.angle is None for a in f.arms)


def test_body_scale_freezes_when_projection_collapses():
    extractor = FeatureExtractor()
    hands, pose = observations()
    original = extractor.extract(hands, pose, 1280, 720, 0.0, 0)
    hands, pose = observations(shoulder_pixels=80)
    collapsed = extractor.extract(hands, pose, 1280, 720, 0.03, 1)
    assert not collapsed.valid and collapsed.scale == original.scale and collapsed.chest == original.chest


@pytest.mark.parametrize("folded,expected", [(False, Shape.OPEN), (True, Shape.FIST)])
def test_hand_shape_rotation_invariance(folded, expected):
    raw = hand(400, 400, 1280, 720, folded)
    points = tuple((p.x * 1280, p.y * 720) for p in raw)
    assert classify(points) == expected
    rotated = tuple((1000.0 - y, x) for x, y in points)
    assert classify(rotated) == expected


def test_jsonl_roundtrip_and_no_pixels(tmp_path):
    hands, pose = observations()
    f = FeatureExtractor().extract(hands, pose, 1280, 720, 1.0, 0)
    assert decode_features(json.loads(json.dumps(asdict(f)))) == f
    path = tmp_path / "record.jsonl"
    recorder = Recorder()
    recorder.start(path)
    recorder.write({"type": "tracking", "features": asdict(f)})
    recorder.close()
    items = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    assert items[0]["schema"] == 1
    assert items[1]["features"]["frame_id"] == 0
    assert "rgb" not in items[1]
