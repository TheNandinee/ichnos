import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.cluster import DBSCAN

from .geo import local_xy_km
from .physics import border_feasible, feasible_region

EV_COLS = ["event_id", "day", "type", "t_start_ms", "t_end_ms", "lat", "lon", "n_aircraft",
           "n_anomalies", "minpts", "mu", "traffic", "region_wkt", "region_area_km2", "border_feasible"]


def minpts_for(traffic_per_h, cc):
    s = (np.pi * cc["eps_space_km"] ** 2 / cc["grid_area_km2"]) * (cc["eps_time_min"] / cc["grid_time_min"])
    mu = max(traffic_per_h, 1.0) * s * cc["c"]
    return max(2, int(poisson.ppf(cc["poisson_q"], mu)) + 1), float(mu)


def cluster_day(day, anoms, traffic, cfg, tag="all"):
    cc = cfg["cluster"]
    if anoms is None or anoms.empty:
        return pd.DataFrame(columns=EV_COLS)
    anoms = anoms.reset_index(drop=True)
    x, y = local_xy_km(anoms["lat"].to_numpy(float), anoms["lon"].to_numpy(float), 22.0, 80.0)
    tm = anoms["ts_ms"].to_numpy(float) / 60000.0
    X = np.c_[x / cc["eps_space_km"], y / cc["eps_space_km"], (tm - tm.min()) / cc["eps_time_min"]]
    labels = DBSCAN(eps=1.0, min_samples=2).fit_predict(X)
    tl = traffic.set_index(["h3", "hour"])["n_ac"] if not traffic.empty else pd.Series(dtype=float)
    rows, k = [], 0
    for lab in np.unique(labels):
        if lab < 0:
            continue
        g = anoms[labels == lab]
        n_ac = g["icao"].nunique()
        if n_ac < cc["min_aircraft"]:
            continue
        cell = g["h3"].mode().iat[0]
        hour = int(g["hour"].median())
        d = float(tl.get((cell, hour), 1.0))
        mp, mu = minpts_for(d, cc)
        if len(g) < mp:
            continue
        lanes = set(g["lane"])
        typ = "mixed" if len(lanes) > 1 else next(iter(lanes))
        per = g.sort_values("alt_ft").drop_duplicates("icao")
        region, area = feasible_region(per["lat"].to_numpy(float), per["lon"].to_numpy(float),
                                       per["alt_ft"].to_numpy(float), cfg["physics"]["emitter_height_m"])
        k += 1
        rows.append({
            "event_id": f"E-{day}-{tag}-{k:04d}", "day": day, "type": typ,
            "t_start_ms": int(g["ts_ms"].min()), "t_end_ms": int(g["ts_ms"].max()),
            "lat": float(g["lat"].mean()), "lon": float(g["lon"].mean()),
            "n_aircraft": int(n_ac), "n_anomalies": int(len(g)), "minpts": int(mp), "mu": mu, "traffic": d,
            "region_wkt": region.wkt if region is not None else None,
            "region_area_km2": area, "border_feasible": border_feasible(region),
        })
    print(f"[cluster] {day} ({tag}): {len(rows)} events")
    return pd.DataFrame(rows, columns=EV_COLS)
