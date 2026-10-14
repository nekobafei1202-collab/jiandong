"""Push-up counting diagnostic on real stock videos.

Runs the desktop MediaPipe detector frame-by-frame, feeds PoseResults into
PushupRecognizer under multiple configs, at native fps and at the phone
bridge's ~12fps subsampling. The recognizer's wall-clock (datetime.now) is
patched to a fake clock advancing at the effective frame interval, so
min_state_duration_ms / min_rep_interval_ms behave exactly as on-device.

Usage:
    .venv/Scripts/python -m jiandong_ai.scripts.diagnose_pushup_count \
        _diag_videos/pushup_11545.mp4 [--truth N] [--verbose]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import cv2

from jiandong_ai.ai.action import pushup_recognizer as pr_mod
from jiandong_ai.ai.action.pushup_config import PushupConfig
from jiandong_ai.ai.action.pushup_recognizer import PushupRecognizer
from jiandong_ai.ai.pose.mediapipe_detector import MediaPipePoseDetector


class FakeClock:
    """datetime stand-in: now() advances by a fixed step per recognize() call."""

    def __init__(self, start: datetime, step_ms: float) -> None:
        self._now = start
        self._step = timedelta(milliseconds=step_ms)

    def advance(self) -> None:
        self._now += self._step

    def now(self, tz=None) -> datetime:  # noqa: ARG002 - match datetime.now signature
        return self._now


def extract_poses(video: Path, detector: MediaPipePoseDetector):
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    poses = []
    t0 = datetime(2026, 1, 1)
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        pose = detector.detect(frame, timestamp=t0 + timedelta(seconds=idx / fps))
        poses.append(pose)
        idx += 1
    cap.release()
    return fps, poses


def run_recognizer(poses, fps: float, target_fps: float, config: PushupConfig,
                   label: str, verbose: bool) -> dict:
    stride = max(1, round(fps / target_fps))
    step_ms = 1000.0 * stride / fps
    clock = FakeClock(datetime(2026, 1, 1), step_ms)
    real_datetime = pr_mod.datetime
    pr_mod.datetime = clock  # type: ignore[assignment]
    rec = PushupRecognizer(config=config)
    rows = []
    try:
        for i in range(0, len(poses), stride):
            pose = poses[i]
            clock.advance()
            res = rec.recognize(pose)
            rows.append({
                "frame": i,
                "t_ms": round(i / fps * 1000),
                "L": res.left_elbow_angle,
                "R": res.right_elbow_angle,
                "P": res.elbow_angle,
                "state": res.machine_state.name if res.machine_state else "-",
                "reps": res.rep_count,
                "just": res.just_completed_rep,
                "cue": res.form_cue,
                "pending": rec._pending_state.name if rec._pending_state else "-",
                "match": rec._match_frames,
                "reliable": res.has_reliable_pose,
            })
    finally:
        pr_mod.datetime = real_datetime  # type: ignore[assignment]

    final = rows[-1]["reps"] if rows else 0
    print(f"\n=== {label} | reps counted: {final} ===")
    if verbose:
        for r in rows:
            fmt = lambda v: f"{v:6.1f}" if isinstance(v, float) else "     -"
            mark = " <<< REP" if r["just"] else ""
            print(
                f"f{r['frame']:>4} t={r['t_ms']:>5}ms "
                f"L={fmt(r['L'])} R={fmt(r['R'])} P={fmt(r['P'])} "
                f"{r['state']:<15} pend={r['pending']:<8}x{r['match']} "
                f"reps={r['reps']} cue={r['cue'] or '-'}{mark}"
            )
    else:
        # compact elbow trace, one char per sampled frame
        lo, hi = 60.0, 180.0
        line = ""
        for r in rows:
            v = r["P"]
            if not isinstance(v, float):
                line += "?"
            else:
                line += str(max(0, min(9, int((v - lo) / (hi - lo) * 9.999))))
        print(f"primary-elbow trace (0={lo}deg .. 9={hi}deg, ?=unreliable):")
        print(line)
        for r in rows:
            if r["just"]:
                print(f"  REP #{r['reps']} at frame {r['frame']} (t={r['t_ms']}ms)")
    return {"label": label, "reps": final, "rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--truth", type=int, default=None, help="actual rep count")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--fps", type=float, nargs="*", default=[30.0, 12.0],
                    help="effective frame rates to simulate")
    args = ap.parse_args()

    detector = MediaPipePoseDetector()
    if not detector.available:
        raise SystemExit(f"detector unavailable: {detector.init_error}")
    fps, poses = extract_poses(args.video, detector)
    detector.close()
    n_rel = sum(1 for p in poses if p.detected)
    print(f"{args.video.name}: {len(poses)} frames @ {fps:.1f}fps, "
          f"reliable pose in {n_rel}/{len(poses)}")
    if args.truth is not None:
        print(f"ground truth reps: {args.truth}")

    configs = [
        ("strict(current)", PushupConfig()),
        ("lenient(old confirm=3,dur=120)", replace(
            PushupConfig.lenient(), state_confirm_frames=3,
            min_state_duration_ms=120)),
        ("lenient(fixed)", PushupConfig.lenient()),
    ]
    summary = []
    for tfps in args.fps:
        if tfps > fps + 0.5:
            continue
        for label, cfg in configs:
            out = run_recognizer(poses, fps, tfps, cfg,
                                 f"{label} @ {tfps:g}fps", args.verbose)
            summary.append((out["label"], tfps, out["reps"]))

    print("\n==== SUMMARY ====")
    if args.truth is not None:
        print(f"ground truth: {args.truth} reps")
    for label, tfps, reps in summary:
        print(f"{tfps:>5g}fps | {label:<26} -> {reps} reps")


if __name__ == "__main__":
    sys.exit(main())
