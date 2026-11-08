import os
import sys
from pathlib import Path


def root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def user_dir() -> Path:
    directory = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local")) / "MirrorMoon"
    directory.mkdir(parents=True, exist_ok=True)
    return directory
