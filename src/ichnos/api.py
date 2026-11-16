import json

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .config import ROOT, WEB_DATA

app = FastAPI(title="ICHNOS API", version="0.1.0")


def _read(name):
    p = WEB_DATA / name
    if not p.exists():
        raise HTTPException(404, f"{name} not found; run `python -m ichnos.cli export`")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    return _read("meta.json")


@app.get("/api/metrics")
def metrics():
    return _read("metrics.json")


@app.get("/api/events")
def events():
    return _read("events.geojson")


@app.get("/api/events/{event_id}")
def event(event_id: str):
    for f in _read("events.geojson")["features"]:
        if f["properties"]["event_id"] == event_id:
            return f
    raise HTTPException(404, "event not found")


_dist = ROOT / "web" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
