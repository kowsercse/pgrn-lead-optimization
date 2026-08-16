"""Typed loader for config.yaml — runtime parameters for the PGRN-Sortilin pipeline.

Every tool in workflows/tools/ reads its parameters from a PipelineConfig instance
instead of hardcoding them, so target IDs, thresholds, and engine choices can change
without touching tool code.
"""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


class TargetConfig(BaseModel):
    gene_a: str
    gene_b: str
    pdb_ids: list[str]
    known_ligand_names: list[str] = []


class StructurePredictionConfig(BaseModel):
    engine: str = "boltz2"
    use_msa: bool = True
    recycling_steps: int = 3
    sampling_steps: int = 200
    diffusion_samples: int = 1


class InterfaceConfig(BaseModel):
    ligand_contact_cutoff_angstrom: float = 4.5
    pocket_expand_residues: int = 0
    exclude_resnames: list[str] = ["HOH", "GOL", "PEG", "EDO", "DMS", "MPD", "NAG", "BMA", "MAN", "FUC", "GAL", "SIA", "NA", "CL", "MG", "CA", "ZN", "K", "SO4", "PO4"]


class LigandMiningConfig(BaseModel):
    pubchem_query_field: str = "name"


class OdesignConfig(BaseModel):
    num_generations: int = 50
    population_size: int = 10
    dock_every_n_generations: int = 10
    # Vina affinities (kcal/mol) mapped onto a 0-1 "higher is better" scale for
    # blending with the model/similarity scores; values outside this range clamp.
    affinity_best_kcal_mol: float = -12.0
    affinity_worst_kcal_mol: float = -4.0
    score_weights: dict[str, float] = {"model_score": 0.4, "docking_score": 0.4, "ligand_similarity": 0.2}


class DockingConfig(BaseModel):
    engine: str = "vina"
    exhaustiveness: int = 8
    num_poses: int = 9
    energy_range: float = 3.0
    seed: int | None = 42
    reference_ligand_padding_angstrom: float = 4.0
    positive_control_rank_threshold_pct: float = 10.0


class HitTriageConfig(BaseModel):
    pains_filter: bool = True
    diversity_cluster_cutoff: float = 0.4
    top_n: int = 50


class AdmetConfig(BaseModel):
    provider: str = "rdkit_proxy"
    lipinski_violations_max: int = 1
    qed_min: float = 0.3


class BenchlingConfig(BaseModel):
    enabled: bool = False
    base_url: str = "https://hackathon.bnchdev.org"
    entity_schema_id: str | None = None
    results_folder_id: str | None = None


class PrioritizationConfig(BaseModel):
    weights: dict[str, float] = {"docking_score": 0.5, "admet": 0.3, "diversity": 0.2}
    top_n: int = 20
    benchling: BenchlingConfig = BenchlingConfig()


class PipelineConfig(BaseModel):
    llm_model: str = "anthropic/claude-sonnet-4-6"
    target: TargetConfig
    structure_prediction: StructurePredictionConfig = StructurePredictionConfig()
    interface: InterfaceConfig = InterfaceConfig()
    ligand_mining: LigandMiningConfig = LigandMiningConfig()
    odesign: OdesignConfig = OdesignConfig()
    docking: DockingConfig = DockingConfig()
    hit_triage: HitTriageConfig = HitTriageConfig()
    admet: AdmetConfig = AdmetConfig()
    prioritization: PrioritizationConfig = PrioritizationConfig()


def load_config(path: str | Path | None = None) -> PipelineConfig:
    """Load PipelineConfig from `path`, PGRN_CONFIG_PATH, or config.yaml (in that order)."""
    resolved = Path(path or os.environ.get("PGRN_CONFIG_PATH") or DEFAULT_CONFIG_PATH)
    with resolved.open() as f:
        raw = yaml.safe_load(f)
    return PipelineConfig.model_validate(raw)
