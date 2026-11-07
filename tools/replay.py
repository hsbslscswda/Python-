"""Replay opt-in JSONL keypoints through the pure engine; optional expected_state labels."""

import argparse
import json
from pathlib import Path

from mirror_moon.diagnostics import decode_features
from mirror_moon.interaction import Engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--mode", choices=("circle", "blade", "mirror"), default="circle")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    engine = Engine()
    engine.mode = args.mode
    results = []
    last_reset = 0
    for line in args.input.read_text("utf-8").splitlines():
        item = json.loads(line)
        if item.get("type") != "tracking":
            continue
        f = decode_features(item["features"])
        controls = item.get("controls") or {}
        reset = controls.get("reset_id", 0) != last_reset
        last_reset = controls.get("reset_id", 0)
        engine.circle.bent, engine.circle.extended = (
            controls.get("bent", 75.0),
            controls.get("extended", 160.0),
        )
        engine.circle.profiles = {
            side: (bent, extended) for side, bent, extended in controls.get("profiles", ())
        }
        if item.get("input_suppressed", False):
            view, events = engine.view, ()
        else:
            view, events = engine.update(
                f, controls.get("mode", args.mode), controls.get("paused", False), reset
            )
        expected = item.get("expected_state")
        if expected and expected != view.state:
            raise AssertionError(f"frame {f.frame_id}: expected {expected}, actual {view.state}")
        results.append(
            {
                "frame_id": f.frame_id,
                "state": view.state,
                "intensity": view.intensity,
                "events": [e.kind for e in events],
            }
        )
    data = {"input": str(args.input), "frames": len(results), "results": results}
    if args.output:
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    print(
        json.dumps(
            {"frames": len(results), "states": sorted({r["state"] for r in results})}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
