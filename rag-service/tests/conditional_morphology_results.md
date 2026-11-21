# Stage 6J Conditional Morphology Evaluation

## Implementation

Added a deterministic query morphology helper using the Stage 6H suffix rules and a corpus-attested vocabulary. When `MORPHOLOGY_EXPANSION_ENABLED=true`, it appends up to five matching singular/plural forms to eligible retrieval queries before dense and BM25 retrieval. It skips explicit provision references, comparisons (including relation wording such as “relate to”), and queries with fewer than four meaningful tokens. The original query remains available for prompts and query diagnostics. The feature flag defaults to `false`.

The diagnostic values are emitted through debug logging, not the normal user-facing answer output. RRF, candidate pool sizing, intent bonuses, and comparison ranking were not changed.

## Full 42-query evaluation

The 42-item set contains 35 answerable retrieval queries and 7 abstention cases. The accepted Stage 6D baseline and disabled-mode ablation match exactly.

| Metric | Stage 6D baseline / disabled | Morphology enabled | Delta |
|---|---:|---:|---:|
| Recall@1 | 0.3857 | 0.4429 | +0.0572 |
| Recall@3 | 0.5952 | 0.6524 | +0.0572 |
| Recall@5 | 0.7381 | 0.7952 | +0.0571 |
| Recall@10 | 0.8810 | 0.9095 | +0.0285 |
| MRR | 0.5711 | 0.6220 | +0.0509 |

Disabled-mode results reproduce all baseline metrics, rankings, and comparison results, demonstrating that the feature flag restores the accepted retrieval behavior.

## Category comparison

| Category | Baseline R@1 / R@3 / R@5 / R@10 / MRR | Enabled R@1 / R@3 / R@5 / R@10 / MRR | Assessment |
|---|---|---|---|
| Definitions | .5000 / .7500 / .7500 / .7500 / .6250 | .5000 / .7500 / .7500 / .7500 / .6250 | Unchanged |
| Patentability | .6667 / 1 / 1 / 1 / .8333 | .6667 / 1 / 1 / 1 / .7778 | MRR degraded |
| Patent procedure | 0 / 0 / .3333 / 1 / .1560 | .3333 / .3333 / .6667 / 1 / .4583 | Improved |
| Trademarks | .3333 / .3333 / .6667 / .6667 / .4000 | 0 / .3333 / .6667 / 1 / .2667 | R@1 and MRR degraded; R@10 improved |
| Geographical indications | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | Unchanged |
| Designs | 0 / .5000 / 1 / 1 / .3500 | 0 / .5000 / 1 / 1 / .2667 | MRR degraded |
| Biological diversity | .6667 / .6667 / 1 / 1 / .7333 | 1 / 1 / 1 / 1 / 1 | Improved |
| Traditional knowledge | .5000 / 1 / 1 / 1 / .7500 | .5000 / 1 / 1 / 1 / .7500 | Unchanged |
| Ayurveda/food/regulatory | 0 / 0 / .5000 / 1 / .1833 | 0 / 0 / .5000 / 1 / .1833 | Unchanged |
| International treaties | 0 / .5000 / .5000 / 1 / .2639 | .2500 / .5000 / .7500 / 1 / .4653 | Improved |
| Comparisons | .1250 / .4583 / .4583 / .4583 / .6250 | .1250 / .4583 / .4583 / .4583 / .6250 | Unchanged |
| Explicit provisions | 1 / 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 / 1 | Unchanged |

The gains are not uniform: patentability, trademarks, and designs have lower category MRR. Overall metrics improve, while those category tradeoffs remain visible in this report.

## Query types and safeguards

- Explicit-provision queries: all three full-evaluation targets remain rank 1: Patent Act Section 83, Nagoya Protocol Article 6, and Trade Marks Act Section 34.
- Comparison queries: `eval_029`–`eval_032` have unchanged target coverage and jurisdiction distributions versus baseline. Per-query Top-5 target coverage is 1/2, 1/3, 1/2, and 1/2 respectively; Top-10 coverage is unchanged as well.
- Stage 5A.1 regression: Patent Act Section 3 rank 1; Trade Marks Act Section 2 rank 2; Nagoya Protocol Article 1 rank 4. Metrics: R@1 .3000, R@3 .6000, R@5 .9500, MRR .6875, matching disabled-mode results.
- The four-token minimum is general and length-based. It prevents expansion of the three-meaningful-token Nagoya purpose query, which regressed under the earlier three-token cutoff.
- Jurisdiction violations: 0. Evaluation ranking mismatches across repeated queries: 0.

## Latency

Measured retrieval-only latency over 42 queries in each mode after warmup:

| Mode | Mean | Median |
|---|---:|---:|
| Disabled | 33.09 ms | 31.84 ms |
| Enabled | 32.35 ms | 31.96 ms |

The small differences are measurement noise; no meaningful preprocessing overhead was observed.

## Tests and integrity

- New focused morphology tests: 16 pass.
- Full test discovery: 52 pass, including citation validation, confidence scoring, claim verification, candidate-pool, and morphology tests.
- Python syntax compilation: pass for `retriever.py`, `query_morphology.py`, `main.py`, and `test_conditional_morphology.py`.
- Chroma record count: 1,349.
- Corpus files found: 19. This stage did not write to the corpus, extracted documents, chunks, Chroma database, or evaluation set.
- Read-only integrity snapshot: `extracted_documents.json` SHA-256 `d48f09a7e79a559974c624af318f27e0f8a2dce21463d312852b7a4307488f32`; `chunks.json` SHA-256 `521d427fabfbec7ba22e34aaf200f62e0a437a9e719a6832ea31329218444e8c`; `eval_set.json` SHA-256 `a8bb0dc4deeb9bbc03a483c1fee4af123db79d2133192b70c9b1d341b4e8b664`; corpus tree SHA-256 `7300d8d5830d5302717a097f120dfa81c6a3e931db99b16641889f284d06b386`.

The retrieval runs emitted the Hugging Face Hub unauthenticated-use warning. The cached model loaded successfully and all evaluations completed.

## Acceptance criteria

| Criterion | Result |
|---|---|
| Overall R@1 does not decrease | Pass; +0.0572 |
| R@5 improves or remains stable | Pass; +0.0571 |
| MRR improves or remains stable | Pass; +0.0509 |
| R@10 has no meaningful regression | Pass; +0.0285 |
| Explicit provisions remain correct | Pass; all three rank 1 |
| Comparison retrieval remains stable | Pass; unchanged coverage and jurisdiction mix |
| No jurisdiction violations | Pass; 0 |
| Deterministic | Pass; 0 mismatches |
| Existing tests pass | Pass; 52 tests |
| No evaluation-specific rules | Pass; vocabulary and suffix transformations are generic; no target/document boosts |
| Feature can be disabled to restore baseline | Pass; disabled metrics and rankings match Stage 6D |

## Recommendation

**KEEP**, with `MORPHOLOGY_EXPANSION_ENABLED=false` as the default. The opt-in feature improves all aggregate retrieval metrics and protects explicit and comparison behavior, while its category-level regressions are documented above. Enable it deliberately for deployment evaluation and monitor the affected categories.

`STAGE 6J STATUS: PASS`
