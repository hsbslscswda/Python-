"""Synthetic angle response versus the fixed v0.2.0 controller. No human motion claims."""

import json
import math
import subprocess
import types
from pathlib import Path

from mirror_moon.control import IntensityController

ROOT = Path(__file__).resolve().parents[1]


def measure(factory):
    dt = 1 / 15
    c = factory()
    for i in range(15):
        c.update(75.0, i * dt)
    rise = None
    for i in range(1, 31):
        value = c.update(160.0, 1 + i * dt)
        if value >= 0.9 and rise is None:
            rise = round(i * dt * 1000, 1)
    c = factory()
    values = []
    for i in range(120):
        angle = None if i % 3 in (1, 2) else 120.0 + 4.0 * math.sin(i * 0.7)
        value = c.update(angle, i * dt)
        if i >= 30:
            values.append(value)
    return {
        "rise_to_90_percent_ms": rise,
        "steady_dropouts_output_range": round(max(values) - min(values), 4),
        "steady_dropouts_max_adjacent_jump": round(max(abs(b - a) for a, b in zip(values, values[1:])), 4),
    }


def main():
    code = subprocess.check_output(["git", "show", "ac1e4ba:src/mirror_moon/control.py"], cwd=ROOT).decode(
        "utf-8"
    )
    module = types.ModuleType("mirror_moon._v020_control")
    module.__package__ = "mirror_moon"
    exec(compile(code, "v0.2.0_control.py", "exec"), module.__dict__)
    report = {
        "synthetic_only": True,
        "sample_hz": 15,
        "baseline_commit": "ac1e4ba9b842d915dc05b10e9563a1f5aa33198f",
        "baseline": measure(module.IntensityController),
        "candidate": measure(IntensityController),
        "limitation": "Injected angle sequences only; no MediaPipe accuracy, calibrated user actions or end-to-end latency measured",
    }
    (ROOT / "local/control-bench.json").write_text(json.dumps(report, indent=2), "utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
