# Offline Weighted-RRF Analysis

## 1. Executive summary

The experiment evaluated **35 answerable queries** and **40 expected targets**. For each query it captured one global Stage 6D dense pool and one BM25 pool, then rescored those same rows offline under five fixed weight configurations. No retrieval call was made for any weighted configuration.

Baseline configuration A reproduces the required full-set metrics: R@1 **0.3857**, R@3 **0.5952**, R@5 **0.7381**, R@10 **0.8810**, MRR **0.5711**. The baseline uses `RRF_K=60` and current production intent/explicit bonuses.

No weighting setting is recommended for production from this 35-query experiment. The report compares retrieval metrics, categories, comparisons, explicit provisions, and source-specific target groups; the recommendation section explains the tradeoffs.

## 2. Baseline and weighted formulas

Baseline:
```text
base_rrf = 1 / (RRF_K + dense_rank) + 1 / (RRF_K + bm25_rank)
```

Weighted offline variant:
```text
weighted_rrf = dense_weight / (RRF_K + dense_rank)
             + bm25_weight / (RRF_K + bm25_rank)
final_score = weighted_rrf + current_intent_bonus + current_explicit_provision_bonus
```

A missing source rank contributes zero. Ranks, candidate membership, exact-provision fallback, bonuses, tie-breaking, jurisdiction filtering, and current post-fusion comparison selection follow Stage 6D. Only the dense/BM25 multipliers differ.

### Tested configurations

| Configuration | Dense weight | BM25 weight |
|---|---:|---:|
| A baseline (1.0/1.0) | 1.00 | 1.00 |
| B dense 1.25 (1.25/1.0) | 1.25 | 1.00 |
| C dense 1.5 (1.5/1.0) | 1.50 | 1.00 |
| D dense 2.0 (2.0/1.0) | 2.00 | 1.00 |
| E BM25 0.75 (1.0/0.75) | 1.00 | 0.75 |

## 3. Overall metric comparison

Deltas are relative to A, with A deltas equal to zero.

| Configuration | R@1 | ΔR@1 | R@3 | ΔR@3 | R@5 | ΔR@5 | R@10 | ΔR@10 | MRR | ΔMRR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A baseline (1.0/1.0) | 0.3857 | +0.0000 | 0.5952 | +0.0000 | 0.7381 | +0.0000 | 0.8810 | +0.0000 | 0.5711 | +0.0000 |
| B dense 1.25 (1.25/1.0) | 0.3952 | +0.0095 | 0.5810 | -0.0143 | 0.7238 | -0.0143 | 0.8524 | -0.0286 | 0.5657 | -0.0054 |
| C dense 1.5 (1.5/1.0) | 0.3952 | +0.0095 | 0.5810 | -0.0143 | 0.6952 | -0.0429 | 0.8238 | -0.0571 | 0.5557 | -0.0154 |
| D dense 2.0 (2.0/1.0) | 0.3952 | +0.0095 | 0.5381 | -0.0571 | 0.6952 | -0.0429 | 0.8238 | -0.0571 | 0.5477 | -0.0235 |
| E BM25 0.75 (1.0/0.75) | 0.3952 | +0.0095 | 0.5810 | -0.0143 | 0.7238 | -0.0143 | 0.8524 | -0.0286 | 0.5657 | -0.0054 |

## 4. Category-level comparison

Each row is macro-averaged over answerable queries in that category; multiple expected targets contribute target-fraction recall, matching the Stage 6 evaluator.

| Category | Config | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---|---:|---:|---:|---:|---:|
| Definitions | A baseline (1.0/1.0) | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 |
| Definitions | B dense 1.25 (1.25/1.0) | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 |
| Definitions | C dense 1.5 (1.5/1.0) | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 |
| Definitions | D dense 2.0 (2.0/1.0) | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.5833 |
| Definitions | E BM25 0.75 (1.0/0.75) | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 |
| Patentability | A baseline (1.0/1.0) | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.8333 |
| Patentability | B dense 1.25 (1.25/1.0) | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.8333 |
| Patentability | C dense 1.5 (1.5/1.0) | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.8333 |
| Patentability | D dense 2.0 (2.0/1.0) | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.8333 |
| Patentability | E BM25 0.75 (1.0/0.75) | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.8333 |
| Patent procedure | A baseline (1.0/1.0) | 0.0000 | 0.0000 | 0.3333 | 1.0000 | 0.1560 |
| Patent procedure | B dense 1.25 (1.25/1.0) | 0.0000 | 0.0000 | 0.3333 | 1.0000 | 0.1639 |
| Patent procedure | C dense 1.5 (1.5/1.0) | 0.0000 | 0.0000 | 0.3333 | 1.0000 | 0.1639 |
| Patent procedure | D dense 2.0 (2.0/1.0) | 0.0000 | 0.0000 | 0.3333 | 1.0000 | 0.1639 |
| Patent procedure | E BM25 0.75 (1.0/0.75) | 0.0000 | 0.0000 | 0.3333 | 1.0000 | 0.1639 |
| Trademarks | A baseline (1.0/1.0) | 0.3333 | 0.3333 | 0.6667 | 0.6667 | 0.4000 |
| Trademarks | B dense 1.25 (1.25/1.0) | 0.3333 | 0.3333 | 0.6667 | 0.6667 | 0.4000 |
| Trademarks | C dense 1.5 (1.5/1.0) | 0.3333 | 0.3333 | 0.6667 | 0.6667 | 0.4000 |
| Trademarks | D dense 2.0 (2.0/1.0) | 0.3333 | 0.3333 | 0.6667 | 0.6667 | 0.4000 |
| Trademarks | E BM25 0.75 (1.0/0.75) | 0.3333 | 0.3333 | 0.6667 | 0.6667 | 0.4000 |
| Geographical indications | A baseline (1.0/1.0) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Geographical indications | B dense 1.25 (1.25/1.0) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Geographical indications | C dense 1.5 (1.5/1.0) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Geographical indications | D dense 2.0 (2.0/1.0) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Geographical indications | E BM25 0.75 (1.0/0.75) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Designs | A baseline (1.0/1.0) | 0.0000 | 0.5000 | 1.0000 | 1.0000 | 0.3500 |
| Designs | B dense 1.25 (1.25/1.0) | 0.0000 | 0.5000 | 0.5000 | 1.0000 | 0.2500 |
| Designs | C dense 1.5 (1.5/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0833 |
| Designs | D dense 2.0 (2.0/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0833 |
| Designs | E BM25 0.75 (1.0/0.75) | 0.0000 | 0.5000 | 0.5000 | 1.0000 | 0.2500 |
| Biological diversity | A baseline (1.0/1.0) | 0.6667 | 0.6667 | 1.0000 | 1.0000 | 0.7333 |
| Biological diversity | B dense 1.25 (1.25/1.0) | 0.6667 | 0.6667 | 1.0000 | 1.0000 | 0.7333 |
| Biological diversity | C dense 1.5 (1.5/1.0) | 0.6667 | 0.6667 | 1.0000 | 1.0000 | 0.7333 |
| Biological diversity | D dense 2.0 (2.0/1.0) | 0.6667 | 0.6667 | 1.0000 | 1.0000 | 0.7500 |
| Biological diversity | E BM25 0.75 (1.0/0.75) | 0.6667 | 0.6667 | 1.0000 | 1.0000 | 0.7333 |
| Traditional knowledge | A baseline (1.0/1.0) | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.7500 |
| Traditional knowledge | B dense 1.25 (1.25/1.0) | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.7500 |
| Traditional knowledge | C dense 1.5 (1.5/1.0) | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.7500 |
| Traditional knowledge | D dense 2.0 (2.0/1.0) | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.7500 |
| Traditional knowledge | E BM25 0.75 (1.0/0.75) | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.7500 |
| Ayurveda/food/regulatory | A baseline (1.0/1.0) | 0.0000 | 0.0000 | 0.5000 | 1.0000 | 0.1833 |
| Ayurveda/food/regulatory | B dense 1.25 (1.25/1.0) | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 0.2250 |
| Ayurveda/food/regulatory | C dense 1.5 (1.5/1.0) | 0.0000 | 0.5000 | 1.0000 | 1.0000 | 0.2917 |
| Ayurveda/food/regulatory | D dense 2.0 (2.0/1.0) | 0.0000 | 0.5000 | 1.0000 | 1.0000 | 0.2917 |
| Ayurveda/food/regulatory | E BM25 0.75 (1.0/0.75) | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 0.2250 |
| International treaties | A baseline (1.0/1.0) | 0.0000 | 0.5000 | 0.5000 | 1.0000 | 0.2639 |
| International treaties | B dense 1.25 (1.25/1.0) | 0.0000 | 0.5000 | 0.5000 | 0.7500 | 0.2812 |
| International treaties | C dense 1.5 (1.5/1.0) | 0.0000 | 0.5000 | 0.5000 | 0.7500 | 0.2440 |
| International treaties | D dense 2.0 (2.0/1.0) | 0.0000 | 0.2500 | 0.5000 | 0.7500 | 0.2232 |
| International treaties | E BM25 0.75 (1.0/0.75) | 0.0000 | 0.5000 | 0.5000 | 0.7500 | 0.2812 |
| Comparisons | A baseline (1.0/1.0) | 0.1250 | 0.4583 | 0.4583 | 0.4583 | 0.6250 |
| Comparisons | B dense 1.25 (1.25/1.0) | 0.2083 | 0.3333 | 0.3333 | 0.4583 | 0.5833 |
| Comparisons | C dense 1.5 (1.5/1.0) | 0.2083 | 0.3333 | 0.3333 | 0.4583 | 0.5833 |
| Comparisons | D dense 2.0 (2.0/1.0) | 0.2083 | 0.2083 | 0.3333 | 0.4583 | 0.5625 |
| Comparisons | E BM25 0.75 (1.0/0.75) | 0.2083 | 0.3333 | 0.3333 | 0.4583 | 0.5833 |
| Explicit provisions | A baseline (1.0/1.0) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Explicit provisions | B dense 1.25 (1.25/1.0) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Explicit provisions | C dense 1.5 (1.5/1.0) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Explicit provisions | D dense 2.0 (2.0/1.0) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Explicit provisions | E BM25 0.75 (1.0/0.75) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## 5. Comparison-query analysis

Target coverage is the fraction of expected provisions retrieved by the cutoff. Jurisdiction representation is shown separately and is not treated as target success.

| Query | Config | Target coverage@5 | Target coverage@10 | Jurisdictions Top-5 | Jurisdictions Top-10 |
|---|---|---:|---:|---|---|
| eval_029 | A baseline (1.0/1.0) | 0.500 (1/2) | 0.500 (1/2) | {'India': 3, 'International': 2} | {'India': 7, 'International': 3} |
| eval_029 | B dense 1.25 (1.25/1.0) | 0.000 (0/2) | 0.000 (0/2) | {'India': 5} | {'India': 10} |
| eval_029 | C dense 1.5 (1.5/1.0) | 0.000 (0/2) | 0.000 (0/2) | {'India': 5} | {'India': 10} |
| eval_029 | D dense 2.0 (2.0/1.0) | 0.000 (0/2) | 0.000 (0/2) | {'India': 5} | {'India': 10} |
| eval_029 | E BM25 0.75 (1.0/0.75) | 0.000 (0/2) | 0.000 (0/2) | {'India': 5} | {'India': 10} |
| eval_030 | A baseline (1.0/1.0) | 0.333 (1/3) | 0.333 (1/3) | {'International': 5} | {'International': 10} |
| eval_030 | B dense 1.25 (1.25/1.0) | 0.333 (1/3) | 0.333 (1/3) | {'International': 5} | {'International': 9, 'India': 1} |
| eval_030 | C dense 1.5 (1.5/1.0) | 0.333 (1/3) | 0.333 (1/3) | {'International': 5} | {'International': 9, 'India': 1} |
| eval_030 | D dense 2.0 (2.0/1.0) | 0.333 (1/3) | 0.333 (1/3) | {'International': 5} | {'International': 9, 'India': 1} |
| eval_030 | E BM25 0.75 (1.0/0.75) | 0.333 (1/3) | 0.333 (1/3) | {'International': 5} | {'International': 9, 'India': 1} |
| eval_031 | A baseline (1.0/1.0) | 0.500 (1/2) | 0.500 (1/2) | {'India': 3, 'International': 2} | {'India': 7, 'International': 3} |
| eval_031 | B dense 1.25 (1.25/1.0) | 0.500 (1/2) | 1.000 (2/2) | {'India': 3, 'International': 2} | {'India': 8, 'International': 2} |
| eval_031 | C dense 1.5 (1.5/1.0) | 0.500 (1/2) | 1.000 (2/2) | {'India': 3, 'International': 2} | {'India': 8, 'International': 2} |
| eval_031 | D dense 2.0 (2.0/1.0) | 0.500 (1/2) | 1.000 (2/2) | {'India': 3, 'International': 2} | {'India': 8, 'International': 2} |
| eval_031 | E BM25 0.75 (1.0/0.75) | 0.500 (1/2) | 1.000 (2/2) | {'India': 3, 'International': 2} | {'India': 8, 'International': 2} |
| eval_032 | A baseline (1.0/1.0) | 0.500 (1/2) | 0.500 (1/2) | {'International': 5} | {'International': 8, 'India': 2} |
| eval_032 | B dense 1.25 (1.25/1.0) | 0.500 (1/2) | 0.500 (1/2) | {'International': 5} | {'International': 7, 'India': 3} |
| eval_032 | C dense 1.5 (1.5/1.0) | 0.500 (1/2) | 0.500 (1/2) | {'International': 5} | {'International': 7, 'India': 3} |
| eval_032 | D dense 2.0 (2.0/1.0) | 0.500 (1/2) | 0.500 (1/2) | {'International': 5} | {'International': 7, 'India': 3} |
| eval_032 | E BM25 0.75 (1.0/0.75) | 0.500 (1/2) | 0.500 (1/2) | {'International': 5} | {'International': 7, 'India': 3} |

| Aggregate comparison measure | A baseline (1.0/1.0) | B dense 1.25 (1.25/1.0) | C dense 1.5 (1.5/1.0) | D dense 2.0 (2.0/1.0) | E BM25 0.75 (1.0/0.75) |
|---|---:|---:|---:|---:|---:|
| Mean target coverage@5 | 0.4583 | 0.3333 | 0.3333 | 0.3333 | 0.3333 |
| Mean target coverage@10 | 0.4583 | 0.4583 | 0.4583 | 0.4583 | 0.4583 |
| Aggregate jurisdiction counts Top-5 | {'India': 6, 'International': 14} | {'India': 8, 'International': 12} | {'India': 8, 'International': 12} | {'India': 8, 'International': 12} | {'India': 8, 'International': 12} |
| Aggregate jurisdiction counts Top-10 | {'India': 16, 'International': 24} | {'India': 22, 'International': 18} | {'India': 22, 'International': 18} | {'India': 22, 'International': 18} | {'India': 22, 'International': 18} |

## 6. Target-level rank changes

The table includes each expected target whose raw scored-union rank or returned Top-10 rank changed in at least one weighted configuration. Dense/BM25 ranks are from the single unchanged baseline candidate pools. `Δ score` compares the weighted score with baseline for the same target chunk selected as the baseline's highest-ranked matching chunk. `Top-1/3/5/10` refers to the target's earliest matching result in the final returned list.

| ID | Target / title | Source group | Dense rank | BM25 rank | Baseline raw/Top-10 | Config | Weighted raw/Top-10 | Δ score | Top-1/3/5/10 |
|---|---|---|---:|---:|---|---|---|---:|---|
| eval_002 | Biological Diversity Act 2002 section 2 — Definitions | BM25 only | — | 1 | 11/— | C dense 1.5 (1.5/1.0) | 14/— | 0.000000 | N/N/N/N |
| eval_002 | Biological Diversity Act 2002 section 2 — Definitions | BM25 only | — | 1 | 11/— | D dense 2.0 (2.0/1.0) | 21/— | 0.000000 | N/N/N/N |
| eval_004 | Gi Act section 2 — untitled | both | 6 | 2 | 2/2 | D dense 2.0 (2.0/1.0) | 3/3 | 0.015152 | N/Y/Y/Y |
| eval_010 | Patent Act 2024 section 43 — Grant of patents | dense only | 1 | — | 7/7 | B dense 1.25 (1.25/1.0) | 6/6 | 0.004098 | N/N/N/Y |
| eval_010 | Patent Act 2024 section 43 — Grant of patents | dense only | 1 | — | 7/7 | C dense 1.5 (1.5/1.0) | 6/6 | 0.008197 | N/N/N/Y |
| eval_010 | Patent Act 2024 section 43 — Grant of patents | dense only | 1 | — | 7/7 | D dense 2.0 (2.0/1.0) | 6/6 | 0.016393 | N/N/N/Y |
| eval_010 | Patent Act 2024 section 43 — Grant of patents | dense only | 1 | — | 7/7 | E BM25 0.75 (1.0/0.75) | 6/6 | 0.000000 | N/N/N/Y |
| eval_011 | Trademarks Act section 9 — untitled | BM25 only | — | 12 | 20/— | B dense 1.25 (1.25/1.0) | 28/— | 0.000000 | N/N/N/N |
| eval_011 | Trademarks Act section 9 — untitled | BM25 only | — | 12 | 20/— | C dense 1.5 (1.5/1.0) | 28/— | 0.000000 | N/N/N/N |
| eval_011 | Trademarks Act section 9 — untitled | BM25 only | — | 12 | 20/— | D dense 2.0 (2.0/1.0) | 28/— | 0.000000 | N/N/N/N |
| eval_011 | Trademarks Act section 9 — untitled | BM25 only | — | 12 | 20/— | E BM25 0.75 (1.0/0.75) | 28/— | -0.003472 | N/N/N/N |
| eval_016 | Designs Act section 2 — In this Act, unless there is anything repugnant in the subject or | BM25 only | — | 1 | 2/2 | B dense 1.25 (1.25/1.0) | 3/3 | 0.000000 | N/Y/Y/Y |
| eval_016 | Designs Act section 2 — In this Act, unless there is anything repugnant in the subject or | BM25 only | — | 1 | 2/2 | C dense 1.5 (1.5/1.0) | 11/— | 0.000000 | N/N/N/N |
| eval_016 | Designs Act section 2 — In this Act, unless there is anything repugnant in the subject or | BM25 only | — | 1 | 2/2 | D dense 2.0 (2.0/1.0) | 21/— | 0.000000 | N/N/N/N |
| eval_016 | Designs Act section 2 — In this Act, unless there is anything repugnant in the subject or | BM25 only | — | 1 | 2/2 | E BM25 0.75 (1.0/0.75) | 3/3 | -0.004098 | N/Y/Y/Y |
| eval_017 | Designs Act section 11 — untitled | both | 4 | 13 | 5/5 | B dense 1.25 (1.25/1.0) | 6/6 | 0.003906 | N/N/N/Y |
| eval_017 | Designs Act section 11 — untitled | both | 4 | 13 | 5/5 | C dense 1.5 (1.5/1.0) | 6/6 | 0.007812 | N/N/N/Y |
| eval_017 | Designs Act section 11 — untitled | both | 4 | 13 | 5/5 | D dense 2.0 (2.0/1.0) | 6/6 | 0.015625 | N/N/N/Y |
| eval_017 | Designs Act section 11 — untitled | both | 4 | 13 | 5/5 | E BM25 0.75 (1.0/0.75) | 6/6 | -0.003425 | N/N/N/Y |
| eval_020 | Biological Diversity Act 2002 section 21 — Determination of 6[fair and equitable] benefit sharing by National Biodiversity Authority | both | 1 | 17 | 5/5 | D dense 2.0 (2.0/1.0) | 4/4 | 0.016393 | N/N/Y/Y |
| eval_023 | Fssai Ayurveda Aahara Regulations 2022 section 12 — Labelling of Ayurveda Aahara .- The labelling of Ayurveda Aahara shall be in accordance wi th | both | 1 | 14 | 6/6 | B dense 1.25 (1.25/1.0) | 4/4 | 0.004098 | N/N/Y/Y |
| eval_023 | Fssai Ayurveda Aahara Regulations 2022 section 12 — Labelling of Ayurveda Aahara .- The labelling of Ayurveda Aahara shall be in accordance wi th | both | 1 | 14 | 6/6 | C dense 1.5 (1.5/1.0) | 4/4 | 0.008197 | N/N/Y/Y |
| eval_023 | Fssai Ayurveda Aahara Regulations 2022 section 12 — Labelling of Ayurveda Aahara .- The labelling of Ayurveda Aahara shall be in accordance wi th | both | 1 | 14 | 6/6 | D dense 2.0 (2.0/1.0) | 4/4 | 0.016393 | N/N/Y/Y |
| eval_023 | Fssai Ayurveda Aahara Regulations 2022 section 12 — Labelling of Ayurveda Aahara .- The labelling of Ayurveda Aahara shall be in accordance wi th | both | 1 | 14 | 6/6 | E BM25 0.75 (1.0/0.75) | 4/4 | -0.003378 | N/N/Y/Y |
| eval_024 | Fssai Ayurveda Aahara Regulations 2022 section 8 — Not to claim treating human disease, etc. .- The labelling, presentation and advertisement shall not | both | 1 | 4 | 5/5 | C dense 1.5 (1.5/1.0) | 3/3 | 0.008197 | N/Y/Y/Y |
| eval_024 | Fssai Ayurveda Aahara Regulations 2022 section 8 — Not to claim treating human disease, etc. .- The labelling, presentation and advertisement shall not | both | 1 | 4 | 5/5 | D dense 2.0 (2.0/1.0) | 3/3 | 0.016393 | N/Y/Y/Y |
| eval_025 | Nagoya Protocol article 1 — OBJECTIVE | both | 11 | 6 | 2/2 | C dense 1.5 (1.5/1.0) | 3/3 | 0.007042 | N/Y/Y/Y |
| eval_025 | Nagoya Protocol article 1 — OBJECTIVE | both | 11 | 6 | 2/2 | D dense 2.0 (2.0/1.0) | 4/4 | 0.014085 | N/N/Y/Y |
| eval_026 | Budapest Treaty article 3 — Recognition and Effect of the Deposit | both | 2 | 4 | 3/3 | B dense 1.25 (1.25/1.0) | 2/2 | 0.004032 | N/Y/Y/Y |
| eval_026 | Budapest Treaty article 3 — Recognition and Effect of the Deposit | both | 2 | 4 | 3/3 | C dense 1.5 (1.5/1.0) | 2/2 | 0.008065 | N/Y/Y/Y |
| eval_026 | Budapest Treaty article 3 — Recognition and Effect of the Deposit | both | 2 | 4 | 3/3 | D dense 2.0 (2.0/1.0) | 2/2 | 0.016129 | N/Y/Y/Y |
| eval_026 | Budapest Treaty article 3 — Recognition and Effect of the Deposit | both | 2 | 4 | 3/3 | E BM25 0.75 (1.0/0.75) | 2/2 | -0.003906 | N/Y/Y/Y |
| eval_027 | Pct article 11 — Filing Date and Effects of the International Application | BM25 only | — | 3 | 9/9 | B dense 1.25 (1.25/1.0) | 11/— | 0.000000 | N/N/N/N |
| eval_027 | Pct article 11 — Filing Date and Effects of the International Application | BM25 only | — | 3 | 9/9 | C dense 1.5 (1.5/1.0) | 18/— | 0.000000 | N/N/N/N |
| eval_027 | Pct article 11 — Filing Date and Effects of the International Application | BM25 only | — | 3 | 9/9 | D dense 2.0 (2.0/1.0) | 22/— | 0.000000 | N/N/N/N |
| eval_027 | Pct article 11 — Filing Date and Effects of the International Application | BM25 only | — | 3 | 9/9 | E BM25 0.75 (1.0/0.75) | 12/— | -0.003968 | N/N/N/N |
| eval_028 | Madrid Protocol article 4 — Effects of International Registration | both | 8 | 17 | 9/9 | B dense 1.25 (1.25/1.0) | 8/8 | 0.003676 | N/N/N/Y |
| eval_028 | Madrid Protocol article 4 — Effects of International Registration | both | 8 | 17 | 9/9 | C dense 1.5 (1.5/1.0) | 7/7 | 0.007353 | N/N/N/Y |
| eval_028 | Madrid Protocol article 4 — Effects of International Registration | both | 8 | 17 | 9/9 | D dense 2.0 (2.0/1.0) | 7/7 | 0.014706 | N/N/N/Y |
| eval_028 | Madrid Protocol article 4 — Effects of International Registration | both | 8 | 17 | 9/9 | E BM25 0.75 (1.0/0.75) | 8/8 | -0.003247 | N/N/N/Y |
| eval_029 | Trips Agreement article 27 — Patentable Subject Matter | BM25 only | — | 1 | 2/2 | B dense 1.25 (1.25/1.0) | 18/— | 0.000000 | N/N/N/N |
| eval_029 | Trips Agreement article 27 — Patentable Subject Matter | BM25 only | — | 1 | 2/2 | C dense 1.5 (1.5/1.0) | 21/— | 0.000000 | N/N/N/N |
| eval_029 | Trips Agreement article 27 — Patentable Subject Matter | BM25 only | — | 1 | 2/2 | D dense 2.0 (2.0/1.0) | 21/— | 0.000000 | N/N/N/N |
| eval_029 | Trips Agreement article 27 — Patentable Subject Matter | BM25 only | — | 1 | 2/2 | E BM25 0.75 (1.0/0.75) | 21/— | -0.004098 | N/N/N/N |
| eval_030 | Nagoya Protocol article 6 — ACCESS TO GENETIC RESOURCES | both | 1 | 4 | 2/2 | B dense 1.25 (1.25/1.0) | 1/1 | 0.004098 | Y/Y/Y/Y |
| eval_030 | Nagoya Protocol article 6 — ACCESS TO GENETIC RESOURCES | both | 1 | 4 | 2/2 | C dense 1.5 (1.5/1.0) | 1/1 | 0.008197 | Y/Y/Y/Y |
| eval_030 | Nagoya Protocol article 6 — ACCESS TO GENETIC RESOURCES | both | 1 | 4 | 2/2 | D dense 2.0 (2.0/1.0) | 1/1 | 0.016393 | Y/Y/Y/Y |
| eval_030 | Nagoya Protocol article 6 — ACCESS TO GENETIC RESOURCES | both | 1 | 4 | 2/2 | E BM25 0.75 (1.0/0.75) | 1/1 | -0.003906 | Y/Y/Y/Y |
| eval_030 | Nagoya Protocol article 5 — FAIR AND EQUITABLE BENEFIT-SHARING | dense only | 20 | — | 29/— | B dense 1.25 (1.25/1.0) | 20/— | 0.003125 | N/N/N/N |
| eval_030 | Nagoya Protocol article 5 — FAIR AND EQUITABLE BENEFIT-SHARING | dense only | 20 | — | 29/— | C dense 1.5 (1.5/1.0) | 20/— | 0.006250 | N/N/N/N |
| eval_030 | Nagoya Protocol article 5 — FAIR AND EQUITABLE BENEFIT-SHARING | dense only | 20 | — | 29/— | D dense 2.0 (2.0/1.0) | 20/— | 0.012500 | N/N/N/N |
| eval_030 | Nagoya Protocol article 5 — FAIR AND EQUITABLE BENEFIT-SHARING | dense only | 20 | — | 29/— | E BM25 0.75 (1.0/0.75) | 20/— | 0.000000 | N/N/N/N |
| eval_031 | Gi Act section 9 — A geographical indication | dense only | 4 | — | 11/— | B dense 1.25 (1.25/1.0) | 9/9 | 0.003906 | N/N/N/Y |
| eval_031 | Gi Act section 9 — A geographical indication | dense only | 4 | — | 11/— | C dense 1.5 (1.5/1.0) | 9/9 | 0.007812 | N/N/N/Y |
| eval_031 | Gi Act section 9 — A geographical indication | dense only | 4 | — | 11/— | D dense 2.0 (2.0/1.0) | 9/9 | 0.015625 | N/N/N/Y |
| eval_031 | Gi Act section 9 — A geographical indication | dense only | 4 | — | 11/— | E BM25 0.75 (1.0/0.75) | 9/9 | 0.000000 | N/N/N/Y |
| eval_031 | Trips Agreement article 22 — Protection of Geographical Indications | both | 11 | 2 | 2/2 | B dense 1.25 (1.25/1.0) | 3/3 | 0.003521 | N/Y/Y/Y |
| eval_031 | Trips Agreement article 22 — Protection of Geographical Indications | both | 11 | 2 | 2/2 | C dense 1.5 (1.5/1.0) | 3/3 | 0.007042 | N/Y/Y/Y |
| eval_031 | Trips Agreement article 22 — Protection of Geographical Indications | both | 11 | 2 | 2/2 | D dense 2.0 (2.0/1.0) | 4/4 | 0.014085 | N/N/Y/Y |
| eval_031 | Trips Agreement article 22 — Protection of Geographical Indications | both | 11 | 2 | 2/2 | E BM25 0.75 (1.0/0.75) | 3/3 | -0.004032 | N/Y/Y/Y |
| eval_032 | Designs Act section 4 — A design which | dense only | 13 | — | 21/— | B dense 1.25 (1.25/1.0) | 14/— | 0.003425 | N/N/N/N |
| eval_032 | Designs Act section 4 — A design which | dense only | 13 | — | 21/— | C dense 1.5 (1.5/1.0) | 14/— | 0.006849 | N/N/N/N |
| eval_032 | Designs Act section 4 — A design which | dense only | 13 | — | 21/— | D dense 2.0 (2.0/1.0) | 14/— | 0.013699 | N/N/N/N |
| eval_032 | Designs Act section 4 — A design which | dense only | 13 | — | 21/— | E BM25 0.75 (1.0/0.75) | 14/— | 0.000000 | N/N/N/N |

### Improved, degraded, and unchanged target counts

Here, improved/degraded/unchanged refer to returned Top-10 rank (a previously absent target entering Top-10 counts as improved; a returned target becoming absent counts as degraded). Raw rank movement that does not change actual Top-10 status remains visible in the preceding table.

| Configuration vs baseline | Improved | Degraded | Unchanged |
|---|---:|---:|---:|
| B dense 1.25 (1.25/1.0) | 6 | 5 | 29 |
| C dense 1.5 (1.5/1.0) | 7 | 6 | 27 |
| D dense 2.0 (2.0/1.0) | 8 | 7 | 25 |
| E BM25 0.75 (1.0/0.75) | 6 | 5 | 29 |

## 7. Dense-only/BM25-only/both/neither target groups

Groups are assigned once from the highest-ranked baseline candidate matching each expected provision, then held fixed across weight settings. Values are target-instance hit rates, not document counts.

| Source group | Targets | Config | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|---|---:|---|---:|---:|---:|---:|---:|
| dense only | 4 | A baseline (1.0/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.2500 | 0.0357 |
| dense only | 4 | B dense 1.25 (1.25/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0694 |
| dense only | 4 | C dense 1.5 (1.5/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0694 |
| dense only | 4 | D dense 2.0 (2.0/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0694 |
| dense only | 4 | E BM25 0.75 (1.0/0.75) | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0694 |
| BM25 only | 5 | A baseline (1.0/1.0) | 0.0000 | 0.4000 | 0.4000 | 0.6000 | 0.2222 |
| BM25 only | 5 | B dense 1.25 (1.25/1.0) | 0.0000 | 0.2000 | 0.2000 | 0.2000 | 0.0667 |
| BM25 only | 5 | C dense 1.5 (1.5/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| BM25 only | 5 | D dense 2.0 (2.0/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| BM25 only | 5 | E BM25 0.75 (1.0/0.75) | 0.0000 | 0.2000 | 0.2000 | 0.2000 | 0.0667 |
| both | 29 | A baseline (1.0/1.0) | 0.4828 | 0.7241 | 0.8966 | 1.0000 | 0.6461 |
| both | 29 | B dense 1.25 (1.25/1.0) | 0.5172 | 0.7241 | 0.8966 | 1.0000 | 0.6655 |
| both | 29 | C dense 1.5 (1.5/1.0) | 0.5172 | 0.7586 | 0.8966 | 1.0000 | 0.6650 |
| both | 29 | D dense 2.0 (2.0/1.0) | 0.5172 | 0.6897 | 0.8966 | 1.0000 | 0.6552 |
| both | 29 | E BM25 0.75 (1.0/0.75) | 0.5172 | 0.7241 | 0.8966 | 1.0000 | 0.6655 |
| neither | 2 | A baseline (1.0/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| neither | 2 | B dense 1.25 (1.25/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| neither | 2 | C dense 1.5 (1.5/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| neither | 2 | D dense 2.0 (2.0/1.0) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| neither | 2 | E BM25 0.75 (1.0/0.75) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## 8. Important failure-case analysis

The provisions below are diagnostics only; no rules are keyed to these documents or evaluation IDs.

| Case | Global dense rank | Global BM25 rank | Filtered diagnostic | Baseline raw/Top-10 | Weighted ranks raw/Top-10 (B / C / D / E) |
|---|---:|---:|---|---|---|
| eval_029: Patent Act 2024 section 3 | — | — | filtered dense —, BM25 — (India) | —/— | —/— ; —/— ; —/— ; —/— |
| eval_030: Biological Diversity Act 2002 section 6 | — | — | filtered dense 10, BM25 16 (India) | —/— | —/— ; —/— ; —/— ; —/— |
| eval_031: Gi Act section 9 | 4 | — | filtered dense 4, BM25 — (India) | 11/— | 9/9 ; 9/9 ; 9/9 ; 9/9 |
| eval_032: Designs Act section 4 | 13 | — | filtered dense 5, BM25 — (India) | 21/— | 14/— ; 14/— ; 14/— ; 14/— |

Interpretation:
- Patent Act Section 3 (eval_029) is absent from the global dense/BM25 pools and also absent from the India-filtered pools; weights cannot recover a missing candidate.
- Biological Diversity Act Section 6 (eval_030) is absent globally but recoverable through India-filtered retrieval (the report shows its current filtered ranks). Weighting the global lists cannot fix that candidate-generation miss.
- GI Act Section 9 and Designs Act Section 4 enter the global candidate union. Their raw and final weighted ranks quantify whether dense weight counters fusion displacement; filtered ranks are diagnostic only.

## 9. Aggregate answers and regression analysis

- **Dense-only targets:** their Top-10 hit rate rises from 1/4 to 2/4 under every weighted variant, but Top-5 remains 0/4. The gain is limited to late retrieval.
- **BM25-only targets:** Top-5 hits fall from 2/5 at baseline to 1/5 with B or E, and 0/5 with C or D. Larger dense weights strongly suppress this group.
- **Targets in both lists:** Top-5 remains 26/29 under every tested weighting, while some ranks shift. Thus source-group gains do not translate into improved overall R@5.
- **GI Act Section 9:** raw rank improves from 11 to 9 for every weighted variant; it enters Top-10 but remains outside Top-5. This isolated recovery does not offset other comparison losses.
- **Designs Act Section 4:** raw rank improves from 21 to 14 under the weighted variants but remains outside returned Top-10. Its filtered dense rank 5 does not change the global candidate ranks used here.
- **Biological Diversity Act Section 6 and Patent Act Section 3 (eval_029):** both are absent from their global candidate lists, so no tested weighting can recover them. Section 6 is present only in India-filtered candidates; Section 3 is absent there too.
- **Overall cutoffs:** every weighted variant increases R@1 by 0.0095, but lowers R@3, R@5, R@10, and MRR. The R@5 and MRR reductions are meaningful and grow with dense weight.
- **Comparisons:** mean target coverage@5 drops from 0.4583 to 0.3333 for every weighted variant; coverage@10 stays 0.4583. Jurisdiction mix shifts toward India, but that does not mean expected targets were retrieved.
- **Explicit provisions:** all three remain rank 1 in every configuration; this evaluation does not show exact-provision regression.
- **Categories:** the clearest gain is Ayurveda/food/regulatory, while Designs and International treaties regress at stronger dense weights. The category table does not support a broad category-neutral improvement.

A higher dense multiplier can only help a target by changing score ordering among candidates already present. Compare the source-group, comparison, category, and explicit-provision tables together.

Explicit-provision regression check:

| Config | eval_033 Patent Act §83 | eval_034 Nagoya Article 6 | eval_035 Designs Act §34 |
|---|---:|---:|---:|
| A baseline (1.0/1.0) | 1 | 1 | 1 |
| B dense 1.25 (1.25/1.0) | 1 | 1 | 1 |
| C dense 1.5 (1.5/1.0) | 1 | 1 | 1 |
| D dense 2.0 (2.0/1.0) | 1 | 1 | 1 |
| E BM25 0.75 (1.0/0.75) | 1 | 1 | 1 |

## 10. Recommendation

Production implementation is **not justified by this offline experiment alone**. Consider a future controlled implementation only if one configuration improves R@5, R@10, and MRR without unacceptable R@1, explicit-provision, comparison, or category regressions. A configuration that wins only a single cutoff is not sufficient.
The current 1.0/1.0 weighting remains the conservative choice unless the tables show a broadly consistent gain. Candidate-absent failures require candidate-generation work rather than weighting.

## 11. Validation and unchanged-state checks

- Baseline RRF K: **60**; required value 60: **PASS**.
- Chroma records before / after: **1349 / 1349**; expected 1,349: **PASS**.
- Corpus, extracted documents, chunks, eval set, and production retriever hashes unchanged during experiment: **PASS**.
- Candidate scoring deterministic when repeated from preserved candidate lists: **PASS**.
- Each answerable query received one current, unweighted global dense/BM25 candidate-pool fetch. Four additional current, unweighted jurisdiction-filtered diagnostic runs (one per specified case) verified the comparison observations; no weighted configuration triggered retrieval.
- No Chroma add/update/delete operation was used; no production retrieval parameters or behavior were modified.
