# Available tools — re:AGENT hackathon

From the slides in [`resources/`](resources/):
[Proto](resources/proto-installation-instructions.png),
[Biohub](resources/biohub-platform-api.png),
[Benchling](resources/benchling-developer-platform.png),
[BenchFlow](resources/benchflow-setup.png),
[Sundial](resources/sundial-writing-copilot.png).

## Platforms

- **Proto** — open-source infrastructure layer for generative biology
  - `proto-tools` — ready-to-run computational biology models
  - `proto-language` — optimization layer for building design loops
- **Modal** — remote compute for running the models
- **Biohub Platform** — hosted ESM models and APIs
- **Benchling** — R&D data platform, hackathon tenant with an antibody discovery dataset
  - Benchling MCP server
  - Benchling Apps + API
  - Benchling AI
- **BenchFlow** — environment / benchmark framework
- **Sundial** — scientific writing copilot
  - Sundial Desktop
  - Sundial web editor

## Capabilities

### Proto
- Built by Laboratory of Evolutionary Design, Arc Institute
- Four primitives: sequences, generators, constraints, optimizers
- `proto-language`: constraint-based sequence design (DNA/RNA/protein); propose–score–refine loop
- `proto-tools`: single Python interface over 17 tool categories, 60+ tools (full list below)
- Source: [proto-tools](https://github.com/evo-design/proto-tools) · [proto-language](https://github.com/evo-design/proto-language) · [Arc Institute announcement](https://arcinstitute.org/news/proto)

### Modal
- Serverless CPU/GPU compute, per-second billing
- No infra reservation/management; containers start in ~1s
- Single-GPU to multi-node runs (up to 128 B200s, 3200 Gbps InfiniBand) from one code file
- Functions, images, secrets, schedules, GPU requirements, endpoints defined in Python
- Source: [modal.com](https://modal.com/)

### Biohub Platform
- Hosts ESMC (protein language model), ESMFold2, ESM Atlas
- ESMFold2: converts ESMC sequence representations into 3D structure; accuracy and speed-optimized variants; open weights on Hugging Face (MIT)
- ESM Atlas: 6.8B predicted protein structures/annotations, 1.1B with high-res ESMFold2 structures; free on AWS S3
- Guardrails restrict controlled pathogen/toxin sequences and keywords
- Access: install `esm` Python package + API key
- Source: [biohub.ai](https://biohub.ai/) · [world model of protein biology](https://biohub.org/news/world-model-of-protein-biology/)

### Benchling
- AI Connectors: MCP-based, connects scientific data to external AI tools
- Dual MCP role: client (connects Benchling AI to external servers — Notion, SharePoint, Snowflake, Elicit) and server (exposes Benchling experiments/entities/results/relationships to approved AI assistants)
- Governance: same auth/permission rules as Benchling itself; no external data storage or model training on customer data
- Python SDK available for direct API access
- Source: [Benchling Developer Platform](https://www.benchling.com/developer-platform) · [AI Connectors announcement](https://www.benchling.com/blog/benchling-launches-ai-connectors-to-power-data-ecosystem)

### BenchFlow
- Universal environment/benchmark framework — "a benchmark is just a frozen environment"
- Three-layer routing: native frameworks, format translation, custom harnesses
- Compatible agents: Claude Code, Codex, Gemini CLI, OpenCode, OpenHands, custom agents
- Evaluation modes: single-agent, multi-agent (coder+reviewer), multi-round; loop strategies (verify-retry, self-review)
- Sandboxes: Docker, Apple Container, Daytona (parallel cloud), Modal (serverless), AgentCore (AWS)
- Outputs training-ready data: Verifiers/ORS reward format, ATIF, ADP
- Task format: `task.md` (YAML config + markdown prompt); CLI for scaffolding/validation/migration
- Requires Python 3.12+; no API key needed with subscription auth (`claude auth login`, Codex)
- Source: [benchflow-ai/benchflow](https://github.com/benchflow-ai/benchflow)

### Sundial
- Built by a human-agent collaboration research lab (San Francisco)
- "The Editor" — Markdown/LaTeX editor with AI delegation, per-edit attribution, approve/reject changes
- "Sun" — local-first log of all human + agent actions for reconstructing collaborative work
- Desktop app drives locally installed Claude Code or Codex; web editor is template-based (bioRxiv, PLOS, NeurIPS, ICML)
- Source: [sundial.md](https://sundial.md)

## Models in `proto-tools`

| Category | Tools |
| --- | --- |
| Binder design | bindcraft, freebindcraft, germinal |
| Causal models | evo1, evo2, progen2, progen3 |
| Database retrieval | alphafold_db, alphamissense_db, ccd_lookup, ensembl, interproscan, ncbi, pdb, pubchem, sequence_fetch, uniprot |
| Gene annotation | crispr_tracr_rna, meme, minced, miranda, promoter_calculator, pyhmmer |
| Inverse folding | esm_if1, fampnn, ligandmpnn, proteinmpnn |
| Masked models | ablang, codonfm, esm2, esm3, esmc |
| Molecular docking | vina |
| Mutagenesis | random_nucleotide, random_protein |
| ORF prediction | orfipy, prodigal |
| RNA splicing | pangolin, splice_transformer, spliceai |
| Sequence alignment | blast, mafft, mmseqs2 |
| Sequence scoring | alphagenome, borzoi, deeppbs_specificity, enformer, malinois, na_mpnn_specificity, parade, primer3, puffin, segmasker |
| Structure alignment | foldmason, foldseek, pymol_rmsd, tmalign, usalign |
| Structure design | rfdiffusion3 |
| Structure dynamics | bioemu |
| Structure prediction | alphafold2, alphafold3, boltz2, chai1, esmfold, esmfold2, opendde, protenix, rf3, viennarna, x3dna |
| Structure scoring | dssp, ipsae, metal3d, pdockq2, pyrosetta, structure_metrics |

## Models on Biohub Platform

- Binder design protocol
- ESMFold2
- ESMC SAE model
- ESM Atlas

## Data in the Benchling tenant

- Plasmids
- IgG
- scFv
- VHH
- Cell lines
- Assay results

## Claude Code integration

No Claude skill exists for any of these tools. The one exception is Benchling, which exposes an
MCP server (`https://hackathon.mcp.bnchdev.org/mcp`) that a Claude Code / Desktop MCP client can
connect to directly. Proto, Modal, Biohub, BenchFlow, and Sundial are plain SDKs/CLIs/APIs with no
Claude-side wrapper.
