"""Learned spoofing detector, trained on spoofing injected into real clean tracks.
  python -m ichnos.learned train   # train + ablation on held-out days -> models/, results
  python -m ichnos.learned score   # apply to every processed day -> data/derived/model_scores.csv
Injected-attack metrics measure the simulated attack model only; real-world evidence is the
day-level benchmark (python -m ichnos.bench_v1)."""
import json
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from .config import DER, PARQ, ROOT, load_config
from .daily import RADIUS_KM, REGIONS, reported_del
from .geo import haversine_km
from .lanes2 import alt_consensus, alt_steps
from .spoofing import detect_spoofing

MODEL_DIR = ROOT / "models"
RESULTS = ROOT / "benchmarks" / "in-rfi-replay-v1" / "results"
FEATURES = {
    "kinematic": ["v_max", "v_med", "resid_max", "speed_ratio", "jump_ratio"],
    "altitude": ["dh_step", "dh_rel", "dh_std"],
    "integrity": ["nic_med", "nacp_med", "nic_drop"],
    "context": ["alt", "n"],
}
ALL = [f for g in FEATURES.values() for f in g]
TARGET_FPR = 1e-3


def minute_features(df):
    df = df.sort_values(["icao", "ts_ms"]).reset_index(drop=True)
    icao = df["icao"].to_numpy()
    t = df["ts_ms"].to_numpy() / 1000.0
    lat, lon = df["lat"].to_numpy(float), df["lon"].to_numpy(float)
    same = np.r_[False, icao[1:] == icao[:-1]]
    nxt = np.r_[icao[1:] == icao[:-1], False]
    lat_p, lat_n = np.r_[np.nan, lat[:-1]], np.r_[lat[1:], np.nan]
    lon_p, lon_n = np.r_[np.nan, lon[:-1]], np.r_[lon[1:], np.nan]
    t_p, t_n = np.r_[np.nan, t[:-1]], np.r_[t[1:], np.nan]
    with np.errstate(divide="ignore", invalid="ignore"):
        dt = t - t_p
        v = np.where(same & (dt >= 0.5), haversine_km(lat_p, lon_p, lat, lon) * 1000.0 / dt, np.nan)
        frac = (t - t_p) / (t_n - t_p)
    plat, plon = lat_p + (lat_n - lat_p) * frac, lon_p + (lon_n - lon_p) * frac
    resid = np.where(same & nxt, haversine_km(lat, lon, plat, plon) * 1000.0, np.nan)
    baro_ok = ((df["flags"].to_numpy() & 8) == 0) & df["alt_geom_ft"].notna().to_numpy() & df["alt_ft"].notna().to_numpy()
    df = df.assign(v=v, resid=resid, gs_ms=df["gs_kt"] * 0.514444,
                   dh=np.where(baro_ok, df["alt_geom_ft"] - df["alt_ft"], np.nan),
                   minute=df["ts_ms"] // 60000)
    agg = dict(n=("ts_ms", "size"), v_max=("v", "max"), v_med=("v", "median"), resid_max=("resid", "max"),
               gs_med=("gs_ms", "median"), dh_med=("dh", "median"), dh_std=("dh", "std"),
               nic_med=("nic", "median"), nacp_med=("nacp", "median"), alt=("alt_ft", "median"),
               lat=("lat", "mean"), lon=("lon", "mean"))
    if "label" in df:
        agg.update(label=("label", "max"), attack=("attack", "max"))
    f = df.groupby(["icao", "minute"], as_index=False).agg(**agg)
    near = f["icao"].eq(f["icao"].shift()) & ((f["minute"] - f["minute"].shift()) <= 3)
    gap = (f["minute"] - f["minute"].shift()).to_numpy(float)
    jump = haversine_km(f["lat"].shift().to_numpy(float), f["lon"].shift().to_numpy(float),
                        f["lat"].to_numpy(float), f["lon"].to_numpy(float)) * 1000.0
    moving = f["gs_med"] > 30
    with np.errstate(divide="ignore", invalid="ignore"):
        f["jump_ratio"] = pd.Series(jump / (f["gs_med"].to_numpy() * 60.0 * gap)).where(near & moving)
        f["speed_ratio"] = (f["v_med"] / f["gs_med"]).where(moving)
    f["dh_step"] = (f["dh_med"] - f["dh_med"].shift()).abs().where(near)
    f["nic_drop"] = (f["nic_med"].shift() - f["nic_med"]).where(near)
    f["dh_rel"] = f["dh_med"] - f.groupby("icao")["dh_med"].transform("median")
    return f


def inject(df, rng, frac=0.2, min_track_min=20):
    """Add spoofing to a fraction of real tracks. Integrity values are left unchanged,
    because real spoofing usually keeps them high."""
    df = df.reset_index(drop=True)
    lat, lon = df["lat"].to_numpy(float).copy(), df["lon"].to_numpy(float).copy()
    geom = df["alt_geom_ft"].to_numpy(float).copy()
    t = df["ts_ms"].to_numpy() / 1000.0
    lab = np.zeros(len(df), np.int8)
    att = np.full(len(df), "", dtype=object)
    groups = df.groupby("icao").indices
    keys = list(groups)
    rng.shuffle(keys)
    for k in keys[: max(1, int(len(keys) * frac))]:
        ix = groups[k]
        t0, t1 = t[ix].min(), t[ix].max()
        if t1 - t0 < min_track_min * 60:
            continue
        dur = min(rng.uniform(5, 30) * 60, 0.8 * (t1 - t0))
        s = rng.uniform(t0, t1 - dur)
        m = ix[(t[ix] >= s) & (t[ix] < s + dur)]
        if len(m) < 5:
            continue
        kind = rng.choice(["drift", "jump", "altitude"])
        b = rng.uniform(0, 2 * np.pi)
        if kind == "drift":
            off = rng.uniform(30, 150) * (t[m] - s)
        elif kind == "jump":
            off = np.full(len(m), rng.uniform(3000, 30000))
        else:
            off = np.full(len(m), rng.uniform(1000, 5000))
            geom[m] = geom[m] + rng.choice([-1, 1]) * rng.uniform(1000, 5000)
        lat[m] += off * np.cos(b) / 111320.0
        lon[m] += off * np.sin(b) / (111320.0 * np.cos(np.radians(lat[m])))
        lab[m], att[m] = 1, kind
    return df.assign(lat=lat, lon=lon, alt_geom_ft=geom, label=lab, attack=att)


def rule_minutes(df, cfg):
    d = df.sort_values(["icao", "ts_ms"]).reset_index(drop=True).assign(h3="", hour=0)
    hits = [detect_spoofing(d, cfg["spoofing"]), alt_steps(d), alt_consensus(d)]
    return {(i, m) for h in hits for i, m in zip(h["icao"], h["ts_ms"] // 60000)}


def away_from_hotspots(f, km=250):
    keep = np.ones(len(f), bool)
    for key in ("DEL", "ATQ"):
        _, la, lo = REGIONS[key]
        keep &= haversine_km(f["lat"].to_numpy(float), f["lon"].to_numpy(float), la, lo) > km
    return f[keep]


def clean_days():
    days = sorted(p.stem.replace("points_", "") for p in PARQ.glob("points_*.parquet"))
    bad = lambda d: reported_del(d) or "2025-10-27" <= d <= "2025-11-10" or "2025-05-07" <= d <= "2025-05-12"
    return [d for d in days if not bad(d)]


def build(days, seed, cfg, rules=False):
    rng = np.random.default_rng(seed)
    out = []
    for d in days:
        raw = inject(pd.read_parquet(PARQ / f"points_{d}.parquet"), rng)
        f = away_from_hotspots(minute_features(raw)).assign(day=d)
        if rules:
            keys = rule_minutes(raw, cfg)
            f["rule"] = [(i, m) in keys for i, m in zip(f["icao"], f["minute"])]
        out.append(f)
        print(f"[learned] {d}: {len(f)} aircraft-minutes, {int(f['label'].sum())} injected")
    return pd.concat(out, ignore_index=True)


def fit(X, y):
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                                         l2_regularization=1.0, class_weight="balanced", random_state=0)
    return clf.fit(X, y)


def op_point(y, p):
    thr = float(np.quantile(p[y == 0], 1 - TARGET_FPR))
    return thr, float((p[y == 1] > thr).mean()), float((p[y == 0] > thr).mean())


def train(max_train=10, max_test=4):
    cfg = load_config()
    days = clean_days()
    if len(days) < 6:
        raise SystemExit(f"Need at least 6 clean processed days; have {len(days)}. Let the overnight run finish.")
    test_days = days[::3][:max_test]
    train_days = [d for d in days if d not in test_days][:max_train]
    tr, te = build(train_days, 1, cfg), build(test_days, 2, cfg, rules=True)
    y_tr, y_te = tr["label"].to_numpy(), te["label"].to_numpy()
    rows, full = [], None
    variants = {"model_full": ALL}
    variants.update({f"model_no_{g}": [f for f in ALL if f not in FEATURES[g]] for g in ("kinematic", "altitude", "integrity")})
    for name, feats in variants.items():
        clf = fit(tr[feats], y_tr)
        p = clf.predict_proba(te[feats])[:, 1]
        thr, tpr, fpr = op_point(y_te, p)
        row = {"method": name, "auc": float(roc_auc_score(y_te, p)), "recall_at_fpr_0.1pct": tpr, "fpr": fpr}
        row.update({f"recall_{k}": float((p[(y_te == 1) & (te["attack"] == k).to_numpy()] > thr).mean())
                    for k in ("drift", "jump", "altitude")})
        rows.append(row)
        if name == "model_full":
            full = (clf, thr, p)
    rule = te["rule"].to_numpy()
    rule_row = {"method": "rules (lanes A+B)", "auc": None, "recall_at_fpr_0.1pct": float(rule[y_te == 1].mean()),
                "fpr": float(rule[y_te == 0].mean())}
    rule_row.update({f"recall_{k}": float(rule[(y_te == 1) & (te["attack"] == k).to_numpy()].mean())
                     for k in ("drift", "jump", "altitude")})
    either = rule | (full[2] > full[1])
    rows += [rule_row, {"method": "rules OR model", "auc": None,
                        "recall_at_fpr_0.1pct": float(either[y_te == 1].mean()), "fpr": float(either[y_te == 0].mean())}]
    MODEL_DIR.mkdir(exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": full[0], "features": ALL, "threshold": full[1], "train_days": train_days,
                 "test_days": test_days, "target_fpr": TARGET_FPR}, MODEL_DIR / "spoof_hgb_v1.joblib")
    (RESULTS / "ablation.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    pct = lambda x: "n/a" if x is None or np.isnan(x) else f"{100 * x:.1f}%"
    lines = ["| Method | AUC | Recall @ FPR 0.1% | FPR | Drift | Jump | Altitude |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['method']} | {'n/a' if r['auc'] is None else f'{r[chr(97)+chr(117)+chr(99)]:.3f}'} | "
              f"{pct(r['recall_at_fpr_0.1pct'])} | {pct(r['fpr'])} | {pct(r.get('recall_drift'))} | "
              f"{pct(r.get('recall_jump'))} | {pct(r.get('recall_altitude'))} |" for r in rows]
    (MODEL_DIR / "MODEL_CARD.md").write_text("\n".join([
        "# ICHNOS learned spoofing detector v1", "",
        "HistGradientBoostingClassifier on per-aircraft-minute features (kinematic, altitude, integrity, context).",
        f"Training: {len(train_days)} clean days with injected drift, jump and altitude-offset attacks on 20% of tracks; "
        "integrity values left unchanged. Minutes within 250 km of Delhi IGI and Amritsar are excluded.",
        f"Test: {len(test_days)} other clean days, attacks injected with a different seed. "
        f"Threshold set for {TARGET_FPR:.1%} false positives on clean test minutes.", "",
        "## Ablation (held-out days, injected attacks)", "", *lines, "",
        "## Limits",
        "- Injected attacks are a simulation; these numbers do not measure real-world recall.",
        "- Real archives pass through readsb's own position filter, so real jumps look different from injected ones.",
        "- 'Clean' days may still contain unreported interference.",
        "- Real-world evidence is the day-level benchmark: python -m ichnos.bench_v1",
    ]) + "\n", encoding="utf-8")
    print("\n".join(lines))


def score_all():
    pack = joblib.load(MODEL_DIR / "spoof_hgb_v1.joblib")
    rows = []
    for p in sorted(PARQ.glob("points_*.parquet")):
        day = p.stem.replace("points_", "")
        f = minute_features(pd.read_parquet(p))
        f["flag"] = pack["model"].predict_proba(f[pack["features"]])[:, 1] > pack["threshold"]
        for key, (_, la, lo) in REGIONS.items():
            sub = f[haversine_km(f["lat"].to_numpy(float), f["lon"].to_numpy(float), la, lo) <= RADIUS_KM]
            ac = sub["icao"].nunique()
            rows.append({"day": day, "region": key, "method": "model",
                         "score": sub.loc[sub["flag"], "icao"].nunique() / ac if ac else np.nan})
        print(f"[learned] scored {day}")
    pd.DataFrame(rows).to_csv(DER / "model_scores.csv", index=False)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "train":
        train()
    elif cmd == "score":
        score_all()
    else:
        print(__doc__)