"""Write scripts/days_v1.txt: Delhi window days first, then a weekly 12-month sample (priority order)."""
from datetime import date, timedelta
from pathlib import Path

window = [date(2025, 10, 30) + timedelta(i) for i in range(9)]
weekly, d = [], date(2025, 3, 5)
while d <= date(2026, 2, 25):
    weekly.append(d)
    d += timedelta(7)
extra = [date(2025, 5, 7), date(2025, 5, 8), date(2025, 5, 9), date(2025, 5, 10), date(2025, 10, 14)]
order = window + weekly[::4] + extra + [x for i, x in enumerate(weekly) if i % 4]
out, seen = [], set()
for x in order:
    if x not in seen:
        seen.add(x)
        out.append(x.isoformat())
Path(__file__).with_name("days_v1.txt").write_text("\n".join(out) + "\n")
print(f"{len(out)} days written to scripts/days_v1.txt")