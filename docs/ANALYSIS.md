# Analysis — SPEC.md

Review of `SPEC.md` as of 15 Aug 2026. Seven defects, three of them blocking. Numbers
below are computed from the spec's own values.

## Verdict

The spec is internally consistent on interfaces and grading. It is **not** consistent on
decision logic or on time. One check as written rejects the reference target. The build
is over-committed against its own schedule by 35 minutes at best, 125 minutes when blocks
are matched to steps individually.

| # | Defect | Severity | Fix cost |
|---|---|---|---|
| 1 | `n_scaffolds >= 2` rejects a congeneric series | **Blocking** | 10 min |
| 2 | Build total misstated; schedule over-committed | **Blocking** | 20 min |
| 3 | Loop's "decorative" test cannot distinguish two failure modes | **Blocking** | 15 min |
| 4 | `set_difference` argument order contradicts expected return | High | 5 min |
| 5 | `unverified` requires a `reason` field the schema lacks | High | 5 min |
| 6 | Resolver has no throughput budget | Medium | 15 min |
| 7 | No minimum-viable-run definition | Medium | 10 min |

---

## 1. `n_scaffolds >= 2` rejects the reference target — BLOCKING

Two thresholds pull in opposite directions:

```
THRESHOLDS  Congeneric series: >= 80% share one Murcko scaffold
THRESHOLDS  Series usable for SAR: n_scaffolds >= 2
LOOP        Else if n_scaffolds < 2 → not ready for SBDD
```

The first wants scaffold **concentration**. The second requires scaffold **diversity**.
Question 3 of the dossier asks whether a congeneric series exists — and the more
congeneric the series, the closer `n_scaffolds` gets to 1.

The regression fixture makes this concrete. The SORT1 series is 106 compounds on a single
5,5-dimethyl-<span>L</span>-norleucine core from one patent family. If Murcko scaffold
extraction collapses them to one scaffold — which is the expected outcome for a single
congeneric series — then:

- `n_scaffolds` = 1
- LOOP branch 2 fires
- recommendation = "not ready for SBDD"
- **fixture expects "proceed, triage-only"**

The spec's own regression test fails against the spec's own logic.

**Root cause.** `n_scaffolds >= 2` is a mis-operationalization. The failure mode it was
meant to catch is a degenerate "series" that is one compound repeated, or a set of
unrelated singletons. Neither is measured by scaffold count alone.

**Fix.** Replace with two checks that measure the actual failure modes:

```
n_analogs >= 20                          (already present)
n_distinct_inchikeys == n_analogs        (catches duplicates)
max_scaffold_share <= 0.95               (catches one compound repeated)
max_scaffold_share >= 0.50               (catches scattered singletons — series is congeneric)
```

Note the last two are a *band*, not a floor. Delete `n_scaffolds >= 2` entirely.

---

## 2. Build total misstated and schedule over-committed — BLOCKING

The spec states `Total 9.7h`. Summing its own step budgets:

| Step | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | Sum |
|---|---|---|---|---|---|---|---|---|---|---|---|
| min | 20 | 40 | 60 | 80 | 120 | 90 | 135 | 50 | 75 | 10 | **680** |

680 min = **11h20m**, not 9.7h. The stated figure understates by 98 minutes.

Schedule build capacity, excluding sleep, freeze and submit:

```
Sat 17:30 – 01:45   495 min
Sun 07:00 – 09:30   150 min
                    ------
                    645 min  (10h45m)
```

**680 needed against 645 available — 35 minutes over before anything goes wrong.**

Per-block, the mismatch is worse than the total suggests:

| Schedule block | Allotted | Steps mapped | Needed | Delta |
|---|---:|---|---:|---:|
| store | 60 | 0 + 1 | 60 | 0 |
| scouts and dispatch | 90 | 2 + 3 | 140 | **−50** |
| resolver | 120 | 4 | 120 | 0 |
| joins | 90 | 5 | 90 | 0 |
| render + replicate | 135 | 6 | 135 | 0 |
| feasibility and loop | 60 | 7 + 8 | 125 | **−65** |
| second target cold | 90 | — | ~10 | +80 |
| — | — | 9 (audit) | 10 | **unscheduled** |

Two blocks are under-provisioned by 50 and 65 minutes. The 90-minute "second target"
block holds roughly 80 minutes of slack, since a cold run is a pipeline execution, not
construction.

**Fix.** Correct the total to 11h20m. Move 50 minutes from the second-target block to
scouts, and re-cut feasibility/loop to start at 06:30 or absorb from the same slack.
Schedule step 9 explicitly. Alternatively cut step 6's scope — the replicate sub-step is
the only genuinely optional item in the critical path.

---

## 3. The "decorative loop" test is not diagnostic — BLOCKING

```
LOOP  Run on 2 targets, at least 1 failing a check
LOOP  If both targets give the same recommendation, report the loop as decorative
GENERALISATION RUN — CTSL  no fixture, by design
                           A negative recommendation is a pass
```

CTSL is a real target with real data. Whether it fails a check is **unknown at spec
time** — cathepsin L has 2,286 pChEMBL compounds and 42 liganded structures, so it may
well pass everything. If both targets pass, the spec instructs reporting the loop as
decorative, which would be false: the loop may be working perfectly and simply have been
handed two good targets.

The test conflates *the branch logic is broken* with *both inputs happened to be good*.

**Fix.** Separate the two runs by purpose:

- **Branch test** — a constructed input with values forced past each threshold. Assert
  each branch is reachable. Deterministic, needs no network, runs in seconds.
- **Generalisation run** — CTSL, real, no assertions on which branch fires.

Only the constructed test may conclude anything about whether the loop is decorative.

---

## 4. `set_difference` argument order contradicts its expected return — High

```
JOINS   set_difference(train, holdout) -> set[str]  on InChIKey
Step 5  verify set_difference returns 106
DONE    set_difference returns 106, or time-split claim withdrawn
```

Read literally, `set_difference(train, holdout)` computes `train \ holdout`, whose
cardinality is `|train| − overlap` ≈ 172 for SORT1, not 106. Returning 106 requires
`holdout \ train`.

Separately, `FEASIBILITY` consumes `holdout_overlap`, which is `|train ∩ holdout|` — a
different quantity again, and one the stated signature does not return.

**Fix.** Make the contract explicit:

```
set_difference(holdout, train) -> set[str]   # returns holdout members absent from train
holdout_overlap = len(holdout) - len(set_difference(holdout, train))
```

Assert `len(...) == 106` and `holdout_overlap == 0` as two separate checks.

---

## 5. `unverified` requires a field the schema does not have — High

```
GRADES  unverified requires reason
SCHEMA  record: record_id, run_id, scout, claim, value, grade,
                source_id, source_url, source_date, retrieved_at, query, output_hash
```

There is no `reason` column on `record`. The `gap` table has one, but a record graded
`unverified` is not a gap row — gaps are per-domain, records are per-claim.

Related asymmetry: the schema enforces the `verified`/`documented` requirement with a
`CHECK` constraint, but `measured requires query and output_hash` has no equivalent —
`output_hash` is nullable and unconstrained.

**Fix.** Add `reason TEXT` to `record`. Add:

```sql
CHECK (grade <> 'unverified'  OR reason IS NOT NULL)
CHECK (grade <> 'measured'    OR output_hash IS NOT NULL)
```

---

## 6. The resolver has no throughput budget — Medium

```
PARAMETERS  RESOLVER_TIMEOUT_S = 30
PARAMETERS  MAX_SERIES_RETURNED = 500
RESOLVER    Fetch source_id independently of the scout
```

`RESOLVER_TIMEOUT_S` bounds a single fetch. Nothing bounds the count. Five scouts each
returning up to their caps could produce several hundred `verified` records; at a
30-second worst case, serial resolution runs into hours. Step 4's budget is 120 minutes
total, including implementation.

**Fix.** Add `RESOLVER_CONCURRENCY = 8` and `RESOLVER_BUDGET_S = 300`. On budget
exhaustion, leave unresolved records at their scout-assigned grade, mark them
`resolution.note = "budget exhausted"`, and list the count in the gap section. Cache by
`source_id` — the same PDB or ChEMBL accession will be cited by several records.

---

## 7. No minimum-viable-run definition — Medium

The spec is clear that a hung scout produces a gap and the run continues. It never says
how many scouts may fail before the dossier is not worth shipping.

A run where `structures` and `bioactivity` both gapped would still satisfy every DONE
checkbox — five answers rendered, gap list present, cost line present — while containing
no receptor and no compound counts.

**Fix.** Add to SCOPE: a dossier requires `structures` and `bioactivity` to have returned;
if either gapped, emit the gap list and a stated "insufficient retrieval" verdict, and
skip the feasibility checks rather than computing them over absent data.

---

## Vestigial content

Four `MUST NOT` entries govern tools the spec now excludes entirely. They are harmless but
they dilute a list that should be scannable at 2 a.m.:

| Entry | Governs |
|---|---|
| Set MSA `search_mode="local"` | proto-tools — excluded |
| Use `ccd-lookup` or `pubchem-fetch` for novel compounds | proto-tools — excluded |
| Call `BRICS.BRICSBuild` without `islice` | generative chemistry — out of scope |
| Run `pip install vina` on arm64 | AutoDock Vina — excluded |

Keep the Vina entry, since it names a temptation someone may act on. The other three
belong in the excluded-tooling note, not in the operating rules.

## Traceability

The spec carries no mapping to the Track A judging criteria; that lives only in
`roadmap.md` §7. Every criterion is nonetheless implemented:

| Criterion | Spec sections |
|---|---|
| Closing the loop | FEASIBILITY, LOOP, GENERALISATION RUN |
| Inspectability | SCHEMA (`query`, `output_hash`, `source_date`, `retrieved_at`), DOSSIER OUTPUT |
| Validation | RESOLVER, GRADES, REGRESSION FIXTURE |
| Sponsor tools | ENVIRONMENT (ChEMBL, PubMed, Paperclip) |

Defect 3 weakens the first criterion specifically — the one the build most depends on.

## Timing check

Demo segments sum to 25 + 45 + 60 + 90 + 30 + 30 + 30 = **310 s**, against a 5-minute
slot. Ten seconds over, with no allowance for transitions. Trim the opening to 15 s.

## Recommended order

1. Defect 1 — one threshold line; without it the reference target fails
2. Defect 3 — constructed branch test; the loop is the primary judging criterion
3. Defect 2 — re-cut the schedule before 20:00 Saturday, when the first shortfall lands
4. Defects 4 and 5 — both are single-line contract fixes, do them inside their build steps
5. Defects 6 and 7 — needed before the cold run, not before the first build step

Total fix cost 80 minutes, of which 45 minutes is schedule arithmetic that removes more
risk than it costs.
