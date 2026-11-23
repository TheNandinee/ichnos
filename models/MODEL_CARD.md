# ICHNOS learned spoofing detector v1

HistGradientBoostingClassifier on per-aircraft-minute features (kinematic, altitude, integrity, context).
Training: 10 clean days with injected drift, jump and altitude-offset attacks on 20% of tracks; integrity values left unchanged. Minutes within 250 km of Delhi IGI and Amritsar are excluded.
Test: 4 other clean days, attacks injected with a different seed. Threshold set for 0.1% false positives on clean test minutes.

## Ablation (held-out days, injected attacks)

| Method | AUC | Recall @ FPR 0.1% | FPR | Drift | Jump | Altitude |
|---|---|---|---|---|---|---|
| model_full | 0.877 | 53.0% | 0.1% | 79.5% | 7.4% | 64.7% |
| model_no_kinematic | 0.744 | 21.9% | 0.1% | 0.1% | 0.0% | 69.2% |
| model_no_altitude | 0.777 | 34.3% | 0.1% | 79.5% | 8.3% | 4.6% |
| model_no_integrity | 0.876 | 52.1% | 0.1% | 78.2% | 7.2% | 63.5% |
| rules (lanes A+B) | n/a | 4.8% | 0.1% | 3.1% | 3.5% | 8.3% |
| rules OR model | n/a | 53.4% | 0.1% | n/a | n/a | n/a |

## Limits
- Injected attacks are a simulation; these numbers do not measure real-world recall.
- Real archives pass through readsb's own position filter, so real jumps look different from injected ones.
- 'Clean' days may still contain unreported interference.
- Real-world evidence is the day-level benchmark: python -m ichnos.bench_v1
