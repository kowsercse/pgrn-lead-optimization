# Design — resolutions to the seven spec defects

Companion to [`ANALYSIS.md`](ANALYSIS.md), which identified the defects, and
[`SPEC.md`](SPEC.md), which this document amends. Each decision states the problem, the
options considered, the decision, and the resulting contract.

**One decision supersedes the analysis.** D1 rejects the fix `ANALYSIS.md` proposed; the
reason is given there.

---

## D1 — Series quality

**Problem.** `n_scaffolds >= 2` rejects a congeneric series, which is the property
question 3 exists to find. The SORT1 fixture — 106 analogs on one core — fails the spec's
own logic.

**Options.**

| | Approach | Verdict |
|---|---|---|
| A | Scaffold-share band, `0.50 <= max_scaffold_share <= 0.95` | **Rejected** |
| B | Drop scaffold logic; rely on `n_analogs` and distinct InChIKeys alone | Rejected — cannot distinguish 30 analogs on one core from 30 unrelated singletons |
| C | Measure series depth on the dominant scaffold | **Adopted** |

**Option A was the analysis's recommendation and it is wrong.** Its upper bound of 0.95
rejects a *perfect* congeneric series. If all 106 SORT1 compounds share one Murcko
scaffold, `max_scaffold_share` = 1.00, which exceeds the bound — the same failure as
`n_scaffolds >= 2`, arrived at differently. The upper bound was intended to catch "one
compound repeated," but that failure mode is a duplication problem, not a scaffold
problem, and scaffold share is the wrong instrument for it.

**Decision.** Separate the two concerns. Measure depth on the dominant scaffold; catch
duplicates by identity.

```
n_analogs            >= 20    # enough matter to reason over
n_distinct_inchikeys == n_analogs   # no duplicates masquerading as a series
dominant_scaffold_n  >= 15    # enough analogs on ONE core to support SAR
activity_span_log    >= 2.0   # unchanged
```

`dominant_scaffold_n` = count of analogs bearing the most common Murcko scaffold.

**Behaviour against the failure modes:**

| Input | `n_distinct` | `dominant_scaffold_n` | Result |
|---|---|---|---|
| 106 analogs, one core (SORT1) | 106 | 106 | **pass** |
| 30 unrelated singletons | 30 | 1–2 | fail — no SAR series |
| 1 compound, 30 duplicate records | 1 | 1 | fail — duplication |
| 40 analogs across 3 cores, 18 on largest | 40 | 18 | pass |

**Consequence.** `n_scaffolds` is deleted from THRESHOLDS, FEASIBILITY and LOOP.
`Feasibility` gains `n_distinct_inchikeys` and `dominant_scaffold_n`. The threshold
`Congeneric series: >= 80% share one Murcko scaffold` becomes descriptive only — reported
in the dossier, never used as a gate.

---

## D2 — Schedule

**Problem.** Steps sum to 680 min against 645 min of capacity. Two blocks under-provisioned
by 50 and 65 min; step 9 unscheduled.

**Options.**

| | Approach | Verdict |
|---|---|---|
| A | Shorten sleep to 4h25m | Rejected — sleep was scheduled deliberately; a demo delivered on four hours is worse than one feature lighter |
| B | Reduce step budgets to fit | Rejected — the estimates are the estimates; rewriting them to fit the calendar is how a plan lies |
| C | Reallocate slack, then cut the weakest scope item | **Adopted** |

**Decision.** Two moves, together closing exactly 35 min.

1. **Reallocate the second-target block.** It is budgeted 90 min for what is a pipeline
   execution, not construction. A cold run needs ~20 min. 70 min returns to the pool.
2. **Reduce replication scope.** `REPLICATES` 3 → 2, and replicate answer 1 only, not
   answers 1 and 4. Saves 35 min from step 6 (135 → 100). Answer 4's stability is already
   covered — `holdout_overlap` is a deterministic set operation, so re-running it three
   times measures nothing. Replicating it was a category error.

**Revised schedule.**

| Time | Duration | Steps |
|---|---:|---|
| Sat 17:30–18:30 | 60 | 0 env, 1 store |
| Sat 18:30–20:50 | 140 | 2 scout contract + `structures`, 3 remaining scouts + dispatch |
| Sat 20:50–22:50 | 120 | 4 resolver |
| Sat 22:50–00:20 | 90 | 5 joins |
| Sun 00:20–02:00 | 100 | 6 answers, replicate, render |
| Sun 02:00–07:00 | 300 | sleep |
| Sun 07:00–09:05 | 125 | 7 feasibility, 8 loop |
| Sun 09:05–09:15 | 10 | 9 agnosticism audit |
| Sun 09:15–09:35 | 20 | cold run, CTSL |
| Sun 09:35–10:15 | 40 | freeze, rehearse twice |
| Sun 10:15–10:45 | 30 | submit |

Build steps total 645 min; the cold run adds 20 min, for 665 min of wall time against
510 min Saturday (17:30–02:00) and 155 min Sunday (07:00–09:35). Sleep is 5h00m —
**15 minutes less than the original schedule**, which is the plan's only sleep cost.
**Zero slack** — any overrun comes out of the freeze block, which is the correct place
for it to come from.

---

## D3 — Branch coverage

**Problem.** The decorative-loop test compares two real targets. If both pass, the spec
concludes the loop is decorative, which may be false.

**Decision.** Split by purpose. Branch reachability is a unit test over a pure function;
generalisation is an integration run with no branch assertion.

`next_step` is already pure — it takes `Feasibility` and `Answers` and returns a
`Proposal`. Make it table-driven:

```python
CASES = [
    # (overlap, n_analogs, n_distinct, dominant_n, span, mw, heavy, resolution) -> branch
    ((1, 106, 106, 106, 3.1, 380, 27, 2.9), "scaffold_split"),
    ((0,  12,  12,  12, 3.1, 380, 27, 2.9), "not_ready"),
    ((0, 106, 106,   4, 3.1, 380, 27, 2.9), "not_ready"),
    ((0, 106, 106, 106, 0.8, 380, 27, 2.9), "not_ready"),
    ((0, 106, 106, 106, 3.1, 380, 27, 4.2), "no_structure"),
    ((0, 106, 106, 106, 3.1, 380, 27, 2.9), "triage_only"),
    ((0, 106, 106, 106, 3.1, 380, 27, 1.9), "proceed"),
]
```

Deterministic, offline, runs in under a second. Every branch asserted reachable.

**The cold run makes no branch assertion.** CTSL asserts only: run completes, every answer
graded, gap list renders, a recommendation exists. A negative recommendation is a pass.

**Consequence.** `LOOP` loses "if both targets give the same recommendation, report the
loop as decorative." Only the branch test may conclude anything about branch logic. The
demo shows the constructed contrast, since it is guaranteed to differ; the cold run
demonstrates generalisation.

---

## D4 — Disjointness contract

**Problem.** `set_difference(train, holdout)` read literally returns `train \ holdout`
(≈172 for SORT1), not the 106 the verify step expects. `holdout_overlap` is a third
quantity the signature never returns.

**Decision.** One function returning both quantities, named for what it decides.

```python
@dataclass(frozen=True)
class Disjointness:
    novel: set[str]     # holdout \ train — members absent from training
    overlap: set[str]   # train ∩ holdout — members present in both

def holdout_disjointness(train: Iterable[str], holdout: Iterable[str]) -> Disjointness
```

Both operands normalised to InChIKey before comparison. `Feasibility.holdout_overlap`
becomes `len(d.overlap)`. Assertions become two independent statements:
`len(d.novel) == 106` and `len(d.overlap) == 0`.

**Consequence.** `set_difference` is removed from JOINS. Argument order can no longer be
read wrongly, because neither field's meaning depends on it.

---

## D5 — Schema completeness

**Problem.** `unverified requires reason` names a column that does not exist.
`measured requires output_hash` has no constraint while the verified/documented rule does.

**Decision.** Add the column; enforce every grade rule at the same level.

```sql
ALTER TABLE record ADD COLUMN reason TEXT;

CHECK (grade NOT IN ('verified','documented') OR source_url IS NOT NULL)
CHECK (grade <> 'measured'   OR output_hash IS NOT NULL)
CHECK (grade <> 'unverified' OR reason      IS NOT NULL)
```

**Rationale.** A grade rule enforced in prose is a rule that fails at review time; enforced
in the schema it fails at insert time, next to the code that got it wrong. The three rules
are the same kind of rule and should fail the same way.

---

## D6 — Resolver budget

**Problem.** `RESOLVER_TIMEOUT_S` bounds one fetch. Nothing bounds the count. Several
hundred records at a 30-second worst case exceeds step 4's entire budget.

**Decision.** Bound the stage, not only the call, and degrade explicitly.

```
RESOLVER_CONCURRENCY = 8
RESOLVER_BUDGET_S    = 300
```

- Cache by `source_id`. One PDB or ChEMBL accession is cited by many records; resolve once.
- Resolve in `source_id` frequency order — the most-cited identifiers first, so budget
  exhaustion costs the least-load-bearing claims.
- On exhaustion: leave the record at its scout-assigned grade, set
  `resolution.note = "budget exhausted"`, and add one gap row stating the unresolved count.

**Rationale.** Silently leaving records unresolved would make the grades meaningless
exactly as fabricated citations would. Stating the count keeps the gate honest under load.

---

## D7 — Minimum viable run

**Problem.** A run with `structures` and `bioactivity` both gapped satisfies every DONE
checkbox while containing no receptor and no compound counts.

**Decision.** Name the two scouts the verdict depends on.

- `structures` and `bioactivity` are **required**. `patents`, `assays` and `literature`
  are **contributing**.
- If a required scout gapped: emit the gap list, render answers from what returned, state
  the verdict **`insufficient retrieval`**, and **skip the feasibility checks** rather than
  computing them over absent data.
- `insufficient retrieval` is a legitimate terminal verdict, not an error.

**Rationale.** Computing `dominant_scaffold_n` over an empty series returns 0 and branches
to "not ready" — a confident wrong answer produced from missing data. That is the A-Lab
failure mode: a pipeline consuming its own broken analysis without noticing.

---

## D8 — Data splitting is not a tractability signal

**Problem.** The design used "is a clean held-out set available" as a feasibility check
and as a loop branch. It is neither.

The dossier answers one question: is this protein tractable for structure-based design.
Whether a *future* model could be cleanly validated is a planning detail for whoever
picks the work up. A target with 200 well-measured molecules and a 1.8 Å structure is an
excellent candidate whether or not the data partitions neatly.

Worse, partitioning actively harms the assessment. Every measured molecule is evidence
of chemical matter, so splitting them makes the target look thinner than it is.

Two further weaknesses in the original criterion. It split on *which database holds the
data* rather than on anything scientific — a curation accident. And that property is
unstable: ChEMBL ingests patent-derived data over releases, so "absent from ChEMBL"
silently expires.

**Options.**

| | Approach | Verdict |
|---|---|---|
| A | Keep the check, split on date rather than database | Rejected — still answers a question the dossier is not asking |
| B | Drop the check; pool all sources for the count | **Adopted** |
| C | Drop it entirely and report nothing about time | Rejected — recency is a real signal, just not this one |

**Decision.** Remove data splitting from the checks and from the loop. Pool every source
on canonical identity for the chemical-matter count. Report recency separately, and never
as a gate.

- `holdout_disjointness` is replaced by `pool_compounds(*sources)`, which merges sources
  and deduplicates on InChIKey. The same canonicalisation, serving the correct purpose:
  the same molecule reported by two databases must not be counted twice.
- `Feasibility.holdout_overlap` is deleted, taking the checks from five to four.
- The `scaffold_split` branch is deleted, taking the outcomes from five to four.
- `Feasibility.latest_year` is added, with `years_since_latest` and `dormant` — reported
  in the dossier, never consulted by `next_step`.
- Dossier question 4 changes from *"what can serve as a held-out validation set"* to
  *"is anyone still working on this target"*.

**Consequence.** The prospective-validation claim, one of the two headline claims the
project was built around, is withdrawn. It was evidence about our methodology, not about
the target, and it did not belong in the target's dossier.

**Risk accepted.** `DORMANT_YEARS = 10` is a judgement with no published basis, which is
exactly why it reports rather than gates.

---

## Vestigial rules

Three `MUST NOT` entries govern excluded tooling. Move to a note under EXCLUDED:
MSA `search_mode="local"`, `ccd-lookup`/`pubchem-fetch` for novel compounds, and
`BRICS.BRICSBuild` without `islice`.

**Keep** `Run pip install vina on arm64` in MUST NOT. It names a temptation someone may
act on under time pressure; the other three name tools nobody will reach for.

---

## Parameter delta

| Parameter | Before | After |
|---|---|---|
| `REPLICATES` | 3 | 2 |
| `RESOLVER_CONCURRENCY` | — | 8 |
| `RESOLVER_BUDGET_S` | — | 300 |

## Threshold delta

| Threshold | Before | After |
|---|---|---|
| `n_scaffolds` | >= 2 | **deleted** |
| `n_distinct_inchikeys` | — | `== n_analogs` |
| `dominant_scaffold_n` | — | >= 15 |
| Congeneric series 80% | gate | descriptive only |

## Schema delta

- `record.reason TEXT` added
- two `CHECK` constraints added
- `resolution.note` now carries `"budget exhausted"`

## Interface delta

- `set_difference` removed
- `holdout_disjointness(train, holdout) -> Disjointness` added
- `Feasibility` gains `n_distinct_inchikeys`, `dominant_scaffold_n`; loses `n_scaffolds`

---

## Risks accepted

| Risk | Why accepted |
|---|---|
| Zero schedule slack | Overruns take from the freeze block, which is the right place. Alternative was cutting sleep |
| `dominant_scaffold_n >= 15` is unvalidated | No published basis for the exact figure. It is a judgement, reported as such in the dossier, and the number is one line to change |
| Replication reduced to answer 1 at n=2 | Weakens the agreement statistic. Answer 4 is deterministic, so replicating it measured nothing; answer 1 at n=2 still detects instability, just less precisely |
| Required-scout rule may fire on a transient outage | Better than a confident verdict over absent data |

## D9 — Question 3 is about the compound set, not about the receptor

**Problem.** `_series` answered question 3 — *is there a congeneric series?* — from the
claim `series core matches the receptor ligand`. Two things follow, and both are wrong.

First, the question is mis-answered even when that claim exists. Whether a family of
related analogs exists is a property of the compound set alone. Whether its core matches
a bound ligand decides *which structure to design against*, which is question 1. A target
can have an excellent 106-analog series and no matching co-structure; the honest answer to
question 3 is then "yes, and no structure matches it", not "not established".

Second, no component emits that claim any more. It was written by `to_records` until the
harmonisation refactor moved `scaffold_match` into `dossier/receptor.py`. Since then the
answer has fallen through to its second branch on every run, so question 3 has reported
*"Not established … no series core has been matched to the receptor ligand"* regardless of
the data. Question 4 has the same defect for the same reason: nothing emits
`most recent measurement`, so it returns its placeholder on every run.

Neither had a test. The two questions with no coverage in `test_answers.py` were exactly
the two that could not produce an answer.

**Options considered.**

| Option | Rejected because |
|---|---|
| Re-emit `series core matches the receptor ligand` from `receptor.py` | Restores the claim but keeps the conflation. Question 3 would still be unanswerable whenever no structure matches |
| Answer question 3 from `dominant_scaffold_n` in `feasibility.py` | Inverts the loop. The checks are supposed to measure the committed answer, not supply it |
| Answer from a `congeneric series` record, and say plainly why it is missing | Chosen |

**Decision.** `_series` reads a `congeneric series` claim. Grouping compounds into a series
needs a structure per compound, which the bioactivity scout does not yet return, so on a
live run the answer states that obstacle by name instead of blaming an unrelated one. Three
tests pin it: a retrieved series is reported, the answer never mentions the receptor, and
the unanswerable case names the real obstacle.

**Left open.** Question 4 asks *is anyone still working on this target?* and is answered
from `most recent measurement`, which nothing emits. It is also non-gating by design —
`Feasibility.dormant` is reported and never branches. So it is the one question whose
answer cannot change the output, and it currently has no answer either. The assays scout
already retrieves `qHTS screens`, `assays carrying a real potency value` and
`compounds behind qHTS screens`, none of which reach any answer, and which would decide
whether the question-2 count is dose–response data or single-shot noise. Replacing
question 4 with assay quality is the obvious move and is deferred to a decision, not made
here.


## Changes to make in SPEC.md

1. THRESHOLDS — delete `n_scaffolds >= 2`; add `n_distinct_inchikeys == n_analogs` and `dominant_scaffold_n >= 15`; demote the 80% rule to descriptive
2. PARAMETERS — `REPLICATES` = 2; add `RESOLVER_CONCURRENCY`, `RESOLVER_BUDGET_S`
3. SCHEMA — add `record.reason`; add two CHECK constraints
4. JOINS — replace `set_difference` with `holdout_disjointness`
5. FEASIBILITY — swap the scaffold fields; add the required-scout precondition
6. LOOP — delete the decorative-loop rule; add the branch-test case table
7. REPLICATION — answer 1 only, n=2
8. SCHEDULE — replace wholesale with the revised table in D2
9. BUILD ORDER — correct total to 645 min; step 6 135 → 100
10. SCOPE — add `insufficient retrieval` as a terminal verdict
11. MUST NOT — move three vestigial entries to EXCLUDED
12. DEMO — opening 25 s → 15 s
