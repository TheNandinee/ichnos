"""Daily interference index per region.
  python -m ichnos.daily day 2025-11-04
  python -m ichnos.daily report
"""
import json
import sys

import h3
import numpy as np
import pandas as pd
from scipy.stats import binomtest, mannwhitneyu

from .config import DER, PARQ, WEB_DATA, ensure_dirs, load_config
from .geo import haversine_km
from .jamming import capable, jam_flags
from .lanes2 import CHORD_COLS, alt_consensus, alt_steps, crossing_chords, locate
from .spoofing import detect_spoofing

RADIUS_KM = 150
REGIONS = {
    "DEL": ("Delhi IGI", 28.5665, 77.1031),
    "ATQ": ("Amritsar", 31.7096, 74.7973),
    "BOM": ("Mumbai", 19.0896, 72.8656),
    "CCU": ("Kolkata", 22.6547, 88.4467),
    "HYD": ("Hyderabad", 17.2403, 78.4294),
    "BLR": ("Bengaluru", 13.1986, 77.7066),
    "MAA": ("Chennai", 12.9941, 80.1709),
}

def reported_del(day):
    # Spoofing near IGI reported ~4-7 Nov 2025 (Business Today 6 Nov; Rajya Sabha 1 Dec 2025).
    # 623 reports around Delhi in Jan-Feb 2026 (Lok Sabha, 12 Mar 2026).
    return ("2025-10-30" <= day <= "2025-11-07") or day[:7] in ("2026-01", "2026-02")


def _near(frame, la, lo, r=RADIUS_KM):
    return haversine_km(frame["lat"].to_numpy(float), frame["lon"].to_numpy(float), la, lo) <= r


def _member(frame, key):
    if len(frame) == 0:
        return np.zeros(0, bool)
    if key != "REST":
        _, la, lo = REGIONS[key]
        return _near(frame, la, lo)
    return ~np.logical_or.reduce([_near(frame, la, lo) for _, la, lo in REGIONS.values()])


def day_index(day):
    cfg = load_config()
    ensure_dirs()
    df = pd.read_parquet(PARQ / f"points_{day}.parquet")
    if "alt_geom_ft" not in df.columns:
        raise SystemExit(f"{day}: parquet is from the old ingest; run `python -m ichnos.cli ingest --day {day}`")
    df = df.sort_values(["icao", "ts_ms"]).reset_index(drop=True)
    df["h3"] = [h3.latlng_to_cell(a, b, 5) for a, b in zip(df["lat"].to_numpy(), df["lon"].to_numpy())]
    df["hour"] = (df["ts_ms"] // 3_600_000).astype("int64")
    df["cap"] = capable(df)
    df["jam"] = jam_flags(df, cfg["jamming"])
    spoof = detect_spoofing(df, cfg["spoofing"])
    alt = pd.concat([alt_steps(df), alt_consensus(df)], ignore_index=True)
    chords = crossing_chords(df)
    alt.to_parquet(DER / f"altdiv_{day}.parquet")
    chords.to_parquet(DER / f"chords_{day}.parquet")
    mid = chords.assign(lat=(chords["lat_a"] + chords["lat_b"]) / 2, lon=(chords["lon_a"] + chords["lon_b"]) / 2)

    regions = {}
    for k in list(REGIONS) + ["REST"]:
        m = _member(df, k)
        sub = df[m]
        ac = sub["icao"].nunique()
        cap_ac = sub.loc[sub["cap"], "icao"].nunique()
        jam_ac = sub.loc[sub["jam"], "icao"].nunique()
        a = alt[_member(alt, k)]
        s = spoof[_member(spoof, k)]
        nrep = int(m.sum())
        r = {"reports": nrep, "report_share": float(m.mean()), "aircraft": int(ac),
             "capable_aircraft": int(cap_ac), "jam_aircraft": int(jam_ac),
             "jam_share": jam_ac / cap_ac if cap_ac else None,
             "altdiv_aircraft": int(a["icao"].nunique()),
             "altdiv_share": a["icao"].nunique() / ac if ac else None,
             "spoof_jumps": int(len(s)), "spoof_per_m": len(s) / (nrep / 1e6) if nrep else None}
        if k != "REST":
            _, la, lo = REGIONS[k]
            c = chords[_near(mid, la, lo, 300)] if len(chords) else pd.DataFrame(columns=CHORD_COLS)
            r["chords"] = int(len(c))
            r["locate"] = locate(c, la, lo)
        regions[k] = r
    out = {"day": day, "n_reports": int(len(df)), "spoof_total": int(len(spoof)), "regions": regions}
    (DER / f"daily_{day}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    for k, r in regions.items():
        js = "n/a" if r["jam_share"] is None else f"{r['jam_share']:.3f}"
        al = "n/a" if r["altdiv_share"] is None else f"{r['altdiv_share']:.3f}"
        print(f"[daily] {day} {k}: {r['aircraft']} ac | jam share {js} | alt-mismatch share {al} | "
              f"jumps {r['spoof_jumps']} | locate {r.get('locate', {}).get('status', '-')}")


def report():
    files = sorted(DER.glob("daily_*.json"))
    if not files:
        raise SystemExit("No daily_*.json yet. Run `python -m ichnos.daily day YYYY-MM-DD` first.")
    rows = []
    for f in files:
        r = json.loads(f.read_text(encoding="utf-8"))
        for k, v in r["regions"].items():
            loc = v.get("locate") or {}
            rows.append({"day": r["day"], "region": k,
                         "reported": reported_del(r["day"]) if k == "DEL" else None,
                         **{x: v[x] for x in v if x != "locate"},
                         "loc_status": loc.get("status"), "loc_lat": loc.get("lat"), "loc_lon": loc.get("lon"),
                         "loc_r95_km": loc.get("r95_km"), "spoof_total": r["spoof_total"]})
    t = pd.DataFrame(rows).sort_values(["region", "day"])
    t.to_csv(DER / "daily.csv", index=False)

    d = t[t["region"] == "DEL"]
    rep = d["reported"].astype(bool)
    tests = {}
    for metric in ("jam_share", "altdiv_share", "spoof_per_m"):
        a, b = d.loc[rep, metric].dropna(), d.loc[~rep, metric].dropna()
        if len(a) >= 2 and len(b) >= 3:
            tests[metric] = {"reported_median": float(a.median()), "other_median": float(b.median()),
                             "n_reported": int(len(a)), "n_other": int(len(b)),
                             "p_one_sided": float(mannwhitneyu(a, b, alternative="greater").pvalue)}
    conc = []
    for _, r in d.iterrows():
        if r["spoof_total"] > 0:
            p = binomtest(int(r["spoof_jumps"]), int(r["spoof_total"]), float(r["report_share"]), alternative="greater").pvalue
            conc.append({"day": r["day"], "k_delhi": int(r["spoof_jumps"]), "n_india": int(r["spoof_total"]),
                         "delhi_traffic_share": round(float(r["report_share"]), 4), "p_value": float(p)})

    out = {"days": sorted(t["day"].unique().tolist()), "series": json.loads(t.to_json(orient="records")),
           "tests_delhi_reported_vs_other": tests, "jump_concentration_delhi": conc,
           "note": "Reported days from public statements; Amritsar interference is chronic, so it has no clean control."}
    for target in (DER / "daily.json", WEB_DATA / "daily.json"):
        target.write_text(json.dumps(out, indent=2), encoding="utf-8")

    cols = ["day", "reported", "aircraft", "jam_share", "altdiv_share", "spoof_per_m", "chords", "loc_status", "loc_lat", "loc_lon", "loc_r95_km"]
    print(d[cols].to_string(index=False))
    print("\nTests (Delhi, reported days vs other days):", json.dumps(tests, indent=2))
    print("Jump concentration vs Delhi traffic share:", json.dumps(conc, indent=2))
    print("\nAmritsar:\n", t[t["region"] == "ATQ"][cols].to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "day":
        day_index(sys.argv[2])
    elif sys.argv[1:2] == ["report"]:
        report()
    elif sys.argv[1:2] == ["redo"]:
        for p in sorted(PARQ.glob("points_*.parquet")):
            try:
                day_index(p.stem.replace("points_", ""))
            except SystemExit as e:
                print(e)
    else:
        print(__doc__)