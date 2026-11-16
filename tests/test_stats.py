from ichnos.bench import poisson_upper, wilson
from ichnos.cluster import minpts_for


def test_wilson():
    lo, hi = wilson(9, 10)
    assert abs(lo - 0.596) < 0.005 and abs(hi - 0.982) < 0.005


def test_rule_of_three():
    assert abs(poisson_upper(0) - 2.996) < 0.01


def test_minpts_worked_example():
    cc = {"eps_space_km": 35, "eps_time_min": 75, "grid_area_km2": 109, "grid_time_min": 60,
          "c": 0.00108, "poisson_q": 0.99}
    assert minpts_for(30, cc)[0] == 6
    assert minpts_for(3, cc)[0] == 2
