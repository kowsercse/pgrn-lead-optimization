"""SQLite store. Every stage writes here and reads back; no stage passes objects
directly to the next, so any stage can be re-run against a previous run's data.

Grade rules are CHECK constraints rather than prose, so a violation fails at insert
time next to the code that caused it.
"""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal, Sequence

Grade = Literal["measured", "verified", "documented", "inferred", "unverified"]

GRADES: tuple[str, ...] = ("measured", "verified", "documented", "inferred", "unverified")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS run (
    run_id      TEXT PRIMARY KEY,
    target      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    tokens      INTEGER,
    tool_calls  INTEGER
);

CREATE TABLE IF NOT EXISTS record (
    record_id    TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES run(run_id),
    scout        TEXT NOT NULL,
    claim        TEXT NOT NULL,
    value        TEXT NOT NULL,
    grade        TEXT NOT NULL,
    source_id    TEXT,
    source_url   TEXT,
    source_date  TEXT,
    retrieved_at TEXT NOT NULL,
    query        TEXT NOT NULL,
    output_hash  TEXT,
    reason       TEXT,
    CHECK (grade IN ('measured','verified','documented','inferred','unverified')),
    CHECK (grade NOT IN ('verified','documented') OR source_url IS NOT NULL),
    CHECK (grade <> 'measured'   OR output_hash IS NOT NULL),
    CHECK (grade <> 'unverified' OR reason      IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS gap (
    gap_id      TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES run(run_id),
    scout       TEXT,
    description TEXT NOT NULL,
    reason      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resolution (
    record_id    TEXT PRIMARY KEY,
    resolved     INTEGER NOT NULL,
    fetched_at   TEXT,
    span_found   INTEGER,
    demoted_from TEXT,
    note         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS record_by_run ON record(run_id, grade);
CREATE INDEX IF NOT EXISTS gap_by_run ON gap(run_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Record:
    run_id: str
    scout: str
    claim: str
    value: str
    grade: Grade
    query: str
    source_id: str | None = None
    source_url: str | None = None
    source_date: str | None = None
    output_hash: str | None = None
    reason: str | None = None
    retrieved_at: str = field(default_factory=_now)
    record_id: str = field(default_factory=lambda: uuid.uuid4().hex)


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def new_run(conn: sqlite3.Connection, *, target: str) -> str:
    run_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO run (run_id, target, started_at) VALUES (?, ?, ?)",
        (run_id, target, _now()),
    )
    conn.commit()
    return run_id


_COLUMNS = (
    "record_id", "run_id", "scout", "claim", "value", "grade", "source_id",
    "source_url", "source_date", "retrieved_at", "query", "output_hash", "reason",
)


def insert_records(conn: sqlite3.Connection, records: Sequence[Record]) -> list[str]:
    rows = [tuple(getattr(r, c) for c in _COLUMNS) for r in records]
    placeholders = ", ".join("?" * len(_COLUMNS))
    try:
        conn.executemany(
            f"INSERT INTO record ({', '.join(_COLUMNS)}) VALUES ({placeholders})", rows
        )
    except sqlite3.IntegrityError:
        conn.rollback()
        raise
    conn.commit()
    return [r.record_id for r in records]


def records_for(
    conn: sqlite3.Connection, run_id: str, *, grade: Grade | None = None
) -> list[Record]:
    sql = f"SELECT {', '.join(_COLUMNS)} FROM record WHERE run_id = ?"
    params: list[str] = [run_id]
    if grade is not None:
        sql += " AND grade = ?"
        params.append(grade)
    return [Record(**dict(row)) for row in conn.execute(sql, params)]


@dataclass(frozen=True)
class Gap:
    run_id: str
    description: str
    reason: str
    scout: str | None = None
    gap_id: str = field(default_factory=lambda: uuid.uuid4().hex)


def insert_gaps(conn: sqlite3.Connection, gaps: Sequence[Gap]) -> list[str]:
    conn.executemany(
        "INSERT INTO gap (gap_id, run_id, scout, description, reason) VALUES (?,?,?,?,?)",
        [(g.gap_id, g.run_id, g.scout, g.description, g.reason) for g in gaps],
    )
    conn.commit()
    return [g.gap_id for g in gaps]


def gaps_for(conn: sqlite3.Connection, run_id: str) -> list[Gap]:
    rows = conn.execute(
        "SELECT gap_id, run_id, scout, description, reason FROM gap WHERE run_id = ?",
        (run_id,),
    )
    return [Gap(**dict(r)) for r in rows]
