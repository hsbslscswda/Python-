"""Real GL checks with deterministic synthetic textures; never uses the camera."""

import argparse
import json
import math
import time
from pathlib import Path

import cv2
import moderngl
import numpy as np
from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat

from mirror_moon.mirror_texture import MIRROR_ASPECT, mirror_texture

ROOT = Path(__file__).resolve().parents[1]
VERTEX = """#version 330
in vec2 position; out vec2 uv;
void main() { gl_Position=vec4(position,0,1); uv=position*0.5+0.5; }
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "local/shader-probe")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication([])
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    native = QOpenGLContext()
    native.setFormat(fmt)
    assert native.create() and native.makeCurrent(surface)
    ctx = moderngl.create_context(require=330)
    source = (ROOT / "assets/stage.frag").read_text("utf-8")
    vertices = np.array((-1, -1, 1, -1, -1, 1, 1, 1), dtype="f4")

    def draw(fragment, rgb, size, timings=None, **overrides):
        program = ctx.program(vertex_shader=VERTEX, fragment_shader=fragment)
        buffer = ctx.buffer(vertices.tobytes())
        vao = ctx.vertex_array(program, [(buffer, "2f", "position")])
        texture = ctx.texture((rgb.shape[1], rgb.shape[0]), 3, rgb.tobytes(), alignment=1)
        texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        colors = [ctx.texture(size, 4) for _ in range(2)]
        fbo = ctx.framebuffer(color_attachments=colors)
        fbo.use()
        ctx.viewport = (0, 0, *size)
        ctx.disable(moderngl.BLEND | moderngl.DEPTH_TEST)
        texture.use(0)
        values = dict(
            camera_tex=0,
            viewport=size,
            source_size=(rgb.shape[1], rgb.shape[0]),
            center=(320.0, 180.0),
            palm=(400.0, 200.0),
            chest=(320.0, 180.0),
            shoulder=100.0,
            radius=140.0,
            time=12.0,
            visibility=1.0,
            intensity=0.0,
            migration=0.0,
            mirror_angle=0.0,
            mode=0,
            mirrored=0,
            lightning=0,
            folded=0,
            effect_gain=1.15,
            quality=0,
            body_yaw=0.0,
            mirror_time=12.0,
            slash_count=0,
            mirror_closing=0,
            object_count=0,
            cast_direction=(0.25, -0.10, -1.0),
        )
        values.update(overrides)
        for name, value in values.items():
            if name in program:
                program[name].value = value
        if timings is not None:
            for _ in range(3):
                vao.render(moderngl.TRIANGLE_STRIP)
                ctx.finish()
            samples = []
            for _ in range(12):
                started = time.perf_counter()
                vao.render(moderngl.TRIANGLE_STRIP)
                ctx.finish()
                samples.append((time.perf_counter() - started) * 1000)
            timings.update(
                p50_ms=float(np.median(samples)), p95_ms=float(np.percentile(samples, 95)), samples_ms=samples
            )
        vao.render(moderngl.TRIANGLE_STRIP)
        pixels = (
            np.frombuffer(fbo.read(components=3, alignment=1), dtype="uint8")
            .reshape(size[1], size[0], 3)
            .copy()
        )
        for resource in (vao, buffer, fbo, *colors, texture, program):
            resource.release()
        return pixels

    flat = np.full((360, 640, 3), (24, 37, 54), dtype="uint8")
    current = draw(source, flat, (640, 360))
    cv2.imwrite(str(args.output / "array-after.png"), cv2.cvtColor(current, cv2.COLOR_RGB2BGR))
    report = {"synthetic_only": True, "renderer": ctx.info["GL_RENDERER"]}
    if args.comparison:
        before = draw(args.comparison.read_text("utf-8"), flat, (640, 360))
        cv2.imwrite(str(args.output / "array-before.png"), cv2.cvtColor(before, cv2.COLOR_RGB2BGR))
        white_before = float(np.mean(np.all(before >= 245, axis=-1)))
        white_after = float(np.mean(np.all(current >= 245, axis=-1)))
        report["fixed_input_near_white_fraction"] = {"before": white_before, "after": white_after}
        assert white_after <= max(white_before * 1.10, 0.001), report

    # Sample the complete current mirror fragment on exactly the CPU patch's grid.
    # Exclude its exterior frame; frozen shards retain the mirror interior image.
    original = "vec2 px = uv * viewport;"
    assert source.count(original) == 1
    patch = source.replace(
        original,
        """vec2 patchQ = (gl_FragCoord.xy-vec2(0.5)) / (viewport-vec2(1.0));
    patchQ = (patchQ-vec2(0.5))*vec2(radius*2.0,radius*1.36);
    float patchFit = min(viewport.x/source_size.x, viewport.y/source_size.y);
    vec2 rawPoint = center + rot(-mirror_angle)*patchQ;
    if (mirrored == 1) rawPoint.x = source_size.x - rawPoint.x;
    vec2 px = rawPoint*patchFit + (viewport-source_size*patchFit)*0.5;""",
    )
    y, x = np.mgrid[:360, :640]
    rgb = np.stack((40 + x / 5, 30 + y / 3, 60 + (x + y) / 8), axis=-1).astype("uint8")
    rows = []
    for test_radius in (12.0, 120.0, 360.0):
        for mirrored in (False, True):
            for folded in (False, True):
                for angle in (0.0, 0.8):
                    cpu = mirror_texture(rgb, (320.0, 180.0), test_radius, angle, folded, 100.0, 12.0)
                    h, w = cpu.shape[:2]
                    gpu = draw(
                        patch,
                        rgb,
                        (w, h),
                        mode=2,
                        radius=test_radius,
                        mirror_angle=angle,
                        folded=int(folded),
                        mirrored=int(mirrored),
                    )
                    px, py = np.meshgrid(
                        np.linspace(-test_radius, test_radius, w),
                        np.linspace(-test_radius * MIRROR_ASPECT, test_radius * MIRROR_ASPECT, h),
                    )
                    interior = (
                        np.maximum(abs(px) - test_radius, abs(py) - test_radius * MIRROR_ASPECT)
                        < -min(35, test_radius * 0.28)
                    ) & (abs(px) / test_radius + abs(py) / (test_radius * MIRROR_ASPECT) < 1.45)
                    # A large/rotated mirror extends off camera; only displayed fragments can be compared.
                    world_x = 320.0 + math.cos(angle) * px - math.sin(angle) * py
                    world_y = 180.0 + math.sin(angle) * px + math.cos(angle) * py
                    interior &= (world_x > 1) & (world_x < 639) & (world_y > 1) & (world_y < 359)
                    error = np.abs(cpu.astype("float32") - gpu.astype("float32"))[interior]
                    median, p95 = float(np.median(error)), float(np.percentile(error, 95))
                    rows.append(
                        {
                            "radius": test_radius,
                            "mirrored": mirrored,
                            "folded": folded,
                            "angle": angle,
                            "channel_error_median": median,
                            "channel_error_p95": p95,
                        }
                    )
                    assert median <= 2.0 and p95 <= 5.0, rows
    report["cpu_gl_mirror_interior_parity"] = rows
    if args.comparison:
        runs = []
        for quality in (0, 1, 2):
            for label, fragment in (("v0.4.2", args.comparison.read_text("utf-8")), ("v0.4.3", source)):
                timing = {"version": label, "quality": quality}
                draw(
                    fragment,
                    flat,
                    (1280, 720),
                    timings=timing,
                    intensity=1.4,
                    migration=0.65,
                    quality=quality,
                )
                runs.append(timing)
        report["serialized_stage_draw_1280x720"] = {
            "method": "3 warmups + 12 draws, ctx.finish; excludes compile, Qt, camera, postprocessing; not displayed FPS",
            "runs": runs,
        }
    (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(report))
    ctx.release()
    native.doneCurrent()
    surface.destroy()
    app.quit()


if __name__ == "__main__":
    main()
