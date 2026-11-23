import csv
import gzip
import json
import tarfile
import time

import pyarrow as pa
import pyarrow.parquet as pq

from .config import DER, PARQ

try:
    import orjson
    _loads = orjson.loads
except ImportError:
    _loads = json.loads

NIC_MAX_AGE_S = 60  # never carry an integrity value further than this

SCHEMA = pa.schema([
    ("icao", pa.string()), ("ts_ms", pa.int64()), ("lat", pa.float64()), ("lon", pa.float64()),
    ("alt_ft", pa.float64()), ("alt_geom_ft", pa.float64()), ("gs_kt", pa.float64()),
    ("nic", pa.float64()), ("nacp", pa.float64()), ("flags", pa.int32()), ("src", pa.string()),
])


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _decode(raw):
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return _loads(raw)


def trace_rows(obj, bb):
    """readsb trace entry: [dt, lat, lon, alt|'ground'|None, gs, track, flags, vrate, details|None,
    source, alt_geom, geom_rate, ...]. If flags & 8, field 3 is geometric rather than barometric."""
    cols = {k: [] for k in SCHEMA.names}
    icao = str(obj.get("icao", "")).lower()
    t0 = float(obj.get("timestamp", 0) or 0)
    nic = nacp = None
    t_nic = t_nacp = -1e18
    for p in obj.get("trace") or []:
        if not isinstance(p, list) or len(p) < 4:
            continue
        t = t0 + float(p[0])
        det = p[8] if len(p) > 8 else None
        if isinstance(det, dict):
            if "nic" in det:
                nic, t_nic = _num(det.get("nic")), t
            if "nac_p" in det:
                nacp, t_nacp = _num(det.get("nac_p")), t
        lat, lon, alt = p[1], p[2], p[3]
        if lat is None or lon is None or alt == "ground":
            continue
        if not (bb["lat_min"] <= lat <= bb["lat_max"] and bb["lon_min"] <= lon <= bb["lon_max"]):
            continue
        flags = p[6] if len(p) > 6 and isinstance(p[6], int) else 0
        geom = _num(p[10]) if len(p) > 10 else None
        if geom is None and isinstance(det, dict):
            geom = _num(det.get("alt_geom"))
        cols["icao"].append(icao)
        cols["ts_ms"].append(int(t * 1000))
        cols["lat"].append(float(lat))
        cols["lon"].append(float(lon))
        cols["alt_ft"].append(_num(alt))
        cols["alt_geom_ft"].append(geom)
        cols["gs_kt"].append(_num(p[4]) if len(p) > 4 else None)
        cols["nic"].append(nic if t - t_nic <= NIC_MAX_AGE_S else None)
        cols["nacp"].append(nacp if t - t_nacp <= NIC_MAX_AGE_S else None)
        cols["flags"].append(int(flags))
        src = p[9] if len(p) > 9 else None
        cols["src"].append(str(src) if src is not None else None)
    return cols


def peek(tar_path, n=1):
    with tarfile.open(tar_path, "r:*") as tf:
        for m in tf:
            if m.isfile() and "trace_full" in m.name:
                obj = _decode(tf.extractfile(m).read())
                print("file:", m.name, "| keys:", list(obj.keys()))
                for entry in (obj.get("trace") or [])[:5]:
                    print(json.dumps(entry)[:400])
                n -= 1
                if n <= 0:
                    return


def ingest_day(day, tar_path, cfg):
    bb = cfg["india_bbox"]
    out = PARQ / f"points_{day}.parquet"
    tmp = out.with_suffix(".parquet.part")
    writer = pq.ParquetWriter(tmp, SCHEMA, compression="zstd")
    batch = {k: [] for k in SCHEMA.names}
    n_files = n_rows = 0
    complete = True
    t_start = time.time()

    def flush():
        nonlocal batch, n_rows
        if batch["icao"]:
            writer.write_table(pa.table(batch, schema=SCHEMA))
            n_rows += len(batch["icao"])
            batch = {k: [] for k in SCHEMA.names}

    try:
        with tarfile.open(tar_path, "r:*") as tf:
            for m in tf:
                if not m.isfile() or "trace_full" not in m.name:
                    continue
                f = tf.extractfile(m)
                if f is None:
                    continue
                try:
                    obj = _decode(f.read())
                except Exception:
                    continue
                rows = trace_rows(obj, bb)
                for k in batch:
                    batch[k].extend(rows[k])
                n_files += 1
                if len(batch["icao"]) >= 500_000:
                    flush()
    except (tarfile.ReadError, EOFError, OSError) as e:
        complete = False
        print(f"[ingest] WARNING: archive ended early ({e}); keeping {n_files} traces")
    flush()
    writer.close()
    tmp.rename(out)
    secs = time.time() - t_start
    perf = DER / "perf.csv"
    new = not perf.exists()
    with open(perf, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["day", "trace_files", "india_rows", "seconds", "rows_per_s", "complete"])
        w.writerow([day, n_files, n_rows, round(secs, 1), round(n_rows / secs, 1) if secs else 0, complete])
    print(f"[ingest] {day}: {n_rows} India reports from {n_files} traces in {secs / 60:.1f} min")
    return out