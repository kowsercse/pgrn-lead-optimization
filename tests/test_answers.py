"""Stage 4: the five answers.

Each is ONE committed choice with a reason, never a candidate list. A dossier that
reads as a literature review has failed — see PLAN.md risks.
"""
import pytest

from dossier.answers import QUESTIONS, compose
from dossier.store import Gap, Record


def struct(pdb, resolution, ligand="LIG", grade="verified"):
    return Record(run_id="r", scout="structures", claim="candidate structure",
                  value=f"PDB {pdb}, {resolution} A, X-RAY DIFFRACTION, "
                        f"drug-like ligand: {ligand}",
                  grade=grade, query="q", source_id=pdb,
                  source_url=f"https://www.rcsb.org/structure/{pdb}")


def count(claim, value, scout="bioactivity"):
    return Record(run_id="r", scout=scout, claim=claim, value=value,
                  grade="measured", query="q", output_hash="h")


def base_records():
    return [
        struct("1ABC", 2.0), struct("2DEF", 2.9),
        count("distinct compounds with measured activity", "138"),
        count("activity records", "400"),
        count("potency range", "1 nM to 79400 nM, median 1200 nM"),
    ]


# --- shape ---------------------------------------------------------------

def test_five_questions_are_always_answered():
    answers = compose(base_records(), gaps=[], verdict=None)
    assert [a.question_no for a in answers] == [1, 2, 3, 4, 5]


def test_questions_are_answered_even_with_no_records_at_all():
    answers = compose([], gaps=[], verdict=None)
    assert len(answers) == 5
    assert all(a.value for a in answers), "an unanswerable question still needs a value"


def test_every_question_has_declared_text():
    assert len(QUESTIONS) == 5


# --- answer 1: the receptor ---------------------------------------------

def test_the_best_resolution_candidate_is_chosen():
    a = compose(base_records(), gaps=[], verdict=None)[0]
    assert "1ABC" in a.value
    assert a.source_id == "1ABC"


def test_the_choice_is_singular_not_a_list():
    a = compose(base_records(), gaps=[], verdict=None)[0]
    assert "2DEF" not in a.value.split(".")[0], "the first sentence must commit"


def test_the_runner_up_is_named_as_a_fallback():
    a = compose(base_records(), gaps=[], verdict=None)[0]
    assert "2DEF" in a.value


def test_no_candidates_yields_an_unverified_answer():
    a = compose([count("distinct compounds with measured activity", "0")],
                gaps=[], verdict=None)[0]
    assert a.grade == "unverified"


def test_an_answer_never_outranks_the_record_it_rests_on():
    """A demoted record must not support a `verified` answer."""
    a = compose([struct("1ABC", 2.0, grade="inferred")], gaps=[], verdict=None)[0]
    assert a.grade == "inferred"


# --- answer 2: chemical matter ------------------------------------------

def test_chemical_matter_reports_distinct_compounds_not_records():
    a = compose(base_records(), gaps=[], verdict=None)[1]
    assert "138" in a.value
    assert "400" in a.value, "the record count belongs in the answer as context"


def test_chemical_matter_without_data_is_unverified():
    a = compose([struct("1ABC", 2.0)], gaps=[], verdict=None)[1]
    assert a.grade == "unverified"


# --- answer 5: what is missing ------------------------------------------

def test_gaps_are_listed_in_the_fifth_answer():
    gaps = [Gap(run_id="r", scout="literature", description="literature did not return",
                reason="deadline exceeded")]
    a = compose(base_records(), gaps=gaps, verdict=None)[4]
    assert "literature" in a.value


def test_no_gaps_still_produces_an_answer():
    a = compose(base_records(), gaps=[], verdict=None)[4]
    assert a.value, "the gap answer must render even when empty"


def test_an_insufficient_retrieval_verdict_is_surfaced():
    a = compose(base_records(), gaps=[], verdict="insufficient retrieval")[4]
    assert "insufficient retrieval" in a.value


# --- agreement -----------------------------------------------------------

def test_agreement_is_carried_when_supplied():
    answers = compose(base_records(), gaps=[], verdict=None, agreement={1: (2, 2)})
    assert (answers[0].agree_n, answers[0].agree_of) == (2, 2)


def test_agreement_is_absent_when_not_replicated():
    answers = compose(base_records(), gaps=[], verdict=None)
    assert answers[1].agree_n is None
