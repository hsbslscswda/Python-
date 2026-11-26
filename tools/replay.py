"""Replay recorded keypoints and compare spell states with the original log."""

import argparse
import json
from pathlib import Path

from mirror_moon import __version__
from mirror_moon.diagnostics import decode_features
from mirror_moon.interaction import Engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--mode", choices=("circle", "blade", "mirror", "water", "fire"), default="circle",
        help="fallback for records without a mode in their controls",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    engine = None
    results = []
    last_reset = 0
    previous_frame_id = -1
    sessions = recorded_frames = recorded_state_differences = 0
    recorded_version = None
    with args.input.open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            if item.get("type") == "header":
                recorded_version = item.get("app_version")
            if item.get("type") != "tracking":
                continue
            f = decode_features(item["features"])
            controls = item.get("controls") or {}
            # The recorder can stay open while a preview restart creates a new Pipeline.
            if engine is None or f.frame_id < previous_frame_id:
                engine = Engine()
                if "mode" not in controls:
                    engine.mode = args.mode
                last_reset = 0
                sessions += 1
            previous_frame_id = f.frame_id
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
                raise AssertionError(
                    f"session {sessions}, frame {f.frame_id}: expected {expected}, actual {view.state}"
                )
            result = {
                "session": sessions,
                "frame_id": f.frame_id,
                "timestamp": f.timestamp,
                "mode": view.mode,
                "state": view.state,
                "intensity": view.intensity,
                "events": [e.kind for e in events],
            }
            recorded = item.get("spell") or {}
            if "mode" in recorded and "state" in recorded:
                result["recorded_mode"] = recorded["mode"]
                result["recorded_state"] = recorded["state"]
                recorded_frames += 1
                if (recorded["mode"], recorded["state"]) != (view.mode, view.state):
                    recorded_state_differences += 1
            results.append(result)
    summary = {
        "frames": len(results),
        "states": sorted({r["state"] for r in results}),
        "sessions": sessions,
        "recorded_version": recorded_version,
        "replay_version": __version__,
        "recorded_frames": recorded_frames,
        "recorded_state_differences": recorded_state_differences,
    }
    if args.output:
        data = {"input": str(args.input), **summary, "results": results}
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
