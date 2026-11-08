"""Build/extract a real ZIP into a unique Chinese path, then run the camera without dev PATH."""

import argparse
import hashlib
import json
import subprocess
import uuid
import zipfile
from pathlib import Path

from package_smoke import isolated_env

from mirror_moon import __version__

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", type=Path, required=True)
    args = parser.parse_args()
    directory = args.app_dir.resolve()
    source_exe = directory / "MirrorMoon.exe"
    assert source_exe.is_file()
    scratch = (ROOT / "local" / ("中文 解压验证 " + uuid.uuid4().hex[:10])).resolve()
    assert scratch.is_relative_to((ROOT / "local").resolve()) and not scratch.exists()
    scratch.mkdir(parents=True)
    archive = scratch / "payload.zip"
    extract = scratch / "解压后"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for file in sorted(directory.rglob("*")):
            if file.is_file():
                z.write(file, Path(directory.name) / file.relative_to(directory))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name in z.namelist():
            assert (extract / name).resolve().is_relative_to(extract.resolve())
        z.extractall(extract)
    exe = extract / directory.name / "MirrorMoon.exe"
    expected = hashlib.sha256(source_exe.read_bytes()).hexdigest()
    assert hashlib.sha256(exe.read_bytes()).hexdigest() == expected
    metric = scratch / "metrics.json"
    completed = subprocess.run(
        [str(exe), "--autostart", "--diagnostics", "--quit-after", "6", "--metrics", str(metric)],
        cwd=ROOT / "local",
        env=isolated_env(),
        capture_output=True,
        timeout=45,
    )
    if completed.returncode != 0 or not metric.exists():
        raise RuntimeError(f"Extracted EXE failed: {completed.returncode}; {completed.stderr[-1000:]}")
    value = json.loads(metric.read_text("utf-8"))
    assert value["pipeline_error"] is None and value["paired_inference_hz"] > 0 and value["paint_count"] > 0
    assert value["workers_closed_cleanly"]
    result = {
        "version": __version__,
        "zip_extracted_before_test": True,
        "application_path_contains_chinese": any(ord(c) > 127 for c in str(exe)),
        "application_path_characters": len(str(exe)),
        "exe_matches_deliverable": True,
        "exe_sha256": expected,
        "camera_metrics": value,
        "images_saved": False,
        "human_actions_tested": False,
    }
    (ROOT / "local/extracted-package-smoke.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), "utf-8"
    )
    print(json.dumps({"passed": True, "version": __version__, "tracking_hz": value["paired_inference_hz"]}))


if __name__ == "__main__":
    main()
