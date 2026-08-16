"""Stage 2b — ligand mining: known tool compounds/chemical probes for the target."""

from proto_tools.tools.database_retrieval.pubchem.pubchem_fetch import (
    PubChemFetchConfig,
    PubChemFetchInput,
    run_pubchem_fetch,
)

from conductor.ai.agents import tool
from workflows.config import load_config


@tool
def search_known_ligands(target: str) -> dict:
    """Find known tool compounds/chemical probes binding the target via PubChem.

    Looks up config.yaml's `target.known_ligand_names` — the compounds
    co-crystallized in the target's known structures (`target.pdb_ids`). Query
    field (name/smiles/cid) is set by `ligand_mining.pubchem_query_field`.
    Compounds PubChem can't resolve (e.g. paper-only compound numbering) are
    reported with `resolved: False` rather than failing the whole lookup.
    """
    cfg = load_config()
    field = cfg.ligand_mining.pubchem_query_field

    results = []
    for name in cfg.target.known_ligand_names:
        try:
            output = run_pubchem_fetch(PubChemFetchInput(**{field: name}), PubChemFetchConfig())
            results.append(
                {
                    "query": name,
                    "resolved": True,
                    "cid": output.cid,
                    "title": output.title,
                    "smiles": output.smiles,
                    "molecular_weight": output.molecular_weight,
                    "source_url": output.source_url,
                }
            )
        except Exception as exc:  # noqa: BLE001 - PubChem lookups fail for many valid reasons (unresolvable, rate limit)
            results.append({"query": name, "resolved": False, "error": str(exc)})

    return {"target": target, "known_ligands": results}
