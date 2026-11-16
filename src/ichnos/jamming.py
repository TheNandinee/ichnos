import pandas as pd

COLS = ["icao", "ts_ms", "lat", "lon", "alt_ft", "h3", "hour", "lane"]


def jam_flags(df, c):
    nic, nacp = df["nic"], df["nacp"]
    return (nic.notna() & (nic <= c["nic_max"])) | (nacp.notna() & (nacp <= c["nacp_max"]))


def hex_share(df, c):
    tot = df.groupby(["h3", "hour"])["icao"].nunique().rename("n_ac")
    jam = df[df["jam"]].groupby(["h3", "hour"])["icao"].nunique().rename("n_jam")
    out = pd.concat([tot, jam], axis=1).fillna({"n_jam": 0}).reset_index()
    out["n_jam"] = out["n_jam"].astype("int64")
    out["share"] = out["n_jam"] / out["n_ac"]
    return out[out["n_ac"] >= c["min_aircraft"]]


def jam_anomalies(df):
    j = df[df["jam"]].copy()
    if j.empty:
        return pd.DataFrame(columns=COLS)
    j["minute"] = j["ts_ms"] // 60000
    j = j.drop_duplicates(["icao", "minute"])
    j["lane"] = "jam"
    return j[COLS]
