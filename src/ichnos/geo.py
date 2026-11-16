import numpy as np

R_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * R_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def local_xy_km(lat, lon, lat0, lon0):
    x = np.radians(np.asarray(lon) - lon0) * R_KM * np.cos(np.radians(lat0))
    y = np.radians(np.asarray(lat) - lat0) * R_KM
    return x, y
