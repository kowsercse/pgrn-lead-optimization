---
name: biohub
description: Call Biohub Platform (biohub.ai) for ESM protein models — ESMFold2 structure prediction, ESMC embeddings/logits/SAE features, ESM Atlas lookups, antibody/binder design. Use for any protein sequence, structure prediction, or binder-design task in this project.
---

# Biohub Platform

Hosted ESM models. Base URL: `https://biohub.ai`. Auth: `Authorization: Bearer $BIOHUB_API_KEY` header (REST) or `token=` kwarg (SDK).

## Setup

1. API key: `biohub.ai` → Developer console → Sign up → create key
2. Store as `BIOHUB_API_KEY` env var
3. Install SDK: `pip install esm@git+https://github.com/Biohub/esm.git@main`

## Structure prediction (ESMFold2)

```python
from esm.sdk.forge import SequenceStructureForgeInferenceClient

client = SequenceStructureForgeInferenceClient(
    model="esmfold2-2026-05",       # or "esmfold2-fast-2026-05" for speed
    url="https://biohub.ai",
    token=os.environ["BIOHUB_API_KEY"],
)
```

## Embeddings / logits / SAE features (ESMC)

```python
from esm.sdk.forge import ESMCForgeInferenceClient
from esm.sdk.api import LogitsConfig

client = ESMCForgeInferenceClient(
    model="esmc-6b-2024-12",        # or esmc-300m-2024-12 / esmc-600m-2024-12
    url="https://biohub.ai",
    token=os.environ["BIOHUB_API_KEY"],
)
# LogitsConfig(sequence=True, return_embeddings=True) for embeddings
```

## Antibody / binder design

```python
from esm.sdk.forge import DesignApp

app = DesignApp()
app.load(use_scaling_critics=False)
sequence, trajectory, scores = app.design(
    target_sequence="...",
    binder_sequence="...",
    is_antibody=True,
)
```

## ESM Atlas

6.8B predicted structures + annotations. API docs: `biohub.ai/esm/protein/atlas/api-docs/`. Bulk dataset free on AWS S3.

## Raw REST endpoints (v1, if not using SDK)

`/api/v1/logits` `/encode` `/decode` `/generate` `/generate_tensor` `/forward_and_sample` `/fold` `/fold_all_atom` `/inverse_fold`

## Guardrails

Platform blocks controlled pathogen/toxin sequences and keywords. Set `potential_sequence_of_concern: true` on a request if a legitimate sequence trips this.
