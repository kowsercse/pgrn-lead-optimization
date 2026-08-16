## Flow

- Given our therapeutic hypothesis, here are the following steps:
- Query paperclip for existing biomed literature to support the hypothesis: inhibiting PGRN/Sortin complex
- Query PDB database for complex structure
- Extract known tool compounds which binds to PGRN/sortin
- Search/compile small compound library for virtual screening, with above compounds spike-in as positive control to QC
  the virtual screening
- SRA or ADMET calculation for the positive hits

## Improved

- Literature validation: query Paperclip for biomedical literature supporting the hypothesis that inhibiting the PGRN–Sortilin complex is therapeutically relevant
- Structural reference: pull the PGRN–Sortilin complex structure from PDB
- Known ligands: extract literature-reported tool compounds that bind PGRN or Sortilin
- Screening library: assemble a small-molecule library for virtual screening, spiking in the known tool compounds as positive controls to QC the screen
- Hit triage: run SAR/ADMET profiling on the positive hits

## Diagram

```mermaid
flowchart TD
    A["Literature validation<br/>Query Paperclip for PGRN-Sortilin<br/>inhibition evidence"] --> B["Structural reference<br/>Pull PGRN-Sortilin complex from PDB"]
    B --> C["Known ligands<br/>Extract tool compounds binding<br/>PGRN/Sortilin"]
    C --> D["Screening library<br/>Assemble small-molecule library,<br/>spike in known compounds as positive controls"]
    D --> E["Virtual screening<br/>QC against spiked-in positive controls"]
    E --> F["Hit triage<br/>SAR/ADMET profiling of positive hits"]
```

## Computational biologist review

### Diagram

```mermaid
flowchart TD
    subgraph S1["1. Target validation"]
        A1["Paperclip: mine literature for<br/>PGRN-Sortilin PPI evidence + interaction site"]
    end

    subgraph S2["2. Structural modeling"]
        B1["PDB: retrieve experimental complex structure"]
        B2{"Structure available?"}
        B3["AlphaFold3 / Boltz2 / Chai-1:<br/>co-fold PGRN + Sortilin"]
        B4["Score model quality<br/>(ipsae, pdockq2, dssp)"]
        B1 --> B2
        B2 -- No --> B3 --> B4
        B2 -- Yes --> B4
    end

    subgraph S3["3. Interface mapping"]
        C1["Identify PPI interface residues /<br/>druggable pocket"]
    end

    subgraph S4["4. Ligand mining"]
        D1["Extract known tool compounds<br/>(literature + PubChem/ChEMBL)"]
    end

    subgraph S5["5. Library + docking"]
        E1["Assemble screening library:<br/>candidates + positive controls + decoys"]
        E2["Vina: dock against interface pocket"]
        E3{"Positive controls recover<br/>expected pose/rank?"}
        E1 --> E2 --> E3
        E3 -- No --> E1
    end

    subgraph S6["6. Hit triage"]
        F1["Filter: docking score, pose plausibility,<br/>PAINS, scaffold diversity"]
    end

    subgraph S7["7. ADMET profiling"]
        G1["Predict ADMET properties,<br/>deprioritize poor PK/tox"]
    end

    subgraph S8["8. Prioritization"]
        H1["Rank shortlist: score + ADMET + diversity"]
        H2["Hand off to experimental validation<br/>(Benchling)"]
    end

    A1 --> B1
    B4 --> C1 --> D1 --> E1
    E3 -- Yes --> F1 --> G1 --> H1 --> H2
    H2 -. "hit/no-hit feedback" .-> E1
```

### Steps

- Target validation: Paperclip literature mining — confirm PGRN–Sortilin PPI hypothesis, extract reported interaction site/hotspot residues
- Structural modeling: pull PDB complex if available; else co-fold with AlphaFold3/Boltz2/Chai-1; score model quality (ipsae, pdockq2, dssp)
- Interface mapping: define the druggable pocket at the PPI interface (PPI interfaces are often flat — pocket ID matters more than for a classic active site)
- Ligand mining: pull known tool compounds/chemical probes (literature + PubChem/ChEMBL) as pharmacophore seeds and controls
- Library + docking: build screening library with positive controls (known binders) and decoys (for enrichment/ROC); dock with Vina against the interface pocket
- Docking validation gate: re-dock positive controls first — only proceed to full-library screen if they recover expected pose/rank
- Hit triage: filter by docking score, pose/interaction-fingerprint plausibility, PAINS, and scaffold diversity (avoid redundant chemotypes)
- ADMET profiling: predict PK/tox liabilities, deprioritize poor-ADMET hits
- Prioritization: rank shortlist (score + ADMET + diversity), hand off to experimental validation (tracked in Benchling)
- Feedback loop: feed experimental hit/no-hit data back into library/docking to refine scoring — not a one-shot screen
