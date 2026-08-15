"""Barebone Conductor agent pipeline for the PGRN-Sortilin screening flow.

Implements the "Computational biologist review" stages from
spec/therapeutic-hypothesis.md as a sequential Conductor agent pipeline.
See spec/conductor-workflow-spec.md for scope.

Tool bodies are stubs (raise NotImplementedError) — only the agent
topology (names, instructions, tool wiring, pipeline order) is implemented.
Paperclip and Biohub are wired as MCP tools instead (see
spec/conductor-workflow-spec.md, "MCP tool integration") — the Biohub MCP
server itself is not yet built.

Requirements:
    - Conductor server reachable via CONDUCTOR_SERVER_URL
    - CONDUCTOR_AGENT_LLM_MODEL set (defaults to anthropic/claude-sonnet-4-6)
    - PAPERCLIP_API_KEY set (see .env.example) for the Paperclip MCP server
    - BIOHUB_API_KEY set (see .env.example) for the Biohub MCP server
"""

import os

from conductor.ai.agents import Agent, AgentRuntime, mcp_tool, tool

LLM_MODEL = os.environ.get("CONDUCTOR_AGENT_LLM_MODEL", "anthropic/claude-sonnet-4-6")

# Biohub has no hosted MCP server upstream (REST + `esm` SDK only) — this
# assumes a local MCP server wrapping the `esm` SDK, not yet built.
BIOHUB_MCP_URL = os.environ.get("BIOHUB_MCP_URL", "http://localhost:8090/mcp")


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

@tool
def fetch_pdb_structure(pdb_id: str) -> dict:
    """Fetch an experimental structure from PDB."""
    raise NotImplementedError("TODO: call proto-tools pdb database retrieval")


biohub_mcp = mcp_tool(
    server_url=BIOHUB_MCP_URL,
    name="biohub_mcp",
    description="Biohub Platform ESM models (ESMFold2 structure prediction, ESMC, ESM Atlas) via MCP.",
    headers={"Authorization": "Bearer ${BIOHUB_API_KEY}"},
    credentials=["BIOHUB_API_KEY"],
)


@tool
def score_structure_quality(structure: dict) -> dict:
    """Score a structure/complex model's quality."""
    raise NotImplementedError("TODO: call ipsae / pdockq2 / dssp via proto-tools")


structure_agent = Agent(
    name="structure_agent",
    model=LLM_MODEL,
    tools=[fetch_pdb_structure, biohub_mcp, score_structure_quality],
    instructions=(
        "Try fetch_pdb_structure for the PGRN-Sortilin complex first. If no "
        "experimental structure exists, fall back to the Biohub MCP tools to "
        "predict one. Always score_structure_quality on the resulting model "
        "before proceeding."
    ),
)


# ── 3. Interface mapping ─────────────────────────────────────────────

@tool
def map_interface_pocket(structure: dict) -> dict:
    """Identify PPI interface residues and the druggable pocket."""
    raise NotImplementedError("TODO: interface/pocket detection")


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

@tool
def search_known_ligands(target: str) -> dict:
    """Find known tool compounds/chemical probes binding the target."""
    raise NotImplementedError("TODO: query literature + PubChem/ChEMBL via proto-tools")


ligand_mining_agent = Agent(
    name="ligand_mining_agent",
    model=LLM_MODEL,
    tools=[search_known_ligands],
    instructions=(
        "Use search_known_ligands to compile known tool compounds/chemical "
        "probes for PGRN or Sortilin. These become pharmacophore seeds and "
        "positive controls for screening."
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
            "Therapeutic hypothesis: inhibiting the PGRN-Sortilin complex.",
        )
        result.print_result()

        # Production pattern:
        # runtime.deploy(pipeline)   # once, during CI/CD
        # runtime.serve(pipeline)    # long-lived worker process
