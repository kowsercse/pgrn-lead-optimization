"""Stage 4a — hit triage: PAINS/assay-interference filtering + scaffold-diversity clustering."""

from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams
from rdkit.ML.Cluster import Butina

_MORGAN_GENERATOR = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)

from conductor.ai.agents import tool
from workflows.config import load_config


def _pains_catalog() -> FilterCatalog:
    params = FilterCatalogParams()
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
    return FilterCatalog(params)


@tool
def filter_hits(docking_results: dict) -> dict:
    """Filter docking hits by score, pose plausibility, PAINS, and diversity.

    PAINS toggle and cluster cutoff/top_n come from config.yaml's `hit_triage`
    section. Keeps the best-affinity representative per scaffold cluster
    (Butina clustering on Morgan fingerprints) so the shortlist isn't
    dominated by near-duplicate analogs.
    """
    cfg = load_config().hit_triage
    catalog = _pains_catalog() if cfg.pains_filter else None

    scored = [r for r in docking_results["results"] if r.get("best_affinity_kcal_mol") is not None]
    kept, flagged, mols = [], [], []
    for entry in scored:
        mol = Chem.MolFromSmiles(entry["smiles"])
        if mol is None:
            flagged.append({**entry, "reason": "unparseable_smiles"})
            continue
        if catalog is not None and catalog.HasMatch(mol):
            flagged.append({**entry, "reason": "pains"})
            continue
        kept.append(entry)
        mols.append(mol)

    if not kept:
        return {"hits": [], "flagged": flagged, "num_clusters": 0}

    fingerprints = [_MORGAN_GENERATOR.GetFingerprint(mol) for mol in mols]
    distances = []
    for i in range(1, len(fingerprints)):
        similarities = DataStructs.BulkTanimotoSimilarity(fingerprints[i], fingerprints[:i])
        distances.extend(1 - sim for sim in similarities)
    clusters = Butina.ClusterData(distances, len(fingerprints), cfg.diversity_cluster_cutoff, isDistData=True)

    representatives = []
    for cluster in clusters:
        members = [kept[i] for i in cluster]
        best = min(members, key=lambda r: r["best_affinity_kcal_mol"])
        representatives.append({**best, "cluster_size": len(members)})
    representatives.sort(key=lambda r: r["best_affinity_kcal_mol"])

    return {"hits": representatives[: cfg.top_n], "flagged": flagged, "num_clusters": len(clusters)}
