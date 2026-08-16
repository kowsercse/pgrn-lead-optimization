# Build plan — seven stages

Executable plan derived from [`DESIGN.md`](DESIGN.md). Supersedes the build-step list in
`SPEC.md` §BUILD ORDER and §SCHEDULE. Diagrams, data model and repo layout are in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

**665 minutes of wall time, exactly filled.** 645 min of build steps plus a 20 min cold
run, against 510 min Saturday (17:30–02:00) and 155 min Sunday (07:00–09:35). **Zero
slack.** Overruns come out of the freeze block or out of the degradation ladder at the end
of this document — never out of a stage gate.

Sleep is 5h00m (02:00–07:00), 15 minutes less than the original schedule. That reduction
is the only sleep cost in the plan and it is deliberate; the alternative was cutting a
stage gate.

## Stages

| # | Stage | Window | Min | Exit gate |
|---|---|---|---:|---|
| 0 | Foundation | Sat 17:30–18:30 | 60 | Schema rejects a malformed grade |
| 1 | Retrieval | Sat 18:30–20:50 | 140 | Five scouts return; killing one yields a gap |
| 2 | Verification | Sat 20:50–22:50 | 120 | Fabricated accession is demoted and flagged |
| 3 | Joins | Sat 22:50–00:20 | 90 | Pooling merges sources without double-counting |
| 4 | Answers and render | Sun 00:20–02:00 | 100 | Dossier v1 opens with no network |
| — | *Sleep* | Sun 02:00–07:00 | 300 | — |
| 5 | Feasibility and loop | Sun 07:00–09:05 | 125 | All four outcomes reachable |
| 6 | Audit and cold run | Sun 09:05–09:35 | 30 | Grep clean; CTSL completes |
| — | Freeze, rehearse | Sun 09:35–10:15 | 40 | Two timed run-throughs |
| — | Submit | Sun 10:15–10:45 | 30 | — |

**No stage begins before the previous stage's gate passes.** A failed gate escalates to
the degradation ladder, not to "carry on and fix it later."

---

## Stage 0 — Foundation

**Window** Sat 17:30–18:30 · 60 min · Applies D5

### Tasks

1. **Environment** (20 min)
   ```bash
   # edit pyproject.toml: requires-python = "==3.12.*"
   python3.12 -m venv .venv && source .venv/bin/activate
   pip install -U pip && pip install -e . rdkit requests
   python -c "import sys; assert sys.version_info[:2]==(3,12), sys.version"
   paperclip --version   # expect >= 0.7.36
   ```

2. **Schema** (25 min) — `dossier/store.py`, all eight tables, with D5's three constraints:
   ```sql
   CHECK (grade NOT IN ('verified','documented') OR source_url IS NOT NULL)
   CHECK (grade <> 'measured'   OR output_hash IS NOT NULL)
   CHECK (grade <> 'unverified' OR reason      IS NOT NULL)
   ```
   `record` gains `reason TEXT`.

3. **Typed accessors** (15 min) — `Record` dataclass, `insert_records`, `records_for`.

### Exit gate

```python
insert(Record(grade="verified",   source_url=None))   # must raise
insert(Record(grade="measured",   output_hash=None))  # must raise
insert(Record(grade="unverified", reason=None))       # must raise
insert(Record(grade="inferred"))                      # must succeed
records_for(conn, run_id="A")                         # must not return run B's rows
```

**Fallback** None. This stage is load-bearing for every later one.

---

## Stage 1 — Retrieval

**Window** Sat 18:30–20:50 · 140 min · Applies D7

### Tasks

1. **Scout protocol** (25 min) — `dossier/scouts/base.py`. Brief template parameterised on
   `target` alone. No spawn tool. No expected accession named anywhere in a brief.

2. **`structures`** (35 min) — build one scout completely before the rest; the contract will
   change once and it should change at n=1. Returns PDB IDs, resolution, method, ligand HET
   codes. Counts drug-like-ligand entries separately from total.

3. **Remaining four scouts** (50 min) — `bioactivity`, `patents`, `assays`, `literature`.
   Each carries its named check from `SPEC.md` §SCOUTS.

4. **Dispatch and deadlines** (20 min) — `dossier/dispatch.py`, concurrent,
   `SCOUT_DEADLINE_S = 180`, gap row on expiry, run continues.

5. **Required-scout rule** (10 min) — D7. `structures` and `bioactivity` required;
   `patents`, `assays`, `literature` contributing. If a required scout gaps, set verdict
   `insufficient retrieval` and mark feasibility as skipped.

### Exit gate

- All five return inside 180 s against the SORT1 fixture
- `structures` yields both 6X48 and 5MRI; drug-like count differs from total count
- `bioactivity` reports distinct compounds, not activity records
- Set one scout's deadline to 1 s → gap row written, run still completes
- Force `bioactivity` to gap → verdict is `insufficient retrieval`, feasibility skipped

**Fallback** If at 20:20 fewer than four scouts work, ship three (`structures`,
`bioactivity`, `literature`) and gap the rest. The dossier degrades honestly.

---

## Stage 2 — Verification

**Window** Sat 20:50–22:50 · 120 min · Applies D6

### Tasks

1. **Fetchers** (55 min) — PDB, ChEMBL, PubChem AID, DOI, PMID, patent number, shell
   command. Paperclip supplies literature spans.

2. **Span confirmation** (25 min) — fetch `source_id`, confirm `record.value` appears in the
   fetched document, demote to `inferred` and set `demoted_from` on failure.

3. **Budget and cache** (40 min) — D6.
   ```
   RESOLVER_CONCURRENCY = 8
   RESOLVER_BUDGET_S    = 300
   ```
   Cache by `source_id`. Resolve in frequency order, most-cited first. On exhaustion leave
   the scout grade, set `resolution.note = "budget exhausted"`, add one gap row with the
   unresolved count.

### Exit gate

- A true accession stays `verified`
- A fabricated accession demotes to `inferred` and is flagged in the dossier
- A run of 300 synthetic records completes inside `RESOLVER_BUDGET_S`
- Cache hit rate reported and non-zero on the SORT1 fixture

**This gate is not negotiable.** Every grade above `inferred` is meaningless without it.
If it fails, stop and fix rather than proceeding.

---

## Stage 3 — Joins

**Window** Sat 22:50–00:20 · 90 min · Applies D8

### Tasks

1. **`pool_compounds`** (25 min) — D8. Merge every source on canonical identity.
   ```python
   def pool_compounds(*sources: Iterable[str]) -> set[str]
   ```
   All measured molecules are evidence of chemical matter wherever they were deposited,
   so they are pooled rather than partitioned. Canonicalisation stops the same molecule,
   reported by two databases under different SMILES, from being counted twice.

2. **`scaffold_match`** (20 min) — RDKit substructure, patent core against co-crystal ligand.

3. **`alias_resolution`** (25 min) — pathway and phenotypic identifiers, not only the
   molecular target.

4. **`record_vs_compound`** (20 min) — reconcile activity-record counts against distinct
   compounds.

Each join writes one `join_result` row.

### Exit gate

- pooling the public set with the patent set yields more than either alone, and fewer than their sum
- `scaffold_match` true for the SORT1 core/UP4 pair, false for an unrelated ligand
- Four `join_result` rows written per run

**Fallback** `alias_resolution` and `record_vs_compound` are cuttable; the first two joins
carry the demo.

---

## Stage 4 — Answers and render

**Window** Sun 00:20–02:00 · 100 min · Applies D2

### Tasks

1. **Answers** (35 min) — five questions, each **one committed choice with a reason**, never
   a candidate list.

2. **Replication** (15 min) — D2. `REPLICATES = 2`, **answer 1 only**. Answer 4 is a
   date lookup; replicating it measures nothing.

3. **Renderer** (50 min) — six sections in order: answers, contradictions, gap list,
   recommendation and failure condition, hand-off spec, cost line. Gap section renders when
   empty. Every answer expands to `query`, `output_hash`, `source_date`, `retrieved_at`.
   Reuse `docs/roadmap.css`, and the figure-inlining and self-containment pattern in
   `docs/build_roadmap.py`.

### Exit gate

- `dossier_v1.html` opens with no network
- Every claim shows a grade; every `verified` claim shows a resolvable identifier
- Gap section present when empty
- Cost line reports tokens, tool calls, wall clock
- Answer 1 carries `agree_n`/`agree_of`

**Fallback** Drop replication entirely (−15 min) before dropping any renderer section. The
gap list and the expand-a-claim interaction are the inspectability criterion.

---

## Stage 5 — Feasibility and loop

**Window** Sun 07:00–09:05 · 125 min · Applies D1, D3

### Tasks

1. **Feasibility** (45 min) — D1 thresholds. `Feasibility` gains `n_distinct_inchikeys` and
   `dominant_scaffold_n`; `n_scaffolds` is deleted.
   ```
   n_analogs            >= 20
   n_distinct_inchikeys == n_analogs
   dominant_scaffold_n  >= 15
   activity_span_log    >= 2.0
   ligand_mw            >= 250
   ligand_heavy         >= 15
   best_resolution      <= 2.5  (design) / <= 3.5 (triage)
   ```
   One `check_result` row per check.

2. **Branch table** (35 min) — D3. Seven cases over the pure `next_step(f, a)`, asserting
   every one of the four outcomes reachable. Deterministic, offline, under one second.

3. **Loop and dossier v2** (45 min) — regenerate with the revised recommendation and the
   hand-off spec: receptor, resolution, method, site origin, train accession, holdout
   accession, fallback receptor, resolution qualifier.

### Exit gate

- SORT1 fixture: `dominant_scaffold_n` 106, `activity_span_log` ≥ 2
- **SORT1 produces `triage_only`, not `not_ready`** — this is defect 1's regression test
- All four outcomes assert reachable
- Dossier v2 differs from v1 in recommendation text on at least one constructed case

**This stage carries judging criterion 1.** Protect it. If Stage 4 overruns, cut from
Stage 4, not from here.

---

## Stage 6 — Audit and cold run

**Window** Sun 09:05–09:35 · 30 min

### Tasks

1. **Agnosticism audit** (10 min)
   ```bash
   grep -rE '6X48|5MRI|UP4|CHEMBL3091|CHEMBL4680051|2202264|norleucine|SORT1|CTSL' dossier/
   # must return nothing
   ```

2. **Cold run** (20 min) — CTSL, no fixture. Assert only: run completes, every answer
   graded, gap list renders, recommendation produced. **No branch assertion.** A negative
   recommendation is a pass.

### Exit gate

- Grep returns nothing
- CTSL run completes and its dossier is kept, whatever it says

---

## Degradation ladder

Slack is zero. Cut in this order, and record what was cut in the dossier's gap section.

| Order | Cut | Saves | Cost |
|---:|---|---:|---|
| 1 | `record_vs_compound` join | 20 min | One named check unimplemented |
| 2 | Replication entirely | 15 min | No agreement statistic; answer 1 unreplicated |
| 3 | `alias_resolution` join | 25 min | Pathway-filed series stay invisible |
| 4 | `assays` scout | 15 min | qHTS inflation unflagged; gap row instead |
| 5 | `literature` scout | 20 min | No mechanism context; gap row instead |
| 6 | Contradictions section | 15 min | Cross-scout conflicts unreported |

**Never cut:** the resolver gate, the feasibility checks, the branch table, the gap
section, or the agnosticism audit. Those four carry the three judging criteria and the
target-agnosticism claim.

---

## Verification summary

Run at every stage boundary:

```bash
pytest tests/ -x -q                                   # all stages
python -m dossier.cli run --target SORT1 --dry-run     # stages 1+
grep -rE '6X48|5MRI|UP4|CHEMBL3091|CHEMBL4680051|2202264|norleucine|SORT1|CTSL' dossier/
open dossier_v1.html                                   # stages 4+, with wifi off
```

## Artifacts by stage

| Stage | Produces |
|---|---|
| 0 | `dossier.db` with eight tables and three CHECK constraints |
| 1 | Records from five scouts; gap rows for any that timed out |
| 2 | `resolution` rows; at least one demotion on the fabricated-accession test |
| 3 | Four `join_result` rows |
| 4 | `dossier_v1.html` |
| 5 | `check_result` rows; `dossier_v2.html`; branch-table test output |
| 6 | Clean grep; `dossier_ctsl.html` |

## Open items

| Item | Owner | Blocks |
|---|---|---|
| Repo write access — account has pull-only | user | first commit |
| Confirm 10:45 submission against acceptance email | user | Stage 6 timing |
| Apply the 12 `SPEC.md` edits listed in `DESIGN.md` | unassigned | Stage 0 |
