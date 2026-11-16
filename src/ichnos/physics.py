import json
import math

import numpy as np
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union

from .config import ROOT

GPS_L1_MHZ = 1575.42
GPS_CA_MIN_DBM = -128.5
_BORDER = None


def horizon_km(h_tx_m, h_rx_m):
    return 4.12 * (math.sqrt(max(h_tx_m, 0.0)) + math.sqrt(max(h_rx_m, 0.0)))


def fspl_db(f_mhz, d_km):
    return 32.44 + 20 * math.log10(f_mhz) + 20 * math.log10(d_km)


def jam_to_signal_db(p_tx_dbm, d_km, f_mhz=GPS_L1_MHZ):
    return (p_tx_dbm - fspl_db(f_mhz, d_km)) - GPS_CA_MIN_DBM


def feasible_region(lats, lons, alts_ft, h_tx_m):
    pts = [(la, lo, a) for la, lo, a in zip(lats, lons, alts_ft)
           if a is not None and np.isfinite(a) and a > 0]
    if not pts:
        return None, 0.0
    lat0 = float(np.mean([p[0] for p in pts]))
    lon0 = float(np.mean([p[1] for p in pts]))
    aeqd = f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +units=m +datum=WGS84"
    fwd = Transformer.from_crs("EPSG:4326", aeqd, always_xy=True)
    inv = Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True)
    region = None
    for la, lo, a in pts:
        x, y = fwd.transform(lo, la)
        disc = Point(x, y).buffer(horizon_km(h_tx_m, a * 0.3048) * 1000.0, quad_segs=32)
        region = disc if region is None else region.intersection(disc)
        if region.is_empty:
            return None, 0.0
    area = region.area / 1e6
    geo = transform(lambda x, y, z=None: inv.transform(x, y), region)
    return geo, float(area)


def border_feasible(region):
    """Optional: put a Survey of India-compliant border line in configs/border.geojson."""
    global _BORDER
    if region is None:
        return None
    p = ROOT / "configs" / "border.geojson"
    if not p.exists():
        return None
    if _BORDER is None:
        with open(p, encoding="utf-8") as f:
            gj = json.load(f)
        _BORDER = unary_union([shape(ft["geometry"]) for ft in gj["features"]])
    return bool(region.intersects(_BORDER))
