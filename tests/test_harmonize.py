"""Stage 3 exit gate: harmonisation.

Three kinds of sameness — same molecule, same protein, same evidence — resolved so the
counts mean something. Nothing here looks for a difference between sources.
"""
import pytest

from dossier.harmonize import (
    alias_resolution,
    inchikey,
    pool_compounds,
    record_vs_compound,
    to_records,
)
from dossier.receptor import scaffold_match
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


# --- same molecule: pooling without double-counting ---------------------

def test_pooling_merges_sources():
    assert len(pool_compounds([BENZENE], [TOLUENE, PHENOL])) == 3


def test_the_same_molecule_from_two_sources_is_counted_once():
    """The reason pooling needs canonical identity: patent and public sets overlap."""
    assert len(pool_compounds([ETHANOL], [ETHANOL_REVERSED])) == 1


def test_pooling_a_source_with_itself_changes_nothing():
    assert len(pool_compounds([BENZENE, TOLUENE], [BENZENE])) == 2


def test_pooling_skips_unparseable_entries():
    assert len(pool_compounds([BENZENE], ["garbage"])) == 1


def test_pooling_no_sources_is_empty():
    assert pool_compounds() == set()


def test_duplicates_within_one_source_collapse():
    assert len(pool_compounds([TOLUENE, TOLUENE, TOLUENE])) == 1


# --- receptor selection (dossier.receptor, not harmonisation) -----------

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


# --- same evidence: measurements versus molecules ------------------------

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


# --- same protein: alias resolution --------------------------------------

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

def test_each_harmonisation_writes_one_row(tmp_path):
    conn = connect(tmp_path / "j.db")
    run = new_run(conn, target="X")
    to_records(conn, run, pooled=pool_compounds([BENZENE], [TOLUENE]),
               aliases=["X"], counts=(400, 138, True))
    rows = conn.execute("SELECT kind FROM join_result WHERE run_id = ?", (run,)).fetchall()
    assert sorted(r["kind"] for r in rows) == [
        "alias_resolution", "pooled_compounds", "record_vs_compound",
    ]


def test_join_records_are_graded_measured(tmp_path):
    conn = connect(tmp_path / "j.db")
    run = new_run(conn, target="X")
    records = to_records(conn, run, pooled=pool_compounds([BENZENE], [TOLUENE]),
                         aliases=["X"], counts=(400, 138, True))
    assert records
    for r in records:
        assert r.grade == "measured"
        assert r.output_hash
