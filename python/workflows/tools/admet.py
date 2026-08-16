"""Stage 4b — ADMET profiling: RDKit descriptor-based proxy (no proto-tools ADMET tool exists)."""

from rdkit import Chem
from rdkit.Chem import QED, Crippen, Descriptors, Lipinski

from conductor.ai.agents import tool
from workflows.config import load_config


@tool
def predict_admet(compounds: dict) -> dict:
    """Predict ADMET-proxy properties for triaged hits.

    `compounds` is filter_hits output. This is a cheap RDKit descriptor/QED
    proxy (Lipinski Ro5 violations + QED), not a trained ADMET model —
    proto-tools has no ADMET tool (see spec/implementation-plan.md, Stage 4).
    Pass/fail thresholds come from config.yaml's `admet` section.
    """
    cfg = load_config().admet
    results = []
    for hit in compounds.get("hits", []):
        mol = Chem.MolFromSmiles(hit["smiles"])
        if mol is None:
            results.append({**hit, "admet_pass": False, "reason": "unparseable_smiles"})
            continue

        molecular_weight = Descriptors.MolWt(mol)
        logp = Crippen.MolLogP(mol)
        hbd = Lipinski.NumHDonors(mol)
        hba = Lipinski.NumHAcceptors(mol)
        violations = sum([molecular_weight > 500, logp > 5, hbd > 5, hba > 10])
        qed = QED.qed(mol)

        results.append(
            {
                **hit,
                "molecular_weight": molecular_weight,
                "logp": logp,
                "hbd": hbd,
                "hba": hba,
                "tpsa": Descriptors.TPSA(mol),
                "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
                "qed": qed,
                "lipinski_violations": violations,
                "admet_pass": violations <= cfg.lipinski_violations_max and qed >= cfg.qed_min,
            }
        )

    results.sort(key=lambda r: r.get("qed", -1), reverse=True)
    return {"compounds": results, "num_passed": sum(1 for r in results if r.get("admet_pass"))}
