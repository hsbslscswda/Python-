"""MediaPipe boundary: one RGB image and one timestamp for both Tasks."""

import hashlib
import json
import logging
import time

from .features import FeatureExtractor
from .features import classify as classify
from .resources import root


class Tracker:
    def __init__(self):
        self.hands = self.pose = None
        self.model_buffers = {}
        self.close_errors = []
        self.extractor = FeatureExtractor()
        self.last_ms = -1
        directory = root() / "assets" / "models"
        if not (directory / "manifest.json").exists():
            raise RuntimeError("缺少模型清单。请运行 tools/prepare_models.py 准备本地模型。")
        try:
            manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("清单应为对象")
            for name in ("hand_landmarker.task", "pose_landmarker_lite.task"):
                entry = manifest[name]
                digest = entry["sha256"]
                if not isinstance(digest, str) or len(digest) != 64:
                    raise ValueError("SHA256 格式错误")
                int(digest, 16)
                payload = (directory / name).read_bytes()
                if not payload or hashlib.sha256(payload).hexdigest() != digest.lower():
                    raise ValueError("模型校验不一致")
                if "bytes" in entry and entry["bytes"] != len(payload):
                    raise ValueError("模型长度不一致")
                self.model_buffers[name] = payload
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(
                "缺少模型或校验失败，模型清单无效。请运行 tools/prepare_models.py 后再启动。"
            ) from exc
        # File errors must not import native Tasks or initialize its dependencies.
        import mediapipe as mp

        self.mp = mp
        base, vision = mp.tasks.BaseOptions, mp.tasks.vision
        self.hands = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                # Python handles Unicode Windows paths; the native Tasks path loader does not.
                base_options=base(model_asset_buffer=self.model_buffers["hand_landmarker.task"]),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,
            )
        )
        try:
            self.pose = vision.PoseLandmarker.create_from_options(
                vision.PoseLandmarkerOptions(
                    base_options=base(model_asset_buffer=self.model_buffers["pose_landmarker_lite.task"]),
                    running_mode=vision.RunningMode.VIDEO,
                    num_poses=1,
                )
            )
        except Exception:
            self.close()
            raise

    def process(self, rgb, timestamp, frame_id):
        ms = round(timestamp * 1000)
        if ms <= self.last_ms:
            return None
        self.last_ms = ms
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        started = time.perf_counter()
        hands = self.hands.detect_for_video(image, ms)
        hand_finished = time.perf_counter()
        pose = self.pose.detect_for_video(image, ms)
        pose_finished = time.perf_counter()
        self.timings = {
            "hand_ms": (hand_finished - started) * 1000.0,
            "pose_ms": (pose_finished - hand_finished) * 1000.0,
            "hand_timestamp_ms": ms,
            "pose_timestamp_ms": ms,
        }
        return self.extractor.extract(hands, pose, rgb.shape[1], rgb.shape[0], timestamp, frame_id)

    def close(self):
        # Attempt each native closer once. One failure must not leak the other task,
        # mask initialization errors, or make repeated GUI shutdown polls close twice.
        for name in ("hands", "pose"):
            task = getattr(self, name, None)
            setattr(self, name, None)
            if task is not None:
                try:
                    task.close()
                except Exception as exc:
                    self.close_errors.append(f"{name}: {exc}")
                    logging.getLogger(__name__).exception("Native %s close failed", name)
        # Buffers remain owned until this Tracker is released, also on native close failure.
