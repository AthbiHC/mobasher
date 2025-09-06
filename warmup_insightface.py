#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download/prepare InsightFace model pack without running any processing",
    )
    parser.add_argument("--model", default="buffalo_l", help="InsightFace model pack name")
    parser.add_argument("--det-thresh", type=float, default=0.4, help="Detection threshold")
    parser.add_argument(
        "--provider",
        default="CPUExecutionProvider",
        choices=["CPUExecutionProvider"],
        help="ONNX Runtime provider (CPU on this environment)",
    )
    args = parser.parse_args()

    t0 = time.time()
    try:
        from insightface.app import FaceAnalysis  # type: ignore
        app = FaceAnalysis(name=args.model, providers=[args.provider])
        app.prepare(ctx_id=0, det_thresh=args.det_thresh)
        ready = True
    except Exception as exc:  # noqa: BLE001
        ready = False
        print(f"ERROR: {exc}", file=sys.stderr)
    dt = int(time.time() - t0)
    print(f"FACE_ANALYZER_READY={int(ready)} ELAPSED_SECONDS={dt}")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
