import hashlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

from mirror_moon import tracking


def model_fixture(tmp_path, monkeypatch):
    directory = tmp_path / "中文 安装目录" / "assets" / "models"
    directory.mkdir(parents=True)
    payloads = {"hand_landmarker.task": b"hand model bytes", "pose_landmarker_lite.task": b"pose model bytes"}
    manifest = {}
    for name, payload in payloads.items():
        (directory / name).write_bytes(payload)
        manifest[name] = {"sha256": hashlib.sha256(payload).hexdigest()}
    (directory / "manifest.json").write_text(json.dumps(manifest), "utf-8")
    monkeypatch.setattr(tracking, "root", lambda: directory.parents[1])
    calls = []

    def base(**kwargs):
        assert "model_asset_path" not in kwargs
        assert isinstance(kwargs["model_asset_buffer"], bytes)
        calls.append(kwargs["model_asset_buffer"])
        return NS(**kwargs)

    landmarker = NS(create_from_options=lambda options: NS(close=lambda: None))
    vision = NS(
        HandLandmarker=landmarker,
        PoseLandmarker=landmarker,
        HandLandmarkerOptions=lambda **kwargs: NS(**kwargs),
        PoseLandmarkerOptions=lambda **kwargs: NS(**kwargs),
        RunningMode=NS(VIDEO="VIDEO"),
    )
    monkeypatch.setitem(sys.modules, "mediapipe", NS(tasks=NS(BaseOptions=base, vision=vision)))
    return directory, payloads, calls


def test_unicode_model_paths_are_read_by_python_and_passed_as_buffers(tmp_path, monkeypatch):
    _, payloads, calls = model_fixture(tmp_path, monkeypatch)
    tracker = tracking.Tracker()
    assert calls == list(payloads.values())
    assert tracker.model_buffers == payloads
    tracker.close()


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_models_still_validate_before_native_loading(tmp_path, monkeypatch, failure):
    directory, _, calls = model_fixture(tmp_path, monkeypatch)
    model = directory / "hand_landmarker.task"
    if failure == "missing":
        model.unlink()
    else:
        model.write_bytes(b"corrupted")
    with pytest.raises(RuntimeError, match="缺少模型或校验失败"):
        tracking.Tracker()
    assert not calls


@pytest.mark.parametrize(
    "content", ["broken JSON", "[]", "{}", '{"hand_landmarker.task": {"sha256": "invalid"}}']
)
def test_malformed_manifest_is_readable_and_never_calls_native(tmp_path, monkeypatch, content):
    directory, _, calls = model_fixture(tmp_path, monkeypatch)
    (directory / "manifest.json").write_text(content, "utf-8")
    with pytest.raises(RuntimeError, match="模型清单无效"):
        tracking.Tracker()
    assert not calls


def test_close_is_idempotent_and_attempts_other_task_after_failure(tmp_path, monkeypatch, caplog):
    model_fixture(tmp_path, monkeypatch)
    tracker = tracking.Tracker()
    closed = []

    def fail():
        closed.append("hand")
        raise RuntimeError("native close failure")

    tracker.hands.close = fail
    tracker.pose.close = lambda: closed.append("pose")
    tracker.close()
    tracker.close()
    assert closed == ["hand", "pose"]
    assert tracker.close_errors and "native close failure" in caplog.text


def test_pose_init_failure_retains_original_error_even_if_hand_close_fails(tmp_path, monkeypatch):
    model_fixture(tmp_path, monkeypatch)
    vision = sys.modules["mediapipe"].tasks.vision
    closed = []

    def close_fail():
        closed.append("hand")
        raise RuntimeError("cleanup failure")

    vision.HandLandmarker = NS(create_from_options=lambda options: NS(close=close_fail))

    def pose_fail(options):
        raise ValueError("original pose initialization failure")

    vision.PoseLandmarker = NS(create_from_options=pose_fail)
    with pytest.raises(ValueError, match="original pose initialization"):
        tracking.Tracker()
    assert closed == ["hand"]


def test_model_startup_failure_never_opens_camera(monkeypatch):
    from mirror_moon.pipeline import Pipeline

    opened = []

    def fail():
        raise RuntimeError("missing model test")

    monkeypatch.setattr(tracking, "Tracker", fail)
    monkeypatch.setattr("mirror_moon.pipeline.cv2.VideoCapture", lambda *args: opened.append(args))
    pipeline = Pipeline()
    pipeline.start()
    assert pipeline.stop_event.wait(1.0)
    assert pipeline.close(timeout=1.0)
    assert pipeline.error == "missing model test" and not opened
