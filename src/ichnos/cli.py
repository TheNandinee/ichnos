import argparse

from .config import DER, PARQ, RAW, ensure_dirs, load_config


def process_day(day, cfg, delete_raw=False):
    from .cluster import cluster_day
    from .detect import detect_day
    from .download import download_day
    from .ingest import ingest_day

    tar = download_day(day)
    if not (PARQ / f"points_{day}.parquet").exists():
        ingest_day(day, tar, cfg)
    anoms, traffic = detect_day(day, cfg)
    cluster_day(day, anoms, traffic, cfg, "all").to_parquet(DER / f"events_all_{day}.parquet")
    jam = anoms[anoms["lane"] == "jam"] if not anoms.empty else anoms
    cluster_day(day, jam, traffic, cfg, "jam").to_parquet(DER / f"events_jam_{day}.parquet")
    if delete_raw:
        tar.unlink(missing_ok=True)
        print(f"[run] deleted raw {tar.name}")


def main():
    ap = argparse.ArgumentParser(prog="ichnos")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("releases"); p.add_argument("--month", required=True, help="YYYY-MM or YYYY-MM-DD")
    for name in ("download", "peek", "ingest", "detect"):
        p = sub.add_parser(name); p.add_argument("--day", required=True)
    p = sub.add_parser("run"); p.add_argument("--days", nargs="+", required=True)
    p.add_argument("--delete-raw", action="store_true")
    sub.add_parser("bench")
    sub.add_parser("export")
    p = sub.add_parser("serve"); p.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    cfg = load_config()
    ensure_dirs()

    if a.cmd == "releases":
        from .download import tags_with_prefix
        repo, tags = tags_with_prefix(a.month[:4], a.month.replace("-", "."))
        for t in tags:
            print(t)
        print(f"{len(tags)} tags in adsblol/{repo}")
        if not tags:
            print(f"None found. Open https://github.com/adsblol/{repo}/releases and copy one tag name.")
    elif a.cmd == "download":
        from .download import download_day
        download_day(a.day)
    elif a.cmd == "peek":
        from .ingest import peek
        peek(RAW / f"{a.day}.tar")
    elif a.cmd == "ingest":
        from .ingest import ingest_day
        ingest_day(a.day, RAW / f"{a.day}.tar", cfg)
    elif a.cmd == "detect":
        process_day(a.day, cfg)
    elif a.cmd == "run":
        for d in a.days:
            process_day(d, cfg, a.delete_raw)
    elif a.cmd == "bench":
        from .bench import run_bench
        run_bench()
    elif a.cmd == "export":
        from .export import export_all
        export_all(cfg)
    elif a.cmd == "serve":
        import uvicorn
        uvicorn.run("ichnos.api:app", host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    main()
