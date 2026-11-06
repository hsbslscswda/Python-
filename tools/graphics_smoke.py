"""Exercise our Qt widgets directly, with synthetic input. No personal video is captured."""

import argparse
import json
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
    states = defaultdict(set)
    checks = []

    def observe():
        if window.data.scene:
            view = window.data.scene.spell
            states[view.mode].add(view.state)

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
        checks.append(
            {
                "resize": index,
                "size": [image.width(), image.height()],
                "fbo": window.stage.defaultFramebufferObject(),
                "red_marker_correct": color.red() > color.green() * 1.5 and color.red() > color.blue() * 1.5,
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
    QTimer.singleShot(5000, lambda: (window.showNormal(), window.resize(1180, 820)))
    QTimer.singleShot(8000, lambda: window.stage_image(args.output / "circle-overdrive.png"))
    QTimer.singleShot(17000, lambda: window.mode.setCurrentIndex(1))
    QTimer.singleShot(18100, lambda: window.stage_image(args.output / "blade.png"))
    QTimer.singleShot(22000, lambda: window.mode.setCurrentIndex(2))
    QTimer.singleShot(26400, lambda: window.stage_image(args.output / "mirror-fold.png"))
    QTimer.singleShot(32900, lambda: window.stage_image(args.output / "mirror-shatter.png"))

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
        }
        (args.output / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")

    QTimer.singleShot(35000, finish)
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
