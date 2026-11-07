"""Exercise preview stop/restart through our own Qt API. Never save camera images."""

import argparse
import json
import time
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from mirror_moon.app import STYLE, Window


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    out = Path("local")
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication([])
    app.setStyleSheet(STYLE)
    options = SimpleNamespace(
        demo=args.demo,
        compat=False,
        mode="circle",
        video=None,
        camera=0,
        autostart=True,
        quit_after=None,
        metrics=None,
        screenshot=None,
        screenshot_after=None,
        record_features=None,
        diagnostics=True,
    )
    window = Window(options)
    window.resize(1350, 930)
    window.show()
    started = time.perf_counter()
    phase = 0
    old_pipeline = None
    stopped_at = None
    result = {"synthetic_only": args.demo, "camera_images_saved": False}

    def poll():
        nonlocal phase, old_pipeline, stopped_at
        if time.perf_counter() - started > 35:
            result["error"] = "preview lifecycle timeout"
            window.close()
            return
        if phase == 0 and window.data.scene is not None:
            if args.demo:
                window.grab().save(str(out / "ui-guide-synthetic.png"))
            result["first_preview"] = window.metrics()
            old_pipeline = window.pipeline
            stopped_at = time.perf_counter()
            window.stop_button.click()
            window.stop_preview()  # repeated hotkey must be harmless while closing
            phase = 1
        elif phase == 1 and window.pipeline is None:
            result["preview_closed_cleanly"] = old_pipeline.closed_cleanly
            result["stop_seconds"] = time.perf_counter() - stopped_at
            result["scene_cleared"] = window.data.scene is None
            window.start_button.click()
            phase = 2
        elif phase == 2 and window.data.scene is not None:
            result["reopened_preview"] = window.metrics()
            result["new_pipeline"] = window.pipeline is not old_pipeline
            phase = 3
            timer.stop()
            window.close()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(100)
    app.exec()
    result["final_workers_closed_cleanly"] = window.pipeline.closed_cleanly if window.pipeline else True
    suffix = "demo" if args.demo else "camera"
    (out / f"ui-smoke-{suffix}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    assert "error" not in result, result
    assert result["preview_closed_cleanly"] and result["scene_cleared"] and result["new_pipeline"]
    assert result["reopened_preview"]["pipeline_error"] is None and result["final_workers_closed_cleanly"]
    print(json.dumps({"case": suffix, "stop_seconds": result["stop_seconds"], "passed": True}))


if __name__ == "__main__":
    main()
