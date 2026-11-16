import json

import h3
import pandas as pd

from .config import DER, PARQ
from .jamming import COLS, hex_share, jam_anomalies, jam_flags
from .spoofing import detect_spoofing


def detect_day(day, cfg):
    df = pd.read_parquet(PARQ / f"points_{day}.parquet")
    stats = {"day": day, "n_reports": int(len(df)), "n_aircraft": int(df["icao"].nunique()) if len(df) else 0}
    (DER / f"stats_{day}.json").write_text(json.dumps(stats), encoding="utf-8")
    if df.empty:
        print(f"[detect] {day}: no India reports")
        empty = pd.DataFrame(columns=COLS)
        return empty, pd.DataFrame(columns=["h3", "hour", "n_ac", "n_reports"])
    df = df.sort_values(["icao", "ts_ms"]).reset_index(drop=True)
    res = cfg["h3_res"]
    df["h3"] = [h3.latlng_to_cell(a, b, res) for a, b in zip(df["lat"].to_numpy(), df["lon"].to_numpy())]
    df["hour"] = (df["ts_ms"] // 3_600_000).astype("int64")

    traffic = df.groupby(["h3", "hour"]).agg(n_ac=("icao", "nunique"), n_reports=("icao", "size")).reset_index()
    traffic.to_parquet(DER / f"traffic_{day}.parquet")

    df["jam"] = jam_flags(df, cfg["jamming"])
    hex_share(df, cfg["jamming"]).to_parquet(DER / f"jamhex_{day}.parquet")

    anoms = pd.concat([jam_anomalies(df), detect_spoofing(df, cfg["spoofing"])], ignore_index=True)
    anoms.to_parquet(DER / f"anomalies_{day}.parquet")
    print(f"[detect] {day}: {stats['n_reports']} reports, {stats['n_aircraft']} aircraft, "
          f"{(anoms['lane'] == 'jam').sum()} jam / {(anoms['lane'] == 'spoof').sum()} spoof anomalies")
    return anoms, traffic
