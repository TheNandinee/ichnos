from ichnos.physics import fspl_db, horizon_km, jam_to_signal_db


def test_horizon_matches_dossier():
    assert abs(horizon_km(30, 10668) - 448) < 2
    assert abs(horizon_km(30, 914) - 147) < 2


def test_link_budget():
    assert abs(fspl_db(1575.42, 50) - 130.4) < 0.1
    assert abs(jam_to_signal_db(30, 50) - 28.1) < 0.2
