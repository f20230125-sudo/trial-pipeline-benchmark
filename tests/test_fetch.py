"""The fetcher is tested against a fake session: no network, no waiting."""

from __future__ import annotations

import json

import pytest
import requests

from tp import fetch
from tp import sources as S


class Resp:
    def __init__(self, status=200, body: bytes = b"{}", headers=None):
        self.status_code = status
        self.content = body
        self.headers = headers or {}


def page(n_studies: int, token: str | None = None, total: int | None = None, text: str = "x") -> Resp:
    body = {"studies": [{"id": f"{text}{i}"} for i in range(n_studies)]}
    if token:
        body["nextPageToken"] = token
    if total is not None:
        body["totalCount"] = total
    return Resp(200, json.dumps(body, ensure_ascii=False).encode("utf-8"))


class FakeSession:
    """Answers the version URL from `versions` and every study request from `studies`, in order."""

    def __init__(self, studies, versions=("2026-10-14T09:00:05",)):
        self.studies = list(studies)
        self.versions = list(versions)
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if url == S.VERSION_URL:
            v = self.versions.pop(0) if len(self.versions) > 1 else self.versions[0]
            return Resp(200, json.dumps({"dataTimestamp": v}).encode())
        item = self.studies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


Q = fetch.Query("MSD", "Merck", "lead")


def study_calls(session):
    return [c for c in session.calls if c[0] == S.STUDIES_URL]


def test_pages_until_the_token_is_absent(tmp_path):
    s = FakeSession([page(2, "t1", total=5), page(2, "t2"), page(1)])
    entry = fetch.fetch_query(s, Q, raw_dir=tmp_path, sleep=lambda _: None)
    assert (entry["studies"], entry["pages"], entry["totalCount"]) == (5, 3, 5)
    calls = study_calls(s)
    assert [c[1].get("pageToken") for c in calls] == [None, "t1", "t2"]
    assert [("countTotal" in c[1]) for c in calls] == [True, False, False]
    assert all(c[1]["pageSize"] == "1000" and "fields" in c[1] for c in calls)
    assert calls[0][1]["query.lead"] == "Merck"


def test_retry_after_header_is_honoured():
    waits = []
    s = FakeSession([Resp(429, headers={"Retry-After": "7"}), page(1)])
    resp = fetch.get_with_retry(s, S.STUDIES_URL, {}, sleep=waits.append)
    assert resp.status_code == 200 and waits == [7.0]


def test_server_errors_back_off_exponentially():
    waits = []
    s = FakeSession([Resp(500), Resp(502), Resp(503), page(1)])
    fetch.get_with_retry(s, S.STUDIES_URL, {}, sleep=waits.append)
    assert waits == [1.0, 2.0, 4.0]


def test_timeouts_are_retried_then_give_up():
    waits = []
    s = FakeSession([requests.Timeout("slow")] * 3)
    with pytest.raises(fetch.FetchError, match="gave up after 3 tries"):
        fetch.get_with_retry(s, S.STUDIES_URL, {}, sleep=waits.append, max_tries=3)
    assert waits == [1.0, 2.0]  # no wait after the last attempt


def test_other_statuses_are_final():
    s = FakeSession([Resp(404)])
    with pytest.raises(fetch.FetchError, match="HTTP 404"):
        fetch.get_with_retry(s, S.STUDIES_URL, {}, sleep=lambda _: None)
    assert len(study_calls(s)) == 1


def test_resume_reads_cached_pages_and_asks_only_for_the_rest(tmp_path):
    first = page(2, "t1", total=3)
    d = tmp_path / Q.slug
    d.mkdir(parents=True)
    (d / "page_0001.json").write_bytes(first.content)
    s = FakeSession([page(1)])
    entry = fetch.fetch_query(s, Q, raw_dir=tmp_path, sleep=lambda _: None)
    assert entry["studies"] == 3
    assert [c[1].get("pageToken") for c in study_calls(s)] == ["t1"]


def test_count_mismatch_raises(tmp_path):
    s = FakeSession([page(2, total=3)])
    with pytest.raises(fetch.CountMismatch, match="read 2 studies but the API announced 3"):
        fetch.fetch_query(s, Q, raw_dir=tmp_path, sleep=lambda _: None)


def test_bytes_are_saved_as_received_and_read_as_utf8(tmp_path):
    p = page(1, total=1, text="Keytruda® Türkiye ")
    s = FakeSession([p])
    fetch.fetch_query(s, Q, raw_dir=tmp_path, sleep=lambda _: None)
    saved = (tmp_path / Q.slug / "page_0001.json").read_bytes()
    assert saved == p.content
    assert "Keytruda®" in saved.decode("utf-8") and "Â®" not in saved.decode("utf-8")


def test_a_half_written_page_is_never_mistaken_for_a_page(tmp_path):
    s = FakeSession([page(1, total=1)])
    fetch.fetch_query(s, Q, raw_dir=tmp_path, sleep=lambda _: None)
    assert not list((tmp_path / Q.slug).glob("*.part"))


def test_run_writes_a_manifest_that_ties_to_the_totals(tmp_path):
    s = FakeSession([page(2, total=2)], versions=("v1",))
    m = fetch.run(session=s, raw_dir=tmp_path / "raw", manifest_path=tmp_path / "m.json", queries=[Q],
                  sleep=lambda _: None)
    saved = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert saved == m
    assert m["dataTimestamp_start"] == m["dataTimestamp_end"] == "v1"
    assert m["terms"][0]["studies"] == m["terms"][0]["totalCount"] == 2


def test_run_refuses_a_snapshot_the_api_refreshed_during(tmp_path):
    s = FakeSession([page(1, total=1)], versions=("v1", "v2"))
    with pytest.raises(fetch.FetchError, match="refreshed during the run"):
        fetch.run(session=s, raw_dir=tmp_path / "raw", manifest_path=tmp_path / "m.json", queries=[Q],
                  sleep=lambda _: None)
    assert not (tmp_path / "m.json").exists()


def test_cached_pages_from_an_older_refresh_are_discarded(tmp_path):
    raw = tmp_path / "raw"
    (raw / Q.slug).mkdir(parents=True)
    (raw / Q.slug / "page_0001.json").write_bytes(page(9, total=9).content)
    (raw / "_run.json").write_text(json.dumps({"dataTimestamp": "old"}), encoding="utf-8")
    s = FakeSession([page(1, total=1)], versions=("new",))
    m = fetch.run(session=s, raw_dir=raw, manifest_path=tmp_path / "m.json", queries=[Q], sleep=lambda _: None)
    assert m["terms"][0]["studies"] == 1  # the stale 9-study page was not used


def test_the_real_query_list_is_well_formed():
    qs = fetch.load_queries()
    assert len({q.slug for q in qs}) == len(qs)
    groups = {q.group for q in qs}
    assert groups >= {"MSD", "Pfizer", "AstraZeneca", "Novartis", "Roche", "BMS", "Lilly", "Novo Nordisk", "AbbVie",
                      "GSK", "Sanofi", "J&J", "Ecosystem"}
    assert len(groups) == 13  # 12 companies plus the ecosystem pull
    assert {q.param for q in qs} == {"lead", "intr"}
    assert [q.term for q in qs if q.param == "intr"] == ["pembrolizumab"]
