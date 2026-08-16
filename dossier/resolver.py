"""The resolver gate.

A scout that fabricated a source will confidently grade its own claim `verified`.
Self-reported grades are worth exactly what the retrieval layer beneath them is worth,
and the measured cost of not having one is severe: in the Robin ablation a scientist
blinded to source found 44.5% of references from an ungrounded model call were
fabricated, rising to ~58% for drug-candidate proposals.

Every `verified` or `documented` claim has its identifier fetched independently of the
scout that cited it, and the fetched document must self-identify with that identifier.
Anything that fails is demoted to `inferred`, recorded, and surfaced in the dossier.

Confirmation is at identifier level, not value level: we assert that the accession
resolves to a document that names itself. Confirming that a specific quoted number
appears in the source is a stronger claim and is deferred.
"""
from __future__ import annotations

import dataclasses
import sqlite3
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Sequence

from .store import Gap, Record, insert_gaps

RESOLVER_CONCURRENCY = 8
RESOLVER_BUDGET_S = 300.0

RESOLVABLE = ("verified", "documented")

Fetcher = Callable[[str], str | None]


@dataclass(frozen=True)
class Resolution:
    record_id: str
    resolved: bool
    fetched_at: str | None = None
    span_found: bool | None = None
    demoted_from: str | None = None
    note: str = ""


@dataclass(frozen=True)
class ResolveOutcome:
    records: list[Record]
    resolutions: list[Resolution]
    gaps: list[Gap]
    demoted: list[Record]
    fetches: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def confirms(document: str, source_id: str) -> bool:
    """A document confirms an identifier when it names it."""
    return source_id.lower() in document.lower()


def resolve_records(
    conn: sqlite3.Connection,
    run_id: str,
    records: Sequence[Record],
    fetch: Fetcher,
    *,
    budget_s: float = RESOLVER_BUDGET_S,
    concurrency: int = RESOLVER_CONCURRENCY,
) -> ResolveOutcome:
    needs = [r for r in records if r.grade in RESOLVABLE and r.source_id]

    # Most-cited identifiers first, so budget exhaustion costs the least
    # load-bearing claims rather than an arbitrary slice of them.
    order = [sid for sid, _ in Counter(r.source_id for r in needs).most_common()]

    documents: dict[str, str | None] = {}
    errors: dict[str, str] = {}
    started = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=max(1, concurrency))
    try:
        futures = {}
        for sid in order:
            if time.monotonic() - started >= budget_s:
                break
            futures[pool.submit(fetch, sid)] = sid
        for fut, sid in futures.items():
            remaining = budget_s - (time.monotonic() - started)
            if remaining <= 0:
                break
            try:
                documents[sid] = fut.result(timeout=remaining)
            except Exception as exc:
                documents[sid] = None
                errors[sid] = f"{type(exc).__name__}: {exc}"
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    out_records: list[Record] = []
    resolutions: list[Resolution] = []
    demoted: list[Record] = []
    unresolved = 0

    for r in records:
        if r.grade not in RESOLVABLE or not r.source_id:
            out_records.append(r)
            continue
        if r.source_id not in documents:  # never reached inside the budget
            unresolved += 1
            resolutions.append(Resolution(record_id=r.record_id, resolved=False,
                                          note="budget exhausted"))
            out_records.append(r)  # keep the scout's grade; the gap states the count
            continue

        doc = documents[r.source_id]
        ok = doc is not None and confirms(doc, r.source_id)
        note = errors.get(r.source_id, "" if ok else "identifier did not resolve")
        resolutions.append(Resolution(
            record_id=r.record_id, resolved=ok, fetched_at=_now(),
            span_found=ok, demoted_from=None if ok else r.grade, note=note,
        ))
        if ok:
            out_records.append(r)
        else:
            fallen = dataclasses.replace(r, grade="inferred")
            out_records.append(fallen)
            demoted.append(fallen)

    gaps: list[Gap] = []
    if unresolved:
        gaps.append(Gap(
            run_id=run_id, scout=None,
            description=f"{unresolved} claims left unresolved",
            reason=f"resolver budget of {budget_s}s exhausted",
        ))
        insert_gaps(conn, gaps)

    if resolutions:
        conn.executemany(
            "INSERT OR REPLACE INTO resolution "
            "(record_id, resolved, fetched_at, span_found, demoted_from, note) "
            "VALUES (?,?,?,?,?,?)",
            [(x.record_id, int(x.resolved), x.fetched_at,
              None if x.span_found is None else int(x.span_found),
              x.demoted_from, x.note) for x in resolutions],
        )
        conn.commit()

    return ResolveOutcome(records=out_records, resolutions=resolutions, gaps=gaps,
                          demoted=demoted, fetches=len(documents))
