import pandas as pd
from scipy.stats import mannwhitneyu

t = pd.read_csv("data/derived/daily.csv")
d = t[t.region == "DEL"].set_index("day").copy()
d["atq_feed"] = t[t.region == "ATQ"].set_index("day")["aircraft"].reindex(d.index).fillna(0) > 20
d["india_reports"] = d["reports"] / d["report_share"]
rep = d["reported"].astype(bool)
buffer = (d.index >= "2025-10-27") & (d.index <= "2025-11-10") & ~rep
lowcov = d["india_reports"] < 0.5 * d["india_reports"].median()
d = d[~buffer & ~lowcov]

for metric in ("jam_share", "altdiv_share", "spoof_per_m"):
    for name, m in (("all days", d.index == d.index), ("ATQ feed on", d.atq_feed), ("ATQ feed off", ~d.atq_feed)):
        x = d[m].dropna(subset=[metric])
        p, n = x[x.reported.astype(bool)][metric], x[~x.reported.astype(bool)][metric]
        if len(p) >= 2 and len(n) >= 3:
            u = mannwhitneyu(p, n, alternative="greater")
            print(f"{metric:13s} {name:13s} AUC {u.statistic / (len(p) * len(n)):.2f}  p {u.pvalue:.3f}  pos/neg {len(p)}/{len(n)}")
        else:
            print(f"{metric:13s} {name:13s} too few days ({len(p)} pos / {len(n)} neg)")

print("\nTop Delhi jam days:")
print(d.sort_values("jam_share", ascending=False)[["reported", "atq_feed", "aircraft", "jam_share", "altdiv_share", "spoof_jumps"]].head(12).to_string())