"""Crunch counting diagnostic on real stock videos.

Mirrors diagnose_pushup_count.py: desktop MediaPipe frame-by-frame →
PoseResult → CrunchRecognizer, at native fps and at the phone bridge's
~12fps subsampling. Crunch timing uses pose.timestamp (set from the effective
frame interval here), so 12fps simulation is exact — no clock patching.

Usage:
    .venv/Scripts/python -m jiandong_ai.scripts.diagnose_crunch_count \
        _diag_videos/crunch_4591.mp4 [--truth N] [--verbose]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import cv2

from jiandong_ai.ai.action.crunch_config import CrunchConfig
from jiandong_ai.ai.action.crunch_recognizer import CrunchRecognizer
from jiandong_ai.ai.pose.mediapipe_detector import MediaPipePoseDetector


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
        poses.append(detector.detect(frame, timestamp=t0 + timedelta(seconds=idx / fps)))
        idx += 1
    cap.release()
    return fps, poses


def run_recognizer(poses, fps: float, target_fps: float, config: CrunchConfig,
                   label: str, verbose: bool) -> dict:
    stride = max(1, round(fps / target_fps))
    step_ms = 1000.0 * stride / fps
    rec = CrunchRecognizer(config=config)
    rows = []
    t0 = datetime(2026, 1, 1)
    for i in range(0, len(poses), stride):
        pose = poses[i]
        # re-time to the effective frame cadence (bridge timestamps at 12fps)
        pose.timestamp = t0 + timedelta(milliseconds=step_ms * (i // stride))
        res = rec.recognize(pose)
        shoulder = pose.left_shoulder or pose.right_shoulder
        rows.append({
            "frame": i,
            "t_ms": round(i / fps * 1000),
            "torso": res.knee_angle,  # crunch maps torso angle onto knee_angle
            "sh_y": shoulder.y if shoulder else None,
            "state": res.machine_state.name if res.machine_state else "-",
            "reps": res.rep_count,
            "just": res.just_completed_rep,
            "cue": res.form_cue,
            "reliable": res.has_reliable_pose,
        })

    final = rows[-1]["reps"] if rows else 0
    print(f"\n=== {label} | reps counted: {final} ===")
    if verbose:
        for r in rows:
            fmt = lambda v: f"{v:6.1f}" if isinstance(v, float) else "     -"
            mark = " <<< REP" if r["just"] else ""
            print(
                f"f{r['frame']:>4} t={r['t_ms']:>5}ms "
                f"torso={fmt(r['torso'])} sh_y={fmt(r['sh_y'])} "
                f"{r['state']:<15} reps={r['reps']} cue={r['cue'] or '-'}{mark}"
            )
    else:
        lo, hi = 40.0, 170.0
        line = ""
        for r in rows:
            v = r["torso"]
            if not isinstance(v, float):
                line += "?"
            else:
                line += str(max(0, min(9, int((v - lo) / (hi - lo) * 9.999))))
        print(f"torso-angle trace (0={lo}deg .. 9={hi}deg, ?=unreliable):")
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
    ap.add_argument("--fps", type=float, nargs="*", default=[30.0, 12.0])
    args = ap.parse_args()

    detector = MediaPipePoseDetector()
    if not detector.available:
        raise SystemExit(f"detector unavailable: {detector.init_error}")
    fps, poses = extract_poses(args.video, detector)
    detector.close()
    n_rel = sum(1 for p in poses if p.detected)
    print(f"{args.video.name}: {len(poses)} frames @ {fps:.1f}fps, "
          f"detected in {n_rel}/{len(poses)}")
    if args.truth is not None:
        print(f"ground truth reps: {args.truth}")

    configs = [
        ("crunch(fixed)", CrunchConfig()),
        # 修复前阈值（仍带新加的中值平滑，仅作近似对照；修复前的真实计数
        # 为 4591=0、36015=5@30fps/4@12fps，记录在任务报告中）。
        ("crunch(old thresholds)", replace(
            CrunchConfig(), high_torso_angle=140, down_torso_angle=120,
            bottom_torso_angle=90, min_count_torso_angle=95,
            min_effective_range_of_motion=35, state_confirm_frames=2,
            min_state_duration_ms=60)),
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
        print(f"{tfps:>5g}fps | {label:<24} -> {reps} reps")


if __name__ == "__main__":
    sys.exit(main())
