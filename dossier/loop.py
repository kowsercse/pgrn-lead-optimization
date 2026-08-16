"""The loop: the recommendation changes when the checks change.

The dossier commits to an assessment before any of these numbers exist. The checks are
then computed over the retrieved data and can contradict it. Two of the branches below
overturn what the agent committed to.

`next_step` is pure, so branch reachability is a unit test rather than something
inferred from two real targets — which may both happen to pass, making a working loop
look decorative and a decorative one look fine. See DESIGN.md D3.
"""
from __future__ import annotations

from dataclasses import dataclass

from .feasibility import (
    MIN_ANALOGS,
    MIN_DOMINANT_SCAFFOLD,
    MIN_SPAN_LOG,
    RESOLUTION_DESIGN,
    Feasibility,
)

BRANCHES = (
    "not_ready",        # recommendation reverses
    "no_structure",     # recommendation reverses
    "triage_only",      # recommendation is qualified
    "proceed",          # assessment confirmed
)


@dataclass(frozen=True)
class Handoff:
    """Identifiers derived at runtime by the scouts. Nothing here is hard-coded."""
    receptor: str | None
    fallback_receptor: str | None
    site_ligand: str | None
    train_accession: str | None
    holdout_accession: str | None

    def spec(self) -> str:
        parts = [f"receptor {self.receptor}"]
        if self.site_ligand:
            parts.append(f"site defined by {self.site_ligand}")
        if self.train_accession:
            parts.append(f"train on {self.train_accession}")
        if self.holdout_accession:
            parts.append(f"validate on {self.holdout_accession}")
        if self.fallback_receptor:
            parts.append(f"fall back to {self.fallback_receptor}")
        return "; ".join(parts)


@dataclass(frozen=True)
class Proposal:
    branch: str
    recommendation: str
    failed_checks: tuple[str, ...] = ()


def next_step(f: Feasibility, handoff: Handoff) -> Proposal:
    """Nothing here names a target. Every identifier comes from `handoff`."""
    failed = tuple(r["kind"] for r in f.as_rows() if not r["passed"])

    # How a future model would be validated is a planning detail for whoever picks
    # the work up. It says nothing about whether this protein is tractable, so it is
    # not a branch condition. See DESIGN.md D8.

    if not f.series_ok:
        why = (
            f"fewer than {MIN_ANALOGS} analogs" if f.n_analogs < MIN_ANALOGS
            else "the series contains duplicate compounds"
            if f.n_distinct_inchikeys != f.n_analogs
            else f"no core carries {MIN_DOMINANT_SCAFFOLD} or more analogs"
        )
        return Proposal(
            "not_ready",
            f"Not ready for structure-based design — {why}, so structure–activity "
            "reasoning is unsupportable. Go ligand-based, or generate data first.",
            failed,
        )

    if not f.span_ok:
        return Proposal(
            "not_ready",
            f"Not ready for structure-based design — activity spans "
            f"{f.activity_span_log:.1f} log units, under the {MIN_SPAN_LOG:.0f} needed "
            "to rank anything. Go ligand-based, or generate data first.",
            failed,
        )

    if not f.ligand_ok or f.resolution_tier == "none":
        why = ("no structure resolves well enough to design against"
               if f.resolution_tier == "none"
               else "the best site is defined by a fragment or additive, not a "
                    "drug-like ligand")
        return Proposal(
            "no_structure",
            f"Not tractable for structure-based design — {why}.",
            failed,
        )

    if f.resolution_tier == "triage":
        return Proposal(
            "triage_only",
            f"Proceed with structure-based design, triage-only: {handoff.spec()}. "
            f"At {f.best_resolution} A this supports shape work and triage; "
            f"contact-level optimisation needs a structure at "
            f"{RESOLUTION_DESIGN} A or better.",
            failed,
        )

    return Proposal(
        "proceed",
        f"Proceed with structure-based design: {handoff.spec()}.",
        failed,
    )
