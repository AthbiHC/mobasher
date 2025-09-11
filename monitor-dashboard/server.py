from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import httpx


app = FastAPI(title="Mobasher Monitor Dashboard")


@app.on_event("startup")
async def startup() -> None:
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index() -> FileResponse:
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(index_path)


@app.get("/health/summary")
async def health_summary() -> JSONResponse:
    api_host = os.environ.get("API_HOST", "127.0.0.1")
    api_port = int(os.environ.get("API_PORT", "8010"))
    api_base = f"http://{api_host}:{api_port}"
    out: Dict[str, Any] = {
        "db": "unknown",
        "redis": "unknown",
        "api": "unknown",
        "segments_10m": 0,
        "transcripts_10m": 0,
        "status": "red",
    }
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            # API health
            r = await client.get(f"{api_base}/health")
            out["api"] = "ok" if (r.status_code == 200 and r.json().get("status") == "ok") else "error"
            # Recent segments/transcripts via /segments and /transcripts
            now = datetime.now(timezone.utc)
            since = (now - timedelta(minutes=10)).isoformat()
            segs = await client.get(f"{api_base}/segments", params={"start": since, "limit": 1})
            trs = await client.get(f"{api_base}/transcripts", params={"since": since, "limit": 1})
            if segs.status_code == 200:
                out["segments_10m"] = len(segs.json().get("items", []))
            if trs.status_code == 200:
                out["transcripts_10m"] = len(trs.json().get("items", []))
            # DB/Redis inferred from API availability (simple heuristic)
            out["db"] = "ok" if out["api"] == "ok" else "unknown"
            out["redis"] = "ok" if out["api"] == "ok" else "unknown"
    except Exception:
        pass
    out["status"] = "green" if out["api"] == "ok" else "red"
    return JSONResponse(out)


@app.get("/shots")
async def shots(p: str = Query(..., description="Absolute screenshot file path")) -> FileResponse:
    root = os.environ.get("MOBASHER_SCREENSHOT_ROOT", "/Volumes/ExternalDB/Media-View-Data/data/screenshot")
    rp = os.path.realpath(p)
    rr = os.path.realpath(root)
    if not rp.startswith(rr):
        raise HTTPException(status_code=400, detail="path outside screenshot root")
    if not os.path.exists(rp) or not os.path.isfile(rp):
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(rp)


