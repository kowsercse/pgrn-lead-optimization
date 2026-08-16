"""Stage 5 — prioritization: composite ranking + Benchling handoff.

Benchling handoff uses its documented Apps + API OAuth2 client-credentials flow
(REST, not MCP) — Benchling's hosted MCP server is OAuth-redirect/interactive
(see docs/setup.md), which doesn't fit a server-side Conductor tool the way
Paperclip's bearer-token MCP does. Real request shape, untested against a live
tenant (needs BENCHLING_CLIENT_ID/BENCHLING_CLIENT_SECRET + the tenant's
entity-schema/folder IDs, none of which are available in this environment).
"""

import os

import requests
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from conductor.ai.agents import tool
from workflows.config import BenchlingConfig, load_config

_MORGAN_GENERATOR = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def _normalize(values: list[float], higher_is_better: bool) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0] * len(values)
    if higher_is_better:
        return [(v - lo) / (hi - lo) for v in values]
    return [(hi - v) / (hi - lo) for v in values]


def _diversity_scores(smiles_list: list[str]) -> list[float]:
    """Mean Tanimoto distance of each compound to the rest of the shortlist."""
    fingerprints = [_MORGAN_GENERATOR.GetFingerprint(mol) if (mol := Chem.MolFromSmiles(s)) else None for s in smiles_list]
    scores = []
    for i, fp in enumerate(fingerprints):
        others = [other for j, other in enumerate(fingerprints) if j != i and other is not None]
        if fp is None or not others:
            scores.append(0.0 if fp is None else 1.0)
            continue
        similarities = DataStructs.BulkTanimotoSimilarity(fp, others)
        scores.append(1 - (sum(similarities) / len(similarities)))
    return scores


def _push_to_benchling(shortlist: list[dict], cfg: BenchlingConfig) -> dict:
    if not cfg.enabled:
        return {"pushed": False, "reason": "prioritization.benchling.enabled is false in config.yaml"}
    if not cfg.entity_schema_id or not cfg.results_folder_id:
        return {"pushed": False, "reason": "prioritization.benchling.entity_schema_id/results_folder_id not set"}

    client_id = os.environ.get("BENCHLING_CLIENT_ID")
    client_secret = os.environ.get("BENCHLING_CLIENT_SECRET")
    if not client_id or not client_secret:
        return {"pushed": False, "reason": "BENCHLING_CLIENT_ID/BENCHLING_CLIENT_SECRET not set"}

    token_response = requests.post(
        f"{cfg.base_url}/api/v2/token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=30,
    )
    token_response.raise_for_status()
    access_token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    entity_ids = []
    for compound in shortlist:
        response = requests.post(
            f"{cfg.base_url}/api/v2/custom-entities",
            headers=headers,
            json={
                "schemaId": cfg.entity_schema_id,
                "folderId": cfg.results_folder_id,
                "name": compound.get("name") or compound["smiles"],
                "fields": {
                    "smiles": {"value": compound["smiles"]},
                    "docking_affinity_kcal_mol": {"value": compound.get("best_affinity_kcal_mol")},
                    "composite_score": {"value": compound.get("composite_score")},
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        entity_ids.append(response.json().get("id"))

    return {"pushed": True, "entity_ids": entity_ids}


@tool
def rank_and_handoff(compounds: dict) -> dict:
    """Rank the final shortlist and hand off to experimental validation.

    Composite score is a weighted combination of docking affinity, ADMET
    (QED), and scaffold diversity (mean Tanimoto distance to the rest of the
    shortlist) — weights and shortlist size come from config.yaml's
    `prioritization` section. Pushes the shortlist to Benchling only when
    `prioritization.benchling.enabled` and its IDs are set; otherwise reports
    why it didn't.
    """
    cfg = load_config().prioritization
    entries = compounds.get("compounds", [])
    if not entries:
        return {"shortlist": [], "benchling": {"pushed": False, "reason": "no compounds to rank"}}

    norm_affinity = _normalize([e["best_affinity_kcal_mol"] for e in entries], higher_is_better=False)
    norm_qed = _normalize([e.get("qed", 0.0) for e in entries], higher_is_better=True)
    norm_diversity = _normalize(_diversity_scores([e["smiles"] for e in entries]), higher_is_better=True)

    weights = cfg.weights
    ranked = []
    for entry, affinity, qed, diversity in zip(entries, norm_affinity, norm_qed, norm_diversity, strict=True):
        composite = (
            weights.get("docking_score", 0.0) * affinity
            + weights.get("admet", 0.0) * qed
            + weights.get("diversity", 0.0) * diversity
        )
        ranked.append({**entry, "composite_score": composite})
    ranked.sort(key=lambda r: r["composite_score"], reverse=True)

    shortlist = ranked[: cfg.top_n]
    return {"shortlist": shortlist, "benchling": _push_to_benchling(shortlist, cfg.benchling)}
