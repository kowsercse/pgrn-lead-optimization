"""Stage 3 exit gate: the cross-source joins.

These produce the findings no single database returns. Join 2 in particular decides
whether a prospective time split is available at all.
"""
import pytest

from dossier.joins import (
    Disjointness,
    alias_resolution,
    holdout_disjointness,
    inchikey,
    record_vs_compound,
    scaffold_match,
    to_records,
)
from dossier.store import Record, connect, new_run

ETHANOL = "CCO"
ETHANOL_REVERSED = "OCC"      # same molecule, different SMILES traversal
BENZENE = "c1ccccc1"
TOLUENE = "Cc1ccccc1"
PHENOL = "Oc1ccccc1"


# --- normalisation -------------------------------------------------------

def test_the_same_molecule_written_two_ways_has_one_inchikey():
    assert inchikey(ETHANOL) == inchikey(ETHANOL_REVERSED)


def test_different_molecules_have_different_inchikeys():
    assert inchikey(BENZENE) != inchikey(TOLUENE)


def test_unparseable_smiles_yields_no_key():
    assert inchikey("not a molecule") is None


# --- join 2: holdout disjointness ---------------------------------------

def test_fully_disjoint_sets_yield_all_holdout_as_novel():
    d = holdout_disjointness(train=[BENZENE], holdout=[TOLUENE, PHENOL])
    assert len(d.novel) == 2
    assert d.overlap == set()


def test_overlap_is_detected_across_smiles_spellings():
    """The join must not be fooled by a different traversal of the same molecule."""
    d = holdout_disjointness(train=[ETHANOL], holdout=[ETHANOL_REVERSED, BENZENE])
    assert len(d.overlap) == 1
    assert len(d.novel) == 1


def test_a_holdout_wholly_inside_training_has_no_novel_members():
    d = holdout_disjointness(train=[BENZENE, TOLUENE], holdout=[BENZENE])
    assert d.novel == set()
    assert len(d.overlap) == 1


def test_novel_and_overlap_partition_the_holdout():
    d = holdout_disjointness(train=[BENZENE], holdout=[BENZENE, TOLUENE, PHENOL])
    assert len(d.novel) + len(d.overlap) == 3
    assert d.novel & d.overlap == set()


def test_unparseable_entries_are_skipped_not_counted_as_novel():
    d = holdout_disjointness(train=[BENZENE], holdout=[TOLUENE, "garbage"])
    assert len(d.novel) == 1


def test_empty_holdout_is_not_an_error():
    d = holdout_disjointness(train=[BENZENE], holdout=[])
    assert d.novel == set() and d.overlap == set()


def test_duplicates_within_the_holdout_collapse():
    d = holdout_disjointness(train=[], holdout=[TOLUENE, TOLUENE, TOLUENE])
    assert len(d.novel) == 1


# --- join 1: scaffold match ---------------------------------------------

def test_a_core_contained_in_a_ligand_matches():
    assert scaffold_match(BENZENE, TOLUENE) is True


def test_an_unrelated_core_does_not_match():
    assert scaffold_match("CCCCCCCC", BENZENE) is False


def test_a_molecule_matches_itself():
    assert scaffold_match(TOLUENE, TOLUENE) is True


def test_a_ligand_is_not_a_substructure_of_its_own_core():
    """Direction matters: the core must be inside the ligand, not the reverse."""
    assert scaffold_match(TOLUENE, BENZENE) is False


def test_unparseable_input_does_not_match():
    assert scaffold_match("garbage", BENZENE) is False
    assert scaffold_match(BENZENE, "garbage") is False


# --- join 4: record versus compound -------------------------------------

def test_conflated_counts_are_flagged():
    n_records, n_distinct, conflated = record_vs_compound(400, 138)
    assert (n_records, n_distinct) == (400, 138)
    assert conflated is True


def test_equal_counts_are_not_flagged():
    _, _, conflated = record_vs_compound(138, 138)
    assert conflated is False


def test_distinct_exceeding_records_is_impossible():
    with pytest.raises(ValueError):
        record_vs_compound(10, 11)


# --- join 3: alias resolution -------------------------------------------

def test_aliases_include_the_target_itself():
    assert "SORTX" in alias_resolution("SORTX", lookup=lambda t: [])


def test_aliases_are_deduplicated_and_sorted():
    got = alias_resolution("B", lookup=lambda t: ["A", "B", "A"])
    assert got == ["A", "B"]


def test_alias_lookup_failure_degrades_to_the_target_alone():
    def boom(target):
        raise ConnectionError("down")

    assert alias_resolution("SORTX", lookup=boom) == ["SORTX"]


# --- persistence ---------------------------------------------------------

def test_each_join_writes_one_row(tmp_path):
    conn = connect(tmp_path / "j.db")
    run = new_run(conn, target="X")
    d = holdout_disjointness(train=[BENZENE], holdout=[TOLUENE])
    to_records(conn, run, disjointness=d, scaffold_matched=True,
               aliases=["X"], counts=(400, 138, True))
    rows = conn.execute("SELECT kind FROM join_result WHERE run_id = ?", (run,)).fetchall()
    assert sorted(r["kind"] for r in rows) == [
        "alias_resolution", "holdout_disjointness", "record_vs_compound", "scaffold_match",
    ]


def test_join_records_are_graded_measured(tmp_path):
    conn = connect(tmp_path / "j.db")
    run = new_run(conn, target="X")
    d = holdout_disjointness(train=[BENZENE], holdout=[TOLUENE])
    records = to_records(conn, run, disjointness=d, scaffold_matched=True,
                         aliases=["X"], counts=(400, 138, True))
    assert records
    for r in records:
        assert r.grade == "measured"
        assert r.output_hash
