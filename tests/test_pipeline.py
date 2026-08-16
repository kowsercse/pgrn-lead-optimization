"""Stage 6: the pipeline wiring.

The ordering that matters: dossier v1 is written BEFORE the checks are computed. The
agent commits, then the numbers arrive and may contradict it. If that order inverts,
the loop is retrospective and criterion 1 is not met.
"""
import pytest

from dossier.pipeline import Evidence, run_pipeline
from dossier.store import Record, connect


class StubScout:
    def __init__(self, name, records=None, boom=False):
        self.name, self.deadline_s, self.boom = name, 1, boom
        self._records = records or []

    def brief(self, target):
        return f"Investigate {target}."

    def run(self, target):
        if self.boom:
            raise RuntimeError("down")
        return list(self._records)


def rec(scout, claim, value, grade="measured", **over):
    base = dict(run_id="", scout=scout, claim=claim, value=value, grade=grade, query="q")
    if grade == "measured":
        base["output_hash"] = "h"
    if grade in ("verified", "documented"):
        base["source_id"] = value
        base["source_url"] = f"https://example.org/{value}"
    return Record(**{**base, **over})


def scouts(**over):
    default = {
        "structures": [rec("structures", "candidate structure",
                           "PDB 1ABC, 2.0 A, X-RAY DIFFRACTION, drug-like ligand: LIG",
                           grade="verified", source_id="1ABC",
                           source_url="https://example.org/1ABC")],
        "bioactivity": [rec("bioactivity", "distinct compounds with measured activity", "138"),
                        rec("bioactivity", "activity records", "400")],
    }
    default.update(over)
    return [StubScout(name, recs) for name, recs in default.items()]


def fetch_ok(source_id):
    return f"document for {source_id}"


@pytest.fixture()
def conn(tmp_path):
    return connect(tmp_path / "p.db")


def evidence(**over):
    base = dict(series_smiles=["C" * n + "c1ccccc1" for n in range(1, 23)],
                pchembl_values=[5.0, 8.0], holdout_overlap=0,
                ligand_mw=380.0, ligand_heavy=27, best_resolution=2.0)
    return Evidence(**{**base, **over})


# --- ordering ------------------------------------------------------------

def test_version_one_is_written_before_the_checks_run(conn, tmp_path):
    out = run_pipeline(conn, target="TGT", scouts=scouts(), fetch=fetch_ok,
                       evidence=evidence(), out_dir=tmp_path)
    assert out.dossier_v1.exists()
    assert "Checks" in out.dossier_v1.read_text()
    assert out.v1_written_before_checks is True


def test_both_versions_are_produced_when_the_checks_run(conn, tmp_path):
    out = run_pipeline(conn, target="TGT", scouts=scouts(), fetch=fetch_ok,
                       evidence=evidence(), out_dir=tmp_path)
    assert out.dossier_v2 is not None and out.dossier_v2.exists()
    assert out.proposal is not None


# --- degradation ---------------------------------------------------------

def test_a_missing_required_scout_downgrades_and_skips_the_checks(conn, tmp_path):
    broken = [StubScout("structures", boom=True)] + scouts()[1:]
    out = run_pipeline(conn, target="TGT", scouts=broken, fetch=fetch_ok,
                       evidence=evidence(), out_dir=tmp_path)
    assert out.verdict == "insufficient retrieval"
    assert out.proposal is None, "checks must not run over absent data"
    assert out.dossier_v1.exists(), "a degraded dossier is still produced"


def test_absent_evidence_skips_the_checks_without_crashing(conn, tmp_path):
    out = run_pipeline(conn, target="TGT", scouts=scouts(), fetch=fetch_ok,
                       evidence=None, out_dir=tmp_path)
    assert out.proposal is None
    assert out.dossier_v1.exists()


def test_a_contributing_scout_failing_does_not_downgrade(conn, tmp_path):
    with_lit = scouts() + [StubScout("literature", boom=True)]
    out = run_pipeline(conn, target="TGT", scouts=with_lit, fetch=fetch_ok,
                       evidence=evidence(), out_dir=tmp_path)
    assert out.verdict is None
    assert any(g.scout == "literature" for g in out.gaps)


# --- the resolver is in the path ----------------------------------------

def test_an_unresolvable_identifier_is_demoted_in_the_dossier(conn, tmp_path):
    out = run_pipeline(conn, target="TGT", scouts=scouts(), fetch=lambda s: None,
                       evidence=evidence(), out_dir=tmp_path)
    assert out.demoted, "the resolver must run inside the pipeline"
    assert "demot" in out.dossier_v1.read_text().lower()


# --- cost ----------------------------------------------------------------

def test_the_cost_line_is_populated(conn, tmp_path):
    out = run_pipeline(conn, target="TGT", scouts=scouts(), fetch=fetch_ok,
                       evidence=evidence(), out_dir=tmp_path)
    assert out.cost["tool_calls"] > 0
    assert out.cost["wall_clock_s"] >= 0
    assert "Cost" in out.dossier_v1.read_text()


def test_the_run_is_persisted(conn, tmp_path):
    out = run_pipeline(conn, target="TGT", scouts=scouts(), fetch=fetch_ok,
                       evidence=evidence(), out_dir=tmp_path)
    row = conn.execute("SELECT target, finished_at FROM run WHERE run_id = ?",
                       (out.run_id,)).fetchone()
    assert row["target"] == "TGT" and row["finished_at"]
