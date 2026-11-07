import math
import time
from collections import deque
from dataclasses import replace

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget

from .geometry import OneEuro
from .resources import root


def qimage(rgb):
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888)


def shard_mesh(event, size):
    """A bounded pre-cut triangle mesh. UVs retain the mirror's frozen camera content."""
    center, (radius, angle) = event.points[:2]
    rng = np.random.default_rng(event.seed)
    rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    out = []
    for y in range(6):
        for x in range(10):
            corners = np.array(
                [
                    (x / 5 - 1.0, y / 3 - 1.0),
                    ((x + 1) / 5 - 1.0, y / 3 - 1.0),
                    ((x + 1) / 5 - 1.0, (y + 1) / 3 - 1.0),
                    (x / 5 - 1.0, (y + 1) / 3 - 1.0),
                ]
            )
            corners *= (radius, radius * 0.66)
            for ids in ((0, 1, 2), (0, 2, 3)):
                local = corners[list(ids)]
                centroid = local.mean(axis=0)
                velocity = centroid * 0.9 + rng.normal(0.0, 40.0, 2)
                for p in local:
                    world = np.asarray(center) + rotation @ p
                    sample = np.asarray(center) + np.array([-p[0], p[1]])
                    out.append((*world, *(sample / size), *velocity))
    return np.asarray(out, dtype="f4")


class RenderState:
    def __init__(self):
        self.scene = None
        self.image = None
        self.mirrored = True
        self.element = "moon"
        self.quality = 1
        self.gain = 1.0
        self.debug = False
        self.slashes = []
        self.shatter = None
        self.last_event_id = 0
        self.last_frame_id = -1
        self.paint_times, self.data_ages = deque(maxlen=1800), deque(maxlen=1800)
        self.paint_stamps = deque(maxlen=1800)
        self.renderer_info = "兼容画质 · QPainter"
        self.recorder = None
        self.anchor_filters = [OneEuro(2.0, 0.01) for _ in range(3)]

    def accept(self, scene):
        if self.scene and scene.spell.mode != self.scene.spell.mode:
            self.reset_effects()
            self.anchor_filters = [OneEuro(2.0, 0.01) for _ in range(3)]
        x, y = scene.spell.center
        radius = scene.spell.radius
        t = scene.features.timestamp
        view = replace(
            scene.spell,
            center=(self.anchor_filters[0](x, t), self.anchor_filters[1](y, t)),
            radius=self.anchor_filters[2](radius, t),
        )
        self.scene, self.image = replace(scene, spell=view), qimage(scene.frame.rgb)

    def reset_effects(self):
        self.slashes.clear()
        self.shatter = None

    def events(self, events):
        for e in events:
            if e.event_id <= self.last_event_id:
                continue
            self.last_event_id = e.event_id
            if e.kind in ("slash", "double", "cross"):
                self.slashes.append(e)
                self.slashes = self.slashes[-8:]
            elif e.kind == "shatter" and e.image is not None:
                self.shatter = e

    def record(self, started):
        now = time.perf_counter()
        self.paint_times.append((now - started) * 1000)
        self.paint_stamps.append(now)
        if self.scene and self.scene.frame.frame_id != self.last_frame_id:
            self.last_frame_id = self.scene.frame.frame_id
            self.data_ages.append((now - self.scene.frame.captured) * 1000)
            if self.recorder:
                self.recorder.write(
                    {
                        "type": "render",
                        "frame_id": self.last_frame_id,
                        "submitted": now,
                        "data_age_ms": self.data_ages[-1],
                        "renderer": self.renderer_info,
                    }
                )

    def metrics(self):
        stamps = list(self.paint_stamps)
        fps = (len(stamps) - 1) / (stamps[-1] - stamps[0]) if len(stamps) > 1 else 0.0
        return {
            "renderer": self.renderer_info,
            "render_fps": round(fps, 2),
            "paint_cpu_p95_ms": round(float(np.percentile(self.paint_times, 95)), 2)
            if self.paint_times
            else None,
            "capture_to_first_paint_p95_ms": round(float(np.percentile(self.data_ages, 95)), 2)
            if self.data_ages
            else None,
            "paint_count": len(stamps),
            "frame_interval_p95_ms": round(float(np.percentile(np.diff(stamps) * 1000.0, 95)), 2)
            if len(stamps) > 1
            else None,
        }


class GLStage(QOpenGLWidget):
    failed = Signal(str)

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.ctx = None
        self.camera_texture = self.frozen_texture = None
        self.shard_vbo = self.shard_vao = None
        self.frame_id = self.frozen_id = -1
        self.target = None
        self.target_key = None
        self.error = None
        self.post_resources = []
        self.post_size = None
        self.setMinimumSize(640, 360)

    def initializeGL(self):
        try:
            import moderngl

            self.ctx = moderngl.create_context(require=330)
            self.ctx.gc_mode = "auto"
            directory = root() / "assets"
            self.program = self.ctx.program(
                vertex_shader=(directory / "stage.vert").read_text(),
                fragment_shader=(directory / "stage.frag").read_text(),
            )
            vertices = np.array([-1, -1, 0, 1, 1, -1, 1, 1, -1, 1, 0, 0, 1, 1, 1, 0], dtype="f4")
            self.vbo = self.ctx.buffer(vertices.tobytes())
            self.vao = self.ctx.vertex_array(self.program, [(self.vbo, "2f 2f", "in_position", "in_uv")])
            self.shard_program = self.ctx.program(
                vertex_shader=(directory / "shards.vert").read_text(),
                fragment_shader=(directory / "shards.frag").read_text(),
            )
            self.blur_program = self.ctx.program(
                vertex_shader=(directory / "stage.vert").read_text(),
                fragment_shader=(directory / "blur.frag").read_text(),
            )
            self.compose_program = self.ctx.program(
                vertex_shader=(directory / "stage.vert").read_text(),
                fragment_shader=(directory / "compose.frag").read_text(),
            )
            self.blur_vao = self.ctx.vertex_array(
                self.blur_program, [(self.vbo, "2f 2f", "in_position", "in_uv")]
            )
            self.compose_vao = self.ctx.vertex_array(
                self.compose_program, [(self.vbo, "2f 2f", "in_position", "in_uv")]
            )
            self.blur_program["input_tex"].value = 2
            self.compose_program["scene_tex"].value = 2
            self.compose_program["bloom_tex"].value = 3
            self.program["camera_tex"].value = 0
            self.shard_program["frozen_tex"].value = 1
            self.context().aboutToBeDestroyed.connect(self.shutdown)
            self.data.renderer_info = (
                f"OpenGL {self.ctx.version_code / 100:.2f} · {self.ctx.info['GL_RENDERER']}"
            )
        except Exception as exc:
            from PySide6.QtCore import QTimer

            self.error = f"OpenGL 初始化失败，已切换兼容画质：{exc}"
            QTimer.singleShot(0, lambda: self.failed.emit(self.error))

    def paintGL(self):
        if not self.ctx or self.error:
            return
        started = time.perf_counter()
        try:
            import moderngl

            # Qt owns this framebuffer and changes it after resize. Never bind framebuffer 0.
            key = (
                self.defaultFramebufferObject(),
                round(self.width() * self.devicePixelRatioF()),
                round(self.height() * self.devicePixelRatioF()),
            )
            if self.target_key != key:
                self.target = self.ctx.detect_framebuffer(glo=key[0])
                self.target_key = key
            self.target.use()
            self.ctx.viewport = (0, 0, key[1], key[2])
            self.ctx.disable(moderngl.BLEND | moderngl.DEPTH_TEST)
            self.ctx.clear(0.025, 0.045, 0.065, 1.0)
            scene, d = self.data.scene, self.data
            if scene is None:
                return
            if d.quality > 0:
                self._ensure_post((key[1], key[2]))
                self.scene_fbo.use()
                self.ctx.viewport = (0, 0, key[1], key[2])
            rgb, spell, f = scene.frame.rgb, scene.spell, scene.features
            if self.frame_id != scene.frame.frame_id:
                size = (rgb.shape[1], rgb.shape[0])
                if self.camera_texture is None or self.camera_texture.size != size:
                    if self.camera_texture:
                        self.camera_texture.release()
                    self.camera_texture = self.ctx.texture(size, 3)
                    self.camera_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
                self.camera_texture.write(rgb.tobytes(), alignment=1)
                self.frame_id = scene.frame.frame_id
            self.camera_texture.use(0)
            values = {
                "viewport": (key[1], key[2]),
                "source_size": (f.width, f.height),
                "center": spell.center,
                "palm": f.arm(spell.caster).wrist if spell.caster else f.chest,
                "chest": f.chest,
                "shoulder": f.scale,
                "radius": spell.radius,
                "time": started % 4096,
                "visibility": spell.visibility,
                "intensity": spell.intensity,
                "migration": spell.migration,
                "mirror_angle": spell.mirror_angle,
                "mode": {"circle": 0, "blade": 1, "mirror": 2}[spell.mode],
                "mirrored": int(d.mirrored),
                "lightning": int(d.element == "lightning"),
                "folded": int(spell.folded),
                "effect_gain": d.gain,
                "quality": d.quality,
            }
            for name, value in values.items():
                self.program[name].value = value
            live = [e for e in d.slashes if started - e.timestamp < 0.80]
            d.slashes = live
            paths, params = np.zeros((8, 4), "f4"), np.zeros((8, 2), "f4")
            for i, event in enumerate(live):
                paths[i] = (*event.points[0], *event.points[-1])
                params[i] = (started - event.timestamp, event.strength)
            self.program["slash_count"].value = len(live)
            self.program["slashes"].write(paths.tobytes())
            self.program["slash_data"].write(params.tobytes())
            self.vao.render(moderngl.TRIANGLE_STRIP)
            if d.quality > 0:
                self.emission_tex.use(2)
                self.blur_a.use()
                self.ctx.viewport = (0, 0, *self.blur_tex_a.size)
                self.blur_program["step_uv"].value = (2.0 / key[1], 0.0)
                self.blur_vao.render(moderngl.TRIANGLE_STRIP)
                self.blur_tex_a.use(2)
                self.blur_b.use()
                self.blur_program["step_uv"].value = (0.0, 1.0 / self.blur_tex_a.size[1])
                self.blur_vao.render(moderngl.TRIANGLE_STRIP)
                self.target.use()
                self.ctx.viewport = (0, 0, key[1], key[2])
                self.scene_tex.use(2)
                self.blur_tex_b.use(3)
                self.compose_program["gain"].value = 0.3 if d.quality == 1 else 0.48
                self.compose_vao.render(moderngl.TRIANGLE_STRIP)
            event = d.shatter
            if event and started - event.timestamp < 0.85:
                if event.event_id != self.frozen_id:
                    self._prepare_shards(event)
                self.frozen_texture.use(1)
                for name, value in {
                    "viewport": (key[1], key[2]),
                    "source_size": (f.width, f.height),
                    "age": started - event.timestamp,
                    "mirrored": int(d.mirrored),
                }.items():
                    self.shard_program[name].value = value
                self.ctx.enable(moderngl.BLEND)
                self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
                self.shard_vao.render(moderngl.TRIANGLES)
                self.ctx.disable(moderngl.BLEND)
            elif event:
                d.shatter = None
            if d.debug:
                painter = QPainter(self)
                draw_debug(painter, d, self.width(), self.height())
                painter.end()
            d.record(started)
        except Exception as exc:
            self.error = f"OpenGL 绘制失败，切换兼容画质：{exc}"
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, lambda: self.failed.emit(self.error))

    def _ensure_post(self, size):
        if self.post_size == size:
            return
        for obj in self.post_resources:
            obj.release()
        self.scene_tex = self.ctx.texture(size, 4)
        self.emission_tex = self.ctx.texture(size, 4)
        self.scene_fbo = self.ctx.framebuffer([self.scene_tex, self.emission_tex])
        half = (max(1, size[0] // 2), max(1, size[1] // 2))
        self.blur_tex_a = self.ctx.texture(half, 4)
        self.blur_tex_b = self.ctx.texture(half, 4)
        self.blur_a = self.ctx.framebuffer([self.blur_tex_a])
        self.blur_b = self.ctx.framebuffer([self.blur_tex_b])
        self.post_resources = [
            self.scene_fbo,
            self.blur_a,
            self.blur_b,
            self.scene_tex,
            self.emission_tex,
            self.blur_tex_a,
            self.blur_tex_b,
        ]
        self.post_size = size

    def _prepare_shards(self, event):
        for obj in (self.shard_vao, self.shard_vbo, self.frozen_texture):
            if obj:
                obj.release()
        image = event.image
        size = (image.shape[1], image.shape[0])
        self.frozen_texture = self.ctx.texture(size, 3, image.tobytes(), alignment=1)
        mesh = shard_mesh(event, np.asarray(size))
        self.shard_vbo = self.ctx.buffer(mesh.tobytes())
        self.shard_vao = self.ctx.vertex_array(
            self.shard_program, [(self.shard_vbo, "2f 2f 2f", "in_point", "in_uv", "in_velocity")]
        )
        self.frozen_id = event.event_id

    def shutdown(self):
        if not self.ctx:
            return
        self.makeCurrent()
        for obj in self.post_resources:
            obj.release()
        self.post_resources = []
        for name in (
            "shard_vao",
            "shard_vbo",
            "frozen_texture",
            "camera_texture",
            "vao",
            "vbo",
            "program",
            "shard_program",
            "blur_vao",
            "compose_vao",
            "blur_program",
            "compose_program",
        ):
            obj = getattr(self, name, None)
            if obj:
                obj.release()
                setattr(self, name, None)
        # Detected Qt FBO is not ours to destroy.
        self.target = None
        self.ctx.release()
        self.ctx = None
        self.doneCurrent()


def source_transform(painter, data, width, height):
    f = data.scene.features
    scale = min(width / f.width, height / f.height)
    painter.translate((width - f.width * scale) / 2, (height - f.height * scale) / 2)
    painter.scale(scale, scale)
    if data.mirrored:
        painter.translate(f.width, 0)
        painter.scale(-1, 1)


def draw_debug(painter, data, width, height):
    painter.save()
    source_transform(painter, data, width, height)
    painter.setPen(QPen(QColor("#d9c69d"), 2))
    for arm in data.scene.features.arms:
        if arm.tracked:
            painter.drawLine(QPointF(*arm.shoulder), QPointF(*arm.elbow))
            painter.drawLine(QPointF(*arm.elbow), QPointF(*arm.wrist))
        for point in arm.landmarks:
            painter.drawEllipse(QPointF(*point), 2, 2)
    painter.restore()


class PainterStage(QWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setMinimumSize(640, 360)
        self.mesh_event = None
        self.mesh = None

    def paintEvent(self, event):
        started = time.perf_counter()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#08131d"))
        d = self.data
        if d.scene:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.save()
            source_transform(p, d, self.width(), self.height())
            p.drawImage(0, 0, d.image)
            view = d.scene.spell
            color = QColor("#abc4ff" if d.element == "lightning" else "#b1e3f9")
            color.setAlphaF(min(1.0, view.visibility * d.gain))
            p.setPen(QPen(color, 3.5))
            p.setBrush(QColor(0, 0, 0, 0))
            if view.mode == "circle" and view.visibility:
                radius = min(view.radius, d.scene.features.height * 0.46)
                for ratio in (1.0, 0.92, 0.80, 0.57):
                    r = radius * ratio
                    p.drawEllipse(QPointF(*view.center), r, r)
                for offset in (0.0, math.pi / 3):
                    vertices = [
                        QPointF(
                            view.center[0] + radius * 0.70 * math.cos(offset + i * math.tau / 3),
                            view.center[1] + radius * 0.70 * math.sin(offset + i * math.tau / 3),
                        )
                        for i in range(3)
                    ]
                    p.drawPolygon(QPolygonF(vertices))
                for i in range(32):
                    a = i * math.tau / 32 + started * 0.05
                    r = radius * 0.86
                    p.drawLine(
                        QPointF(view.center[0] + r * math.cos(a), view.center[1] + r * math.sin(a)),
                        QPointF(
                            view.center[0] + (r + 9) * math.cos(a), view.center[1] + (r + 9) * math.sin(a)
                        ),
                    )
                if view.intensity:
                    wrist = d.scene.features.arm(view.caster).wrist
                    for i in range(3 if view.migration > 0.5 else 1):
                        r = 18 + 50 * view.intensity + i * 18
                        p.drawEllipse(QPointF(wrist[0], wrist[1] - i * 18), r, r * 0.75)
            elif view.mode == "mirror" and view.visibility:
                p.save()
                p.translate(*view.center)
                p.rotate(math.degrees(view.mirror_angle))
                p.setOpacity(view.visibility)
                rect = QRectF(-view.radius, -view.radius * 0.66, view.radius * 2, view.radius * 1.32)
                crop = QRectF(
                    view.center[0] - view.radius,
                    view.center[1] - view.radius * 0.66,
                    view.radius * 2,
                    view.radius * 1.32,
                )
                p.save()
                p.scale(-1, 1)
                p.drawImage(rect, d.image, crop)
                p.restore()
                p.drawRect(rect)
                if view.folded:
                    for i in range(3):
                        p.rotate(60)
                        p.setOpacity(view.visibility * 0.22)
                        p.drawImage(rect, d.image, crop)
                p.restore()
            for e in d.slashes:
                age = started - e.timestamp
                if age < 0.80:
                    c = QColor("#d1efff")
                    c.setAlphaF(max(0.0, 1.0 - age / 0.80))
                    p.setPen(QPen(c, 7.0 + e.strength * 5.0))
                    p.drawPolyline(QPolygonF([QPointF(*pt) for pt in e.points]))
            d.slashes = [e for e in d.slashes if started - e.timestamp < 0.80]
            e = d.shatter
            if e and started - e.timestamp < 0.85:
                if self.mesh_event != e.event_id:
                    self.mesh = shard_mesh(e, np.array((e.image.shape[1], e.image.shape[0]))).reshape(
                        -1, 3, 6
                    )
                    self.mesh_event = e.event_id
                age = started - e.timestamp
                frozen = qimage(e.image)
                p.setOpacity(max(0.0, 1.0 - age / 0.85))
                for tri in self.mesh:
                    moved = tri[:, :2] + tri[:, 4:6] * age + (0.0, 200.0 * age * age)
                    path = QPainterPath()
                    path.addPolygon(QPolygonF([QPointF(float(a), float(b)) for a, b in moved]))
                    p.save()
                    p.setClipPath(path)
                    # Map the frozen mirror image to each moving triangle's UV coordinates.
                    from PySide6.QtGui import QTransform

                    source = QPolygonF(
                        [
                            QPointF(float(a * e.image.shape[1]), float(b * e.image.shape[0]))
                            for a, b in tri[:, 2:4]
                        ]
                    )
                    target = QPolygonF([QPointF(float(a), float(b)) for a, b in moved])
                    source.append(source[2] + source[1] - source[0])
                    target.append(target[2] + target[1] - target[0])
                    transform = QTransform()
                    if QTransform.quadToQuad(source, target, transform):
                        p.setTransform(transform, True)
                        p.drawImage(0, 0, frozen)
                    p.restore()
                p.setOpacity(1.0)
            p.restore()
            if d.debug:
                draw_debug(p, d, self.width(), self.height())
            d.record(started)
        p.end()

    def shutdown(self):
        self.data.reset_effects()
