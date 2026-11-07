"""Non-personal synthetic input for reproducible UI/graphics checks only."""

import math
from functools import lru_cache

import cv2
import numpy as np

from .domain import Arm, Features, Shape


@lru_cache(maxsize=1)
def background():
    width, height = 1280, 720
    y, x = np.mgrid[0:height, 0:width]
    glow = np.exp(-((x - 640) ** 2 / 400000 + (y - 300) ** 2 / 160000))
    rgb = np.empty((height, width, 3), np.uint8)
    for i, (base, add) in enumerate(((13, 16), (24, 20), (36, 24))):
        rgb[:, :, i] = base + glow * add
    for ix in range(0, width, 80):
        cv2.line(rgb, (ix, 0), (ix, height), (24, 39, 51), 1)
    for iy in range(0, height, 80):
        cv2.line(rgb, (0, iy), (width, iy), (24, 39, 51), 1)
    return rgb


def sample(elapsed, now, frame_id, mode="circle"):
    width, height, scale = 1280, 720, 235.0
    rgb = background().copy()
    chest = (640.0, 340.0)
    cycle = elapsed % 16.0
    left_wrist, right_wrist = (615.0, 335.0), (830.0, 310.0)
    right_shape = Shape.OPEN if cycle > 1.0 else Shape.FIST
    if 5.0 < cycle < 10.0:
        a = min(1.0, (cycle - 5.0) / 0.6)
        left_wrist = (615.0 + a * 175.0, 335.0 - a * 3.0)
    if cycle >= 10.0:
        left_wrist = (615.0, 335.0)
    if cycle > 13.0:
        right_shape = Shape.FIST
    angle = 75.0 + 85.0 * (0.5 + 0.5 * math.sin(elapsed * 1.2))
    arms = (
        Arm("left", (525.0, 270.0), (460.0, 370.0), left_wrist, Shape.FIST, True, True, 95.0),
        Arm("right", (760.0, 270.0), (680.0, 350.0), right_wrist, right_shape, True, True, angle),
    )
    from dataclasses import replace

    if mode == "water":
        phase = elapsed % 10.0
        rw = (830.0 + 30 * math.sin(phase * 2), 340.0)
        lw = (420.0, 340.0)
        shape = Shape.FIST if 0.45 < phase < 0.95 else Shape.OPEN
        normal_left = normal_right = (0.0, 0.0, -1.0)
        if 2.5 < phase < 3.6:
            lw = (710.0, 340.0)
            normal_left, normal_right = (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)
        elif 3.6 <= phase < 4.8:
            lw = (790.0, 340.0)
        elif 7.0 < phase < 7.5:
            gap = max(10.0, 180.0 - (phase - 7) * 650)
            lw, rw = (640 - gap, 340.0), (640 + gap, 340.0)
            normal_left, normal_right = (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)
        arms = (
            replace(
                arms[0],
                wrist=lw,
                palm=lw,
                shape=Shape.OPEN,
                normal=normal_left,
                palm_scale=60,
                upper_valid=True,
            ),
            replace(
                arms[1], wrist=rw, palm=rw, shape=shape, normal=normal_right, palm_scale=60, upper_valid=True
            ),
        )
    elif mode == "fire":
        phase = elapsed % 10.0
        shape = Shape.FIST if 0.9 < phase < 3.15 or 7.0 < phase < 7.5 else Shape.OPEN
        arms = tuple(
            replace(
                a,
                wrist=(500.0 + i * 280, 440.0),
                palm=(500.0 + i * 280, 440.0),
                shape=shape,
                openness=0.0 if shape == Shape.FIST else 1.0,
                palm_scale=65,
                normal=(0.0, 1.0 if 7.5 < phase < 8.0 else -1.0, 0.0),
                shoulder=(0.0, 0.0),
                elbow=(0.0, 0.0),
                pose_confidence=0.0,
            )
            for i, a in enumerate(arms)
        )
    elif mode == "blade":
        phase = elapsed % 4.0
        p = min(1.0, max(0.0, (phase - 0.7) / 0.38))
        wrist = (525.0 + 450.0 * p, 270.0 - 90.0 * math.sin(p * math.pi))
        if phase > 1.4:
            p = min(1.0, (phase - 1.4) / 0.38)
            wrist = (975.0 - 450.0 * p, 270.0 + 75.0 * math.sin(p * math.pi))
        arms = (
            replace(arms[0], wrist=(430.0, 600.0), shape=Shape.OTHER),
            replace(arms[1], wrist=wrist, shape=Shape.OPEN),
        )
    elif mode == "mirror":
        phase = elapsed % 12.0
        d = 0.4
        shift = 0.0
        if 0.8 <= phase < 5.0:
            d = 0.4 + 1.4 * min(1.0, (phase - 0.8) / 0.6)
            shift = 110.0 * min(1.0, max(0.0, (phase - 3.2) / 0.8))
        elif 5.0 <= phase < 7.8:
            d = max(0.25, 1.8 - (phase - 5.0) * 0.7)
            shift = 110.0
        elif 9.0 <= phase < 10.5:
            d = 0.4 + 1.4 * min(1.0, (phase - 9.0) / 0.6)
        elif phase >= 10.5:
            d = max(0.25, 1.8 - (phase - 10.5) * 10.0)
        arms = tuple(
            replace(
                a, wrist=(640.0 + shift + (-1 if i == 0 else 1) * d * scale / 2.0, 340.0), shape=Shape.OPEN
            )
            for i, a in enumerate(arms)
        )
    if mode == "mirror" and 7.8 < elapsed % 12.0 < 8.6:
        arms = tuple(replace(a, wrist=(a.wrist[0], 600.0), shape=Shape.OTHER) for a in arms)
    if (
        mode in ("circle", "blade", "mirror")
        and elapsed % (16.0 if mode == "circle" else 4.0 if mode == "blade" else 12.0) < 0.45
    ):
        arms = tuple(replace(a, wrist=(a.wrist[0], 600.0), shape=Shape.OTHER) for a in arms)
    # Asymmetric chart and a silhouette make orientation, channel and aspect errors visible.
    cv2.putText(rgb, "L  /  SYNTHETIC STAGE", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (160, 190, 210), 1)
    cv2.circle(rgb, (1110, 80), 18, (220, 90, 70), -1)
    cv2.ellipse(rgb, (640, 490), (145, 220), 0, 180, 360, (32, 52, 65), -1)
    cv2.circle(rgb, (640, 193), 61, (43, 64, 76), -1)
    for arm in arms:
        if mode != "fire":
            for a, b in ((arm.shoulder, arm.elbow), (arm.elbow, arm.wrist)):
                cv2.line(rgb, tuple(map(int, a)), tuple(map(int, b)), (66, 91, 108), 24, cv2.LINE_AA)
        cv2.circle(rgb, tuple(map(int, arm.wrist)), 16, (149, 178, 190), -1)
    return rgb, Features(now, frame_id, width, height, chest, scale, arms, valid=mode != "fire")
