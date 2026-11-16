import numpy as np

from ichnos.spoofing import track_anomalies

CFG = {"v_th_mps": 650, "min_dt_s": 0.5, "z": 2.326, "min_ref_points": 20}


def _track(n=200, jump_at=None):
    rng = np.random.default_rng(0)
    t = np.arange(n, dtype=float)
    lat = 28.0 + np.zeros(n) + rng.normal(0, 2e-5, n)
    lon = 77.0 + t * (230 / 98000.0) + rng.normal(0, 2e-5, n)
    if jump_at is not None:
        lat[jump_at:] += 0.1  # about 11 km jump, physically impossible in 1 s
    return t, lat, lon


def test_clean_track_has_no_anomalies():
    assert track_anomalies(*_track(), CFG) == []


def test_injected_jump_is_flagged():
    assert 100 in track_anomalies(*_track(jump_at=100), CFG)
