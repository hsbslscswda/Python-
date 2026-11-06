"""Explicit provisioning; application runtime never downloads models."""

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "hand_landmarker.task": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    "pose_landmarker_lite.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
}


def main():
    directory = ROOT / "assets" / "models"
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    pinned = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}
    result = {}
    for name, url in MODELS.items():
        target = directory / name
        if not target.exists():
            temporary = target.with_suffix(".download")
            urllib.request.urlretrieve(url, temporary)
            temporary.replace(target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if name in pinned and digest != pinned[name]["sha256"]:
            raise RuntimeError(f"模型校验失败：{name}，请重新下载官方模型")
        result[name] = {"url": url, "sha256": digest, "bytes": target.stat().st_size, "version": "float16/1"}
        print(name, digest, flush=True)
    manifest_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
