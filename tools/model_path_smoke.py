"""Actual native model loading from a Chinese installation path, without a camera or saved RGB."""

import json
import shutil
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np

from mirror_moon import tracking


def main():
    repo = Path(__file__).resolve().parents[1]
    install = repo / "local" / "中文 模型安装目录" / "镜中取月" / "_internal"
    models = install / "assets" / "models"
    models.mkdir(parents=True, exist_ok=True)
    for name in ("manifest.json", "hand_landmarker.task", "pose_landmarker_lite.task"):
        shutil.copy2(repo / "assets" / "models" / name, models / name)
    with patch.object(tracking, "root", lambda: install):
        tracker = tracking.Tracker()
        try:
            result = tracker.process(np.zeros((360, 640, 3), dtype=np.uint8), time.perf_counter(), 0)
            assert result is not None
            assert tracker.timings["hand_timestamp_ms"] == tracker.timings["pose_timestamp_ms"]
        finally:
            tracker.close()
    record = {
        "both_models_loaded": True,
        "native_source": "model_asset_buffer",
        "installation_path_contains_chinese": True,
        "model_path_characters": len(str(models / "pose_landmarker_lite.task")),
        "dummy_frame_only": True,
        "same_frame_processed": True,
        "images_saved": False,
    }
    (repo / "local" / "model-path-smoke.json").write_text(json.dumps(record, indent=2), "utf-8")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
