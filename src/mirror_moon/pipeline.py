import logging
import time
from collections import Counter, deque
from dataclasses import dataclass, replace
from threading import Event as StopEvent
from threading import Lock, Thread

import cv2
import numpy as np

from .domain import Features, SpellView
from .interaction import Engine
from .transport import EventJournal, Latest


@dataclass(frozen=True)
class FramePacket:
    frame_id: int
    captured: float
    source_time: float
    rgb: np.ndarray


@dataclass(frozen=True)
class ScenePacket:
    frame: FramePacket
    features: Features
    spell: SpellView
    inference_ms: float
    completed: float
    source_label: str


@dataclass(frozen=True)
class Controls:
    mode: str = "circle"
    paused: bool = False
    reset_id: int = 0
    suppress_until: float = 0.0
    bent: float = 75.0
    extended: float = 134.0
    profiles: tuple = ()


class Pipeline:
    def __init__(self, source=0, demo=False, recorder=None):
        self.source, self.demo = source, demo
        self.frames, self.scenes = Latest(), Latest()
        self.events = EventJournal()
        self.stop_event = StopEvent()
        self.models_ready = StopEvent()
        self.control_lock = Lock()
        self.controls = Controls()
        self.status = "等待开始"
        self.engine = Engine()
        self.threads = []
        self.closed_cleanly = False
        self.close_seconds = None
        self.capture_stamps = deque(maxlen=1800)
        self.recorder = recorder
        self.event_counts = Counter()
        self.shutdown_started = None
        self.worker_shutdown = {}
        self.error = None

    def set_controls(self, **kwargs):
        with self.control_lock:
            self.controls = replace(self.controls, **kwargs)

    def start(self):
        if self.threads:
            return
        targets = [self._demo] if self.demo else [self._capture, self._infer]
        self.threads = [Thread(target=t, name=t.__name__, daemon=True) for t in targets]
        for thread in self.threads:
            thread.start()

    def close(self, timeout=1.5):
        started = time.perf_counter()
        if self.shutdown_started is None:
            self.shutdown_started = started
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=max(0.0, timeout - (time.perf_counter() - started)))
        self.closed_cleanly = all(not t.is_alive() for t in self.threads)
        self.close_seconds = time.perf_counter() - self.shutdown_started
        self.status = "已释放摄像头与模型" if self.closed_cleanly else "设备读取未及时退出，请检查摄像头驱动"
        return self.closed_cleanly

    def _capture(self):
        cap = None
        try:
            # Do not race a device open/release against a model startup failure.
            while not self.models_ready.wait(0.05):
                if self.stop_event.is_set():
                    return
            if self.stop_event.is_set():
                return
            is_camera = isinstance(self.source, int)
            cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW if is_camera else cv2.CAP_ANY)
            if not cap.isOpened() and is_camera:
                cap.release()
                cap = cv2.VideoCapture(self.source, cv2.CAP_MSMF)
            if not cap.isOpened():
                raise RuntimeError("无法打开摄像头/视频。请关闭占用摄像头的软件，或选择视频回放。")
            if is_camera:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FPS, 30)
            fps = cap.get(cv2.CAP_PROP_FPS)
            fps = fps if 1 <= fps <= 240 else 30.0
            start = time.perf_counter()
            frame_id = 0
            while not self.stop_event.is_set():
                ok, bgr = cap.read()
                captured = time.perf_counter()
                if not ok:
                    self.status = "摄像头已断开，请重新开始" if is_camera else "视频回放结束，可重新开始"
                    self.stop_event.set()
                    break
                rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                rgb.flags.writeable = False
                self.capture_stamps.append(captured)
                source_time = captured - start if is_camera else frame_id / fps
                self.frames.publish(FramePacket(frame_id, captured, source_time, rgb))
                frame_id += 1
                if not is_camera:
                    self.stop_event.wait(max(0.0, start + frame_id / fps - time.perf_counter()))
        except Exception as exc:
            logging.getLogger(__name__).exception("Capture failed")
            self.error = str(exc)
            self.status = str(exc)
            self.stop_event.set()
        finally:
            if cap is not None:
                cap.release()
            self.worker_shutdown["capture"] = time.perf_counter()

    def _business(self, features, rgb=None):
        with self.control_lock:
            controls = self.controls
        self.last_processed_controls = controls
        self.input_suppressed = False
        self.engine.circle.bent, self.engine.circle.extended = controls.bent, controls.extended
        self.engine.circle.profiles = {side: (bent, extended) for side, bent, extended in controls.profiles}
        reset = controls.reset_id != getattr(self, "last_reset", 0)
        self.last_reset = controls.reset_id
        if reset or controls.mode != self.engine.mode or controls.paused:
            self.events.clear()
        if time.perf_counter() < controls.suppress_until and not reset and controls.mode == self.engine.mode:
            self.input_suppressed = True
            return self.engine.view
        view, events = self.engine.update(features, controls.mode, controls.paused, reset)
        for event in events:
            if event.kind == "shatter":
                event = replace(event, image=rgb)
            self.events.publish(event)
            self.event_counts[event.kind] += 1
            if self.recorder:
                self.recorder.write(
                    {
                        "type": "event",
                        "event_id": event.event_id,
                        "kind": event.kind,
                        "frame_id": event.frame_id,
                        "timestamp": event.timestamp,
                        "points": event.points,
                        "strength": event.strength,
                        "folded": event.folded,
                        "body_scale": event.body_scale,
                    }
                )
        return view

    def _infer(self):
        tracker = None
        try:
            from .tracking import Tracker

            self.status = "正在加载本地模型"
            tracker = Tracker()
            self.models_ready.set()
            version = 0
            while not self.stop_event.is_set():
                next_version, frame = self.frames.read(version, 0.1)
                if next_version == version or frame is None:
                    continue
                version = next_version
                started = time.perf_counter()
                features = tracker.process(frame.rgb, frame.captured, frame.frame_id)
                if features is None:
                    continue
                view = self._business(features, frame.rgb)
                completed = time.perf_counter()
                scene = ScenePacket(
                    frame,
                    features,
                    view,
                    (completed - started) * 1000.0,
                    completed,
                    "实时摄像头" if isinstance(self.source, int) else "视频回放",
                )
                if self.recorder:
                    self.recorder.tracking(
                        scene, tracker.timings, self.last_processed_controls, self.input_suppressed
                    )
                self.scenes.publish(scene)
                self.status = "运行中"
        except Exception as exc:
            logging.getLogger(__name__).exception("Inference failed")
            self.error = str(exc)
            self.status = f"识别停止：{exc}"
            self.stop_event.set()
        finally:
            if tracker:
                tracker.close()
            self.worker_shutdown["inference"] = time.perf_counter()

    def _demo(self):
        from .demo import sample

        start, frame_id = time.perf_counter(), 0
        mode_epoch, previous_mode = start, None
        try:
            while not self.stop_event.is_set():
                now = time.perf_counter()
                with self.control_lock:
                    mode = self.controls.mode
                if mode != previous_mode:
                    mode_epoch, previous_mode = now, mode
                rgb, features = sample(now - mode_epoch, now, frame_id, mode)
                # Demo follows the same rules, but inputs are constructed, never camera validation.
                view = self._business(features, rgb)
                rgb.flags.writeable = False
                frame = FramePacket(frame_id, now, now - start, rgb)
                self.scenes.publish(ScenePacket(frame, features, view, 0.0, now, "构造动作演示 · 非真人识别"))
                frame_id += 1
                self.status = "构造动作演示 · 非真人识别"
                self.stop_event.wait(1.0 / 30)
        except Exception as exc:
            self.status = f"演示停止：{exc}"
            self.stop_event.set()
