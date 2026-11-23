import numpy as np
import pandas as pd

from ichnos.geo import haversine_km
from ichnos.lanes2 import alt_steps, locate


def test_locate_recovers_circle_centre():
    rng = np.random.default_rng(1)
    lat0, lon0, R = 30.0, 75.0, 80.0
    rows = []
    while len(rows) < 12:
        a, b = rng.uniform(0, 2 * np.pi, 2)
        if abs(a - b) < 0.6:
            continue
        pts = [(lat0 + np.degrees(R * np.sin(g) / 6371.0088),
                lon0 + np.degrees(R * np.cos(g) / (6371.0088 * np.cos(np.radians(lat0))))) for g in (a, b)]
        rows.append({"lat_a": pts[0][0], "lon_a": pts[0][1], "lat_b": pts[1][0], "lon_b": pts[1][1]})
    loc = locate(pd.DataFrame(rows), 30.5, 75.5)
    assert loc["status"] == "ok"
    assert haversine_km(loc["lat"], loc["lon"], lat0, lon0) < 3


def test_parallel_chords_refuse_to_locate():
    ch = pd.DataFrame({"lat_a": [30.0, 30.1, 30.2, 30.3], "lon_a": [75.0] * 4,
                       "lat_b": [30.0, 30.1, 30.2, 30.3], "lon_b": [76.0] * 4})
    assert locate(ch, 30.0, 75.5)["status"] != "ok"


def test_alt_step_flags_one_jump_only():
    t = np.arange(40) * 60_000
    df = pd.DataFrame({"icao": "abc", "ts_ms": t, "lat": 28.0, "lon": 77.0,
                       "alt_ft": 35000.0, "alt_geom_ft": 35500.0, "flags": 0})
    assert alt_steps(df).empty
    df.loc[20:, "alt_geom_ft"] = 31000.0
    assert len(alt_steps(df)) == 1