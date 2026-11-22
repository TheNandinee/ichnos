# IN-RFI-Replay v1

An open benchmark of cited GNSS interference windows over India, and a day-level scorer for any detector.

- `windows.yaml`: 14 windows with citations, in four tiers:
  - **dated**: 4 Delhi windows (30 Oct – 7 Nov 2025);
  - **period**: 2 Delhi months (January and February 2026);
  - **chronic**: 7 windows (the Amritsar border region, the Amritsar NOTAM, and five airports with undated "regular reports");
  - **exploratory**: 1 window (Operation Sindoor, 7–10 May 2025), excluded from scoring.
- `data/daily_index_public.csv`: daily per-region index from ICHNOS over a weekly sample from March 2025 to February 2026, plus every day of the Delhi window. Jammer coordinates are removed.
- `results/`: scores for every method, `leaderboard.md`, and the learned-detector ablation.

**Scoring.** For each region with coverage (a median of at least 50 aircraft per day):
- days inside dated or period windows are positives;
- days within ±3 days of a dated window, and days in chronic periods, are excluded;
- all other sampled days are negatives.

We report:
- the day-level AUC, with a bootstrap 95% CI and a one-sided Mann–Whitney p;
- window hits: a window counts as hit if its peak day exceeds the 95th percentile of negative days, with a Wilson CI.

**Limits.**
- Labels come from public statements, not ground truth.
- "Negative" days may contain unreported interference.
- Only Delhi is scorable at present. The border region has no receiver coverage in the archive.

Derived data: ODbL 1.0 (contains data from adsb.lol contributors). Code: Apache-2.0.