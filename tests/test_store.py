"""Stage 0 exit gate: the schema must reject a malformed grade at insert time."""
import sqlite3

import pytest

from dossier.store import Record, connect, insert_records, new_run, records_for


@pytest.fixture()
def conn(tmp_path):
    return connect(tmp_path / "dossier.db")


def rec(**over):
    base = dict(
        run_id="", scout="structures", claim="recommended receptor",
        value="PDB 1ABC", grade="inferred", query="rcsb: X",
    )
    return Record(**{**base, **over})


def test_inferred_record_needs_no_source(conn):
    run = new_run(conn, target="X")
    insert_records(conn, [rec(run_id=run)])
    assert len(records_for(conn, run)) == 1


def test_verified_record_without_source_url_is_rejected(conn):
    run = new_run(conn, target="X")
    with pytest.raises(sqlite3.IntegrityError):
        insert_records(conn, [rec(run_id=run, grade="verified", source_id="1ABC")])


def test_documented_record_without_source_url_is_rejected(conn):
    run = new_run(conn, target="X")
    with pytest.raises(sqlite3.IntegrityError):
        insert_records(conn, [rec(run_id=run, grade="documented")])


def test_measured_record_without_output_hash_is_rejected(conn):
    run = new_run(conn, target="X")
    with pytest.raises(sqlite3.IntegrityError):
        insert_records(conn, [rec(run_id=run, grade="measured")])


def test_unverified_record_without_reason_is_rejected(conn):
    run = new_run(conn, target="X")
    with pytest.raises(sqlite3.IntegrityError):
        insert_records(conn, [rec(run_id=run, grade="unverified")])


def test_unknown_grade_is_rejected(conn):
    run = new_run(conn, target="X")
    with pytest.raises(sqlite3.IntegrityError):
        insert_records(conn, [rec(run_id=run, grade="probably")])


def test_verified_record_with_source_url_is_accepted(conn):
    run = new_run(conn, target="X")
    insert_records(conn, [rec(
        run_id=run, grade="verified", source_id="1ABC",
        source_url="https://www.rcsb.org/structure/1ABC",
    )])
    assert records_for(conn, run)[0].grade == "verified"


def test_records_are_isolated_by_run(conn):
    a = new_run(conn, target="A")
    b = new_run(conn, target="B")
    insert_records(conn, [rec(run_id=a), rec(run_id=a)])
    insert_records(conn, [rec(run_id=b)])
    assert len(records_for(conn, a)) == 2
    assert len(records_for(conn, b)) == 1


def test_records_can_be_filtered_by_grade(conn):
    run = new_run(conn, target="X")
    insert_records(conn, [
        rec(run_id=run, grade="inferred"),
        rec(run_id=run, grade="measured", output_hash="abc123"),
    ])
    assert len(records_for(conn, run, grade="measured")) == 1


def test_retrieved_at_is_stamped_automatically(conn):
    run = new_run(conn, target="X")
    insert_records(conn, [rec(run_id=run)])
    assert records_for(conn, run)[0].retrieved_at
