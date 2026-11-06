"""Build a dynamically linked Qt onedir bundle; preserve third-party licenses."""

import json
import os
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    assert (ROOT / "dist" / "MirrorMoon").resolve().is_relative_to(ROOT.resolve())
    subprocess.run([sys.executable, str(ROOT / "tools" / "prepare_models.py")], check=True, cwd=ROOT)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "MirrorMoon",
        "--paths",
        str(ROOT / "src"),
        "--add-data",
        f"{ROOT / 'assets'};assets",
        "--collect-all",
        "mediapipe",
        "--collect-all",
        "glcontext",
        "--exclude-module",
        "PySide6.QtWebEngineCore",
        "--exclude-module",
        "PySide6.QtQml",
        "--exclude-module",
        "pytest",
        str(ROOT / "run.py"),
    ]
    environment = os.environ.copy()
    windows = Path(os.environ["SystemRoot"])
    # Do not collect unrelated Anaconda/Qt/ICU DLLs from this machine's global PATH.
    environment["PATH"] = os.pathsep.join(
        (str(Path(sys.executable).parent), str(windows / "System32"), str(windows))
    )
    environment["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "local" / "pyinstaller-cache")
    subprocess.run(command, check=True, cwd=ROOT, env=environment)
    target = ROOT / "dist" / "MirrorMoon"
    licenses = target / "THIRD_PARTY_LICENSES"
    licenses.mkdir(exist_ok=True)
    packages = []
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if name.lower() in (
            "mirror-moon",
            "ruff",
            "pytest",
            "iniconfig",
            "pluggy",
            "pygments",
            "pyinstaller-hooks-contrib",
            "psutil",
        ):
            continue
        packages.append(
            {
                "name": name,
                "version": dist.version,
                "license": dist.metadata.get("License-Expression") or dist.metadata.get("License"),
            }
        )
        for entry in dist.files or []:
            text = str(entry).lower()
            if (
                "license" in text or "copying" in text or text.endswith("notice")
            ) and entry.suffix.lower() in (".txt", ".md", ".rst", ""):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    output = licenses / name / str(entry).replace("..", "_")
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, output)
    (licenses / "packages.json").write_text(json.dumps(packages, ensure_ascii=False, indent=2), "utf-8")
    for filename in ("README.md", "THIRD_PARTY_NOTICES.md"):
        if (ROOT / filename).exists():
            shutil.copy2(ROOT / filename, target / filename)
    print(target, flush=True)


if __name__ == "__main__":
    main()
