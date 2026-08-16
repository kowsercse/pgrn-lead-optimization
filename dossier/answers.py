"""The five answers.

Each is one committed choice with a reason, never a candidate list. A dossier that
enumerates options has not decided anything, and deciding is the whole job.

An answer never outranks the record it rests on: if the resolver demoted the evidence,
the answer is demoted with it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from .store import Gap, Grade, Record

QUESTIONS: tuple[str, ...] = (
    "Is there a pocket, and which structure do we design against?",
    "What chemical matter exists, and how good is it?",
    "Is there a congeneric series?",
    "Is anyone still working on this target?",
    "What is missing?",
)

_WEAKEST = ("unverified", "inferred", "documented", "verified", "measured")


@dataclass(frozen=True)
class Answer:
    question_no: int
    question: str
    value: str
    grade: Grade
    source_id: str | None = None
    agree_n: int | None = None
    agree_of: int | None = None


def _resolution(record: Record) -> float:
    m = re.search(r"([\d.]+)\s*A\b", record.value)
    return float(m.group(1)) if m else 999.0


def _claim(records: Sequence[Record], claim: str) -> Record | None:
    for r in records:
        if r.claim == claim:
            return r
    return None


def _floor(grade: Grade, *records: Record | None) -> Grade:
    """An answer is never graded above the evidence beneath it."""
    grades = [grade] + [r.grade for r in records if r is not None]
    return min(grades, key=_WEAKEST.index)


def _receptor(records: Sequence[Record]) -> Answer:
    cands = sorted((r for r in records if r.claim == "candidate structure"),
                   key=_resolution)
    if not cands:
        return Answer(1, QUESTIONS[0],
                      "No structure carries a drug-like ligand, so there is no site to "
                      "design against.", "unverified")
    best = cands[0]
    value = f"{best.value}. "
    if len(cands) > 1:
        value += (f"Chosen over {len(cands) - 1} other candidate"
                  f"{'s' if len(cands) > 2 else ''} on resolution; "
                  f"nearest alternative is {cands[1].source_id}.")
    else:
        value += "It is the only candidate carrying a drug-like ligand."
    return Answer(1, QUESTIONS[0], value, _floor(best.grade, best), best.source_id)


def _matter(records: Sequence[Record]) -> Answer:
    distinct = _claim(records, "distinct compounds with measured activity")
    total = _claim(records, "activity records")
    potency = _claim(records, "potency range")
    if distinct is None:
        return Answer(2, QUESTIONS[1],
                      "No measured bioactivity was retrieved.", "unverified")
    pooled = _claim(records, "pooled chemical matter")
    if pooled is not None:
        value = f"{pooled.value}, pooled across every source"
        if distinct is not None:
            value += f" ({distinct.value} from the public measurement set)"
        value += "."
    else:
        value = f"{distinct.value} distinct compounds with measured activity"
        if total is not None:
            value += f", drawn from {total.value} activity records"
        value += "."
    if potency is not None:
        value += f" Potency {potency.value}."
    return Answer(2, QUESTIONS[1], value, _floor(distinct.grade, distinct, potency))


def _series(records: Sequence[Record]) -> Answer:
    joined = _claim(records, "series core matches the receptor ligand")
    distinct = _claim(records, "distinct compounds with measured activity")
    if joined is not None:
        return Answer(3, QUESTIONS[2], joined.value + ".", _floor(joined.grade, joined))
    if distinct is not None:
        return Answer(3, QUESTIONS[2],
                      f"Not established. {distinct.value} distinct compounds exist, but "
                      "no series core has been matched to the receptor ligand.",
                      "inferred")
    return Answer(3, QUESTIONS[2], "Not established — no compound set was retrieved.",
                  "unverified")


def _recency(records: Sequence[Record]) -> Answer:
    """Reported, never a gate. Silence is a signal about the field, not evidence
    that the protein is intractable. See DESIGN.md D8."""
    pooled = _claim(records, "pooled chemical matter")
    latest = _claim(records, "most recent measurement")
    if latest is None:
        return Answer(4, QUESTIONS[3],
                      "The date of the most recent measurement was not retrieved.",
                      "unverified")
    value = f"Most recent measurement: {latest.value}."
    if pooled is not None:
        value += f" {pooled.value}."
    return Answer(4, QUESTIONS[3], value, _floor(latest.grade, latest, pooled))


def _missing(records: Sequence[Record], gaps: Sequence[Gap], verdict: str | None) -> Answer:
    lines: list[str] = []
    if verdict:
        lines.append(f"Verdict downgraded to {verdict}.")
    for g in gaps:
        who = f"{g.scout}: " if g.scout else ""
        lines.append(f"{who}{g.description} ({g.reason}).")
    demoted = [r for r in records if r.claim == "demoted claim"]
    if demoted:
        lines.append(f"{len(demoted)} claims demoted by the resolver.")
    if not lines:
        lines.append("Nothing was reported as missing. Every scout returned and every "
                     "cited identifier resolved.")
    return Answer(5, QUESTIONS[4], " ".join(lines), "measured")


def compose(
    records: Sequence[Record],
    *,
    gaps: Sequence[Gap],
    verdict: str | None,
    agreement: Mapping[int, tuple[int, int]] | None = None,
) -> list[Answer]:
    answers = [
        _receptor(records),
        _matter(records),
        _series(records),
        _recency(records),
        _missing(records, gaps, verdict),
    ]
    if agreement:
        answers = [
            Answer(a.question_no, a.question, a.value, a.grade, a.source_id,
                   *agreement.get(a.question_no, (None, None)))
            for a in answers
        ]
    return answers
