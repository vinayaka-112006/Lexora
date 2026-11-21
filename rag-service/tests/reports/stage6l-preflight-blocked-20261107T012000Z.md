# Stage 6L Preflight — Blocked

- Evaluated: 2026-11-07
- Stage 6L answer generation: **NOT RUN**
- LLM requests: **0**
- Reason: the required exact Stage 6D baseline gate did not match the current corrected-target retrieval evaluation. The existing runner exits on this mismatch before constructing `OllamaClient`.

## Configuration and inputs

- Provider configured by the project root `.env`: `ollama`.
- Model: `llama3:latest`.
- Configured endpoint: `http://localhost:11434` (configuration read only; endpoint availability was not probed).
- Evaluation dataset: `rag-service/tests/eval_set.json`, 42 items (35 answerable, 7 expected abstentions); SHA-256 `37311e90be445404b3d2a5fc18809248f8f050217972d3c8dff421a20d629513`.
- Candidate chunk map SHA-256: `efd89919dde975cf0427152d7d62d06c1c5b2e513dd9d3073ced72449c7a2a76`.
- Retrieval evidence: `retrieval-candidate-20261107T004000Z-legal-expansion-final.json` (corrected retriever, matching candidate map and disposable index; deterministic across two passes).
- Canonical chunk map hash remained `42e8a14c1f97eac89e6028fd663d5d2e9d3ca37dce88f19d008764eca1d31c63`.

## Stage 6D gate comparison

| Metric | Required hard-coded Stage 6D | Current corrected-target retrieval |
|---|---:|---:|
| Recall@1 | 0.3857 | 0.4571 |
| Recall@3 | 0.5952 | 0.6286 |
| Recall@5 | 0.7381 | 0.7571 |
| Recall@10 | 0.8810 | 0.9905 |
| MRR | 0.5711 | 0.6123 |

The runner requires exact equality for all five metrics. The current run differs on every metric. This gate is therefore incompatible with this corrected-target retrieval run. The historical constants were left unchanged; this report does not establish a replacement baseline.

## Stage 6L metrics

Answer quality, citation validation, claim verification, confidence classification, and abstention metrics are **unavailable** because the gate stopped execution before LLM construction and requests.

The known retrieval limitation remains `eval_030`: Nagoya Protocol Articles 5 and 6 are in the Top 10; Biological Diversity Act Section 6 is not. No generated-answer failure IDs exist because no answers were generated.

## Status

**BLOCKED AT RETRIEVAL PREFLIGHT.** No evaluation queries were sent to Ollama. No baseline constants, evaluation targets, prompts, production configuration, or corpus files were changed.
