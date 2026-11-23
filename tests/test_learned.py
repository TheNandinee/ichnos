import numpy as np
import pandas as pd

from ichnos.bench_v1 import day_labels
from ichnos.learned import inject, minute_features


def _track(icao="abc", n=1800):
    t = np.arange(n) * 1000
    return pd.DataFrame({"icao": icao, "ts_ms": t, "lat": 28.0, "lon": 77.0 + np.arange(n) * 230 / 98300.0,
                         "alt_ft": 35000.0, "alt_geom_ft": 35500.0, "gs_kt": 447.0, "nic": 8.0, "nacp": 9.0,
                         "flags": 0, "src": "adsb_icao"})


def test_clean_features_are_physical():
    f = minute_features(_track())
    assert f["v_max"].max() < 300
    assert (f["dh_step"].fillna(0) < 100).all()


def test_injection_labels_minutes():
    inj = inject(_track(), np.random.default_rng(0), frac=1.0)
    assert inj["label"].sum() > 0
    assert minute_features(inj)["label"].max() == 1


def test_day_labels_buffer():
    w = [{"region": "DEL", "tier": "dated", "class": "spoof", "start": "2025-11-04", "end": "2025-11-05"}]
    assert day_labels(w, "DEL", ["2025-11-04", "2025-11-07", "2025-11-20"]) == \
        {"2025-11-04": 1, "2025-11-07": None, "2025-11-20": 0}