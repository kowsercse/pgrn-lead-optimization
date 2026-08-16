# Architecture — target dossier agent

Diagrams and data model. Build sequence lives in [`PLAN.md`](PLAN.md); contracts and
thresholds in [`SPEC.md`](SPEC.md); the reasoning behind both in [`DESIGN.md`](DESIGN.md).

## 1. System flow

```mermaid
flowchart TD
    CLI["cli.py<br/>run --target &lt;symbol&gt;"]
    STORE[("store.py<br/>SQLite")]

    CLI --> DISPATCH["dispatch.py<br/>concurrent, per-scout deadline"]

    DISPATCH --> SC1["scouts/structures.py<br/>RCSB PDB, AlphaFold DB"]
    DISPATCH --> SC2["scouts/bioactivity.py<br/>ChEMBL MCP, PubChem"]
    DISPATCH --> SC3["scouts/patents.py<br/>PubChem AIDs, patents"]
    DISPATCH --> SC4["scouts/assays.py<br/>assay descriptions"]
    DISPATCH --> SC5["scouts/literature.py<br/>Paperclip, PubMed MCP"]

    SC1 --> RES["resolver.py<br/>fetch, confirm span, demote<br/>concurrency 8, budget 300s"]
    SC2 --> RES
    SC3 --> RES
    SC4 --> RES
    SC5 --> RES

    RES --> JOINS["harmonize.py<br/>resolve the same thing across sources"]
    JOINS --> J2["pool_compounds<br/>same molecule, two databases"]
    JOINS --> J3["alias_resolution<br/>same protein, several names"]
    JOINS --> J4["record_vs_compound<br/>same evidence, two counts"]

    RECEPTOR["receptor.py<br/>scaffold_match — which structure"] --> ANS["answers.py<br/>five questions + gaps"]
    RES --> RECEPTOR
    J2 --> ANS
    J3 --> ANS
    J4 --> ANS

    ANS --> REP["replicate.py<br/>answer 1 only, n=2"]
    REP --> RENDER["render.py<br/>dossier v1"]
    RENDER --> CHK["feasibility.py<br/>deterministic checks, RDKit only"]
    CHK --> LOOP["loop.py<br/>branch on check results"]
    LOOP --> RENDER

    DISPATCH -.writes.-> STORE
    RES -.writes.-> STORE
    JOINS -.writes.-> STORE
    ANS -.writes.-> STORE
    CHK -.writes.-> STORE
    RENDER -.reads.-> STORE
```

Every stage writes to the store and reads from it. No stage passes objects directly to the
next, so any stage can be re-run alone against a previous run's data.

`structures` and `bioactivity` are **required**; the other three are **contributing**. If a
required scout gaps, the verdict is `insufficient retrieval` and the feasibility checks are
skipped rather than computed over absent data.

## 2. Data model

```mermaid
erDiagram
    RUN ||--o{ RECORD : produces
    RUN ||--o{ JOIN_RESULT : produces
    RUN ||--o{ ANSWER : produces
    RUN ||--o{ GAP : produces
    RUN ||--o{ CHECK : produces
    RUN ||--o{ DOSSIER : renders
    RECORD ||--o| RESOLUTION : "checked by"
    RECORD }o--o{ JOIN_RESULT : "feeds"
    JOIN_RESULT }o--|| ANSWER : "supports"
    CHECK ||--|| DOSSIER : "triggers revision of"

    RUN {
        text run_id PK
        text target
        text started_at
        text finished_at
        int tokens
        int tool_calls
    }
    RECORD {
        text record_id PK
        text run_id FK
        text scout
        text claim
        text value
        text grade
        text source_id
        text source_url
        text source_date
        text retrieved_at
        text query
        text output_hash
        text reason
    }
    RESOLUTION {
        text record_id FK
        int resolved
        text fetched_at
        int span_found
        text demoted_from
        text note
    }
    JOIN_RESULT {
        text join_id PK
        text run_id FK
        text kind
        text input_record_ids
        text result
        text grade
    }
    ANSWER {
        text answer_id PK
        text run_id FK
        int question_no
        text value
        text grade
        int agree_n
        int agree_of
    }
    GAP {
        text gap_id PK
        text run_id FK
        text description
        text reason
    }
    CHECK {
        text check_id PK
        text run_id FK
        text kind
        real value
        real threshold
        int passed
        text computed_at
    }
    DOSSIER {
        text dossier_id PK
        text run_id FK
        int version
        text recommendation
        text failure_condition
        text created_at
    }
```

Three grade rules are enforced as `CHECK` constraints rather than in prose, so a violation
fails at insert time next to the code that caused it:

```sql
CHECK (grade NOT IN ('verified','documented') OR source_url IS NOT NULL)
CHECK (grade <> 'measured'   OR output_hash IS NOT NULL)
CHECK (grade <> 'unverified' OR reason      IS NOT NULL)
```

## 3. One run, end to end

```mermaid
sequenceDiagram
    autonumber
    actor Eng as Engineer
    participant CLI as cli.py
    participant D as dispatch.py
    participant S as scouts (x5)
    participant R as resolver.py
    participant J as harmonize.py
    participant DB as store.py

    Eng->>CLI: run --target <symbol>
    CLI->>DB: create RUN
    CLI->>D: dispatch(target, deadline=180s)

    par five scouts concurrently
        D->>S: brief(target, scope, output contract)
        S-->>D: typed records
    end
    Note over D,S: on deadline expiry write a GAP,<br/>do not block the run

    D->>DB: insert RECORDs
    R->>DB: select grade in (verified, documented)
    R->>R: fetch source_id, confirm span, cache by id
    R->>DB: insert RESOLUTION, demote on failure

    J->>DB: select resolved RECORDs
    J->>J: pool_compounds, alias_resolution, record_vs_compound
    J->>DB: insert JOIN_RESULTs

    CLI->>DB: compose five ANSWERs + GAPs
    CLI->>CLI: render dossier v1

    CLI->>CLI: compute feasibility checks over retrieved data
    CLI->>DB: insert CHECKs
    CLI->>CLI: branch, render dossier v2
    CLI-->>Eng: dossier_v1.html, dossier_v2.html
```

## 4. The loop

```mermaid
stateDiagram-v2
    state Evaluate <<choice>>

    [*] --> DossierV1
    DossierV1 --> Checks : assessment commits, checks not yet computed
    Checks --> Evaluate : check results returned
    Evaluate --> ScaffoldSplit : holdout overlap > 0
    Evaluate --> NotReady : thin series or span < 2 logs
    Evaluate --> NoStructure : resolution > 3.5 A
    Evaluate --> TriageOnly : resolution > 2.5 A
    Evaluate --> Proceed : all checks pass
    NotReady --> DossierV2
    NoStructure --> DossierV2
    TriageOnly --> DossierV2
    Proceed --> DossierV2
    DossierV2 --> [*]

    note right of Checks
        Branch decided by numbers
        the agent did not produce.
    end note
```

Data splitting is deliberately absent: whether a future model could be validated
says nothing about whether this protein is tractable. See `DESIGN.md` D8.

"Thin series" is `n_analogs < 20`, `n_distinct_inchikeys != n_analogs`, or
`dominant_scaffold_n < 15`. Scaffold *count* is not a criterion — a congeneric series
correctly collapses to one Murcko scaffold, and gating on diversity would reject the very
property the dossier is looking for. See `DESIGN.md` D1.

## 5. Repository layout

```
pgrn-lead-optimization/
├── dossier/
│   ├── __init__.py
│   ├── cli.py            # entrypoint
│   ├── store.py          # schema + typed insert/select
│   ├── dispatch.py       # concurrent scouts, deadlines, required-scout rule
│   ├── grades.py         # Grade enum, demotion rules
│   ├── resolver.py       # citation gate, budget, cache
│   ├── harmonize.py      # resolve the same thing across sources
│   ├── receptor.py       # which structure to design against
│   ├── answers.py        # five questions + gap list
│   ├── replicate.py      # agreement on answer 1
│   ├── feasibility.py    # deterministic checks, RDKit only
│   ├── loop.py           # branch on check results
│   ├── render.py         # dossier HTML
│   └── scouts/
│       ├── base.py       # Scout protocol, brief template
│       ├── structures.py
│       ├── bioactivity.py
│       ├── patents.py
│       ├── assays.py
│       └── literature.py
├── tests/
│   ├── fixtures/sort1.py # expected values — never imported by dossier/
│   └── test_branches.py  # seven-case table over next_step
└── docs/
```

No module under `dossier/` may contain a PDB ID, ChEMBL accession, PubChem AID, compound
name or target symbol. Enforced by the Stage 6 audit:

```bash
grep -rE '6X48|5MRI|UP4|CHEMBL3091|CHEMBL4680051|2202264|norleucine|SORT1|CTSL' dossier/
```
