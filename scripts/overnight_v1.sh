#!/usr/bin/env bash
# Run: caffeinate -i bash scripts/overnight_v1.sh 2>&1 | tee -a data/derived/overnight_v1.log
cd "$(dirname "$0")/.."
source .venv/bin/activate
while read -r d; do
  [ -z "$d" ] && continue
  if [ -f "data/parquet/points_$d.parquet" ] && [ -f "data/derived/daily_$d.json" ]; then echo "skip $d"; continue; fi
  echo "=== $d  $(date +%H:%M) ==="
  if [ ! -f "data/parquet/points_$d.parquet" ]; then
    python -m ichnos.cli download --day "$d" < /dev/null || { echo "download failed: $d"; continue; }
    python -m ichnos.cli ingest --day "$d" < /dev/null || { echo "ingest failed: $d"; continue; }
    rm -f "data/raw/$d.tar"
  fi
  python -m ichnos.daily day "$d" < /dev/null || echo "daily failed: $d"
done < scripts/days_v1.txt
python -m ichnos.daily report > data/derived/report_latest.txt 2>&1 || true
echo "finished $(date)"