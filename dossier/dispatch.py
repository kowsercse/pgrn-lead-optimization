"""Concurrent scout dispatch with per-scout deadlines.

A scout that hangs or raises becomes a gap-list entry; it never blocks the run. One
agent hung during the reference run and this is the fix.

`structures` and `bioactivity` are required — the verdict depends on them. The other
three are contributing: their absence is a gap, not a downgrade.
"""
from __future__ import annotations

import dataclasses
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
from typing import Protocol, Sequence

from .store import Gap, Record, insert_gaps, insert_records

REQUIRED_SCOUTS: tuple[str, ...] = ("structures", "bioactivity")

INSUFFICIENT = "insufficient retrieval"


class Scout(Protocol):
    name: str
    deadline_s: float

    def brief(self, target: str) -> str: ...
    def run(self, target: str) -> list[Record]: ...


@dataclass(frozen=True)
class DispatchResult:
    records: list[Record]
    gaps: list[Gap]
    verdict: str | None


def dispatch(
    conn: sqlite3.Connection,
    run_id: str,
    target: str,
    scouts: Sequence[Scout],
) -> DispatchResult:
    records: list[Record] = []
    gaps: list[Gap] = []

    pool = ThreadPoolExecutor(max_workers=max(1, len(scouts)))
    try:
        started = time.monotonic()
        futures = {pool.submit(s.run, target): s for s in scouts}

        # Collect in deadline order, each measured from dispatch start, so a scout
        # with a short deadline is never made to wait behind a patient one.
        for fut, scout in sorted(futures.items(), key=lambda kv: kv[1].deadline_s):
            remaining = scout.deadline_s - (time.monotonic() - started)
            try:
                got = fut.result(timeout=max(0.0, remaining))
            except FuturesTimeout:
                gaps.append(Gap(run_id=run_id, scout=scout.name,
                                description=f"{scout.name} did not return records",
                                reason=f"deadline exceeded after {scout.deadline_s}s"))
                continue
            except Exception as exc:  # a scout that raises is a gap, not a crash
                gaps.append(Gap(run_id=run_id, scout=scout.name,
                                description=f"{scout.name} did not return records",
                                reason=f"raised {type(exc).__name__}: {exc}"))
                continue
            records.extend(dataclasses.replace(r, run_id=run_id) for r in got)
    finally:
        # Do not join stragglers: a hung scout must not hold the run open. Its
        # thread is abandoned and its eventual result discarded.
        pool.shutdown(wait=False, cancel_futures=True)

    if records:
        insert_records(conn, records)
    if gaps:
        insert_gaps(conn, gaps)

    gapped = {g.scout for g in gaps}
    verdict = INSUFFICIENT if gapped & set(REQUIRED_SCOUTS) else None
    return DispatchResult(records=records, gaps=gaps, verdict=verdict)
