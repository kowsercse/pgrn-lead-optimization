"""Conductor agent pipeline for the PGRN-Sortilin screening flow.

Implements the "Computational biologist review" stages from
spec/therapeutic-hypothesis.md as a sequential Conductor agent pipeline.
See spec/conductor-workflow-spec.md for scope and spec/implementation-plan.md
for what's real vs. what still needs a live credential/binary to exercise.

Tool bodies live in workflows/tools/ (one module per pipeline stage) and read
their runtime parameters from config.yaml via workflows/config.py — target IDs,
docking/ADMET thresholds, engine choices, etc. are config-driven, not hardcoded
here. Paperclip is wired as a real hosted MCP tool (see spec/conductor-workflow-spec.md,
"MCP tool integration"); Biohub has no hosted MCP server upstream, so it's
called directly via its REST API / `esm` SDK instead.

Requirements:
    - Conductor server reachable via CONDUCTOR_SERVER_URL
    - CONDUCTOR_AGENT_LLM_MODEL set (defaults to config.yaml's llm_model)
    - PAPERCLIP_API_KEY set (see .env.example) for the Paperclip MCP server
    - BIOHUB_API_KEY set (see .env.example) for the Biohub API
"""

import os

from conductor.ai.agents import Agent, AgentRuntime, mcp_tool, tool

from workflows.config import load_config
from workflows.tools.interface import map_interface_pocket
from workflows.tools.ligands import search_known_ligands
from workflows.tools.structure import fetch_pdb_structure, predict_complex_structure, score_structure_quality

CONFIG = load_config()
LLM_MODEL = os.environ.get("CONDUCTOR_AGENT_LLM_MODEL", CONFIG.llm_model)


# ── 1. Target validation ────────────────────────────────────────────

paperclip_mcp = mcp_tool(
    server_url="https://paperclip.gxl.ai/mcp",
    name="paperclip_mcp",
    description="Biomedical literature/trial/database search via Paperclip (11M+ papers, trials, databases).",
    headers={"Authorization": "Bearer ${PAPERCLIP_API_KEY}"},
    credentials=["PAPERCLIP_API_KEY"],
)

literature_agent = Agent(
    name="literature_agent",
    model=LLM_MODEL,
    tools=[paperclip_mcp],
    instructions=(
        "Given a therapeutic hypothesis, use the Paperclip MCP tools to find "
        "literature evidence for/against it. Extract any reported PGRN-Sortilin "
        "interaction site or hotspot residues. Output a summary with citations."
    ),
)


# ── 2. Structural modeling ───────────────────────────────────────────
# Tools implemented in workflows/tools/structure.py (config-driven:
# `structure_prediction` engine choice, `structure_quality.chains`).

structure_agent = Agent(
    name="structure_agent",
    model=LLM_MODEL,
    tools=[fetch_pdb_structure, predict_complex_structure, score_structure_quality],
    instructions=(
        "Try fetch_pdb_structure for the PGRN-Sortilin complex first. If no "
        "experimental structure exists, fall back to predict_complex_structure. "
        "Always score_structure_quality on the resulting model before proceeding."
    ),
)


# ── 3. Interface mapping ─────────────────────────────────────────────
# Tool implemented in workflows/tools/interface.py (config-driven:
# `interface.ligand_contact_cutoff_angstrom`, `interface.exclude_resnames`).

interface_agent = Agent(
    name="interface_agent",
    model=LLM_MODEL,
    tools=[map_interface_pocket],
    instructions=(
        "Use map_interface_pocket to define the druggable pocket at the "
        "PGRN-Sortilin PPI interface. Note that PPI interfaces are often flat — "
        "flag if no clear pocket is found."
    ),
)


# ── 4. Ligand mining ──────────────────────────────────────────────────
# Tool implemented in workflows/tools/ligands.py (config-driven:
# `target.known_ligand_names`, `ligand_mining.pubchem_query_field`).

ligand_mining_agent = Agent(
    name="ligand_mining_agent",
    model=LLM_MODEL,
    tools=[search_known_ligands],
    instructions=(
        "Use search_known_ligands to compile known tool compounds/chemical "
        "probes for PGRN or Sortilin. These become pharmacophore seeds and "
        "positive controls for screening.\n\n"
        "Generic paper compound numbering (e.g. 'Compound 17') is ambiguous in "
        "PubChem's name index and can resolve to an unrelated paper's "
        "same-numbered compound — sanity-check resolved hits (molecular weight, "
        "scaffold) against literature_agent's findings before trusting them as "
        "positive controls."
    ),
)


# ── 5. Library + docking ─────────────────────────────────────────────

@tool
def assemble_screening_library(known_ligands: dict) -> dict:
    """Assemble a screening library with positive controls and decoys."""
    raise NotImplementedError("TODO: compile compound library + decoys")


@tool
def dock_library(library: dict, pocket: dict) -> dict:
    """Dock a compound library against a binding pocket."""
    raise NotImplementedError("TODO: call vina via proto-tools")


@tool
def validate_positive_controls(docking_results: dict) -> dict:
    """Check whether known positive controls recovered their expected pose/rank."""
    raise NotImplementedError("TODO: docking self-validation check")


screening_agent = Agent(
    name="screening_agent",
    model=LLM_MODEL,
    tools=[assemble_screening_library, dock_library, validate_positive_controls],
    instructions=(
        "Assemble the screening library, then dock_library against the interface "
        "pocket. Always validate_positive_controls afterward — if controls fail "
        "to recover their expected pose/rank, re-assemble the library and re-dock "
        "before reporting results."
    ),
)


# ── 6. Hit triage ─────────────────────────────────────────────────────

@tool
def filter_hits(docking_results: dict) -> dict:
    """Filter docking hits by score, pose plausibility, PAINS, and diversity."""
    raise NotImplementedError("TODO: hit filtering/clustering")


triage_agent = Agent(
    name="triage_agent",
    model=LLM_MODEL,
    tools=[filter_hits],
    instructions=(
        "Use filter_hits to remove PAINS/assay-interference compounds and "
        "cluster remaining hits for scaffold diversity, keeping the strongest "
        "representative per cluster."
    ),
)


# ── 7. ADMET profiling ────────────────────────────────────────────────

@tool
def predict_admet(compounds: dict) -> dict:
    """Predict ADMET properties for a set of compounds."""
    raise NotImplementedError("TODO: ADMET prediction")


admet_agent = Agent(
    name="admet_agent",
    model=LLM_MODEL,
    tools=[predict_admet],
    instructions=(
        "Use predict_admet on the triaged hits. Deprioritize compounds with "
        "poor predicted PK/tox liability."
    ),
)


# ── 8. Prioritization ─────────────────────────────────────────────────

@tool
def rank_and_handoff(compounds: dict) -> dict:
    """Rank the final shortlist and hand off to experimental validation."""
    raise NotImplementedError("TODO: rank + push to Benchling")


prioritization_agent = Agent(
    name="prioritization_agent",
    model=LLM_MODEL,
    tools=[rank_and_handoff],
    instructions=(
        "Combine docking score, ADMET, and diversity into a single ranked "
        "shortlist. Use rank_and_handoff to record the shortlist for "
        "experimental validation (tracked in Benchling).\n\n"
        "Note: the experimental hit/no-hit feedback loop back into screening "
        "(see spec/therapeutic-hypothesis.md) is out of scope for this "
        "barebone pipeline."
    ),
)


# ── Pipeline ────────────────────────────────────────────────────────────

pipeline = (
    literature_agent
    >> structure_agent
    >> interface_agent
    >> ligand_mining_agent
    >> screening_agent
    >> triage_agent
    >> admet_agent
    >> prioritization_agent
)


if __name__ == "__main__":
    with AgentRuntime() as runtime:
        result = runtime.run(
            pipeline,
            f"Therapeutic hypothesis: inhibiting the {CONFIG.target.gene_a}-{CONFIG.target.gene_b} complex.",
        )
        result.print_result()

        # Production pattern:
        # runtime.deploy(pipeline)   # once, during CI/CD
        # runtime.serve(pipeline)    # long-lived worker process
