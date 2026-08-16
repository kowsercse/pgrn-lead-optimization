"""Deterministic feasibility checks, computed after the dossier commits.

These are the loop's measurement. The agent writes its assessment first; these numbers
are computed second and can contradict it. All of them run in RDKit on a laptop.

Note what is NOT here: a scaffold *count* criterion. A congeneric series collapses to
one Murcko scaffold — that is what makes it congeneric, and it is the property the
dossier's third question exists to find. Gating on scaffold diversity would reject it.
The two real failure modes are measured directly instead: duplication, by identity,
and scattered singletons, by depth on the dominant scaffold. See DESIGN.md D1.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

from rdkit import Chem, RDLogger
from rdkit.Chem.Scaffolds import MurckoScaffold

from .joins import inchikey

RDLogger.DisableLog("rdApp.*")

# Target-agnostic thresholds. See SPEC.md THRESHOLDS.
MIN_ANALOGS = 20
MIN_DOMINANT_SCAFFOLD = 15
MIN_SPAN_LOG = 2.0
MIN_LIGAND_MW = 250.0
MIN_LIGAND_HEAVY = 15
RESOLUTION_DESIGN = 2.5
RESOLUTION_TRIAGE = 3.5

# Reported alongside the checks, never gating: a target nobody has published on for
# this long is worth flagging, but silence is not evidence the protein is intractable.
CURRENT_YEAR = 2026
DORMANT_YEARS = 10


def murcko(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return MurckoScaffold.MurckoScaffoldSmiles(mol=mol)


def dominant_scaffold(series: Sequence[str]) -> tuple[str | None, int]:
    """The most common Murcko scaffold and how many members bear it."""
    scaffolds = [s for s in (murcko(x) for x in series) if s is not None]
    if not scaffolds:
        return None, 0
    scaffold, count = Counter(scaffolds).most_common(1)[0]
    return scaffold, count


@dataclass(frozen=True)
class Feasibility:
    n_analogs: int
    n_distinct_inchikeys: int
    dominant_scaffold_n: int
    activity_span_log: float
    ligand_mw: float | None
    ligand_heavy: int | None
    best_resolution: float | None
    latest_year: int | None = None

    # --- derived verdicts ---

    @property
    def series_ok(self) -> bool:
        return (
            self.n_analogs >= MIN_ANALOGS
            and self.n_distinct_inchikeys == self.n_analogs
            and self.dominant_scaffold_n >= MIN_DOMINANT_SCAFFOLD
        )

    @property
    def span_ok(self) -> bool:
        return self.activity_span_log >= MIN_SPAN_LOG

    @property
    def years_since_latest(self) -> int | None:
        """Reported, never a gate. Whether anyone is still working on a target is a
        signal worth surfacing; it is not evidence about the protein itself."""
        return None if self.latest_year is None else CURRENT_YEAR - self.latest_year

    @property
    def dormant(self) -> bool:
        gap = self.years_since_latest
        return gap is not None and gap >= DORMANT_YEARS

    @property
    def ligand_ok(self) -> bool:
        return (
            self.ligand_mw is not None
            and self.ligand_heavy is not None
            and self.ligand_mw >= MIN_LIGAND_MW
            and self.ligand_heavy >= MIN_LIGAND_HEAVY
        )

    @property
    def resolution_tier(self) -> str:
        if self.best_resolution is None:
            return "none"
        if self.best_resolution <= RESOLUTION_DESIGN:
            return "design"
        if self.best_resolution <= RESOLUTION_TRIAGE:
            return "triage"
        return "none"

    def as_rows(self) -> list[dict[str, Any]]:
        """One row per check, for the `check_result` table and the dossier."""
        return [
            {"kind": "n_analogs", "value": float(self.n_analogs),
             "threshold": float(MIN_ANALOGS), "passed": self.n_analogs >= MIN_ANALOGS},
            {"kind": "n_distinct_inchikeys", "value": float(self.n_distinct_inchikeys),
             "threshold": float(self.n_analogs),
             "passed": self.n_distinct_inchikeys == self.n_analogs},
            {"kind": "dominant_scaffold_n", "value": float(self.dominant_scaffold_n),
             "threshold": float(MIN_DOMINANT_SCAFFOLD),
             "passed": self.dominant_scaffold_n >= MIN_DOMINANT_SCAFFOLD},
            {"kind": "activity_span_log", "value": self.activity_span_log,
             "threshold": MIN_SPAN_LOG, "passed": self.span_ok},
            {"kind": "ligand_mw", "value": self.ligand_mw or 0.0,
             "threshold": MIN_LIGAND_MW, "passed": self.ligand_ok},
            {"kind": "best_resolution",
             "value": self.best_resolution if self.best_resolution is not None else 99.0,
             "threshold": RESOLUTION_TRIAGE, "passed": self.resolution_tier != "none"},
        ]


def check(
    *,
    series_smiles: Sequence[str],
    pchembl_values: Sequence[float],
    ligand_mw: float | None,
    ligand_heavy: int | None,
    best_resolution: float | None,
    latest_year: int | None = None,
) -> Feasibility:
    keys = {k for k in (inchikey(s) for s in series_smiles) if k is not None}
    _, dominant_n = dominant_scaffold(series_smiles)
    span = (max(pchembl_values) - min(pchembl_values)) if pchembl_values else 0.0
    return Feasibility(
        n_analogs=len(series_smiles),
        n_distinct_inchikeys=len(keys),
        dominant_scaffold_n=dominant_n,
        activity_span_log=span,
        ligand_mw=ligand_mw,
        ligand_heavy=ligand_heavy,
        best_resolution=best_resolution,
        latest_year=latest_year,
    )
