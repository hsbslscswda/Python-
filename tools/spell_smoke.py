"""Actual Qt/GL or compatibility rendering of constructed water/fire actions."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from mirror_moon.app import STYLE, Window


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compat", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("local/new-spells"))
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
        mode="water",
        video=None,
        camera=0,
        autostart=True,
        quit_after=None,
        metrics=str(args.output / "metrics.json"),
        screenshot=None,
        screenshot_after=None,
        record_features=None,
        diagnostics=True,
    )
    window = Window(options)
    window.show()
    states = {"water": set(), "fire": set()}
    object_kinds = set()

    def observe():
        if window.data.scene:
            v = window.data.scene.spell
            states[v.mode].add(v.state)
            object_kinds.update(o.kind for o in v.objects)
            if any(o.kind == 2 for o in v.objects) and not getattr(window, "shot_captured", False):
                window.stage_image(args.output / "water-launch.png")
                window.shot_captured = True
            if any(o.kind == 3 and 0.15 < o.age < 0.4 for o in v.objects) and not getattr(
                window, "splash_captured", False
            ):
                window.stage_image(args.output / "water-splash.png")
                window.splash_captured = True

    timer = QTimer()
    timer.timeout.connect(observe)
    timer.start(20)
    for stamp, name in [
        (1800, "water-held"),
        (3000, "water-scale"),
    ]:
        QTimer.singleShot(stamp, lambda name=name: window.stage_image(args.output / (name + ".png")))
    QTimer.singleShot(9200, lambda: window.mode.setCurrentIndex(4))
    QTimer.singleShot(14200, lambda: window.stage_image(args.output / "fire-dual.png"))
    QTimer.singleShot(14500, lambda: window.grab().save(str(args.output / "ui-fire.png")))
    report = {}

    def finish():
        timer.stop()
        window.close()
        report.update(
            synthetic_only=True,
            states={k: sorted(v) for k, v in states.items()},
            events=dict(window.pipeline.event_counts),
            object_kinds=sorted(object_kinds),
            workers_closed_cleanly=window.pipeline.closed_cleanly,
            renderer=window.data.renderer_info,
        )
        (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")

    QTimer.singleShot(18200, finish)
    result = app.exec()
    assert report["workers_closed_cleanly"]
    for event in (
        "water_open",
        "water_launch",
        "water_hit",
        "water_close",
        "fire_unlock",
        "ignite",
        "fire_out",
    ):
        assert report["events"].get(event, 0) > 0, (event, report)
    assert {1, 2, 3, 4}.issubset(object_kinds), report
    print(json.dumps(report))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
