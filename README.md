# ICHNOS

Open, replayable GPS jamming and spoofing intelligence for Indian airspace, built from public ADS-B aircraft broadcasts.
Every flight, a sensor.

ICHNOS is receive-only. It never transmits, never jams or spoofs, and never accesses any third-party system.

## What it does
1. Downloads daily public ADS-B archives (adsb.lol, ODbL).
2. Keeps reports over India and stores them as Parquet.
3. Jamming lane: flags integrity drops (NIC < 7, NACp < 8).
4. Spoofing lane: flags physically impossible position jumps that pass track-consistency tests.
5. Clusters anomalies into multi-aircraft events with traffic-adaptive thresholds.
6. Bounds where a ground transmitter could be, using radio-horizon physics.
7. Scores itself on a public benchmark of dated incident windows (benchmarks/labels.yaml).
8. Exports a coarse public dataset for the web map in web/.

## Quick start

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    pip install -e .
    pytest -q
    python -m ichnos.cli releases --month 2025-11
    python -m ichnos.cli run --days 2025-10-14 2025-11-04
    python -m ichnos.cli bench
    python -m ichnos.cli export
    cd web && npm install && npm run dev

## Honest limits
- ADS-B coverage over India is uneven, and ADS-B under-counts jamming compared with ground detectors.
- Benchmark labels are time windows, not exact events.
- Physics gives a feasible region, never an exact source location.

## Licences
Code: Apache-2.0. Derived data: ODbL 1.0, see DATA_LICENSE.md.
