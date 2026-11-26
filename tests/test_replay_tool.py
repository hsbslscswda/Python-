import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mirror_moon.demo import sample
from mirror_moon.diagnostics import Recorder
from mirror_moon.pipeline import FramePacket, Pipeline, ScenePacket

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("mode", "active_state"), [("water", "HELD"), ("fire", "BURNING")])
def test_replay_matches_a_log_recorded_across_preview_restarts(tmp_path, mode, active_state):
    path = tmp_path / "recording.jsonl"
    report_path = tmp_path / "report.json"
    recorder = Recorder()
    recorder.start(path)
    for start, frame_count in ((100.0, 135), (110.0, 15)):
        pipeline = Pipeline(demo=True, recorder=recorder)
        pipeline.set_controls(mode=mode)
        for frame_id in range(frame_count):
            elapsed = frame_id / 30.0
            timestamp = start + elapsed
            rgb, features = sample(elapsed, timestamp, frame_id, mode)
            view = pipeline._business(features)
            frame = FramePacket(frame_id, timestamp, elapsed, rgb)
            scene = ScenePacket(frame, features, view, 0.0, timestamp, "synthetic test")
            recorder.tracking(scene, {}, pipeline.last_processed_controls)
    recorder.close()

    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "replay.py"), str(path), "--mode", mode,
         "--output", str(report_path)],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=True,
    )
    summary = json.loads(completed.stdout)
    report = json.loads(report_path.read_text("utf-8"))
    assert summary["recorded_version"] == summary["replay_version"]
    assert summary["sessions"] == 2
    assert summary["recorded_frames"] == summary["frames"] == 150
    assert summary["recorded_state_differences"] == 0
    assert active_state in summary["states"]
    assert report["results"][135]["session"] == 2
    assert report["results"][135]["state"] == "OFF"
