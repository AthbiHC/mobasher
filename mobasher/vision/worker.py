from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
from time import perf_counter

from celery import Celery
from pydantic_settings import BaseSettings


class VisionSettings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    ocr_fps: float = 3.0
    ocr_lang: str = "ar"  # EasyOCR language code
    # Relative ROI bands (fractions of height) for typical news layouts
    enable_roi_headline: bool = True
    roi_headline_top: float = 0.72
    roi_headline_bottom: float = 0.86
    enable_roi_ticker: bool = True
    roi_ticker_top: float = 0.88
    roi_ticker_bottom: float = 0.98
    enable_roi_center: bool = True
    roi_center_top: float = 0.30
    roi_center_bottom: float = 0.70
    # OCR dedup & smoothing
    ocr_write_raw: bool = False
    ocr_iou_threshold: float = 0.3
    ocr_text_sim_threshold: float = 0.6
    ocr_merge_window_s: float = 2.0


settings = VisionSettings()
app = Celery("mobasher_vision", broker=settings.redis_url, backend=settings.redis_url)


def _sample_timestamps(duration_s: float, fps: float) -> List[float]:
    if fps <= 0:
        return []
    step = 1.0 / fps
    t = 0.0
    out: List[float] = []
    while t < duration_s:
        out.append(round(t, 3))
        t += step
    return out


# Global OCR model cache
_OCR = None


def _get_ocr():
    global _OCR
    if _OCR is None:
        import easyocr  # type: ignore
        _OCR = easyocr.Reader([settings.ocr_lang], gpu=False, verbose=False)
    return _OCR


def _read_frame_at(video_path: str, ts_sec: float) -> Optional[Tuple[Any, int, int]]:
    import cv2  # type: ignore
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, ts_sec * 1000.0)
    ok, frame = cap.read()
    h, w = (frame.shape[0], frame.shape[1]) if ok and frame is not None else (0, 0)
    cap.release()
    if not ok or frame is None:
        return None
    return frame, w, h


def _compute_rois(width: int, height: int) -> List[Tuple[str, Tuple[int, int, int, int]]]:
    """Return list of (name, x,y,w,h) ROIs based on configured relative bands.

    The ROIs are conservative and clamped to frame bounds.
    """
    rois: List[Tuple[str, Tuple[int, int, int, int]]] = []
    def clamp01(v: float) -> float:
        return max(0.0, min(1.0, v))

    def band(name: str, top_r: float, bot_r: float) -> None:
        t = int(round(height * clamp01(top_r)))
        b = int(round(height * clamp01(bot_r)))
        if b <= t:
            return
        rois.append((name, (0, t, width, b - t)))

    if settings.enable_roi_headline:
        band("headline", settings.roi_headline_top, settings.roi_headline_bottom)
    if settings.enable_roi_ticker:
        band("ticker", settings.roi_ticker_top, settings.roi_ticker_bottom)
    if settings.enable_roi_center:
        band("center", settings.roi_center_top, settings.roi_center_bottom)
    return rois


def _preprocess_for_ocr(image: Any) -> Any:
    """Lightweight preprocessing to improve contrast for white-on-color overlays."""
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    except Exception:
        gray = image
    # CLAHE enhances local contrast without blowing out highlights
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    # Mild blur to reduce noise before thresholding
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # OTSU thresholding; invert because text is mostly bright
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inv = cv2.bitwise_not(th)
    return inv


@app.task(name="vision.ocr_segment", bind=True, max_retries=2, default_retry_delay=10)
def ocr_segment(self, segment_id: str, segment_started_at_iso: str) -> Dict[str, Any]:
    start = perf_counter()
    # Lazy imports to keep worker light
    from datetime import datetime
    from uuid import UUID
    from mobasher.storage.db import get_session, init_engine
    from mobasher.storage.models import Segment, VisualEvent
    from mobasher.storage.repositories import upsert_segment  # if needed later
    import subprocess

    init_engine()
    with next(get_session()) as db:  # type: ignore
        seg = db.get(Segment, (UUID(segment_id), datetime.fromisoformat(segment_started_at_iso)))
        if seg is None or not seg.video_path:
            raise self.retry(exc=RuntimeError("segment_missing_or_no_video"))

        # Probe duration via ffprobe
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nokey=1:noprint_wrappers=1', seg.video_path
            ], capture_output=True, text=True)
            duration_s = float(result.stdout.strip()) if result.returncode == 0 else 60.0
        except Exception:
            duration_s = 60.0

        timestamps = _sample_timestamps(duration_s, settings.ocr_fps)

        events = 0
        # Keep aggregated per-frame OCR here to deduplicate later
        aggregated_frames: List[Dict[str, Any]] = []
        ocr = _get_ocr()
        import os
        screenshot_root = os.environ.get('MOBASHER_SCREENSHOT_ROOT', '/Volumes/ExternalDB/Media-View-Data/data/screenshot')
        os.makedirs(screenshot_root, exist_ok=True)

        for idx, ts in enumerate(timestamps):
            fr = _read_frame_at(seg.video_path, ts)
            if fr is None:
                continue
            frame, w, h = fr
            # Prepare ROIs including full frame as a fallback
            rois = [("full", (0, 0, w, h))] + _compute_rois(w, h)
            for region_name, (rx, ry, rw, rh) in rois:
                sub = frame[ry:ry+rh, rx:rx+rw]
                # Preprocess copy to help OCR on overlays; keep original for screenshot
                pre = _preprocess_for_ocr(sub)
                # EasyOCR returns list of [bbox, text, conf]
                # Use slightly more permissive thresholds for overlays
                results = ocr.readtext(pre, paragraph=True, detail=1, text_threshold=0.5, low_text=0.3)
                # Save one region screenshot per frame with descriptive name
                fname = os.path.basename(seg.video_path)
                base, _ = os.path.splitext(fname)
                shot_name = f"{base}-seg_{idx}_{region_name}.jpg"
                shot_path = os.path.join(screenshot_root, shot_name)
                try:
                    import cv2
                    cv2.imwrite(shot_path, sub)
                except Exception:
                    pass
                if settings.ocr_write_raw:
                    for item in results:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            box = item[0]
                            text = item[1]
                            conf = (item[2] if len(item) >= 3 else None)
                        else:
                            continue
                        if not text or not str(text).strip():
                            continue
                        xs = [p[0] for p in box]
                        ys = [p[1] for p in box]
                        x_min, y_min = float(max(0, min(xs))) + rx, float(max(0, min(ys))) + ry
                        x_max, y_max = float(min(rw, max(xs))) + rx, float(min(rh, max(ys))) + ry
                        bbox = [int(x_min), int(y_min), int(max(1, x_max - x_min)), int(max(1, y_max - y_min))]
                        ve = VisualEvent(
                            id=None,
                            segment_id=UUID(segment_id),
                            segment_started_at=datetime.fromisoformat(segment_started_at_iso),
                            channel_id=seg.channel_id,
                            timestamp_offset=float(ts),
                            event_type='ocr',
                            bbox=bbox,
                            confidence=float(conf) if conf is not None else None,
                            data={"text": str(text).strip(), "lang": "ar", "region": region_name},
                            video_path=seg.video_path,
                            video_filename=fname,
                            screenshot_path=shot_path,
                            frame_timestamp_ms=int(ts*1000),
                        )
                        db.add(ve)
                        events += 1
                # Aggregated sentence per region for this timestamp
                tokens = []
                union = None
                for item in results:
                    if not (isinstance(item, (list, tuple)) and len(item) >= 2 and str(item[1]).strip()):
                        continue
                    box = item[0]
                    text = str(item[1]).strip()
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    x_min, y_min = float(max(0, min(xs))) + rx, float(max(0, min(ys))) + ry
                    x_max, y_max = float(min(rw, max(xs))) + rx, float(min(rh, max(ys))) + ry
                    tb = [int(x_min), int(y_min), int(max(1, x_max - x_min)), int(max(1, y_max - y_min))]
                    conf = float(item[2]) if (isinstance(item, (list, tuple)) and len(item) >= 3 and item[2] is not None) else None
                    tokens.append({"text": text, "bbox": tb, "conf": conf})
                    if union is None:
                        union = tb.copy()
                    else:
                        ux, uy, uw, uh = union
                        union = [min(ux, tb[0]), min(uy, tb[1]), max(ux+uw, tb[0]+tb[2]) - min(ux, tb[0]), max(uy+uh, tb[1]+tb[3]) - min(uy, tb[1])]
                if tokens:
                    tokens_sorted = sorted(tokens, key=lambda t: t["bbox"][0])
                    aggregated_text = " ".join(t["text"] for t in tokens_sorted)
                    font_px = max(t["bbox"][3] for t in tokens_sorted)
                    aggregated_frames.append({
                        "ts": float(ts),
                        "region": region_name,
                        "text": aggregated_text.strip(),
                        "bbox": union if union is not None else [rx, ry, rw, rh],
                        "font_px": int(font_px),
                        "tokens": tokens_sorted,
                        "shot": shot_path,
                        "fname": fname,
                    })
        # Deduplicate aggregated frames into spans
        def _iou(a: List[int], b: List[int]) -> float:
            ax, ay, aw, ah = a
            bx, by, bw, bh = b
            ax2, ay2 = ax + aw, ay + ah
            bx2, by2 = bx + bw, by + bh
            inter_w = max(0, min(ax2, bx2) - max(ax, bx))
            inter_h = max(0, min(ay2, by2) - max(ay, by))
            inter = inter_w * inter_h
            if inter <= 0:
                return 0.0
            union = aw * ah + bw * bh - inter
            return inter / union if union > 0 else 0.0

        try:
            from rapidfuzz.fuzz import token_set_ratio as _sim  # type: ignore
            def _text_sim(x: str, y: str) -> float:
                return _sim(x, y) / 100.0
        except Exception:
            def _text_sim(x: str, y: str) -> float:
                return 1.0 if x == y else 0.0

        spans: List[Dict[str, Any]] = []
        for region in {e["region"] for e in aggregated_frames}:
            items = [e for e in aggregated_frames if e["region"] == region]
            items.sort(key=lambda r: r["ts"])  # time ascending
            current = None
            for it in items:
                if current is None:
                    current = {
                        "start": it["ts"],
                        "end": it["ts"],
                        "text": it["text"],
                        "bbox": it["bbox"],
                        "font_px": it["font_px"],
                        "tokens": it["tokens"],
                        "shot": it["shot"],
                        "fname": it["fname"],
                    }
                    continue
                time_ok = (it["ts"] - current["end"]) <= settings.ocr_merge_window_s
                if time_ok and _text_sim(current["text"], it["text"]) >= settings.ocr_text_sim_threshold and _iou(current["bbox"], it["bbox"]) >= settings.ocr_iou_threshold:
                    # extend span
                    current["end"] = it["ts"]
                    # union bbox
                    cx, cy, cw, ch = current["bbox"]
                    bx, by, bw, bh = it["bbox"]
                    nx = min(cx, bx)
                    ny = min(cy, by)
                    nx2 = max(cx+cw, bx+bw)
                    ny2 = max(cy+ch, by+bh)
                    current["bbox"] = [nx, ny, nx2-nx, ny2-ny]
                    current["font_px"] = max(current["font_px"], it["font_px"])
                    continue
                # finalize current
                spans.append(current)
                current = {
                    "start": it["ts"],
                    "end": it["ts"],
                    "text": it["text"],
                    "bbox": it["bbox"],
                    "font_px": it["font_px"],
                    "tokens": it["tokens"],
                    "shot": it["shot"],
                    "fname": it["fname"],
                }
            if current is not None:
                spans.append(current)

        # Write canonical span events
        for sp in spans:
            ve_span = VisualEvent(
                id=None,
                segment_id=UUID(segment_id),
                segment_started_at=datetime.fromisoformat(segment_started_at_iso),
                channel_id=seg.channel_id,
                timestamp_offset=float(sp["start"]),
                event_type='ocr',
                bbox=[int(v) for v in sp["bbox"]],
                confidence=None,
                data={
                    "text": sp["text"],
                    "lang": "ar",
                    "region": None,  # region not preserved after merge of full/ROI
                    "aggregated": True,
                    "font_px": int(sp["font_px"]),
                    "tokens": sp["tokens"],
                    "end_offset": float(sp["end"]),
                },
                video_path=seg.video_path,
                video_filename=sp["fname"],
                screenshot_path=sp["shot"],
                frame_timestamp_ms=int(sp["start"]*1000),
            )
            db.add(ve_span)
            events += 1
        db.commit()

    return {"ok": True, "events": events, "elapsed_ms": int((perf_counter() - start) * 1000)}


