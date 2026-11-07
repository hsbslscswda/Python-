"""Opt-in JSONL: landmarks and timing only. Never records RGB or audio."""

import json
from dataclasses import asdict
from pathlib import Path
from threading import Lock

from . import __version__
from .domain import Arm, Features, Shape


class Recorder:
    def __init__(self):
        self.lock = Lock()
        self.file = None
        self.path = None

    def start(self, path):
        with self.lock:
            if self.file:
                self.file.close()
            self.path = Path(path)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.file = self.path.open("w", encoding="utf-8")
            self.file.write(
                json.dumps(
                    {
                        "type": "header",
                        "schema": 1,
                        "app_version": __version__,
                        "privacy": "landmarks and timings only; no RGB or audio",
                    }
                )
                + "\n"
            )

    def write(self, item):
        with self.lock:
            if self.file:
                self.file.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")
                self.file.flush()

    def tracking(self, scene, timings, controls=None, suppressed=False):
        self.write(
            {
                "type": "tracking",
                "source": scene.source_label,
                "frame_id": scene.frame.frame_id,
                "captured": scene.frame.captured,
                "source_time": scene.frame.source_time,
                "features": asdict(scene.features),
                "spell": asdict(scene.spell),
                "hand_sources": {a.side: a.source for a in scene.features.arms},
                "controls": asdict(controls) if controls else None,
                "input_suppressed": suppressed,
                "timings": timings,
            }
        )

    def close(self):
        with self.lock:
            if self.file:
                self.file.close()
                self.file = None


def decode_features(value):
    value = dict(value)
    value["chest"] = tuple(value["chest"])
    value["people"] = tuple(tuple(p) for p in value.get("people", ()))
    arms = []
    for a in value["arms"]:
        a = dict(a)
        a.setdefault("wrist_confidence", a.get("pose_confidence", 0.0))
        for key in ("shoulder", "elbow", "wrist"):
            a[key] = tuple(a[key])
        if a.get("pose_wrist") is not None:
            a["pose_wrist"] = tuple(a["pose_wrist"])
        for key in ("palm", "normal"):
            if a.get(key) is not None:
                a[key] = tuple(a[key])
        a["landmarks"] = tuple(tuple(p) for p in a["landmarks"])
        a["shape"] = Shape(a["shape"])
        arms.append(Arm(**a))
    value["arms"] = tuple(arms)
    return Features(**value)
