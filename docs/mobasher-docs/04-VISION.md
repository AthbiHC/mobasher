## Vision

### Overview
Computer vision pipeline processes video segments for OCR (Arabic focus), object detection, and optional face recognition with a curated gallery.

### OCR
- Frame sampling with ROI regions (headline, ticker, center, full)
- Preprocessing and deduplication with temporal smoothing
- Aggregated spans in JSON; screenshots saved with convention `<base>-seg_<i>_<region>.jpg`

### Objects
- YOLOv8 detections stored as `visual_events` with bounding boxes, classes, and confidences

### Faces (deprioritized for later phase)
- InsightFace detection + ArcFace embeddings
- Gallery building from Wikidata (export, plan, download, process)

### Metrics & storage
- Vision tasks export timings (future)
- `visual_events` table includes `video_path`, `video_filename`, `screenshot_path`, `frame_timestamp_ms`

### CLI
```bash
./scripts/mediaview vision worker -c 2
./scripts/mediaview vision enqueue --limit 20
```


