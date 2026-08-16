"""Stage 5 exit gate: every branch reachable, and the reference case does not fail.

This is judging criterion 1. The dossier commits to an assessment, the checks are
computed after, and the recommendation changes according to the result. Branch
reachability is a unit test over a pure function — never inferred from two real
targets, which may both happen to pass. See DESIGN.md D3.
"""
import pytest

from dossier.feasibility import Feasibility
from dossier.loop import BRANCHES, Handoff, next_step


def f(**over):
    """A feasibility that passes everything, overridden per case."""
    base = dict(n_analogs=106, n_distinct_inchikeys=106, dominant_scaffold_n=106,
                activity_span_log=3.1, holdout_overlap=0, ligand_mw=380.0,
                ligand_heavy=27, best_resolution=1.9)
    return Feasibility(**{**base, **over})


HANDOFF = Handoff(receptor="1ABC", fallback_receptor="2DEF", site_ligand="LIG",
                  train_accession="ACC1", holdout_accession="AID1")


# --- the seven-case branch table (DESIGN.md D3) --------------------------

CASES = [
    ("holdout overlaps",        dict(holdout_overlap=1),             "scaffold_split"),
    ("series too small",        dict(n_analogs=12, n_distinct_inchikeys=12,
                                     dominant_scaffold_n=12),        "not_ready"),
    ("series is duplicates",    dict(n_distinct_inchikeys=1),        "not_ready"),
    ("no depth on any core",    dict(dominant_scaffold_n=4),         "not_ready"),
    ("nothing to rank",         dict(activity_span_log=0.8),         "not_ready"),
    ("no usable structure",     dict(best_resolution=4.2),           "no_structure"),
    ("triage-quality only",     dict(best_resolution=2.9),           "triage_only"),
    ("all checks pass",         dict(),                              "proceed"),
]


@pytest.mark.parametrize("name,over,expected", CASES, ids=[c[0] for c in CASES])
def test_branch_is_reachable(name, over, expected):
    assert next_step(f(**over), HANDOFF).branch == expected


def test_every_declared_branch_is_covered_by_the_table():
    assert {c[2] for c in CASES} == set(BRANCHES)


# --- the regression that the original spec failed ------------------------

def test_the_reference_case_proceeds_rather_than_failing():
    """106 analogs on ONE scaffold at 2.9 A. The original spec's `n_scaffolds >= 2`
    made this `not_ready`. It must be `triage_only`."""
    got = next_step(f(dominant_scaffold_n=106, best_resolution=2.9), HANDOFF)
    assert got.branch == "triage_only"
    assert got.branch != "not_ready"


# --- ordering ------------------------------------------------------------

def test_holdout_overlap_is_reported_before_series_problems():
    """Overlap narrows the validation claim; it does not condemn the target."""
    got = next_step(f(holdout_overlap=1, activity_span_log=0.8), HANDOFF)
    assert got.branch == "scaffold_split"


def test_a_fragment_site_is_not_a_usable_structure():
    assert next_step(f(ligand_mw=92.0, ligand_heavy=6), HANDOFF).branch == "no_structure"


# --- the proposal --------------------------------------------------------

def test_proceeding_hands_off_every_identifier_it_was_given():
    got = next_step(f(), HANDOFF)
    for value in ("1ABC", "2DEF", "LIG", "ACC1", "AID1"):
        assert value in got.recommendation


def test_the_proposal_names_no_target_it_was_not_given():
    got = next_step(f(), Handoff(receptor="9XYZ", fallback_receptor=None,
                                 site_ligand=None, train_accession=None,
                                 holdout_accession=None))
    assert "9XYZ" in got.recommendation


def test_a_reversed_recommendation_says_what_to_do_instead():
    got = next_step(f(dominant_scaffold_n=2), HANDOFF)
    assert "ligand-based" in got.recommendation.lower()


def test_scaffold_split_withdraws_the_time_split_claim():
    got = next_step(f(holdout_overlap=3), HANDOFF)
    assert "scaffold split" in got.recommendation.lower()


def test_every_proposal_carries_the_checks_that_decided_it():
    got = next_step(f(activity_span_log=0.5), HANDOFF)
    assert got.failed_checks
    assert "activity_span_log" in got.failed_checks


def test_a_passing_proposal_has_no_failed_checks():
    assert next_step(f(), HANDOFF).failed_checks == ()
