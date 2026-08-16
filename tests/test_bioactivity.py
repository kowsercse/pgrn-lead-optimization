"""Stage 1: the bioactivity scout must report distinct compounds, never activity
records. The two differ by an order of magnitude and conflating them is the most
common way this assessment goes wrong."""
import pytest

from dossier.scouts.bioactivity import (
    Activity,
    parse_activity,
    pchembl_to_nm,
    summarise,
    to_records,
)


def act(mol="CHEMBL1", pchembl=7.0, kind="IC50", assay="CHEMBL_A1"):
    return Activity(molecule_chembl_id=mol, pchembl_value=pchembl,
                    standard_type=kind, assay_chembl_id=assay)


# --- potency conversion --------------------------------------------------

@pytest.mark.parametrize("pchembl,nm", [(9.0, 1.0), (6.0, 1000.0), (7.0, 100.0)])
def test_pchembl_converts_to_nanomolar(pchembl, nm):
    assert pchembl_to_nm(pchembl) == pytest.approx(nm)


# --- the named check -----------------------------------------------------

def test_one_compound_measured_five_times_is_one_distinct_compound():
    s = summarise([act(mol="CHEMBL1", assay=f"A{i}") for i in range(5)])
    assert s.n_records == 5
    assert s.n_distinct_compounds == 1


def test_distinct_compounds_counts_unique_molecules():
    s = summarise([act(mol="CHEMBL1"), act(mol="CHEMBL2"), act(mol="CHEMBL1")])
    assert s.n_records == 3
    assert s.n_distinct_compounds == 2


# --- potency statistics --------------------------------------------------

def test_median_of_odd_sample():
    s = summarise([act(mol="A", pchembl=6.0), act(mol="B", pchembl=7.0),
                   act(mol="C", pchembl=9.0)])
    assert s.pchembl_median == pytest.approx(7.0)


def test_median_of_even_sample_is_the_midpoint():
    s = summarise([act(mol="A", pchembl=6.0), act(mol="B", pchembl=8.0)])
    assert s.pchembl_median == pytest.approx(7.0)


def test_potency_range_spans_weakest_to_strongest():
    s = summarise([act(mol="A", pchembl=5.0), act(mol="B", pchembl=8.0)])
    assert s.pchembl_min == 5.0 and s.pchembl_max == 8.0


def test_activities_without_pchembl_are_counted_but_excluded_from_statistics():
    s = summarise([act(mol="A", pchembl=7.0), act(mol="B", pchembl=None)])
    assert s.n_records == 2
    assert s.n_distinct_compounds == 2
    assert s.n_with_pchembl == 1
    assert s.pchembl_median == pytest.approx(7.0)


def test_a_set_with_no_pchembl_values_has_no_statistics():
    s = summarise([act(mol="A", pchembl=None)])
    assert s.n_with_pchembl == 0
    assert s.pchembl_median is None and s.pchembl_min is None


def test_assay_types_are_deduplicated_and_sorted():
    s = summarise([act(kind="Ki", mol="A"), act(kind="IC50", mol="B"),
                   act(kind="IC50", mol="C")])
    assert s.assay_types == ("IC50", "Ki")


def test_empty_input_summarises_to_zero_without_raising():
    s = summarise([])
    assert s.n_records == 0 and s.n_distinct_compounds == 0
    assert s.pchembl_median is None


# --- parsing -------------------------------------------------------------

def test_parse_activity_reads_chembl_payload():
    got = parse_activity({
        "molecule_chembl_id": "CHEMBL25", "pchembl_value": "7.5",
        "standard_type": "IC50", "assay_chembl_id": "CHEMBL_A9",
    })
    assert got == Activity("CHEMBL25", 7.5, "IC50", "CHEMBL_A9")


def test_parse_activity_tolerates_a_missing_pchembl():
    got = parse_activity({"molecule_chembl_id": "CHEMBL25", "pchembl_value": None,
                          "standard_type": "IC50", "assay_chembl_id": "A"})
    assert got.pchembl_value is None


# --- records -------------------------------------------------------------

def test_records_report_both_counts_and_name_them_unambiguously():
    records = to_records(summarise([act(mol="A"), act(mol="A"), act(mol="B")]))
    by_claim = {r.claim: r.value for r in records}
    assert by_claim["distinct compounds with measured activity"] == "2"
    assert by_claim["activity records"] == "3"


def test_counts_are_measured_and_hashed():
    for r in to_records(summarise([act()])):
        if r.claim in {"distinct compounds with measured activity", "activity records"}:
            assert r.grade == "measured" and r.output_hash


def test_records_name_the_scout():
    for r in to_records(summarise([act()])):
        assert r.scout == "bioactivity"


def test_potency_record_is_omitted_when_there_are_no_values():
    claims = {r.claim for r in to_records(summarise([act(pchembl=None)]))}
    assert "potency range" not in claims
