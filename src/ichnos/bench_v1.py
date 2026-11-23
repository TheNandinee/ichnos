"""IN-RFI-Replay v1 scorer.
  python -m ichnos.bench_v1
Reads data/derived/daily.csv (run `python -m ichnos.daily report` first) and, if present,
data/derived/model_scores.csv (from `python -m ichnos.learned score`)."""
import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import yaml
from scipy.stats import mannwhitneyu

from .bench import wilson
from .config import DER, ROOT

BENCH = ROOT / "benchmarks" / "in-rfi-replay-v1"
BUFFER_DAYS = 3
MIN_AIRCRAFT = 50
RULE_METRICS = {"integrity_jam": "jam_share", "spoof_altitude": "altdiv_share", "spoof_jumps": "spoof_per_m"}


def span(a, b):
    d0, d1 = date.fromisoformat(a), date.fromisoformat(b)
    return {(d0 + timedelta(i)).isoformat() for i in range((d1 - d0).days + 1)}


def load_windows():
    return yaml.safe_load((BENCH / "windows.yaml").read_text(encoding="utf-8"))["windows"]


def day_labels(windows, region, days):
    """1 = reported, 0 = negative, None = excluded (buffer, chronic or exploratory)."""
    pos, excl = set(), set()
    for w in windows:
        if w["region"] != region:
            continue
        s = span(w["start"], w["end"])
        if w["tier"] in ("dated", "period"):
            pos |= s
            if w["tier"] == "dated":
                lo = (date.fromisoformat(w["start"]) - timedelta(BUFFER_DAYS)).isoformat()
                hi = (date.fromisoformat(w["end"]) + timedelta(BUFFER_DAYS)).isoformat()
                excl |= span(lo, hi)
        else:
            excl |= s
    return {d: 1 if d in pos else (None if d in excl else 0) for d in days}


def auc_ci(pos, neg, n_boot=2000, seed=0):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    auc = lambda p, n: mannwhitneyu(p, n, alternative="two-sided").statistic / (len(p) * len(n))
    rng = np.random.default_rng(seed)
    boots = [auc(rng.choice(pos, len(pos)), rng.choice(neg, len(neg))) for _ in range(n_boot)]
    p = mannwhitneyu(pos, neg, alternative="greater").pvalue
    return float(auc(pos, neg)), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)), float(p)


def load_scores():
    t = pd.read_csv(DER / "daily.csv")
    base = t[["day", "region", "aircraft"]]
    frames = [t[["day", "region", "aircraft", col]].rename(columns={col: "score"}).assign(method=m)
              for m, col in RULE_METRICS.items()]
    s = pd.concat(frames, ignore_index=True)
    piv = s[s["method"].isin(["spoof_altitude", "spoof_jumps"])].pivot_table(
        index=["day", "region"], columns="method", values="score")
    rank = piv.groupby(level="region").rank(pct=True).mean(axis=1).rename("score").reset_index()
    s = pd.concat([s, rank.merge(base, on=["day", "region"]).assign(method="rules_spoof")], ignore_index=True)
    mp = DER / "model_scores.csv"
    if mp.exists():
        m = pd.read_csv(mp).merge(base, on=["day", "region"], how="left")
        s = pd.concat([s, m[["day", "region", "aircraft", "score", "method"]]], ignore_index=True)
    return t, s.dropna(subset=["score"])


def evaluate():
    windows = load_windows()
    table, scores = load_scores()
    days = sorted(scores["day"].unique())
    coverage, results = [], []
    for reg in sorted({w["region"] for w in windows}):
        sr = scores[scores["region"] == reg]
        med_ac = float(sr.groupby("day")["aircraft"].max().median()) if len(sr) else 0.0
        lab = day_labels(windows, reg, days)
        npos = sum(v == 1 for v in lab.values())
        nneg = sum(v == 0 for v in lab.values())
        ok = med_ac >= MIN_AIRCRAFT and npos >= 2 and nneg >= 3
        reason = None if ok else ("no receiver coverage" if med_ac < MIN_AIRCRAFT else "no dated/period windows")
        coverage.append({"region": reg, "median_aircraft_per_day": med_ac, "positive_days": npos,
                         "negative_days": nneg, "scorable": ok, "reason": reason})
        if not ok:
            continue
        for method, g in sr.groupby("method"):
            g = g.groupby("day")["score"].max()
            pos = [g[d] for d, v in lab.items() if v == 1 and d in g.index]
            neg = [g[d] for d, v in lab.items() if v == 0 and d in g.index]
            if len(pos) < 2 or len(neg) < 3:
                continue
            auc, lo, hi, p = auc_ci(pos, neg)
            thr = float(np.percentile(neg, 95))
            hits = n = 0
            for w in windows:
                if w["region"] != reg or w["tier"] not in ("dated", "period"):
                    continue
                ds = [d for d in span(w["start"], w["end"]) if d in g.index]
                if ds:
                    n += 1
                    hits += int(max(g[d] for d in ds) > thr)
            wlo, whi = wilson(hits, n)
            results.append({"region": reg, "method": method, "auc": auc, "auc_ci": [lo, hi], "p_one_sided": p,
                            "n_pos_days": len(pos), "n_neg_days": len(neg), "window_hits": hits,
                            "n_windows": n, "window_recall_ci": [wlo, whi]})
    return table, coverage, results


def main():
    table, coverage, results = evaluate()
    out = BENCH / "results"
    out.mkdir(parents=True, exist_ok=True)
    (BENCH / "data").mkdir(exist_ok=True)
    (out / "scores.json").write_text(json.dumps({"coverage": coverage, "results": results}, indent=2), encoding="utf-8")
    table.drop(columns=[c for c in table.columns if c.startswith("loc_")]).to_csv(
        BENCH / "data" / "daily_index_public.csv", index=False)
    f = lambda x: "n/a" if x is None else f"{x:.2f}"
    lines = ["# IN-RFI-Replay v1 leaderboard", "",
             "| Region | Method | Day AUC (95% CI) | p (one-sided) | Windows hit (95% CI) | Pos/neg days |",
             "|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: (r["region"], -r["auc"])):
        lines.append(f"| {r['region']} | {r['method']} | {r['auc']:.2f} ({r['auc_ci'][0]:.2f}–{r['auc_ci'][1]:.2f}) | "
                     f"{r['p_one_sided']:.3g} | {r['window_hits']}/{r['n_windows']} "
                     f"({f(r['window_recall_ci'][0])}–{f(r['window_recall_ci'][1])}) | {r['n_pos_days']}/{r['n_neg_days']} |")
    lines += ["", "## Coverage", "", "| Region | Median aircraft/day | Scorable | Reason |", "|---|---|---|---|"]
    lines += [f"| {c['region']} | {c['median_aircraft_per_day']:.0f} | {c['scorable']} | {c['reason'] or ''} |" for c in coverage]
    (out / "leaderboard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()