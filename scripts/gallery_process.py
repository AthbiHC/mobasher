#!/usr/bin/env python3
from __future__ import annotations

"""
Process a downloaded gallery into curated crops and embeddings.
- Walk images under --root (identity folders)
- Detect face (SCRFD), keep largest passing score/size
- Align/resize to 112x112, compute ArcFace embedding
- Keep up to --per_identity crops with farthest-point sampling
- Write manifest.jsonl (identity, files, emb_mean)

NOTE: This script performs only local processing; no network I/O.
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Tuple

import numpy as np  # type: ignore
import cv2  # type: ignore


def _init_face(det_thresh: float):
    from insightface.app import FaceAnalysis  # type: ignore

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_thresh=det_thresh)
    return app


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def _select_diverse(embs: List[np.ndarray], k: int) -> List[int]:
    if not embs:
        return []
    n = len(embs)
    k = min(k, n)
    sel = [0]
    if k == 1:
        return sel
    # greedy farthest-point sampling
    dists = np.zeros((n,), dtype=np.float32)
    for _ in range(1, k):
        for i in range(n):
            if i in sel:
                continue
            d = max(0.0, 1.0 - _cosine(embs[i], embs[sel[-1]]))
            dists[i] = max(dists[i], d)
        sel.append(int(np.argmax(dists)))
    return sel


def main() -> int:
    ap = argparse.ArgumentParser(description="Curate crops and embeddings for gallery")
    ap.add_argument("--root", default=os.environ.get("FACES_GALLERY_DIR", "/Volumes/ExternalDB/Media-View-Data/data/gallery/images"))
    ap.add_argument("--out", default=os.environ.get("FACES_GALLERY_DIR", "/Volumes/ExternalDB/Media-View-Data/data/gallery/images"))
    ap.add_argument("--per_identity", type=int, default=5)
    ap.add_argument("--det_thresh", type=float, default=0.6)
    args = ap.parse_args()

    root = Path(args.root)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    fa = _init_face(args.det_thresh)

    manifest_path = out_root / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as man:
        for ident_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            crops: List[Tuple[Path, np.ndarray]] = []
            for img_name in ident_dir.iterdir():
                if img_name.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                    continue
                img = cv2.imread(str(img_name))
                if img is None:
                    continue
                faces = fa.get(img)
                if not faces:
                    continue
                # choose largest face
                f = max(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
                if getattr(f, "det_score", 0.0) < args.det_thresh:
                    continue
                x1, y1, x2, y2 = map(int, f.bbox)
                x1 = max(0, x1); y1 = max(0, y1); x2 = min(img.shape[1], x2); y2 = min(img.shape[0], y2)
                crop = img[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                crop = cv2.resize(crop, (112, 112), interpolation=cv2.INTER_AREA)
                emb = f.normed_embedding
                crops.append((img_name, emb))
            if not crops:
                continue
            embs = [e for _, e in crops]
            idxs = _select_diverse(embs, args.per_identity)
            chosen = [crops[i][0] for i in idxs]
            mean_emb = np.mean(np.stack(embs, axis=0), axis=0).tolist()
            rec = {
                "identity": ident_dir.name,
                "files": [str(p) for p in chosen],
                "emb_mean": mean_emb,
            }
            man.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
