import argparse
import json
import logging
import sys
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut, QSurfaceFormat
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .audio import Audio
from .control import fit_calibration, valid_endpoints
from .diagnostics import Recorder
from .guide import PoseGuide
from .pipeline import Pipeline
from .render import GLStage, PainterStage, RenderState
from .resources import user_dir


class Window(QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.setWindowTitle(f"镜中取月 v{__version__} · 动作体验修订版")
        self.resize(1180, 820)
        self.setMinimumSize(960, 680)
        self.pipeline = None
        self.stopping_preview = False
        self.data = RenderState()
        self.recorder = Recorder()
        self.data.recorder = self.recorder
        if args.record_features:
            self.recorder.start(args.record_features)
        self.scene_version = 0
        self.paused = False
        self.reset_id = 0
        self.last_metrics = 0.0
        self.inference_times = deque(maxlen=1800)
        self.inference_stamps = deque(maxlen=1800)
        self.valid_pose_stamps = deque(maxlen=1800)
        self.seen_states = set()
        self.calibration = None
        self.settings_path = user_dir() / "calibration.json"
        self.endpoints = (75.0, 160.0)
        self.profiles = {}
        self.last_record_path = None
        self.effect_notice_until = 0.0
        if self.settings_path.exists():
            try:
                stored = json.loads(self.settings_path.read_text("utf-8"))
                bent, extended = stored["bent"], stored["extended"]
                if valid_endpoints(bent, extended):
                    self.endpoints = (bent, extended)
                for side, pair in stored.get("profiles", {}).items():
                    if side in ("left", "right") and valid_endpoints(*pair):
                        self.profiles[side] = tuple(pair)
            except (ValueError, KeyError, TypeError):
                pass
        self.audio = Audio(self)
        self.container = QWidget()
        self.setCentralWidget(self.container)
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("镜中取月")
        title.setObjectName("title")
        header.addWidget(title)
        header.addWidget(QLabel(f"v{__version__} · 让动作成为法术"))
        header.addStretch()
        self.mode = QComboBox()
        for name, value in (("星环术", "circle"), ("月刃术", "blade"), ("镜界术", "mirror")):
            self.mode.addItem(name, value)
        self.mode.setAccessibleName("施法系统")
        self.element = QComboBox()
        self.element.addItem("月华", "moon")
        self.element.addItem("雷霆", "lightning")
        self.element.setAccessibleName("法阵元素")
        header.addWidget(self.mode)
        header.addWidget(self.element)
        layout.addLayout(header)
        source_row = QHBoxLayout()
        self.source = QComboBox()
        for i in range(3):
            self.source.addItem(f"摄像头 {i}", i)
        if args.camera not in range(3):
            self.source.addItem(f"摄像头 {args.camera}", args.camera)
        self.source.setCurrentIndex(self.source.findData(args.camera))
        self.source.setAccessibleName("摄像头选择")
        source_row.addWidget(self.source)
        self.start_button = QPushButton("打开预览")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start_clicked)
        source_row.addWidget(self.start_button)
        self.stop_button = QPushButton("关闭摄像头 C")
        self.stop_button.clicked.connect(self.stop_preview)
        source_row.addWidget(self.stop_button)
        video_button = QPushButton("打开视频回放")
        video_button.clicked.connect(self.open_video)
        source_row.addWidget(video_button)
        self.pause_button = QPushButton("暂停")
        self.pause_button.clicked.connect(self.pause_clicked)
        source_row.addWidget(self.pause_button)
        source_row.addStretch()
        self.source_label = QLabel("摄像头画面仅在本机处理")
        self.source_label.setObjectName("sourceLabel")
        source_row.addWidget(self.source_label)
        layout.addLayout(source_row)
        self.stage_layout = QHBoxLayout()
        self.stage_layout.setContentsMargins(0, 0, 0, 0)
        self.stage = PainterStage(self.data) if args.compat else GLStage(self.data)
        if isinstance(self.stage, GLStage):
            self.stage.failed.connect(self.fallback)
        self.stage_layout.addWidget(self.stage, 1)
        self.guide = PoseGuide()
        self.stage_layout.addWidget(self.guide)
        layout.addLayout(self.stage_layout, 1)
        self.hint = QLabel("打开摄像头预览，让双肩、双肘和双手进入画面")
        self.hint.setObjectName("hint")
        layout.addWidget(self.hint)
        self.strength = QProgressBar()
        self.strength.setRange(0, 150)
        self.strength.setValue(0)
        self.strength.setTextVisible(True)
        self.strength.setFormat("施法强度 0%")
        self.strength.setFixedHeight(22)
        layout.addWidget(self.strength)
        footer = QHBoxLayout()
        self.status = QLabel("等待开始")
        self.status.setWordWrap(True)
        self.status.setMinimumWidth(0)
        footer.addWidget(self.status, 1)
        self.calibrate_button = QPushButton("20 秒校准")
        self.calibrate_button.clicked.connect(self.begin_calibration)
        footer.addWidget(self.calibrate_button)
        self.calibration_side = QComboBox()
        self.calibration_side.addItem("校准右臂", "right")
        self.calibration_side.addItem("校准左臂", "left")
        for i, side in enumerate(("right", "left")):
            self.calibration_side.setItemText(
                i, ("右臂" if side == "right" else "左臂") + ("已校准" if side in self.profiles else "未校准")
            )
        footer.addWidget(self.calibration_side)
        reset = QPushButton("重置 Esc")
        reset.clicked.connect(self.cancel)
        footer.addWidget(reset)
        screenshot = QPushButton("截图")
        screenshot.clicked.connect(self.screenshot)
        footer.addWidget(screenshot)
        full = QPushButton("全屏 F11")
        full.clicked.connect(self.fullscreen)
        footer.addWidget(full)
        layout.addLayout(footer)
        settings = QHBoxLayout()
        self.quality = QComboBox()
        self.quality.addItems(["轻量画质", "标准画质", "高画质"])
        self.quality.setCurrentIndex(1)
        self.quality.currentIndexChanged.connect(lambda i: setattr(self.data, "quality", i))
        settings.addWidget(self.quality)
        settings.addWidget(QLabel("特效强度"))
        gain = QSlider(Qt.Orientation.Horizontal)
        gain.setRange(20, 150)
        gain.setValue(100)
        gain.setMaximumWidth(130)
        gain.valueChanged.connect(lambda v: setattr(self.data, "gain", v / 100.0))
        settings.addWidget(gain)
        self.mirror_check = QCheckBox("显示镜像")
        self.mirror_check.setChecked(True)
        self.mirror_check.toggled.connect(lambda v: setattr(self.data, "mirrored", v))
        settings.addWidget(self.mirror_check)
        mute = QCheckBox("静音")
        mute.toggled.connect(lambda v: setattr(self.audio, "muted", v))
        settings.addWidget(mute)
        debug = QCheckBox("诊断")
        debug.toggled.connect(lambda v: setattr(self.data, "debug", v))
        settings.addWidget(debug)
        self.record_button = QPushButton("记录 G0 日志")
        self.record_button.clicked.connect(self.record_clicked)
        settings.addWidget(self.record_button)
        logs = QPushButton("打开日志文件夹")
        logs.clicked.connect(self.open_logs)
        settings.addWidget(logs)
        guide_check = QCheckBox("动作示范")
        guide_check.setChecked(True)
        guide_check.toggled.connect(self.guide.setVisible)
        settings.addWidget(guide_check)
        settings.addStretch()
        settings.addWidget(QLabel("Esc 收招    空格 暂停    F11 全屏"))
        layout.addLayout(settings)
        self.diagnostics = QLabel()
        self.diagnostics.setObjectName("diagnostics")
        self.diagnostics.hide()
        debug.toggled.connect(self.diagnostics.setVisible)
        layout.addWidget(self.diagnostics)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.element.currentIndexChanged.connect(
            lambda _: setattr(self.data, "element", self.element.currentData())
        )
        self.source.currentIndexChanged.connect(self.source_changed)
        self.mode.setCurrentIndex({"circle": 0, "blade": 1, "mirror": 2}[args.mode])
        debug.setChecked(args.diagnostics)
        for key, callback in (
            ("Escape", self.cancel),
            ("Space", self.pause_clicked),
            ("F11", self.fullscreen),
            ("C", self.stop_preview),
        ):
            QShortcut(QKeySequence(key), self, activated=callback)
        QApplication.instance().installEventFilter(self)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        if args.demo or args.video or args.autostart:
            QTimer.singleShot(0, lambda: self.start_pipeline(args.video or args.camera, auto=True))
        QTimer.singleShot(0, self.schedule_cli_timers)

    def schedule_cli_timers(self):
        if self.args.quit_after:
            QTimer.singleShot(round(self.args.quit_after * 1000), self.close)
        if self.args.screenshot_after and self.args.screenshot:
            QTimer.singleShot(
                round(self.args.screenshot_after * 1000), lambda: self.stage_image(self.args.screenshot)
            )

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and self.pipeline:
            if (
                isinstance(watched, QWidget)
                and watched is not self.stage
                and not self.stage.isAncestorOf(watched)
            ):
                self.pipeline.set_controls(suppress_until=time.perf_counter() + 0.65)
        return super().eventFilter(watched, event)

    def fallback(self, reason):
        previous = self.stage
        previous.shutdown()
        self.stage_layout.removeWidget(previous)
        previous.deleteLater()
        self.stage = PainterStage(self.data)
        self.stage_layout.insertWidget(0, self.stage, 1)
        self.data.renderer_info = "兼容画质 · QPainter"
        logging.warning(reason)
        self.status.setText(reason)

    def source_changed(self):
        if self.pipeline:
            self.start_pipeline(self.source.currentData(), auto=False)

    def start_clicked(self):
        if self.stopping_preview:
            return
        if self.pipeline and not self.pipeline.stop_event.is_set():
            self.paused = False
            self.pipeline.set_controls(paused=False)
            self.start_button.setText("施法中")
            self.pause_button.setText("暂停")
        else:
            source = self.pipeline.source if self.pipeline else self.source.currentData()
            self.start_pipeline(source, auto=True)

    def stop_preview(self):
        if not self.pipeline or self.stopping_preview:
            return
        self.stopping_preview = True
        self.audio.stop()
        self.data.reset_effects()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.status.setText("正在关闭摄像头…")
        self.poll_preview_stop()

    def poll_preview_stop(self):
        if not self.pipeline:
            return
        if not self.pipeline.close(timeout=0.0):
            QTimer.singleShot(100, self.poll_preview_stop)
            return
        self.pipeline = None
        self.data.scene = None
        self.stopping_preview = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.start_button.setText("打开摄像头")
        self.status.setText("摄像头已关闭；需要时点击打开摄像头")
        self.hint.setText("摄像头已关闭")

    def start_pipeline(self, source, auto=False):
        if self.stopping_preview:
            return
        if self.pipeline:
            if not self.pipeline.close():
                QMessageBox.warning(self, "设备仍在退出", self.pipeline.status)
                return
        self.data.reset_effects()
        self.data.last_event_id = 0
        self.audio.last_id = 0
        self.stage.frame_id = -1
        self.data.last_frame_id = -1
        self.scene_version = 0
        self.inference_times.clear()
        self.inference_stamps.clear()
        self.valid_pose_stamps.clear()
        self.seen_states.clear()
        self.pipeline = Pipeline(source, self.args.demo, self.recorder)
        self.paused = not auto
        self.pipeline.set_controls(
            mode=self.mode.currentData(),
            paused=self.paused,
            bent=self.endpoints[0],
            extended=self.endpoints[1],
            profiles=tuple((side, *pair) for side, pair in self.profiles.items()),
        )
        self.pipeline.start()
        self.start_button.setText("开始施法" if self.paused else "施法中")
        self.source_label.setText(
            "构造动作演示 · 非真人识别"
            if self.args.demo
            else "实时摄像头 · 本机处理"
            if isinstance(source, int)
            else "视频回放 · 非实时摄像头"
        )

    def open_video(self):
        filename, _ = QFileDialog.getOpenFileName(self, "选择本机视频", "", "视频 (*.mp4 *.avi *.mkv *.mov)")
        if filename:
            self.start_pipeline(filename, auto=True)

    def record_clicked(self):
        if self.recorder.file:
            path = self.recorder.path
            self.recorder.close()
            self.record_button.setText("记录 G0 日志")
            self.status.setText(f"关键点日志已保存：{path}")
            self.last_record_path = path
        elif self.args.demo:
            self.hint.setText("构造动作不是真人验证；请先使用摄像头或本机视频")
        else:
            target = user_dir() / "diagnostics" / (time.strftime("G0_%Y%m%d_%H%M%S") + ".jsonl")
            self.recorder.start(target)
            self.last_record_path = target
            self.record_button.setText("停止记录日志")

    def open_logs(self):
        directory = user_dir() / "diagnostics"
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def mode_changed(self):
        self.guide.mode = self.mode.currentData()
        self.guide.started = time.perf_counter()
        self.data.reset_effects()
        self.audio.stop()
        self.element.setEnabled(self.mode.currentData() == "circle")
        if self.pipeline:
            self.pipeline.set_controls(mode=self.mode.currentData())

    def cancel(self):
        self.calibration = None
        self.calibrate_button.setText("20 秒校准")
        self.reset_id += 1
        self.data.reset_effects()
        self.audio.stop()
        if self.pipeline:
            self.pipeline.set_controls(reset_id=self.reset_id)

    def pause_clicked(self):
        if not self.pipeline or self.pipeline.error or self.pipeline.stop_event.is_set():
            return
        self.paused = not self.paused
        self.data.reset_effects()
        self.pause_button.setText("恢复" if self.paused else "暂停")
        if self.pipeline:
            self.pipeline.set_controls(paused=self.paused)

    def fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def begin_calibration(self):
        if (
            not self.pipeline
            or self.pipeline.error
            or self.pipeline.stop_event.is_set()
            or not self.data.scene
            or self.args.demo
        ):
            self.hint.setText("先打开真实摄像头预览，再进行校准")
            return
        self.cancel()
        self.calibration = {
            "start": time.perf_counter(),
            "side": self.calibration_side.currentData(),
            "bent": [],
            "extended": [],
        }
        self.pipeline.set_controls(paused=True)
        self.calibrate_button.setText("Esc 取消校准")

    def calibration_tick(self, now, new_scene):
        calibration = self.calibration
        elapsed = now - calibration["start"]
        side_name = "左" if calibration["side"] == "left" else "右"
        instructions = [
            "自然站定，让双肩与双肘进入画面",
            "抬起左手，保持清晰可见",
            "抬起右手，保持清晰可见",
            f"{side_name}臂自然弯曲，保持舒适",
            f"{side_name}臂朝前舒适伸直，不必锁死肘关节",
        ]
        stage = min(4, int(elapsed / 4))
        self.hint.setText(f"校准 {max(0, 20 - int(elapsed))} 秒：{instructions[stage]}")
        if new_scene and stage >= 3:
            arm = self.data.scene.features.arm(calibration["side"])
            if arm.angle is not None and arm.hand_valid and arm.tracked:
                calibration["bent" if stage == 3 else "extended"].append(arm.angle)
        if elapsed >= 20:
            endpoints = fit_calibration(calibration["bent"], calibration["extended"])
            if endpoints:
                bent, extended = endpoints
                self.profiles[calibration["side"]] = (bent, extended)
                self.calibration_side.setItemText(
                    self.calibration_side.findData(calibration["side"]), f"{side_name}臂已校准"
                )
                self.settings_path.write_text(
                    json.dumps(
                        {
                            "version": 2,
                            "bent": self.endpoints[0],
                            "extended": self.endpoints[1],
                            "profiles": self.profiles,
                        },
                        indent=2,
                    ),
                    "utf-8",
                )
                self.pipeline.set_controls(
                    profiles=tuple((side, *pair) for side, pair in self.profiles.items())
                )
                self.hint.setText(f"{side_name}臂校准已保存；点击开始施法。另一臂可单独校准。")
            else:
                self.hint.setText("未取得足够可靠的弯伸样本，保留原校准；可调整站位后重试")
            self.calibration = None
            self.calibrate_button.setText("20 秒校准")
            self.paused = True
            self.start_button.setText("开始施法")

    def tick(self):
        now = time.perf_counter()
        self.guide.update()
        if self.stopping_preview:
            return
        new_scene = False
        if self.pipeline:
            version, scene = self.pipeline.scenes.read()
            if scene and version != self.scene_version:
                self.scene_version = version
                self.data.accept(scene)
                self.inference_times.append(scene.inference_ms)
                self.inference_stamps.append(scene.completed)
                self.seen_states.add(scene.spell.state)
                if scene.features.valid:
                    self.valid_pose_stamps.append(scene.completed)
                new_scene = True
                self.hint.setText("预览中：调整站位后点击开始施法" if self.paused else scene.spell.hint)
                self.strength.setValue(round(scene.spell.intensity * 100))
                self.strength.setFormat(
                    f"施法强度 {round(scene.spell.intensity * 100)}%"
                    + (" · 搭臂增强" if scene.spell.intensity > 1.0 else "")
                )
                self.strength.setStyleSheet(
                    "QProgressBar::chunk {background: #f4c56d;}" if scene.spell.intensity > 1.0 else ""
                )
            events = self.pipeline.events.consume(now)
            self.data.events(events)
            self.audio.events(events)
            labels = {
                "slash": "月刃已释放",
                "double": "双月连斩已释放",
                "cross": "十字裂空已释放",
                "shatter": "镜面已碎裂",
                "mirror_open": "镜面已展开",
                "overdrive": "搭臂增强已确认",
            }
            for event in events:
                if event.kind in labels:
                    self.effect_notice = labels[event.kind]
                    self.effect_notice_until = now + 0.9
            if now < self.effect_notice_until:
                self.hint.setText(self.effect_notice)
            age = now - self.data.scene.frame.captured if self.data.scene else 100.0
            if self.data.scene and age < 0.4 and not self.pipeline.stop_event.is_set() and not self.paused:
                self.audio.update(self.data.scene.spell.intensity)
            else:
                self.audio.update(0.0)
                if age > 0.4:
                    self.data.reset_effects()
                    # Stale snapshots cannot keep firing or retain a live mirror indefinitely.
                    from dataclasses import replace

                    if self.data.scene:
                        view = replace(self.data.scene.spell, intensity=0.0, visibility=0.0)
                        self.data.scene = replace(self.data.scene, spell=view)
            status = self.pipeline.status
            if self.pipeline.error:
                status = f"识别未启动：{self.pipeline.error}"
                self.hint.setText("识别未启动，不能施法。请查看下方完整错误，修复后点击重试。")
                self.start_button.setText("重试摄像头")
                self.source_label.setText("摄像头/识别未就绪")
            ready = self.pipeline.error is None and not self.pipeline.stop_event.is_set()
            self.pause_button.setEnabled(ready)
            self.calibrate_button.setEnabled(ready)
            if self.data.scene:
                status = f"{self.data.scene.features.reason or self.data.scene.spell.quality}    {status}"
            if self.audio.error():
                status += "    声音不可用，画面可继续使用"
            if isinstance(self.stage, PainterStage):
                status += "    兼容画质"
            if self.last_record_path:
                status += f"\n{'正在记录' if self.recorder.file else '日志已保存'}：{self.last_record_path}"
            self.status.setText(status)
            if self.calibration:
                self.calibration_tick(now, new_scene)
        if now - self.last_metrics > 0.5:
            self.last_metrics = now
            metrics = self.metrics()
            self.diagnostics.setText(
                f"{self.data.renderer_info}\n渲染 {metrics['render_fps']:.1f} FPS    {'演示更新' if self.args.demo else '跟踪'} {metrics['input_update_hz']:.1f} Hz    "
                f"状态 {self.data.scene.spell.state if self.data.scene else 'OFF'}    "
                f"数据年龄 p95 {metrics['capture_to_first_paint_p95_ms']} ms"
            )
        self.stage.update()

    def metrics(self):
        import numpy as np

        metrics = self.data.metrics()
        stamps = list(self.inference_stamps)
        metrics.update(
            {
                "tracking_hz": round((len(stamps) - 1) / (stamps[-1] - stamps[0]), 2)
                if len(stamps) > 1
                else 0.0,
                "inference_p95_ms": round(float(np.percentile(self.inference_times, 95)), 2)
                if self.inference_times
                else None,
                "source": self.data.scene.source_label if self.data.scene else "none",
                "frame_size": list(self.data.scene.frame.rgb.shape[:2][::-1]) if self.data.scene else None,
                "events_expired": self.pipeline.events.expired if self.pipeline else 0,
                "events_emitted": dict(self.pipeline.event_counts) if self.pipeline else {},
                "pipeline_error": self.pipeline.error if self.pipeline else None,
            }
        )
        metrics["input_update_hz"] = metrics["tracking_hz"]
        metrics["paired_inference_hz"] = metrics["tracking_hz"]
        metrics["inference_p50_ms"] = (
            round(float(np.percentile(self.inference_times, 50)), 2) if self.inference_times else None
        )
        valid = list(self.valid_pose_stamps)
        metrics["valid_pose_hz"] = (
            round((len(valid) - 1) / (stamps[-1] - stamps[0]), 2)
            if len(valid) > 1 and len(stamps) > 1
            else 0.0
        )
        capture = list(self.pipeline.capture_stamps) if self.pipeline else []
        metrics["capture_hz"] = (
            round((len(capture) - 1) / (capture[-1] - capture[0]), 2) if len(capture) > 1 else 0.0
        )
        metrics["seen_states"] = sorted(self.seen_states)
        if self.args.demo:
            metrics["tracking_hz"] = None
            metrics["inference_p95_ms"] = None
            metrics["inference_p50_ms"] = None
            metrics["paired_inference_hz"] = None
            metrics["valid_pose_hz"] = None
        return metrics

    def stage_image(self, filename):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        image = (
            self.stage.grabFramebuffer() if isinstance(self.stage, GLStage) else self.stage.grab().toImage()
        )
        return image.save(str(filename))

    def screenshot(self):
        directory = user_dir() / "screenshots"
        directory.mkdir(exist_ok=True)
        target = directory / (time.strftime("镜中取月_%Y%m%d_%H%M%S") + ".png")
        self.stage_image(target)
        self.status.setText(f"截图已保存：{target}")

    def closeEvent(self, event):
        self.timer.stop()
        self.audio.stop()
        clean = self.pipeline.close(timeout=0.05) if self.pipeline else True
        if not clean:
            self.status.setText("正在释放摄像头与识别模型，请稍候…")
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        metrics = self.metrics()
        metrics["workers_closed_cleanly"] = clean
        metrics["workers_close_seconds"] = self.pipeline.close_seconds if self.pipeline else 0.0
        metrics["worker_shutdown_seconds_after_request"] = (
            {
                name: max(0.0, stamp - self.pipeline.shutdown_started)
                for name, stamp in self.pipeline.worker_shutdown.items()
            }
            if self.pipeline and self.pipeline.shutdown_started is not None
            else {}
        )
        if self.args.metrics:
            target = Path(self.args.metrics)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), "utf-8")
        logging.info("shutdown %s", metrics)
        self.stage.shutdown()
        self.recorder.close()
        event.accept()


STYLE = """
QMainWindow, QWidget {
    background: #070e17;
    color: #e2f1ff;
    font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
    font-size: 13px;
}
QLabel#title {
    font-family: 'STXingkai', 'KaiTi', 'Microsoft YaHei UI';
    font-size: 32px;
    font-weight: bold;
    color: #f0f9ff;
    padding-right: 14px;
}
QLabel#hint {
    background: #0f2133;
    border: 1px solid #1e4263;
    border-left: 4px solid #38bdf8;
    border-radius: 6px;
    font-size: 19px;
    font-weight: 600;
    color: #f8fafc;
    padding: 8px 14px;
}
QLabel#sourceLabel {
    background: #0d1d2c;
    border: 1px solid #1e3a52;
    border-radius: 12px;
    color: #7dd3fc;
    padding: 4px 12px;
    font-size: 12px;
}
QLabel#diagnostics {
    background: #09131d;
    border: 1px solid #193046;
    border-radius: 6px;
    font-family: 'Consolas', 'Microsoft YaHei UI';
    font-size: 12px;
    color: #93c5fd;
    padding: 6px 10px;
}
QPushButton, QComboBox {
    background: #112638;
    border: 1px solid #264a68;
    color: #e0f2fe;
    padding: 7px 14px;
    border-radius: 6px;
    font-weight: 500;
}
QPushButton:hover, QComboBox:hover {
    background: #1a3a54;
    border-color: #38bdf8;
}
QPushButton:pressed {
    background: #0d1e2d;
}
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    color: #041019;
    font-weight: bold;
    border: 1px solid #bae6fd;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #7dd3fc);
}
QPushButton:disabled, QComboBox:disabled {
    background: #0b1622;
    border-color: #162a3d;
    color: #476278;
}
QComboBox QAbstractItemView {
    background: #0f2233;
    border: 1px solid #38bdf8;
    selection-background-color: #0284c7;
}
QProgressBar {
    background: #0c1a28;
    border: 1px solid #1e3a52;
    border-radius: 7px;
    text-align: center;
    font-weight: bold;
    color: #ffffff;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:0.65 #38bdf8, stop:1 #a5f3fc);
    border-radius: 6px;
}
QSlider::groove:horizontal {
    height: 5px;
    background: #162c40;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #38bdf8;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    margin: -5px 0;
    background: #e0f2fe;
    border: 2px solid #0284c7;
    border-radius: 7px;
}
QCheckBox {
    spacing: 6px;
    color: #cbd5e1;
}
"""


def main():
    parser = argparse.ArgumentParser(description="镜中取月 · 本地动作 AR 舞台")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--video")
    parser.add_argument("--mode", choices=("circle", "blade", "mirror"), default="circle")
    parser.add_argument("--demo", action="store_true", help="构造动作演示，不能用作真人识别证据")
    parser.add_argument("--compat", action="store_true", help="QPainter 兼容画质")
    parser.add_argument("--autostart", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--record-features", help="主动保存关键点/状态/时序日志，不保存图像")
    parser.add_argument("--quit-after", type=float)
    parser.add_argument("--metrics")
    parser.add_argument("--screenshot")
    parser.add_argument("--screenshot-after", type=float)
    args = parser.parse_args()
    logging.basicConfig(
        filename=user_dir() / "app.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(0)
    fmt.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("MirrorMoon")
    app.setStyleSheet(STYLE)
    window = Window(args)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
