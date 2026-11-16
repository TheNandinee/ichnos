import csv
import json
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.stats import chi2

from .config import DER, WEB_DATA, load_yaml
from .geo import haversine_km


def wilson(k, n, z=1.96):
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def poisson_upper(k, conf=0.95):
    """One-sided upper bound on a Poisson count; k=0 gives about 3 (rule of three)."""
    return float(chi2.ppf(conf, 2 * (k + 1)) / 2)


def _ms(s):
    return int(pd.Timestamp(s).value // 1_000_000)


def _days():
    return sorted(p.stem.replace("stats_", "") for p in DER.glob("stats_*.json"))


def _covered_hours(s, e, days):
    tot = 0.0
    for d in days:
        ds = _ms(d + "T00:00:00Z")
        de = ds + 86_400_000
        ov = min(e, de) - max(s, ds)
        if ov > 0:
            tot += ov / 3.6e6
    return tot


def _load(pattern):
    fs = sorted(DER.glob(pattern))
    frames = [pd.read_parquet(f) for f in fs]
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _in_window(ev, w, airports, s, e):
    if ev.empty:
        return ev
    m = (ev["t_end_ms"] >= s) & (ev["t_start_ms"] <= e)
    if "airport" in w:
        a = airports[w["airport"]]
        dist = haversine_km(ev["lat"].to_numpy(float), ev["lon"].to_numpy(float), a["lat"], a["lon"])
        m &= dist <= w.get("radius_km", 100)
    elif "bbox" in w:
        b = w["bbox"]
        m &= ev["lat"].between(b[0], b[1]) & ev["lon"].between(b[2], b[3])
    return ev[m]


def run_bench():
    labels = load_yaml("benchmarks/labels.yaml")["windows"]
    airports = load_yaml("configs/airports.yaml")
    days = _days()
    methods = {"integrity_only": _load("events_jam_*.parquet"), "ichnos": _load("events_all_*.parquet")}
    windows, summary = [], []
    for name, ev in methods.items():
        det = n = fa = 0
        hours = 0.0
        for w in labels:
            s, e = _ms(w["start"]), _ms(w["end"])
            cov = _covered_hours(s, e, days)
            if cov <= 0:
                continue
            hit = _in_window(ev, w, airports, s, e)
            if w["class"] == "control":
                fa += len(hit)
                hours += cov
            else:
                n += 1
                det += int(len(hit) > 0)
            windows.append({"method": name, "window": w["id"], "class": w["class"],
                            "covered_hours": round(cov, 1), "n_events": int(len(hit))})
        lo, hi = wilson(det, n)
        summary.append({
            "method": name, "n_windows": n, "detected": det,
            "recall": det / n if n else None, "ci_lo": lo, "ci_hi": hi,
            "control_hours": round(hours, 1), "fa_events": fa,
            "fa_rate_ub95_per_h": poisson_upper(fa) / hours if hours else None,
        })
    perf = {}
    pf = DER / "perf.csv"
    if pf.exists():
        with open(pf, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows:
            perf = {"mean_rows_per_s": float(np.mean([float(r["rows_per_s"]) for r in rows])),
                    "days": len(rows)}
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "days": days, "methods": summary, "windows": windows, "performance": perf,
           "note": "Window-level labels from public reports; not exact event ground truth."}
    for target in (DER / "metrics.json", WEB_DATA / "metrics.json"):
        target.write_text(json.dumps(out, indent=2), encoding="utf-8")
    for m in summary:
        print(f"[bench] {m['method']}: {m['detected']}/{m['n_windows']} windows, "
              f"CI {m['ci_lo']}-{m['ci_hi']}, false events {m['fa_events']} in {m['control_hours']} h")
    return out
