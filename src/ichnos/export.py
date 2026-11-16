import csv
import json

import h3
import pandas as pd
from shapely import wkt
from shapely.geometry import mapping

from .config import DATA, DER, WEB_DATA

FC = lambda feats: {"type": "FeatureCollection", "features": feats}


def _days():
    return sorted(p.stem.replace("stats_", "") for p in DER.glob("stats_*.json"))


def _dump(name, obj):
    with open(WEB_DATA / name, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))


def _hex(cell, props):
    ring = [[round(lng, 5), round(lat, 5)] for lat, lng in h3.cell_to_boundary(cell)]
    ring.append(ring[0])
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": props}


def _concat(prefix, days):
    frames = []
    for d in days:
        p = DER / f"{prefix}_{d}.parquet"
        if p.exists():
            f = pd.read_parquet(p)
            if not f.empty:
                frames.append(f)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def export_all(cfg, max_points=60000):
    days = _days()
    if not days:
        raise SystemExit("No processed days. Run: python -m ichnos.cli run --days YYYY-MM-DD ...")
    pres = cfg["public_h3_res"]
    hours = set()

    jh = _concat("jamhex", days)
    feats = []
    if not jh.empty:
        jh["p"] = [h3.cell_to_parent(c, pres) for c in jh["h3"]]
        hourly = jh.groupby(["p", "hour"], as_index=False)[["n_ac", "n_jam"]].sum()
        hourly["share"] = hourly["n_jam"] / hourly["n_ac"]
        for r in hourly[hourly["n_jam"] > 0].itertuples():
            feats.append(_hex(r.p, {"hour": int(r.hour), "share": round(float(r.share), 3), "n_ac": int(r.n_ac)}))
            hours.add(int(r.hour))
        agg = jh.groupby("p", as_index=False)[["n_ac", "n_jam"]].sum()
        agg["share"] = agg["n_jam"] / agg["n_ac"]
        for r in agg[agg["n_jam"] > 0].itertuples():
            feats.append(_hex(r.p, {"hour": -1, "share": round(float(r.share), 3), "n_ac": int(r.n_ac)}))
    _dump("hexes.geojson", FC(feats))

    tr = _concat("traffic", days)
    cov = []
    if not tr.empty:
        tr["p"] = [h3.cell_to_parent(c, pres) for c in tr["h3"]]
        g = tr.groupby("p").agg(reports=("n_reports", "sum"), hrs=("hour", "nunique")).reset_index()
        for r in g.itertuples():
            cov.append(_hex(r.p, {"reports_per_hour": round(float(r.reports / max(r.hrs, 1)), 1)}))
    _dump("coverage.geojson", FC(cov))

    an = _concat("anomalies", days)
    pts = []
    if not an.empty:
        sp = an[an["lane"] == "spoof"]
        if len(sp) > max_points:
            sp = sp.sample(max_points, random_state=0)
        for r in sp.itertuples():
            h = int(r.ts_ms // 3_600_000)
            hours.add(h)
            pts.append({"type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [round(r.lon, 3), round(r.lat, 3)]},
                        "properties": {"lane": "spoof", "hour": h}})
    _dump("anomalies.geojson", FC(pts))

    ev = _concat("events_all", days)
    evf, regf = [], []
    if not ev.empty:
        for r in ev.itertuples():
            props = {"event_id": r.event_id, "day": r.day, "type": r.type,
                     "t_start_ms": int(r.t_start_ms), "t_end_ms": int(r.t_end_ms),
                     "n_aircraft": int(r.n_aircraft), "n_anomalies": int(r.n_anomalies),
                     "minpts": int(r.minpts), "region_area_km2": round(float(r.region_area_km2), 1),
                     "border_feasible": None if pd.isna(r.border_feasible) else bool(r.border_feasible)}
            evf.append({"type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [round(r.lon, 2), round(r.lat, 2)]},
                        "properties": props})
            if isinstance(r.region_wkt, str):
                regf.append({"type": "Feature", "geometry": mapping(wkt.loads(r.region_wkt).simplify(0.01)),
                             "properties": {"event_id": r.event_id}})
    _dump("events.geojson", FC(evf))
    _dump("regions.geojson", FC(regf))

    stats = [json.loads((DER / f"stats_{d}.json").read_text(encoding="utf-8")) for d in days]
    tags = []
    mf = DATA / "manifest.csv"
    if mf.exists():
        with open(mf, encoding="utf-8") as f:
            tags = sorted({row["release_tag"] for row in csv.DictReader(f)})
    meta = {"days": days, "hours": sorted(hours), "release_tags": tags,
            "n_reports": sum(s["n_reports"] for s in stats),
            "n_aircraft": sum(s["n_aircraft"] for s in stats),
            "n_events": len(evf), "public_h3_res": pres,
            "attribution": "Contains data from adsb.lol contributors, ODbL 1.0"}
    _dump("meta.json", meta)
    mp = DER / "metrics.json"
    if mp.exists():
        (WEB_DATA / "metrics.json").write_text(mp.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[export] {len(feats)} hex features, {len(pts)} spoof points, {len(evf)} events -> web/public/data")
