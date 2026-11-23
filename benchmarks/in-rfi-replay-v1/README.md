# IN-RFI-Replay v1

An open benchmark of cited GNSS interference windows over India, and a day-level scorer for any detector.

## Contents

- `windows.yaml`: 14 windows with citations, in four tiers:
  - **dated**: 4 Delhi windows (30 Oct – 7 Nov 2025);
  - **period**: 2 Delhi months (January and February 2026);
  - **chronic**: 7 windows (Amritsar border region, Amritsar NOTAM, five airports with undated "regular reports");
  - **exploratory**: 1 window (Operation Sindoor, 7–10 May 2025), excluded from scoring.
- `data/daily_index_public.csv`: daily per-region index over 63 archive days (weekly, March 2025 – February 2026, plus every day of the Delhi window). Jammer coordinates are removed.
- `results/`: `scores.json`, `leaderboard.md`, `ablation.json`.

## Scoring

For each region with coverage (median of at least 50 aircraft per day):
- days inside dated or period windows are positives;
- days within ±3 days of a dated window, and chronic periods, are excluded;
- all other sampled days are negatives.

Reported: day-level AUC with a bootstrap 95% CI and a one-sided Mann–Whitney p; window hits (peak day above the 95th percentile of negatives) with a Wilson CI.

## Results (v1.0)

Delhi only (17 positive / 45 negative days). The other regions have no dated windows.

| Method | Day AUC (95% CI) | p | Windows hit |
|---|---|---|---|
| Track jumps | 0.85 (0.72–0.96) | 3.7e-06 | 5/6 |
| Spoofing rules combined | 0.85 (0.71–0.96) | 1.4e-05 | 5/6 |
| Altitude mismatch | 0.80 (0.66–0.92) | 1.2e-04 | 5/6 |
| Integrity-only jamming | 0.79 (0.64–0.92) | 2.7e-04 | 4/6 |
| Learned model | 0.73 (0.58–0.86) | 2.7e-03 | 4/6 |

The seven highest Delhi jamming days in the sample all fall in the reported week.

**Coverage confounder.** One volunteer receiver that sees the Amritsar area is online on only 26 of 63 days, and Delhi metrics are higher on those days. Stratified by that receiver (`scripts/confound.py`):

| Metric | Receiver online | Receiver offline |
|---|---|---|
| Jamming share | AUC 0.69 (p 0.08) | AUC 0.82 (p 0.002) |
| Altitude mismatch | AUC 0.55 (p 0.36) | AUC 0.89 (p < 0.001) |
| Jumps per million reports | AUC 0.87 (p 0.002) | AUC 0.84 (p < 0.001) |

The reported week survives the control. The Jan–Feb 2026 signal is inconclusive.

## Limits

- Labels come from public statements, not ground truth, and the six windows overlap.
- "Negative" days may contain unreported interference.
- Only Delhi is scorable.

Derived data: ODbL 1.0 (contains data from adsb.lol contributors). Code: Apache-2.0.