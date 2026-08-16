"""Stage 2 exit gate: a fabricated accession must be demoted and flagged.

Without this gate every grade above `inferred` is self-reported. The measured cost of
not having one, from the Robin ablation: 44.5% of references from an ungrounded model
call were fabricated.
"""
import time

import pytest

from dossier.resolver import Resolution, resolve_records
from dossier.store import Record, connect, new_run


@pytest.fixture()
def conn(tmp_path):
    return connect(tmp_path / "r.db")


def rec(run, grade="verified", source_id="1ABC", **over):
    base = dict(
        run_id=run, scout="structures", claim="candidate structure",
        value=f"PDB {source_id}", grade=grade, query="q",
        source_id=source_id, source_url=f"https://example.org/{source_id}",
    )
    if grade == "measured":
        base["output_hash"] = "deadbeef"
    if grade == "unverified":
        base["reason"] = "not found"
    return Record(**{**base, **over})


def library(**docs):
    """A fetcher over a fixed corpus. Unknown identifiers return None, as a 404 would."""
    calls: list[str] = []

    def fetch(source_id):
        calls.append(source_id)
        return docs.get(source_id)

    fetch.calls = calls
    return fetch


# --- what gets resolved --------------------------------------------------

def test_inferred_records_are_not_fetched(conn):
    run = new_run(conn, target="X")
    fetch = library()
    resolve_records(conn, run, [rec(run, grade="inferred", source_id=None,
                                    source_url=None)], fetch)
    assert fetch.calls == []


def test_measured_records_are_not_fetched(conn):
    run = new_run(conn, target="X")
    fetch = library()
    resolve_records(conn, run, [rec(run, grade="measured", source_id=None,
                                    source_url=None)], fetch)
    assert fetch.calls == []


def test_verified_and_documented_records_are_fetched(conn):
    run = new_run(conn, target="X")
    fetch = library(**{"1ABC": "entry 1ABC", "2DEF": "entry 2DEF"})
    resolve_records(conn, run, [rec(run, source_id="1ABC"),
                                rec(run, grade="documented", source_id="2DEF")], fetch)
    assert sorted(fetch.calls) == ["1ABC", "2DEF"]


# --- the gate ------------------------------------------------------------

def test_identifier_that_resolves_keeps_its_grade(conn):
    run = new_run(conn, target="X")
    out = resolve_records(conn, run, [rec(run, source_id="1ABC")],
                          library(**{"1ABC": "Structure 1ABC at 2.0 A"}))
    assert out.records[0].grade == "verified"
    assert out.resolutions[0].resolved is True


def test_fabricated_identifier_is_demoted_to_inferred(conn):
    run = new_run(conn, target="X")
    out = resolve_records(conn, run, [rec(run, source_id="9ZZZ")], library())
    assert out.records[0].grade == "inferred"
    assert out.resolutions[0].resolved is False
    assert out.resolutions[0].demoted_from == "verified"


def test_document_that_does_not_self_identify_is_demoted(conn):
    """A 200 response for the wrong document must not pass as confirmation."""
    run = new_run(conn, target="X")
    out = resolve_records(conn, run, [rec(run, source_id="1ABC")],
                          library(**{"1ABC": "this page is about something else"}))
    assert out.records[0].grade == "inferred"
    assert out.resolutions[0].span_found is False


def test_demotion_is_flagged_for_the_dossier(conn):
    run = new_run(conn, target="X")
    out = resolve_records(conn, run, [rec(run, source_id="9ZZZ")], library())
    assert out.demoted, "demotions must be surfaced, not just recorded"
    assert out.demoted[0].source_id == "9ZZZ"


def test_resolutions_are_persisted(conn):
    run = new_run(conn, target="X")
    resolve_records(conn, run, [rec(run, source_id="1ABC")],
                    library(**{"1ABC": "1ABC"}))
    rows = conn.execute("SELECT resolved FROM resolution").fetchall()
    assert len(rows) == 1 and rows[0]["resolved"] == 1


# --- budget and cache ----------------------------------------------------

def test_one_identifier_cited_by_many_records_is_fetched_once(conn):
    run = new_run(conn, target="X")
    fetch = library(**{"1ABC": "1ABC"})
    records = [rec(run, source_id="1ABC") for _ in range(4)]
    out = resolve_records(conn, run, records, fetch)
    assert fetch.calls == ["1ABC"]
    assert all(r.grade == "verified" for r in out.records)
    assert out.fetches == 1


def test_most_cited_identifier_is_resolved_first(conn):
    """Budget exhaustion should cost the least load-bearing claims."""
    run = new_run(conn, target="X")
    fetch = library(**{"RARE": "RARE", "COMMON": "COMMON"})
    records = [rec(run, source_id="RARE")] + [rec(run, source_id="COMMON") for _ in range(3)]
    resolve_records(conn, run, records, fetch)
    assert fetch.calls[0] == "COMMON"


def test_budget_exhaustion_leaves_the_grade_and_notes_it(conn):
    run = new_run(conn, target="X")

    def slow(source_id):
        time.sleep(0.2)
        return source_id

    records = [rec(run, source_id=f"ID{i}") for i in range(6)]
    out = resolve_records(conn, run, records, slow, budget_s=0.25, concurrency=1)
    unresolved = [r for r in out.resolutions if r.note == "budget exhausted"]
    assert unresolved, "expected some records to be left unresolved"
    kept = [r for r in out.records if r.source_id == unresolved[0].record_id]
    assert all(r.grade == "verified" for r in out.records if r.grade != "inferred")


def test_budget_exhaustion_emits_one_gap_with_the_count(conn):
    run = new_run(conn, target="X")

    def slow(source_id):
        time.sleep(0.2)
        return source_id

    out = resolve_records(conn, run, [rec(run, source_id=f"ID{i}") for i in range(6)],
                          slow, budget_s=0.25, concurrency=1)
    assert len(out.gaps) == 1
    assert "unresolved" in out.gaps[0].description.lower()


def test_resolution_runs_concurrently(conn):
    run = new_run(conn, target="X")

    def slow(source_id):
        time.sleep(0.2)
        return source_id

    records = [rec(run, source_id=f"ID{i}") for i in range(8)]
    started = time.monotonic()
    resolve_records(conn, run, records, slow, budget_s=10, concurrency=8)
    assert time.monotonic() - started < 0.9, "resolver ran serially"


def test_a_fetcher_that_raises_demotes_rather_than_crashes(conn):
    run = new_run(conn, target="X")

    def boom(source_id):
        raise ConnectionError("network down")

    out = resolve_records(conn, run, [rec(run, source_id="1ABC")], boom)
    assert out.records[0].grade == "inferred"
    assert "ConnectionError" in out.resolutions[0].note
