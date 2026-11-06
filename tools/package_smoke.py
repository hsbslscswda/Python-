"""Launch the actual onedir executable from a Chinese/space path outside its directory."""

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_missing_model(directory=None):
    directory = Path(directory or ROOT / "dist" / "MirrorMoon").resolve()
    model = (directory / "_internal" / "assets" / "models" / "hand_landmarker.task").resolve()
    assert model.is_relative_to(directory.resolve()) and model.is_file()
    backup = model.with_suffix(".task.validation-backup")
    assert not backup.exists()
    work = ROOT / "local" / "外部 启动路径"
    metric = work / "missing-model.json"
    model.rename(backup)
    try:
        completed = subprocess.run(
            [str(directory / "MirrorMoon.exe"), "--autostart", "--quit-after", "4", "--metrics", str(metric)],
            cwd=work,
            timeout=30,
            capture_output=True,
        )
        assert completed.returncode == 0 and metric.exists()
        value = json.loads(metric.read_text("utf-8"))
        assert "缺少模型" in (value["pipeline_error"] or "") and value["workers_closed_cleanly"], value
        (ROOT / "local" / "missing-model-smoke.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2), "utf-8"
        )
        return value
    finally:
        backup.rename(model)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", type=Path, default=ROOT / "dist" / "MirrorMoon")
    args = parser.parse_args()
    app_dir = args.app_dir.resolve()
    exe = app_dir / "MirrorMoon.exe"
    work = ROOT / "local" / "外部 启动路径"
    work.mkdir(exist_ok=True, parents=True)
    results = []
    env = os.environ.copy()
    windows = Path(os.environ["SystemRoot"])
    env["PATH"] = os.pathsep.join((str(windows / "System32"), str(windows)))
    cases = [
        ("demo", ["--demo", "--quit-after", "5"]),
        ("camera", ["--autostart", "--quit-after", "6"]),
        ("compat-mirror", ["--demo", "--compat", "--mode", "mirror", "--quit-after", "12"]),
        ("invalid-camera", ["--autostart", "--camera", "99", "--quit-after", "4"]),
    ]
    for name, arguments in cases:
        metric = work / f"{name}.json"
        completed = subprocess.run(
            [str(exe), *arguments, "--metrics", str(metric)],
            cwd=work,
            env=env,
            timeout=45,
            capture_output=True,
        )
        if completed.returncode != 0 or not metric.exists():
            raise RuntimeError(
                f"{name} failed: returncode={completed.returncode}, stderr={completed.stderr[-1000:]}"
            )
        value = json.loads(metric.read_text("utf-8"))
        assert value["workers_closed_cleanly"], value
        if name == "demo":
            assert value["renderer"].startswith("OpenGL"), value
            assert value["pipeline_error"] is None, value
        if name == "camera":
            assert (
                value["pipeline_error"] is None
                and value["paint_count"] > 0
                and value["paired_inference_hz"] > 0
            ), value
        if name == "compat-mirror":
            assert value["pipeline_error"] is None and value["events_emitted"].get("shatter", 0) > 0, value
        if name == "invalid-camera":
            assert "无法打开" in (value["pipeline_error"] or ""), value
        results.append(
            {
                "case": name,
                "exit_code": completed.returncode,
                "application_path_contains_chinese": any(ord(c) > 127 for c in str(app_dir)),
                "application_path_characters": len(str(exe)),
                "metrics": value,
            }
        )
        print(name, "passed", flush=True)
    (ROOT / "local" / "package-smoke.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), "utf-8"
    )
    test_missing_model(app_dir)
    print("missing-model passed", flush=True)


if __name__ == "__main__":
    main()
