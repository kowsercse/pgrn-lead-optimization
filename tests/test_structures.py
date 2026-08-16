"""Stage 1: the structures scout must count drug-like-ligand entries separately
from total entries, and must never assume the target it is looking at."""
import pytest

from dossier.scouts.structures import (
    DRUGLIKE_HEAVY,
    DRUGLIKE_MW,
    Ligand,
    StructureHit,
    is_druglike,
    parse_entry,
    to_records,
)


def lig(het="ABC", mw=380.0, heavy=27):
    return Ligand(het_code=het, name="ligand", mw=mw, heavy_atoms=heavy)


def hit(pdb_id="1ABC", resolution=2.0, method="X-RAY DIFFRACTION", ligands=()):
    return StructureHit(pdb_id=pdb_id, resolution=resolution, method=method,
                        ligands=tuple(ligands))


# --- drug-likeness -------------------------------------------------------

def test_ligand_at_both_thresholds_is_druglike():
    assert is_druglike(lig(mw=DRUGLIKE_MW, heavy=DRUGLIKE_HEAVY))


def test_light_ligand_is_not_druglike():
    assert not is_druglike(lig(mw=DRUGLIKE_MW - 1, heavy=DRUGLIKE_HEAVY))


def test_small_ligand_is_not_druglike():
    assert not is_druglike(lig(mw=DRUGLIKE_MW, heavy=DRUGLIKE_HEAVY - 1))


def test_crystallisation_additive_is_not_druglike():
    assert not is_druglike(Ligand(het_code="GOL", name="glycerol", mw=92.1, heavy_atoms=6))


# --- parsing -------------------------------------------------------------

def test_parse_entry_reads_resolution_and_method():
    entry = {
        "rcsb_id": "1ABC",
        "rcsb_entry_info": {"resolution_combined": [1.85]},
        "exptl": [{"method": "X-RAY DIFFRACTION"}],
    }
    got = parse_entry(entry, [])
    assert got.pdb_id == "1ABC"
    assert got.resolution == 1.85
    assert got.method == "X-RAY DIFFRACTION"


def test_parse_entry_tolerates_a_structure_with_no_resolution():
    entry = {"rcsb_id": "2XYZ", "rcsb_entry_info": {}, "exptl": [{"method": "SOLUTION NMR"}]}
    assert parse_entry(entry, []).resolution is None


def test_parse_entry_collects_ligands():
    entry = {"rcsb_id": "1ABC", "rcsb_entry_info": {"resolution_combined": [2.0]},
             "exptl": [{"method": "X-RAY DIFFRACTION"}]}
    comps = [{
        "chem_comp": {"id": "LIG", "name": "inhibitor",
                      "formula_weight": 380.4},
        "rcsb_chem_comp_info": {"atom_count_heavy": 27},
    }]
    got = parse_entry(entry, comps)
    assert got.ligands == (Ligand("LIG", "inhibitor", 380.4, 27),)


# --- the named check -----------------------------------------------------

def test_druglike_count_is_reported_separately_from_total():
    hits = [
        hit("1AAA", ligands=[lig()]),                                   # drug-like
        hit("2BBB", ligands=[Ligand("GOL", "glycerol", 92.1, 6)]),      # additive only
        hit("3CCC", ligands=[]),                                        # apo
    ]
    records = to_records(hits)
    by_claim = {r.claim: r.value for r in records}
    assert by_claim["total structures"] == "3"
    assert by_claim["structures with a drug-like ligand"] == "1"


def test_every_structure_record_carries_a_resolvable_source_url():
    records = to_records([hit("1AAA", ligands=[lig()])])
    entries = [r for r in records if r.claim == "candidate structure"]
    assert entries, "no candidate structure emitted"
    for r in entries:
        assert r.grade == "verified"
        assert r.source_id == "1AAA"
        assert r.source_url == "https://www.rcsb.org/structure/1AAA"


def test_counts_are_graded_measured_and_carry_an_output_hash():
    records = to_records([hit("1AAA", ligands=[lig()])])
    counts = [r for r in records if r.claim.endswith("structures")
              or r.claim.startswith("structures with")]
    assert counts
    for r in counts:
        assert r.grade == "measured"
        assert r.output_hash


def test_apo_structures_are_not_offered_as_candidates():
    records = to_records([hit("3CCC", ligands=[])])
    assert [r for r in records if r.claim == "candidate structure"] == []


def test_candidate_value_states_resolution_and_method():
    records = to_records([hit("1AAA", resolution=2.9, ligands=[lig(het="UP4")])])
    value = next(r.value for r in records if r.claim == "candidate structure")
    assert "1AAA" in value and "2.9" in value and "UP4" in value


def test_records_name_the_scout():
    for r in to_records([hit("1AAA", ligands=[lig()])]):
        assert r.scout == "structures"
