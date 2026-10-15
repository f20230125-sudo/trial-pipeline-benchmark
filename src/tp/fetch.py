"""Download the ClinicalTrials.gov snapshot: every study whose lead sponsor matches a search term in
data/ref/sponsor_queries.csv, plus one "ecosystem" pull of every study testing pembrolizumab.

Why this is more than a loop:
- The API pages with an opaque nextPageToken, so a run can only continue from a page it has already read. Each page is
  saved as raw bytes the moment it arrives, and a re-run reads cached pages instead of asking again (resume).
- The data is refreshed daily. Tokens from one refresh are not safe to mix with another, so the run records the API's
  dataTimestamp at the start and the end; if it moved, the pages are discarded and the run starts again.
- The server throttles, so every request waits, and 429/5xx answers are retried with backoff (Retry-After if it is sent).
- query.lead is a full-text search, so a term can return people or universities as well as the company. That is
  expected here; deciding who is who is the job of tp.sponsors, not of the download.
- Bytes are saved as received and read as UTF-8. Reading with the Windows default turns the registered mark into "Â®".

Usage:  python -m tp.fetch [--force] [--delay 1.5] [--only <slug>]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import requests

from . import sources as S

PAGE_SIZE = 1000
DELAY = 1.5
MAX_TRIES = 6
TIMEOUT = (30, 180)
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_WAIT = 120


class FetchError(RuntimeError):
    pass


class CountMismatch(FetchError):
    """Studies read do not add up to the total the API announced."""


@dataclass(frozen=True)
class Query:
    group: str
    term: str
    param: str  # "lead" (lead sponsor) or "intr" (intervention)

    @property
    def slug(self) -> str:
        return f"{_slug(self.group)}__{_slug(self.term)}"

    def params(self) -> dict[str, str]:
        return {f"query.{self.param}": self.term}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def load_queries(path: Path = S.REF / "sponsor_queries.csv") -> list[Query]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = [Query(r["group"].strip(), r["term"].strip(), r["param"].strip()) for r in csv.DictReader(fh)]
    slugs = [q.slug for q in rows]
    if len(set(slugs)) != len(slugs):
        raise FetchError("duplicate query slugs in sponsor_queries.csv")
    return rows


def _retry_after(resp) -> float | None:
    value = resp.headers.get("Retry-After") if getattr(resp, "headers", None) else None
    try:
        return min(float(value), MAX_WAIT) if value is not None else None
    except ValueError:
        return None  # an HTTP-date form; fall back to exponential backoff


def get_with_retry(session, url: str, params: dict, *, sleep: Callable[[float], None] = time.sleep,
                   max_tries: int = MAX_TRIES):
    """GET with backoff. Retries timeouts, connection errors, 429 and 5xx; any other status is final."""
    last = "no attempt made"
    for attempt in range(max_tries):
        wait = float(min(2 ** attempt, MAX_WAIT))
        try:
            resp = session.get(url, params=params, timeout=TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200:
                return resp
            if resp.status_code not in RETRY_STATUS:
                raise FetchError(f"HTTP {resp.status_code} for {url} {params}")
            last = f"HTTP {resp.status_code}"
            wait = _retry_after(resp) or wait
        if attempt < max_tries - 1:
            sleep(wait)
    raise FetchError(f"gave up after {max_tries} tries ({last}) for {url} {params}")


def api_version(session, sleep: Callable[[float], None] = time.sleep) -> str:
    resp = get_with_retry(session, S.VERSION_URL, {}, sleep=sleep)
    return json.loads(resp.content.decode("utf-8"))["dataTimestamp"]


def fetch_query(session, q: Query, *, raw_dir: Path = S.RAW, delay: float = DELAY,
                sleep: Callable[[float], None] = time.sleep, page_size: int = PAGE_SIZE) -> dict:
    """Read every page for one query (cached pages first). Returns its manifest entry; raises on a count mismatch."""
    out = raw_dir / q.slug
    out.mkdir(parents=True, exist_ok=True)
    total = None
    studies = 0
    size = 0
    n = 1
    token = None
    while True:
        page_file = out / f"page_{n:04d}.json"
        if page_file.exists():
            content = page_file.read_bytes()
        else:
            params = {**q.params(), "pageSize": str(page_size), "format": "json", "fields": S.FIELDS}
            if n == 1:
                params["countTotal"] = "true"
            else:
                params["pageToken"] = token
            content = get_with_retry(session, S.STUDIES_URL, params, sleep=sleep).content
            tmp = page_file.with_suffix(".part")
            tmp.write_bytes(content)  # bytes as received, never re-encoded
            tmp.replace(page_file)
            sleep(delay)
        page = json.loads(content.decode("utf-8"))
        if n == 1:
            total = page.get("totalCount")
        studies += len(page.get("studies", []))
        size += len(content)
        token = page.get("nextPageToken")
        if not token:
            break
        n += 1
    if total is None or studies != total:
        raise CountMismatch(f"{q.slug}: read {studies} studies but the API announced {total}")
    return {
        "group": q.group, "term": q.term, "param": q.param, "slug": q.slug,
        "totalCount": total, "pages": n, "studies": studies, "bytes": size,
        "url": f"{S.STUDIES_URL}?query.{q.param}={requests.utils.quote(q.term)}",
    }


def run(*, force: bool = False, delay: float = DELAY, only: str | None = None, session=None,
        raw_dir: Path = S.RAW, manifest_path: Path = S.MANIFEST, queries: list[Query] | None = None,
        sleep: Callable[[float], None] = time.sleep) -> dict:
    session = session or requests.Session()
    if hasattr(session, "headers"):
        session.headers.update({"User-Agent": S.USER_AGENT, "Accept": "application/json"})
    queries = queries if queries is not None else load_queries()
    if only:
        queries = [q for q in queries if q.slug == only]
        if not queries:
            raise FetchError(f"no query with slug {only!r}")

    start = api_version(session, sleep)
    marker = raw_dir / "_run.json"
    if force or (marker.exists() and json.loads(marker.read_text(encoding="utf-8")).get("dataTimestamp") != start):
        if raw_dir.exists():
            shutil.rmtree(raw_dir)  # pages from another refresh cannot be mixed with this one
    raw_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"dataTimestamp": start}), encoding="utf-8")

    entries = []
    for i, q in enumerate(queries, 1):
        entry = fetch_query(session, q, raw_dir=raw_dir, delay=delay, sleep=sleep)
        entries.append(entry)
        print(f"[{i}/{len(queries)}] {q.slug}: {entry['studies']} studies in {entry['pages']} page(s)", flush=True)

    end = api_version(session, sleep)
    if end != start:
        raise FetchError(f"the API refreshed during the run ({start} to {end}); run again to fetch a consistent snapshot")

    manifest = {
        "api": S.STUDIES_URL,
        "dataTimestamp_start": start,
        "dataTimestamp_end": end,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fields": S.FIELDS,
        "page_size": PAGE_SIZE,
        "terms": entries,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--force", action="store_true", help="discard cached pages and fetch everything again")
    ap.add_argument("--delay", type=float, default=DELAY, help="seconds to wait after each request")
    ap.add_argument("--only", help="fetch a single query slug (does not rewrite a complete manifest)")
    args = ap.parse_args(argv)
    try:
        manifest = run(force=args.force, delay=args.delay, only=args.only,
                       manifest_path=S.MANIFEST if not args.only else S.SNAPSHOT / "manifest.partial.json")
    except FetchError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1
    total = sum(t["studies"] for t in manifest["terms"])
    mb = sum(t["bytes"] for t in manifest["terms"]) / 1e6
    print(f"done: {len(manifest['terms'])} queries, {total:,} study rows (before de-duplication), {mb:,.0f} MB, "
          f"API data as of {manifest['dataTimestamp_start']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
