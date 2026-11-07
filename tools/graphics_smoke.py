"""Exercise our Qt widgets directly, with synthetic input. No personal video is captured."""

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from mirror_moon.app import STYLE, Window
from mirror_moon.render import GLStage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compat", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("local/graphics"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication([])
    app.setStyleSheet(STYLE)
    options = SimpleNamespace(
        demo=True,
        compat=args.compat,
        mode="circle",
        video=None,
        camera=0,
        autostart=True,
        quit_after=None,
        metrics=str(args.output / "metrics.json"),
        screenshot=None,
        screenshot_after=None,
        record_features=None,
        diagnostics=False,
    )
    window = Window(options)
    window.show()

    def neutral_resize_phase():
        if window.pipeline is None:
            QTimer.singleShot(20, neutral_resize_phase)
            return
        # New cyan/gold bloom can tint the orientation marker without moving it.
        # Check camera/FBO orientation with an OFF spell, then test effects below.
        window.pipeline.set_controls(suppress_until=time.perf_counter() + 6.0)

    QTimer.singleShot(0, neutral_resize_phase)
    states = defaultdict(set)
    checks = []
    gaps = []
    instrumented = set()

    def observe():
        pipeline = window.pipeline
        if pipeline is not None and id(pipeline) not in instrumented:
            instrumented.add(id(pipeline))
            original = pipeline.engine.update
            last = [None]

            def tracked_update(features, *args, **kwargs):
                if last[0] is not None and features.timestamp - last[0] > 0.35:
                    gaps.append(
                        {
                            "gap_ms": round((features.timestamp - last[0]) * 1000, 2),
                            "mode": pipeline.engine.mode,
                        }
                    )
                last[0] = features.timestamp
                return original(features, *args, **kwargs)

            pipeline.engine.update = tracked_update
        if window.data.scene:
            view = window.data.scene.spell
            states[view.mode].add(view.state)
            if view.mode == "blade" and window.data.slashes and not getattr(window, "blade_captured", False):
                window.stage_image(args.output / "blade.png")
                window.blade_captured = True

    sampler = QTimer()
    sampler.timeout.connect(observe)
    sampler.start(20)

    def check_frame(index, attempt=0):
        if window.data.scene is None and attempt < 15:
            QTimer.singleShot(200, lambda: check_frame(index, attempt + 1))
            return
        if not isinstance(window.stage, GLStage):
            checks.append({"resize": index, "renderer": "compat" if args.compat else "UNEXPECTED FALLBACK"})
            return
        image = window.stage.grabFramebuffer()
        fit = min(image.width() / 1280, image.height() / 720)
        x = (image.width() - 1280 * fit) / 2 + 170 * fit
        y = (image.height() - 720 * fit) / 2 + 80 * fit
        color = image.pixelColor(int(x), int(y))
        marker_ok = color.red() > color.green() * 1.5 and color.red() > color.blue() * 1.5
        if not marker_ok:
            image.save(str(args.output / f"marker-failure-{index}.png"))
        checks.append(
            {
                "resize": index,
                "size": [image.width(), image.height()],
                "fbo": window.stage.defaultFramebufferObject(),
                "red_marker_correct": marker_ok,
                "marker_rgb": [color.red(), color.green(), color.blue()],
            }
        )

    def resize(index):
        if index % 2:
            window.showFullScreen()
        else:
            window.showNormal()
            window.resize(980 + index * 20, 700 + index * 8)
        QTimer.singleShot(180, lambda: check_frame(index))

    for i in range(10):
        QTimer.singleShot(500 + i * 400, lambda i=i: resize(i))

    def fresh_motion_phase():
        window.showNormal()
        window.resize(1180, 820)
        # Resize may legitimately stall input and activate the loss guard.
        # Test gestures after an explicit fresh neutral, not by weakening that guard.
        window.start_pipeline(0, auto=True)

    QTimer.singleShot(6000, fresh_motion_phase)
    QTimer.singleShot(14000, lambda: window.stage_image(args.output / "circle-overdrive.png"))
    QTimer.singleShot(14700, lambda: window.element.setCurrentIndex(1))
    QTimer.singleShot(15200, lambda: window.stage_image(args.output / "circle-lightning.png"))
    QTimer.singleShot(15500, lambda: window.element.setCurrentIndex(0))
    QTimer.singleShot(23000, lambda: window.mode.setCurrentIndex(1))
    QTimer.singleShot(28000, lambda: window.mode.setCurrentIndex(2))
    QTimer.singleShot(32400, lambda: window.stage_image(args.output / "mirror-fold.png"))
    QTimer.singleShot(38900, lambda: window.stage_image(args.output / "mirror-shatter.png"))

    def finish():
        sampler.stop()
        window.close()
        result = {
            "synthetic_only": True,
            "states": {k: sorted(v) for k, v in states.items()},
            "resize_checks": checks,
            "events": dict(window.pipeline.event_counts),
            "workers_closed_cleanly": window.pipeline.closed_cleanly,
            "workers_close_seconds": window.pipeline.close_seconds,
            "renderer": window.data.renderer_info,
            "input_gaps_exceeding_safety_limit": gaps,
        }
        (args.output / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")

    QTimer.singleShot(41000, finish)
    result = app.exec()
    report = json.loads((args.output / "results.json").read_text("utf-8"))
    assert report["workers_closed_cleanly"]
    assert "OVERDRIVE" in report["states"]["circle"]
    assert report["events"].get("slash", 0) > 0
    assert report["events"].get("shatter", 0) > 0
    assert report["events"].get("double", 0) > 0
    if not args.compat:
        assert all(c.get("red_marker_correct", False) for c in checks)
    print(json.dumps(report, ensure_ascii=False))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
