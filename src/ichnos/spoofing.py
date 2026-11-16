import numpy as np
import pandas as pd

from .geo import haversine_km
from .jamming import COLS


def _tau(x, z, min_n):
    x = x[np.isfinite(x) & (x > 0)]
    if x.size < min_n:
        return None
    lx = np.log(x)
    return float(np.exp(lx.mean() + z * lx.std()))


def track_anomalies(t, lat, lon, c):
    """Three-stage screen on one aircraft track. Returns local indices of spoof anomalies.
    Stage 1: implied speed > v_th. Stage 2a: residual from neighbour interpolation above an
    adaptive log-normal threshold. Stage 2b: jump from predecessor above an adaptive threshold."""
    n = len(t)
    if n < 5:
        return []
    d = haversine_km(lat[:-1], lon[:-1], lat[1:], lon[1:]) * 1000.0
    dt = np.diff(t)
    v = np.where(dt >= c["min_dt_s"], d / np.maximum(dt, 1e-9), 0.0)
    cand = np.flatnonzero(v > c["v_th_mps"]) + 1
    if cand.size == 0:
        return []
    i = np.arange(1, n - 1)
    frac = (t[i] - t[i - 1]) / np.maximum(t[i + 1] - t[i - 1], 1e-9)
    plat = lat[i - 1] + (lat[i + 1] - lat[i - 1]) * frac
    plon = lon[i - 1] + (lon[i + 1] - lon[i - 1]) * frac
    resid = np.full(n, np.nan)
    resid[i] = haversine_km(lat[i], lon[i], plat, plon) * 1000.0
    gap = np.full(n, np.nan)
    gap[1:] = d
    ref = np.ones(n, bool)
    ref[cand] = False
    tr = _tau(resid[ref], c["z"], c["min_ref_points"])
    tg = _tau(gap[ref], c["z"], c["min_ref_points"])
    if tr is None or tg is None:
        return []
    return [int(k) for k in cand if np.isfinite(resid[k]) and resid[k] > tr and gap[k] > tg]


def detect_spoofing(df, c):
    if df.empty:
        return pd.DataFrame(columns=COLS)
    icao = df["icao"].to_numpy()
    t = df["ts_ms"].to_numpy() / 1000.0
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()
    bounds = np.flatnonzero(icao[1:] != icao[:-1]) + 1
    starts = np.r_[0, bounds]
    ends = np.r_[bounds, len(df)]
    keep = []
    for s, e in zip(starts, ends):
        keep.extend(s + k for k in track_anomalies(t[s:e], lat[s:e], lon[s:e], c))
    out = df.iloc[keep].copy()
    out["lane"] = "spoof"
    return out[COLS]
