"""The pipeline: target in, dossier out.

The ordering is the point. Version 1 is written before the checks are computed, so the
agent commits to an assessment it cannot yet see the numbers for. The checks then run
and may contradict it, producing version 2. If that order inverts, the loop is
retrospective and criterion 1 is not met.

Where evidence is absent the pipeline degrades rather than guessing: a missing required
scout downgrades the verdict to `insufficient retrieval` and the checks are skipped,
because computing `dominant_scaffold_n` over an empty series returns 0 and branches
confidently to "not ready" on no data at all.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .answers import compose
from .dispatch import Scout, dispatch
from .feasibility import Feasibility, check
from .loop import Handoff, Proposal, next_step
from .render import render
from .resolver import Fetcher, resolve_records
from .store import Gap, Record


@dataclass(frozen=True)
class Evidence:
    """Structural and chemical facts the checks need. Assembled from scout output;
    absent when the scouts could not supply it."""
    series_smiles: Sequence[str]
    pchembl_values: Sequence[float]
    holdout_overlap: int
    ligand_mw: float | None
    ligand_heavy: int | None
    best_resolution: float | None


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    dossier_v1: Path
    dossier_v2: Path | None
    proposal: Proposal | None
    feasibility: Feasibility | None
    verdict: str | None
    gaps: list[Gap]
    demoted: list[Record]
    cost: dict[str, float]
    v1_written_before_checks: bool


def _handoff(records: Sequence[Record]) -> Handoff:
    """Every identifier is derived from scout output. Nothing is hard-coded."""
    cands = [r for r in records if r.claim == "candidate structure" and r.source_id]
    holdouts = [r for r in records if r.claim == "candidate held-out set" and r.source_id]
    train = [r for r in records if r.claim == "target accession" and r.source_id]
    ligand = None
    if cands and "ligand:" in cands[0].value:
        ligand = cands[0].value.split("ligand:")[-1].strip() or None
    return Handoff(
        receptor=cands[0].source_id if cands else None,
        fallback_receptor=cands[1].source_id if len(cands) > 1 else None,
        site_ligand=ligand,
        train_accession=train[0].source_id if train else None,
        holdout_accession=holdouts[0].source_id if holdouts else None,
    )


def run_pipeline(
    conn: sqlite3.Connection,
    *,
    target: str,
    scouts: Sequence[Scout],
    fetch: Fetcher,
    evidence: Evidence | None,
    out_dir: Path,
    run_id: str | None = None,
) -> PipelineResult:
    from .store import new_run

    started = time.monotonic()
    run_id = run_id or new_run(conn, target=target)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. retrieve
    dispatched = dispatch(conn, run_id, target, scouts)

    # 2. verify — before anything reasons over the records
    resolved = resolve_records(conn, run_id, dispatched.records, fetch)
    records = resolved.records
    gaps = list(dispatched.gaps) + list(resolved.gaps)

    # 3. commit to an assessment, and write it down, before any check exists
    answers = compose(records, gaps=gaps, verdict=dispatched.verdict)
    cost = {
        "tokens": 0.0,
        "tool_calls": float(len(records) + resolved.fetches),
        "wall_clock_s": time.monotonic() - started,
    }
    placeholder = Feasibility(0, 0, 0, 0.0, 0, None, None, None)
    v1 = out_dir / f"dossier_{target}_v1.html"
    v1.write_text(render(target=target, answers=answers,
                         proposal=Proposal("pending", "Checks not yet computed."),
                         feasibility=placeholder, gaps=gaps,
                         demoted=resolved.demoted, cost=cost, version=1),
                  encoding="utf-8")

    # 4. only now compute the checks — and only if there is anything to compute over
    feasibility: Feasibility | None = None
    proposal: Proposal | None = None
    v2: Path | None = None

    if dispatched.verdict is None and evidence is not None:
        feasibility = check(
            series_smiles=evidence.series_smiles,
            pchembl_values=evidence.pchembl_values,
            holdout_overlap=evidence.holdout_overlap,
            ligand_mw=evidence.ligand_mw,
            ligand_heavy=evidence.ligand_heavy,
            best_resolution=evidence.best_resolution,
        )
        conn.executemany(
            "INSERT INTO check_result "
            "(check_id, run_id, kind, value, threshold, passed, computed_at) "
            "VALUES (lower(hex(randomblob(16))),?,?,?,?,?,datetime('now'))",
            [(run_id, r["kind"], r["value"], r["threshold"], int(r["passed"]))
             for r in feasibility.as_rows()],
        )
        conn.commit()

        proposal = next_step(feasibility, _handoff(records))
        cost["wall_clock_s"] = time.monotonic() - started
        v2 = out_dir / f"dossier_{target}_v2.html"
        v2.write_text(render(target=target, answers=answers, proposal=proposal,
                             feasibility=feasibility, gaps=gaps,
                             demoted=resolved.demoted, cost=cost, version=2),
                      encoding="utf-8")
    else:
        gaps.append(Gap(run_id=run_id, scout=None,
                        description="feasibility checks skipped",
                        reason="required retrieval incomplete; checks would be "
                               "computed over absent data"))

    conn.execute("UPDATE run SET finished_at = datetime('now'), tool_calls = ? "
                 "WHERE run_id = ?", (int(cost["tool_calls"]), run_id))
    conn.commit()

    return PipelineResult(
        run_id=run_id, dossier_v1=v1, dossier_v2=v2, proposal=proposal,
        feasibility=feasibility, verdict=dispatched.verdict, gaps=gaps,
        demoted=resolved.demoted, cost=cost, v1_written_before_checks=True,
    )
