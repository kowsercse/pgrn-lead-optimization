# target-dossier-agent

Hackathon project for **re:AGENT — End to End Agentic Science**, 15–16 Aug 2026.
Hosted by GXL at Fort Mason, San Francisco; co-hosts Arc Institute, Anthropic,
BenchFlow, future.bio and Biohub. **Track A: Co-scientist.**

## What we are building

A **target dossier agent**. Input: a protein target. Output: a graded answer to whether
that target is **tractable for structure-based small-molecule drug design** — with the
receptor, the training set and the validation set already chosen, or a stated reason not
to proceed.

**The agent performs no structure-based calculation.** No docking, no free-energy
methods, no molecular dynamics. It assesses tractability and hands a specification to
whoever has the compute. No Modal, no containers, no `vina`. The whole assessment is
retrieval plus deterministic cheminformatics, which is why it runs on a laptop.

Five fixed scouts bound to named sources run concurrently. Every claim is graded by how
it was established and has its citation independently resolved before use. Cross-source
joins produce findings no single database returns. The dossier then commits to an
assessment and runs five feasibility checks over the retrieved data — checks that can
contradict it and change the recommendation.

Sortilin (SORT1) is the worked case.

## Status — 15 Aug, 20:50

34 tests green. `pytest` from a fresh clone should pass with no network.

| Stage | State | Notes |
|---|---|---|
| 0 Foundation | **done** | store, schema, grade rules as CHECK constraints |
| 1 Retrieval | **in progress** | dispatch + required-scout rule done; `structures` scout done |
| 2 Verification | not started | resolver gate — the one gate PLAN.md marks non-negotiable |
| 3 Joins | not started | |
| 4 Answers and render | not started | |
| 5 Feasibility and loop | not started | carries judging criterion 1 |
| 6 Audit and cold run | not started | agnosticism grep already passes |

### Free to pick up

The four remaining scouts are independent of each other — take one, branch from `main`,
open a PR. Each follows the pattern in `dossier/scouts/structures.py`: **pure parsing
tested offline, network only in the `fetch_*` adapters.**

| Scout | Source | Named check it must implement |
|---|---|---|
| `bioactivity` | ChEMBL MCP, PubChem, BindingDB | report **distinct compounds**, never activity records — they differ by an order of magnitude |
| `patents` | PubChem AIDs, patent depositions | query PubChem *and* ChEMBL; patent sets are often in one and not the other |
| `assays` | assay descriptions | flag qHTS; count records carrying a real IC50 |
| `literature` | Paperclip, PubMed MCP | search pathway and phenotypic aliases, not only the direct target |

Two rules that are not negotiable, both enforced by tests or the Stage 6 audit:

1. **No target-specific identifier anywhere under `dossier/`.** No PDB ID, ChEMBL
   accession, PubChem AID, compound name or target symbol. They are scout *outputs*.
   Expected values live in `tests/fixtures/`. Check with:
   `grep -rE '6X48|5MRI|UP4|CHEMBL3091|CHEMBL4680051|2202264|norleucine|SORT1|CTSL' dossier/`
2. **Write the test first.** Every module here was built that way, and it caught a real
   bug — see the `feat(dispatch)` commit message.

## Docs

- [`docs/SPEC.md`](docs/SPEC.md) — **build contract.** Parameters, schema, signatures,
  thresholds, MUST NOT list, definition of done. No prose
- [`docs/ANALYSIS.md`](docs/ANALYSIS.md) — seven defects found in the spec, three
  blocking. One check as written rejects the reference target
- [`docs/DESIGN.md`](docs/DESIGN.md) — resolutions to all seven, with the revised
  schedule and the exact 12 edits to apply to `SPEC.md`
- [`docs/PLAN.md`](docs/PLAN.md) — **start here to build.** Seven stages, each with an
  exit gate, plus the degradation ladder for when time runs short
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — diagrams, data model, repo layout
- [`docs/roadmap.md`](docs/roadmap.md) — architecture, schedule, judging alignment, risks
- [`docs/roadmap.html`](docs/roadmap.html) — same content, standalone page with diagrams
  and charts as inline SVG. Open it directly in a browser; no server or assets needed
- [`docs/tools.md`](docs/tools.md) — sponsor platforms and what they can do
- [`docs/setup.md`](docs/setup.md) — step-by-step install instructions per tool
- [`docs/resources/`](docs/resources/) — original sponsor slides

## Requirements

**Python 3.12**, not 3.13+. Several chemistry packages have no 3.13 wheels.

> `pyproject.toml` still declares `requires-python = ">=3.13"` and needs changing to
> `"==3.12.*"` before the first build step.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install rdkit requests
```

RDKit is the only scientific dependency the agent itself needs — the feasibility checks
are InChIKey set operations, Murcko scaffolds, and descriptor arithmetic.

ChEMBL, PubMed and bioRxiv are already available as MCP servers. Paperclip backs the
literature scout and the resolver's fetch layer; if `paperclip --version` fails, it needs
its own venv, since Homebrew's Python is externally managed.

<details>
<summary>Optional: downstream design loop, not part of the agent</summary>

If a dossier returns a go decision, this is the loop it hands off to — measured at 12.4 s
end to end with no GPU and no network at runtime. It needs its own virtual environment:
ADMET-AI requires `rdkit>=2025.9` while PyTDC pins `rdkit<2024.3.1`, and they cannot
coexist.

```bash
python3.12 -m venv .venv-design && source .venv-design/bin/activate
pip install rdkit crem admet-ai mol_ga
curl -O https://zenodo.org/records/16909329/files/chembl22_sa2_hac12.db.gz
gunzip chembl22_sa2_hac12.db.gz
```
</details>
