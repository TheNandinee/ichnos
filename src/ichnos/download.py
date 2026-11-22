import csv
import hashlib
import http.client
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .config import DATA, RAW

GH = "https://api.github.com/repos/adsblol/{repo}"
READ_TIMEOUT_S = 300
MAX_ATTEMPTS = 60


def _api_headers():
    h = {"User-Agent": "ichnos-research", "Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _get_json(url):
    req = urllib.request.Request(url, headers=_api_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code in (403, 429):
            raise SystemExit("GitHub API rate limit hit. Wait an hour, or set GITHUB_TOKEN.")
        raise


def repo_for(year):
    return f"globe_history_{year}"


def tags_with_prefix(year, prefix):
    repo = repo_for(year)
    for p in (f"v{prefix}", prefix):
        refs = _get_json(GH.format(repo=repo) + f"/git/matching-refs/tags/{p}") or []
        tags = sorted({r["ref"].split("/", 2)[2] for r in refs if isinstance(r, dict) and "ref" in r})
        if tags:
            return repo, tags
    return repo, []


def find_release(day, flavour="prod"):
    repo, tags = tags_with_prefix(day[:4], day.replace("-", "."))
    pick = [t for t in tags if flavour in t] or tags
    if not pick:
        raise SystemExit(f"No tags for {day} in adsblol/{repo}.")
    tag = pick[0]
    rel = _get_json(GH.format(repo=repo) + f"/releases/tags/{tag}")
    if not rel:
        raise SystemExit(f"Tag {tag} exists but has no release attached.")
    return repo, rel


def _append_manifest(day, repo, tag, path, sha, nbytes):
    mf = DATA / "manifest.csv"
    new = not mf.exists()
    with open(mf, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["day", "dataset", "release_tag", "file", "bytes", "sha256", "licence", "retrieved_at_utc"])
        w.writerow([day, f"adsblol/{repo}", tag, path.name, nbytes, sha, "ODbL-1.0",
                    datetime.now(timezone.utc).isoformat(timespec="seconds")])


def _fetch_asset(asset, f, sha):
    """Download one asset into open file f, resuming with HTTP Range until the byte count matches."""
    size, got, attempts = asset["size"], 0, 0
    while got < size:
        attempts += 1
        if attempts > MAX_ATTEMPTS:
            raise SystemExit(f"Gave up on {asset['name']} at {got}/{size} bytes. Check your connection and rerun.")
        headers = {"User-Agent": "ichnos-research"}
        if got:
            headers["Range"] = f"bytes={got}-"
        req = urllib.request.Request(asset["browser_download_url"], headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=READ_TIMEOUT_S) as r:
                if got and getattr(r, "status", 200) != 206:
                    raise SystemExit("Server ignored the resume request. Delete data/raw/*.part and rerun.")
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha.update(chunk)
                    got += len(chunk)
                    if got % (500 << 20) < (1 << 20):
                        print(f"[download]   {asset['name']}: {got / 1e9:.2f} / {size / 1e9:.2f} GB")
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as e:
            print(f"[download]   network error ({e}); retrying in 5 s")
            time.sleep(5)
        if got < size:
            print(f"[download]   short read {got}/{size} bytes; resuming (attempt {attempts + 1})")
    if got != size:
        raise SystemExit(f"{asset['name']}: got {got} bytes, expected {size}.")
    return got


def download_day(day):
    out = RAW / f"{day}.tar"
    if out.exists() and out.stat().st_size > 0:
        print(f"[download] {out.name} already present ({out.stat().st_size / 1e9:.2f} GB)")
        return out
    repo, rel = find_release(day)
    assets = sorted((a for a in rel.get("assets", []) if ".tar" in a["name"]), key=lambda a: a["name"])
    if not assets:
        raise SystemExit(f"Release {rel['tag_name']} has no .tar assets.")
    expected = sum(a["size"] for a in assets)
    print(f"[download] {rel['tag_name']}: {len(assets)} part(s), {expected / 1e9:.2f} GB")
    tmp = out.with_suffix(".tar.part")
    sha = hashlib.sha256()
    n = 0
    with open(tmp, "wb") as f:
        for a in assets:
            print(f"[download] {a['name']} ({a['size'] / 1e9:.2f} GB)")
            n += _fetch_asset(a, f, sha)
    if n != expected:
        raise SystemExit(f"Size mismatch: {n} vs {expected} bytes. Delete {tmp.name} and rerun.")
    tmp.rename(out)
    _append_manifest(day, repo, rel["tag_name"], out, sha.hexdigest(), n)
    print(f"[download] VERIFIED {out.name}: {n / 1e9:.2f} GB, sha256 {sha.hexdigest()[:16]}...")
    return out