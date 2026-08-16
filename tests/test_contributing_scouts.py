"""Stage 1, contributing scouts: patents, assays, literature.

None is required for a verdict — their absence is a gap, not a downgrade. Each still
carries a named check from SPEC.md, and those checks are what these tests pin.
"""
import pytest

from dossier.scouts.assays import (
    QHTS_MIN_COMPOUNDS,
    REAL_POTENCY_TYPES,
    AssayRecord,
    has_real_potency,
    is_qhts,
    summarise_assays,
)
from dossier.scouts.assays import to_records as assay_records
from dossier.scouts.literature import (
    alias_queries,
    parse_esearch,
    parse_esummary,
)
from dossier.scouts.literature import to_records as lit_records
from dossier.scouts.patents import (
    DepositedSet,
    parse_pubchem_aids,
    reconcile_with_chembl,
)
from dossier.scouts.patents import to_records as patent_records


# =========================== assays =====================================

def assay(kind="IC50", n=12, desc="binding assay"):
    return AssayRecord(assay_id="A1", standard_type=kind, n_compounds=n,
                       description=desc)


def test_real_potency_types_are_recognised():
    for kind in REAL_POTENCY_TYPES:
        assert has_real_potency(kind)


def test_percent_inhibition_is_not_a_real_potency():
    assert not has_real_potency("Inhibition")
    assert not has_real_potency("Activity")


def test_a_large_screen_is_flagged_as_qhts():
    assert is_qhts(n_compounds=QHTS_MIN_COMPOUNDS, description="")


def test_a_small_assay_is_not_qhts_however_described():
    assert not is_qhts(n_compounds=20, description="qHTS titration screen")


def test_a_large_assay_described_as_qhts_is_flagged():
    assert is_qhts(n_compounds=QHTS_MIN_COMPOUNDS * 2, description="qHTS")


def test_qhts_inflation_is_separated_from_real_potency():
    """The trap: a target showing tens of thousands of compounds where only a few
    hundred carry a real IC50."""
    assays = ([assay(kind="Inhibition", n=50_000, desc="qHTS")] +
              [assay(kind="IC50", n=5) for _ in range(40)])
    s = summarise_assays(assays)
    assert s.n_qhts == 1
    assert s.n_compounds_in_qhts == 50_000
    assert s.n_with_real_potency == 40


def test_assay_records_state_both_numbers():
    s = summarise_assays([assay(kind="Inhibition", n=50_000, desc="qHTS"),
                          assay(kind="IC50", n=5)])
    by_claim = {r.claim: r.value for r in assay_records(s)}
    assert "50,000" in by_claim["compounds behind qHTS screens"]
    assert by_claim["assays carrying a real potency value"] == "1"


def test_no_qhts_still_reports_zero():
    s = summarise_assays([assay(kind="IC50", n=5)])
    assert s.n_qhts == 0
    assert any(r.claim == "compounds behind qHTS screens" for r in assay_records(s))


# =========================== patents ====================================

def test_pubchem_aids_are_parsed():
    got = parse_pubchem_aids({"IdentifierList": {"AID": [1904, 147067]}})
    assert got == [1904, 147067]


def test_an_empty_pubchem_response_yields_no_aids():
    assert parse_pubchem_aids({}) == []


def test_sets_present_in_pubchem_but_absent_from_chembl_are_the_finding():
    """Patent-derived sets are routinely deposited in one and not the other."""
    got = reconcile_with_chembl(pubchem_aids=[1, 2, 3], chembl_assay_aids=[1])
    assert got.only_in_pubchem == (2, 3)
    assert got.in_both == (1,)


def test_full_overlap_reports_nothing_novel():
    got = reconcile_with_chembl(pubchem_aids=[1], chembl_assay_aids=[1, 2])
    assert got.only_in_pubchem == ()


def test_patent_records_name_both_sources():
    got = reconcile_with_chembl(pubchem_aids=[1, 2], chembl_assay_aids=[1])
    claims = {r.claim for r in patent_records(got)}
    assert "assay sets in PubChem" in claims
    assert "assay sets absent from ChEMBL" in claims


def test_a_pubchem_only_set_is_offered_with_a_resolvable_url():
    got = reconcile_with_chembl(pubchem_aids=[2202264], chembl_assay_aids=[])
    cand = [r for r in patent_records(got) if r.claim == "candidate held-out set"]
    assert cand and cand[0].grade == "verified"
    assert "2202264" in cand[0].source_url


# =========================== literature =================================

def test_alias_queries_include_the_target():
    qs = alias_queries("TGT", aliases=[])
    assert any("TGT" in q for q in qs)


def test_alias_queries_cover_pathway_and_phenotypic_terms():
    """A series filed under a pathway identifier is invisible to a target-only query."""
    qs = alias_queries("TGT", aliases=["pathway X"])
    assert any("pathway X" in q for q in qs)


def test_alias_queries_are_deduplicated():
    qs = alias_queries("TGT", aliases=["TGT", "TGT"])
    assert len(qs) == len(set(qs))


def test_esearch_is_parsed():
    pmids, total = parse_esearch({"esearchresult": {"count": "1056",
                                                    "idlist": ["1", "2"]}})
    assert pmids == ["1", "2"] and total == 1056


def test_a_malformed_esearch_does_not_raise():
    assert parse_esearch({}) == ([], 0)


def test_esummary_titles_are_parsed():
    got = parse_esummary({"result": {"uids": ["1"],
                                     "1": {"title": "A paper", "pubdate": "2021 Mar"}}})
    assert got == [("1", "A paper", "2021 Mar")]


def test_literature_records_carry_a_resolvable_pubmed_url():
    recs = lit_records([("12345", "A paper", "2021")], total=1056, queries=["q"])
    cited = [r for r in recs if r.source_id == "12345"]
    assert cited and "12345" in cited[0].source_url
    assert cited[0].grade == "verified"


def test_literature_reports_how_many_queries_were_run():
    recs = lit_records([], total=0, queries=["a", "b"])
    by_claim = {r.claim: r.value for r in recs}
    assert by_claim["alias queries run"] == "2"
