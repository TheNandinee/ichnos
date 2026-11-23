"""Write web/public/data/bench_v1.json: public summary of IN-RFI-Replay v1 (no coordinates).
Run after `python -m ichnos.daily report` and `python -m ichnos.bench_v1`."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DER = ROOT / "data" / "derived"
RES = ROOT / "benchmarks" / "in-rfi-replay-v1" / "results"
OUT = ROOT / "web" / "public" / "data" / "bench_v1.json"


def clean(o):
    if isinstance(o, float):
        return None if math.isnan(o) else o
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items() if not k.startswith("loc")}
    if isinstance(o, list):
        return [clean(v) for v in o]
    return o


truthy = lambda x: str(x) == "True"

daily = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DER.glob("daily_*.json"))]
t = pd.read_csv(DER / "daily.csv")

d = t[t.region == "DEL"].dropna(subset=["jam_share"]).sort_values("jam_share", ascending=False)
top_run = 0
for x in d["reported"]:
    if not truthy(x):
        break
    top_run += 1
top = [{"day": r.day, "reported": truthy(r.reported), "jam_share": float(r.jam_share),
        "altdiv_share": float(r.altdiv_share), "spoof_jumps": int(r.spoof_jumps)} for r in d.head(10).itertuples()]

n4 = json.loads((DER / "daily_2025-11-04.json").read_text(encoding="utf-8"))
R = n4["regions"]
nov4 = {"del_aircraft": R["DEL"]["aircraft"], "del_jam": R["DEL"]["jam_share"], "rest_jam": R["REST"]["jam_share"],
        "del_alt": R["DEL"]["altdiv_share"], "rest_alt": R["REST"]["altdiv_share"],
        "del_jumps": R["DEL"]["spoof_jumps"], "total_jumps": n4["spoof_total"]}

a = t[(t.region == "ATQ") & (t.aircraft > 20)]
atq = {"feed_days": int(len(a)), "jam_min": float(a.jam_share.min()), "jam_max": float(a.jam_share.max())}

scores = json.loads((RES / "scores.json").read_text(encoding="utf-8"))
board = sorted([r for r in scores["results"] if r["region"] == "DEL"], key=lambda r: -r["auc"])
ablation = json.loads((RES / "ablation.json").read_text(encoding="utf-8"))

out = clean({
    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "n_days": len(daily), "n_reports": sum(x["n_reports"] for x in daily),
    "first_day": min(x["day"] for x in daily), "last_day": max(x["day"] for x in daily),
    "delhi": {"top_run": top_run, "top_days": top, "nov4": nov4},
    "atq": atq, "leaderboard": board, "coverage": scores["coverage"], "ablation": ablation,
    "attribution": "Contains data from adsb.lol contributors, ODbL 1.0",
})
s = json.dumps(out, indent=2)
assert "loc_" not in s and '"lat"' not in s and '"lon"' not in s, "coordinates leaked"
OUT.write_text(s, encoding="utf-8")
print(f"wrote {OUT.relative_to(ROOT)}: {out['n_days']} days, {out['n_reports']:,} reports, "
      f"top-{top_run} Delhi jam days all reported, best AUC {board[0]['auc']:.2f} ({board[0]['method']})")