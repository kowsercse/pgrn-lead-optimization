"""Stage 5: the feasibility checks.

The headline case is DESIGN.md D1. A congeneric series collapses to ONE Murcko
scaffold — that is what makes it congeneric, and it is the property the dossier's
third question exists to find. The original spec gated on `n_scaffolds >= 2`, which
rejected exactly that. These tests pin the corrected behaviour.
"""
import pytest

from dossier.feasibility import (
    MIN_ANALOGS,
    MIN_DOMINANT_SCAFFOLD,
    MIN_SPAN_LOG,
    RESOLUTION_DESIGN,
    RESOLUTION_TRIAGE,
    Feasibility,
    check,
    dominant_scaffold,
)

# A homologous series of n-alkylbenzenes: 22 distinct molecules, every one of which
# has benzene as its Murcko scaffold. This is what "congeneric" looks like, and the
# whole point of D1 is that it must pass.
CONGENERIC = ["C" * n + "c1ccccc1" for n in range(1, 23)]    # 22 members

# Unrelated ring systems: scattered singletons, no series.
SINGLETONS = ["c1ccccc1", "C1CCCCC1", "c1ccncc1", "c1ccc2ccccc2c1",
              "C1CCOC1", "c1cc[nH]c1", "C1CCNCC1", "c1ccsc1"]


def feas(**over):
    base = dict(
        series_smiles=CONGENERIC, pchembl_values=[5.0, 7.0, 9.0],
        ligand_mw=380.0, ligand_heavy=27, best_resolution=2.0, latest_year=2024,
    )
    return check(**{**base, **over})


# --- D1: the regression that the original spec failed --------------------

def test_a_congeneric_series_on_one_scaffold_passes():
    """The blocking defect. All members share one Murcko scaffold and that is correct."""
    f = feas()
    assert f.dominant_scaffold_n == len(CONGENERIC)
    assert f.series_ok is True


def test_scaffold_count_is_not_a_criterion():
    """One scaffold across the whole series must not fail anything."""
    f = feas()
    assert dominant_scaffold(CONGENERIC)[1] == len(CONGENERIC)
    assert f.series_ok is True


def test_scattered_singletons_fail_the_series_check():
    f = feas(series_smiles=SINGLETONS)
    assert f.dominant_scaffold_n < MIN_DOMINANT_SCAFFOLD
    assert f.series_ok is False


def test_one_compound_repeated_fails_on_duplication():
    f = feas(series_smiles=["Cc1ccccc1"] * 30)
    assert f.n_analogs == 30
    assert f.n_distinct_inchikeys == 1
    assert f.series_ok is False


def test_a_series_below_the_size_floor_fails():
    f = feas(series_smiles=CONGENERIC[:MIN_ANALOGS - 1])
    assert f.series_ok is False


def test_a_series_exactly_at_both_floors_passes():
    f = feas(series_smiles=CONGENERIC[:MIN_ANALOGS])
    assert f.n_analogs == MIN_ANALOGS
    assert f.dominant_scaffold_n >= MIN_DOMINANT_SCAFFOLD
    assert f.series_ok is True


# --- activity span -------------------------------------------------------

def test_span_is_the_range_of_pchembl_values():
    assert feas(pchembl_values=[5.0, 8.0]).activity_span_log == pytest.approx(3.0)


def test_a_flat_series_has_nothing_to_rank():
    f = feas(pchembl_values=[7.0, 7.2, 7.4])
    assert f.activity_span_log < MIN_SPAN_LOG
    assert f.span_ok is False


def test_no_values_means_no_span():
    f = feas(pchembl_values=[])
    assert f.activity_span_log == 0.0 and f.span_ok is False


# --- recency: reported, never a gate -------------------------------------

def test_recent_activity_is_reported():
    assert feas(latest_year=2024).years_since_latest is not None


def test_a_dormant_target_is_flagged_but_does_not_fail():
    """Nobody publishing for fifteen years is a signal, not a disqualification."""
    f = feas(latest_year=2009)
    assert f.dormant is True
    assert f.series_ok is True and f.span_ok is True


def test_an_unknown_latest_year_does_not_raise():
    assert feas(latest_year=None).dormant is False


# --- receptor ------------------------------------------------------------

def test_a_fragment_sized_ligand_does_not_define_a_site():
    assert feas(ligand_mw=92.0, ligand_heavy=6).ligand_ok is False


def test_resolution_tiers():
    assert feas(best_resolution=1.9).resolution_tier == "design"
    assert feas(best_resolution=RESOLUTION_DESIGN).resolution_tier == "design"
    assert feas(best_resolution=2.9).resolution_tier == "triage"
    assert feas(best_resolution=RESOLUTION_TRIAGE).resolution_tier == "triage"
    assert feas(best_resolution=4.2).resolution_tier == "none"


def test_a_missing_resolution_is_not_design_quality():
    assert feas(best_resolution=None).resolution_tier == "none"


# --- shape ---------------------------------------------------------------

def test_check_returns_a_frozen_feasibility():
    with pytest.raises(Exception):
        feas().n_analogs = 5


def test_every_threshold_is_reported_alongside_its_value():
    rows = feas().as_rows()
    kinds = {r["kind"] for r in rows}
    assert {"n_analogs", "dominant_scaffold_n", "activity_span_log",
            "best_resolution"} <= kinds
    assert "holdout_overlap" not in kinds, "data splitting is not a tractability signal"
    for r in rows:
        assert "value" in r and "threshold" in r and "passed" in r
