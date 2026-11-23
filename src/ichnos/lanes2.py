import h3
import numpy as np
import pandas as pd

from .geo import R_KM, haversine_km, local_xy_km
from .jamming import capable

ALT_COLS = ["icao", "ts_ms", "lat", "lon", "alt_ft", "value_ft", "test"]
CHORD_COLS = ["icao", "ts_ms", "lat_a", "lon_a", "lat_b", "lon_b", "alt_ft", "dur_s"]


def _alt_rows(df, min_alt_ft):
    m = (((df["flags"] & 8) == 0) & df["alt_geom_ft"].notna() & df["alt_ft"].notna()
         & (df["alt_ft"] >= min_alt_ft))
    d = df.loc[m, ["icao", "ts_ms", "lat", "lon", "alt_ft", "alt_geom_ft"]].copy()
    d["delta"] = d["alt_geom_ft"] - d["alt_ft"]
    return d


def alt_steps(df, step_ft=800, max_gap_min=3, max_baro_change_ft=3000, max_flag_frac=0.2, min_alt_ft=5000):
    """Spoofing signature: the GNSS-minus-pressure altitude gap jumps by more than step_ft within
    a few minutes. Weather changes this gap slowly; a spoofed GNSS solution changes it suddenly."""
    d = _alt_rows(df, min_alt_ft)
    if d.empty:
        return pd.DataFrame(columns=ALT_COLS)
    d["minute"] = d["ts_ms"] // 60000
    m = (d.groupby(["icao", "minute"], as_index=False)
           .agg(ts_ms=("ts_ms", "min"), lat=("lat", "mean"), lon=("lon", "mean"),
                alt_ft=("alt_ft", "median"), delta=("delta", "median"))
           .sort_values(["icao", "minute"]))
    same = m["icao"].eq(m["icao"].shift())
    step = (m["delta"] - m["delta"].shift()).abs()
    m["flag"] = (same & ((m["minute"] - m["minute"].shift()) <= max_gap_min) & (step > step_ft)
                 & ((m["alt_ft"] - m["alt_ft"].shift()).abs() < max_baro_change_ft))
    m["value_ft"] = step
    frac = m.groupby("icao")["flag"].transform("mean")   # drop aircraft with erratic avionics
    out = m[m["flag"] & (frac <= max_flag_frac)]
    return out.assign(test="step")[ALT_COLS]


def alt_consensus(df, floor_ft=800, k_mad=5.0, min_aircraft=4, min_alt_ft=5000):
    """Aircraft whose altitude gap disagrees with neighbours at the same level, place and time.
    Catches aircraft already spoofed when they entered coverage. Misses area-wide spoofing
    that affects every neighbour equally (that is what alt_steps is for)."""
    d = _alt_rows(df, min_alt_ft)
    if d.empty:
        return pd.DataFrame(columns=ALT_COLS)
    d["cell"] = [h3.latlng_to_cell(a, b, 4) for a, b in zip(d["lat"].to_numpy(), d["lon"].to_numpy())]
    d["bin"] = d["ts_ms"] // 600_000
    d["band"] = (d["alt_ft"] // 2000).astype("int64")
    key = ["cell", "bin", "band"]
    per = d.groupby(key + ["icao"], as_index=False).agg(
        ts_ms=("ts_ms", "min"), lat=("lat", "mean"), lon=("lon", "mean"),
        alt_ft=("alt_ft", "median"), delta=("delta", "median"))
    g = per.groupby(key)["delta"]
    per["n"] = g.transform("size")
    per["resid"] = per["delta"] - g.transform("median")
    per["absr"] = per["resid"].abs()
    per["mad"] = per.groupby(key)["absr"].transform("median")
    per = per[per["n"] >= min_aircraft].copy()
    if per.empty:
        return pd.DataFrame(columns=ALT_COLS)
    per["resid"] -= per.groupby("icao")["resid"].transform("median")  # each aircraft's constant bias
    thr = np.maximum(floor_ft, k_mad * 1.4826 * per["mad"])
    out = per[per["resid"].abs() > thr]
    return out.assign(value_ft=out["resid"].abs(), test="consensus")[ALT_COLS]


def crossing_chords(df, max_gap_s=120, min_chord_km=15, max_dalt_ft=4000, min_alt_ft=3000):
    """Entry and exit points of each aircraft's pass through a jammed zone (healthy -> degraded -> healthy)."""
    d = df[df["nic"].notna() & capable(df)]
    out = []
    for icao, g in d.groupby("icao", sort=False):
        bad = g["nic"].to_numpy() <= 6
        if not bad.any() or bad.all():
            continue
        t = g["ts_ms"].to_numpy() / 1000.0
        la, lo, al = g["lat"].to_numpy(), g["lon"].to_numpy(), g["alt_ft"].to_numpy(float)
        edges = np.flatnonzero(bad[1:] != bad[:-1]) + 1
        for s, e in zip(np.r_[0, edges], np.r_[edges, len(bad)]):
            if not bad[s] or s == 0 or e == len(bad):
                continue
            if t[s] - t[s - 1] > max_gap_s or t[e] - t[e - 1] > max_gap_s:
                continue
            a1, a2 = al[s], al[e - 1]
            if not (np.isfinite(a1) and np.isfinite(a2)) or min(a1, a2) < min_alt_ft or abs(a1 - a2) > max_dalt_ft:
                continue
            lat_a, lon_a = (la[s - 1] + la[s]) / 2, (lo[s - 1] + lo[s]) / 2
            lat_b, lon_b = (la[e - 1] + la[e]) / 2, (lo[e - 1] + lo[e]) / 2
            if haversine_km(lat_a, lon_a, lat_b, lon_b) < min_chord_km:
                continue
            out.append((icao, int(t[s] * 1000), lat_a, lon_a, lat_b, lon_b, float((a1 + a2) / 2), float(t[e - 1] - t[s])))
    return pd.DataFrame(out, columns=CHORD_COLS)


def _xy_to_ll(x, y, lat0, lon0):
    return lat0 + np.degrees(y / R_KM), lon0 + np.degrees(x / (R_KM * np.cos(np.radians(lat0))))


def locate(ch, lat0, lon0, n_boot=1000, max_cond=30.0, seed=0):
    """Least-squares intersection of chord perpendicular bisectors. Every chord of a circle centred
    at c has a bisector through c, so concentric footprints at different altitudes all point to the
    same centre. Assumes a roughly circular footprint (isotropic emitter, open terrain)."""
    n = len(ch)
    if n < 4:
        return {"status": "too few crossings", "n_chords": int(n)}
    ax, ay = local_xy_km(ch["lat_a"].to_numpy(float), ch["lon_a"].to_numpy(float), lat0, lon0)
    bx, by = local_xy_km(ch["lat_b"].to_numpy(float), ch["lon_b"].to_numpy(float), lat0, lon0)
    M = np.c_[(ax + bx) / 2, (ay + by) / 2]
    D = np.c_[bx - ax, by - ay]
    D /= np.linalg.norm(D, axis=1, keepdims=True)

    def solve(ix):
        Di, Mi = D[ix], M[ix]
        A = Di.T @ Di
        if np.linalg.cond(A) > max_cond:
            return None
        return np.linalg.solve(A, (Di * (Di * Mi).sum(1, keepdims=True)).sum(0))

    c = solve(np.arange(n))
    if c is None:
        return {"status": "crossings too parallel (single airway)", "n_chords": int(n)}
    rng = np.random.default_rng(seed)
    boots = [b for b in (solve(rng.integers(0, n, n)) for _ in range(n_boot)) if b is not None]
    if len(boots) < 0.8 * n_boot:
        return {"status": "unstable geometry", "n_chords": int(n)}
    r95 = float(np.percentile(np.linalg.norm(np.array(boots) - c, axis=1), 95))
    rms = float(np.sqrt(np.mean(((c - M) * D).sum(1) ** 2)))
    lat, lon = _xy_to_ll(c[0], c[1], lat0, lon0)
    return {"status": "ok", "lat": round(float(lat), 3), "lon": round(float(lon), 3),
            "r95_km": round(r95, 1), "rms_km": round(rms, 1), "n_chords": int(n)}