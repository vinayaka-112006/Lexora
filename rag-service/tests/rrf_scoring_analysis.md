# Stage 6F RRF Scoring Analysis

## 1. Executive summary

Analyzed **35 answerable queries** and **40 expected target instances**. The analysis reproduced production Top-10 rankings for 35/35 queries using the fixed candidate lists and Stage 6D score formula.

The current full-evaluation baseline from the checked-in evaluator is R@1 **0.3857**, R@3 **0.5952**, R@5 **0.7381**, R@10 **0.8810**, MRR **0.5711**. Candidate-list score reproduction mismatches: **0**.

The evidence separates two broad problems: targets missing from candidate generation cannot be fixed by RRF; targets present in one or both lists can be outranked by candidates with more combined rank contributions. All competitor observations below are descriptive and do not establish semantic relevance or legal correctness.

## 2. Current RRF formula and explanation

For dense rank `d`, BM25 rank `b`, and current `RRF_K=60`, Stage 6D computes:

```text
base_rrf = (1 / (60 + d), if dense candidate else 0)
         + (1 / (60 + b), if BM25 candidate else 0)
final_score = base_rrf + intent_bonus + explicit_provision_bonus
```

Results sort by descending final score, then BM25 rank, dense rank, and stable chunk ID. Candidate pools default to 20. Intent bonuses are small fixed/configurable additions; an exact explicit-provision match can receive the configured explicit bonus.

## 3. Aggregate target-source statistics

- Target instances: **40**.
- Dense only: **4**; BM25 only: **5**; both: **29**; neither: **2**.
- Failure targets (hybrid rank >5 or absent from returned Top-10): **12**.
- Among failure targets: both candidate lists **3**; exactly one list **7**; neither list **2** (the latter includes all absent targets, including any not in the failure subset).
- Failed dense-only targets with at least one higher-ranked BM25-supported competitor: **7**.
- Failed BM25-only targets with at least one higher-ranked dense-supported competitor: **6**.
- Substantially worse than dense: **5**; substantially worse than BM25: **3**. Definition: raw RRF rank is at least 5 positions below that source rank; targets absent from the scored candidate union are excluded.
- Mean/median dense rank among failed targets where present: **8.71/8.0**.
- Mean/median BM25 rank among failed targets where present: **10.67/13.0**.
- Mean/median hybrid rank among failed targets returned in Top-10: **7.80/8.0**.

- Mean/median raw RRF rank among failed targets present in the scored union: **13.10/10.0**.
### Candidate-source group comparison

Counts below are expected target instances, not all retrieved chunks. An RRF score distribution cannot alone measure legal relevance.

| Target source group | Targets | Mean base RRF | In hybrid Top-5 | In hybrid Top-10 |
|---|---:|---:|---:|---:|
| both | 29 | 0.030833 | 26 | 29 |
| dense only | 4 | 0.014554 | 0 | 1 |
| BM25 only | 5 | 0.015788 | 2 | 3 |

Across all retrieved candidates (not only expected targets), source group frequencies are:

| Candidate source group | Candidate rows across queries | Rows in actual Top-10 | Mean dense rank | Mean BM25 rank |
|---|---:|---:|---:|---:|
| both | 314 | 260 | 9.12 | 8.79 |
| dense only | 386 | 35 | 11.62 | — |
| BM25 only | 386 | 37 | — | 11.89 |
| neither | 18 | 18 | — | — |

Two-source candidates make up **28.4%** of the candidate rows and **74.3%** of actual Top-10 slots across these queries. This is consistent with RRF's additive two-signal advantage, but it is not evidence that those results are less relevant or that mediocre individual ranks should be disregarded.

## 4. Target-level failure table

This table includes every expected target outside hybrid Top-5 or absent from Top-10. `Not returned (raw RRF #N)` means a candidate received a score but did not appear in the final Top-10; `absent` means neither global candidate list contained it (unless explicitly injected).

| ID | Category | Query | Intent | Expected target | Dense r / distance | BM25 r / score | Dense RRF | BM25 RRF | Base RRF | Intent + explicit | Final score | Raw RRF rank / actual Top-10 rank | Candidate source |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| eval_002 | definitions | For biodiversity research in India, how does the Act define biological resources? | definition | Biological Diversity Act 2002 / India / section 2 — Definitions | None / — | 1 / 40.933162 | 0.000000 | 0.016393 | 0.016393 | 0.006000 + 0.000000 | 0.022393 | 11 / not returned | BM25 only |
| eval_009 | patent_procedure | What information belongs in a patent specification filed in India? | general | Patent Act 2024 / India / section 10 — Contents of specifications | 14 / 0.399482 | 17 / 29.256622 | 0.013514 | 0.012987 | 0.026501 | 0.000000 + 0.000000 | 0.026501 | 8 / 8 | both |
| eval_010 | patent_procedure | What legal effect follows when the Controller grants a patent? | general | Patent Act 2024 / India / section 43 — Grant of patents | 1 / 0.281712 | None / — | 0.016393 | 0.000000 | 0.016393 | 0.000000 + 0.000000 | 0.016393 | 7 / 7 | dense only |
| eval_011 | trademarks | What grounds could prevent registration of a proposed brand name as a trademark? | general | Trademarks Act / India / section 9 — untitled | None / — | 12 / 26.065490 | 0.000000 | 0.013889 | 0.013889 | 0.000000 + 0.000000 | 0.013889 | 20 / not returned | BM25 only |
| eval_023 | ayurveda_food_regulatory | What does the Ayurveda Aahara regulation require for labeling these products? | general | Fssai Ayurveda Aahara Regulations 2022 / India / section 12 — Labelling of Ayurveda Aahara .- The labelling of Ayurveda Aahara shall be in accordance wi th | 1 / 0.196414 | 14 / 18.682115 | 0.016393 | 0.013514 | 0.029907 | 0.000000 + 0.000000 | 0.029907 | 6 / 6 | both |
| eval_027 | international_treaties | What is the effect of an international patent application under the PCT? | definition | Pct / International / article 11 — Filing Date and Effects of the International Application | None / — | 3 / 34.336308 | 0.000000 | 0.015873 | 0.015873 | 0.004000 + 0.000000 | 0.019873 | 9 / 9 | BM25 only |
| eval_028 | international_treaties | What effect does an international trademark registration have under the Madrid Protocol? | general | Madrid Protocol / International / article 4 — Effects of International Registration | 8 / 0.459405 | 17 / 22.117397 | 0.014706 | 0.012987 | 0.027693 | 0.000000 + 0.000000 | 0.027693 | 9 / 9 | both |
| eval_029 | comparisons | Compare India?s exclusions from patentability with TRIPS rules on patentable subject matter. | comparison | Patent Act 2024 / India / section 3 — What are not inventions | — | — | — | — | — | — | — | absent / not returned | neither (not explicitly injected) |
| eval_030 | comparisons | How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts? | general | Biological Diversity Act 2002 / India / section 6 — Application for intellectual property rights not to be made without approval of National | — | — | — | — | — | — | — | absent / not returned | neither (not explicitly injected) |
| eval_030 | comparisons | How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts? | general | Nagoya Protocol / International / article 5 — FAIR AND EQUITABLE BENEFIT-SHARING | 20 / 0.432550 | None / — | 0.012500 | 0.000000 | 0.012500 | 0.000000 + 0.000000 | 0.012500 | 29 / not returned | dense only |
| eval_031 | comparisons | Compare Indian protection criteria for geographical indications with TRIPS protection of GIs. | comparison | Gi Act / India / section 9 — A geographical indication | 4 / 0.515147 | None / — | 0.015625 | 0.000000 | 0.015625 | 0.000000 + 0.000000 | 0.015625 | 11 / not returned | dense only |
| eval_032 | comparisons | How does India?s design protection framework compare with the Hague Agreement?s international registration effects? | comparison | Designs Act / India / section 4 — A design which | 13 / 0.490892 | None / — | 0.013699 | 0.000000 | 0.013699 | 0.000000 + 0.000000 | 0.013699 | 21 / not returned | dense only |

### Higher-ranked competitors for present targets

Up to five results that ranked above each failed target are shown. Contributions are calculated at K=60; a single-source competitor has a zero contribution from the other source.

#### eval_002 — Biological Diversity Act 2002 / India / section 2 (actual hybrid rank: not returned (raw RRF #11); raw RRF rank: 11)

| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Biological Diversity Act 2002 / India / section 3 | 8 | 2 | 0.014706 | 0.016129 | 0.036835 |
| 2 | Biological Diversity Act 2002 / India / section 36 | 14 | 12 | 0.013514 | 0.013889 | 0.033402 |
| 3 | Biological Diversity Amendment 2023 / India / section 26 | 1 | 6 | 0.016393 | 0.015152 | 0.031545 |
| 4 | Biological Diversity Amendment 2023 / India / section 23 | 7 | 3 | 0.014925 | 0.015873 | 0.030798 |
| 5 | Biological Diversity Amendment 2023 / India / section 18 | 4 | 15 | 0.015625 | 0.013333 | 0.028958 |

#### eval_009 — Patent Act 2024 / India / section 10 (actual hybrid rank: 8; raw RRF rank: 8)

| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Patent Act 2024 / India / section 13 | 6 | 1 | — | — | 0.031545 |
| 2 | Patent Act 2024 / India / section 8 | 3 | 8 | — | — | 0.030579 |
| 3 | Patent Act 2024 / India / section 33 | 12 | 2 | — | — | 0.030018 |
| 4 | Patent Act 2024 / India / section 25 | 4 | 10 | — | — | 0.029911 |
| 5 | Patent Rules 2024 / India / general — | 9 | 7 | — | — | 0.029418 |

#### eval_010 — Patent Act 2024 / India / section 43 (actual hybrid rank: 7; raw RRF rank: 7)

| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Patent Act 2024 / India / section 20 | 4 | 4 | — | — | 0.031250 |
| 2 | Patent Act 2024 / India / section 117E | 6 | 5 | — | — | 0.030536 |
| 3 | Patent Act 2024 / India / section 51 | 5 | 20 | — | — | 0.027885 |
| 4 | Patent Act 2024 / India / section 44 | 16 | 11 | — | — | 0.027242 |
| 5 | Patent Act 2024 / India / section 132 | 12 | 18 | — | — | 0.026709 |

#### eval_011 — Trademarks Act / India / section 9 (actual hybrid rank: not returned (raw RRF #20); raw RRF rank: 20)

| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Trademarks Act / India / section 11 | 1 | 5 | 0.016393 | 0.015385 | 0.031778 |
| 2 | Trademarks Act / India / section 11 | 6 | 2 | 0.015152 | 0.016129 | 0.031281 |
| 3 | Trademarks Act / India / section 27 | 3 | 11 | 0.015873 | 0.014085 | 0.029958 |
| 4 | Trademarks Act / India / section 70 | 18 | 1 | 0.012821 | 0.016393 | 0.029214 |
| 5 | Trademarks Act / India / section 36 | 7 | 14 | 0.014925 | 0.013514 | 0.028439 |

#### eval_023 — Fssai Ayurveda Aahara Regulations 2022 / India / section 12 (actual hybrid rank: 6; raw RRF rank: 6)

| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Fssai Ayurveda Aahara Regulations 2022 / India / section 3 | 5 | 1 | — | — | 0.031778 |
| 2 | Fssai Ayurveda Aahara Regulations 2022 / India / section 14 | 4 | 2 | — | — | 0.031754 |
| 3 | Fssai Ayurveda Aahara Regulations 2022 / India / section 13 | 3 | 5 | — | — | 0.031258 |
| 4 | Fssai Ayurveda Aahara Regulations 2022 / India / section 2 | 9 | 4 | — | — | 0.030118 |
| 5 | Fssai Ayurveda Aahara Regulations 2022 / India / section 10 | 11 | 3 | — | — | 0.029958 |

#### eval_027 — Pct / International / article 11 (actual hybrid rank: 9; raw RRF rank: 9)

| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Pct / International / article 45 | 1 | 4 | — | — | 0.032018 |
| 2 | Pct / International / article 4 | 6 | 10 | — | — | 0.029437 |
| 3 | Wipo Gratk Treaty 2024 / International / article 10 | 14 | 9 | — | — | 0.028006 |
| 4 | Pct / International / article 24 | 12 | 11 | — | — | 0.027973 |
| 5 | Wipo Gratk Treaty 2024 / International / article 19 | 17 | 8 | — | — | 0.027693 |

#### eval_028 — Madrid Protocol / International / article 4 (actual hybrid rank: 9; raw RRF rank: 9)

| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Madrid Protocol / International / general — | 1 | 1 | — | — | 0.032787 |
| 2 | Madrid Protocol / International / general — | 2 | 2 | — | — | 0.032258 |
| 3 | Madrid Protocol / International / article 1 | 3 | 4 | — | — | 0.031498 |
| 4 | Madrid Protocol / International / article 9 | 7 | 6 | — | — | 0.030077 |
| 5 | Madrid Protocol / International / article 9bis | 11 | 8 | — | — | 0.028790 |

#### eval_030 — Nagoya Protocol / International / article 5 (actual hybrid rank: not returned (raw RRF #29); raw RRF rank: 29)

| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Nagoya Protocol / International / article 16 | 4 | 1 | 0.015625 | 0.016393 | 0.032018 |
| 2 | Nagoya Protocol / International / article 6 | 1 | 4 | 0.016393 | 0.015625 | 0.032018 |
| 3 | Nagoya Protocol / International / article 2 | 3 | 2 | 0.015873 | 0.016129 | 0.032002 |
| 4 | Nagoya Protocol / International / article 10 | 2 | 3 | 0.016129 | 0.015873 | 0.032002 |
| 5 | Nagoya Protocol / International / article 32 | 5 | 6 | 0.015385 | 0.015152 | 0.030536 |

#### eval_031 — Gi Act / India / section 9 (actual hybrid rank: not returned (raw RRF #11); raw RRF rank: 11)

| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Gi Act / India / section 1 | 2 | 4 | 0.016129 | 0.015625 | 0.031754 |
| 2 | Trips Agreement / International / article 22 | 11 | 2 | 0.014085 | 0.016129 | 0.030214 |
| 3 | Gi Act / India / section 21 | 1 | 13 | 0.016393 | 0.013699 | 0.030092 |
| 4 | Trips Agreement / International / article 24 | 7 | 9 | 0.014925 | 0.014493 | 0.029418 |
| 5 | Gi Act / India / section 5 | 13 | 8 | 0.013699 | 0.014706 | 0.028405 |

#### eval_032 — Designs Act / India / section 4 (actual hybrid rank: not returned (raw RRF #21); raw RRF rank: 21)

| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Hague Agreement / International / article 14 | 1 | 2 | 0.016393 | 0.016129 | 0.032522 |
| 2 | Hague Agreement / International / article 12 | 4 | 5 | 0.015625 | 0.015385 | 0.031010 |
| 3 | Hague Agreement / International / article 1 | 9 | 1 | 0.014493 | 0.016393 | 0.030886 |
| 4 | Hague Agreement / International / general — | 8 | 3 | 0.014706 | 0.015873 | 0.030579 |
| 5 | Madrid Protocol / International / article 4 | 3 | 11 | 0.015873 | 0.014085 | 0.029958 |

## 5. Detailed comparison-query analysis

The four Stage 6C/6D comparison items are reconstructed from the current global candidate pools. Filtered ranks are a separate diagnostic run within the target's own jurisdiction and do not affect global scores.

### eval_029

Query: Compare India?s exclusions from patentability with TRIPS rules on patentable subject matter.
Intent: `comparison`; requested jurisdictions: `['India']`.

| Expected target | Global dense rank / distance | Global BM25 rank / score | Dense RRF | BM25 RRF | Base RRF | Intent bonus | Explicit bonus | Final score | Raw RRF rank / actual Top-10 rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Patent Act 2024 section 3 — What are not inventions | absent | absent | — | — | — | — | — | — | absent / not returned |
| Trips Agreement article 27 — Patentable Subject Matter | None / — | 1 / 43.249537 | 0.000000 | 0.016393 | 0.016393 | 0.000000 | 0.000000 | 0.016393 | 2 / 2 |

Filtered-candidate check:
- Patent Act 2024 section 3 (India): filtered dense rank `None`, BM25 rank `None`.
- Trips Agreement article 27 (International): filtered dense rank `5`, BM25 rank `1`.

### eval_030

Query: How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts?
Intent: `general`; requested jurisdictions: `['India', 'International']`.

| Expected target | Global dense rank / distance | Global BM25 rank / score | Dense RRF | BM25 RRF | Base RRF | Intent bonus | Explicit bonus | Final score | Raw RRF rank / actual Top-10 rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Biological Diversity Act 2002 section 6 — Application for intellectual property rights not to be made without approval of National | absent | absent | — | — | — | — | — | — | absent / not returned |
| Nagoya Protocol article 6 — ACCESS TO GENETIC RESOURCES | 1 / 0.267817 | 4 / 66.928151 | 0.016393 | 0.015625 | 0.032018 | 0.000000 | 0.000000 | 0.032018 | 2 / 2 |
| Nagoya Protocol article 5 — FAIR AND EQUITABLE BENEFIT-SHARING | 20 / 0.432550 | None / — | 0.012500 | 0.000000 | 0.012500 | 0.000000 | 0.000000 | 0.012500 | 29 / not returned |

Filtered-candidate check:
- Biological Diversity Act 2002 section 6 (India): filtered dense rank `10`, BM25 rank `16`.
- Nagoya Protocol article 6 (International): filtered dense rank `1`, BM25 rank `4`.
- Nagoya Protocol article 5 (International): filtered dense rank `13`, BM25 rank `None`.

### eval_031

Query: Compare Indian protection criteria for geographical indications with TRIPS protection of GIs.
Intent: `comparison`; requested jurisdictions: `['India']`.

| Expected target | Global dense rank / distance | Global BM25 rank / score | Dense RRF | BM25 RRF | Base RRF | Intent bonus | Explicit bonus | Final score | Raw RRF rank / actual Top-10 rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Gi Act section 9 — A geographical indication | 4 / 0.515147 | None / — | 0.015625 | 0.000000 | 0.015625 | 0.000000 | 0.000000 | 0.015625 | 11 / not returned |
| Trips Agreement article 22 — Protection of Geographical Indications | 11 / 0.541938 | 2 / 37.047093 | 0.014085 | 0.016129 | 0.030214 | 0.000000 | 0.000000 | 0.030214 | 2 / 2 |

Filtered-candidate check:
- Gi Act section 9 (India): filtered dense rank `4`, BM25 rank `None`.
- Trips Agreement article 22 (International): filtered dense rank `2`, BM25 rank `2`.

### eval_032

Query: How does India?s design protection framework compare with the Hague Agreement?s international registration effects?
Intent: `comparison`; requested jurisdictions: `['India', 'International']`.

| Expected target | Global dense rank / distance | Global BM25 rank / score | Dense RRF | BM25 RRF | Base RRF | Intent bonus | Explicit bonus | Final score | Raw RRF rank / actual Top-10 rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Designs Act section 4 — A design which | 13 / 0.490892 | None / — | 0.013699 | 0.000000 | 0.013699 | 0.000000 | 0.000000 | 0.013699 | 21 / not returned |
| Hague Agreement article 14 — Effects of the International Registration | 1 / 0.379150 | 2 / 42.128449 | 0.016393 | 0.016129 | 0.032522 | 0.000000 | 0.000000 | 0.032522 | 1 / 1 |

Filtered-candidate check:
- Designs Act section 4 (India): filtered dense rank `5`, BM25 rank `None`.
- Hague Agreement article 14 (International): filtered dense rank `1`, BM25 rank `2`.

## 6. Dense vs BM25 vs hybrid

- Dense-supported failed targets with BM25-supported higher competitors: **7**. This describes co-occurrence, not causal proof.
- BM25-supported failed targets with dense-supported higher competitors: **6**.
- Targets in both candidate lists but outside Top-5: **3**; targets in exactly one list but outside Top-5: **7**; targets absent from both candidate lists: **2**.
- Substantial rank displacement threshold: hybrid rank ≥ source rank + 5. Dense comparisons: **5**; BM25 comparisons: **3**.
- Two-list candidates receive two positive RRF terms, so they can outscore single-list candidates even when each individual rank is less favorable. The group table above measures the pattern among expected targets; it does not show that every two-list result is more relevant.
- BM25 may return exact names, section headings, and legal terms that dense search ranks lower; the competitor tables show concrete instances through source ranks and raw scores, without attributing correctness.

## 7. RRF-K sensitivity analysis

Each K uses the same per-query dense/BM25 candidate lists, then recomputes RRF and preserves current intent/explicit bonuses and current post-fusion behavior. Production remains K=60.

| Hypothetical K | R@1 | R@3 | R@5 | R@10 | MRR | Comparison coverage@5 | Comparison coverage@10 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 0.3571 | 0.6238 | 0.7381 | 0.9095 | 0.5575 | 0.4583 | 0.4583 |
| 30 | 0.3571 | 0.5952 | 0.7095 | 0.8810 | 0.5475 | 0.4583 | 0.4583 |
| 60 | 0.3857 | 0.5952 | 0.7381 | 0.8810 | 0.5711 | 0.4583 | 0.4583 |
| 100 | 0.3857 | 0.5952 | 0.7095 | 0.8524 | 0.5670 | 0.4583 | 0.4583 |

Compared with K=60, K=10 raises R@3 by +0.0286 and R@10 by +0.0286, but lowers R@1 by -0.0286 and MRR by -0.0136; comparison coverage does not change. Thus K materially changes some rank cutoffs on this set, but offers no comparison-query recovery and has a real tradeoff.
K changes affect only candidates already present in the fixed union. No K value can recover an expected target missing from both candidate lists. Treat these differences as exploratory until reproduced on independent queries.

## 8. Intent-bonus sensitivity analysis

The offline ablation sets only the current intent bonus to zero; candidate generation, K=60, and explicit-provision bonus remain unchanged.

| Ranking mode | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| Production bonuses | 0.3857 | 0.5952 | 0.7381 | 0.8810 | 0.5711 |
| Intent bonus zeroed | 0.3000 | 0.5667 | 0.7095 | 0.8810 | 0.5190 |

Expected-target ranks changed for **5/40** targets: **4** ranked better with the production bonus and **1** ranked worse (ties/unavailable ranks excluded from those counts). The observed bonus values span 0.0000 to 0.0060. The full metric difference is R@1 -0.0857, R@3 -0.0286, R@5 -0.0286, R@10 +0.0000, and MRR -0.0521 with the intent bonus zeroed. In this set the bonus materially changes target ordering and aggregate metrics, although it cannot add a target absent from both candidate lists.

## 9. Root-cause assessment

- **Candidate generation:** the decisive limitation for targets absent from both global pools. RRF cannot recover them. The four comparison diagnostics test whether jurisdiction-filtered pools contain those provisions.
- **RRF fusion:** relevant where targets appear in a source list but rank beyond the returned cutoff. The one-source vs two-source contribution pattern explains how a result can be outranked; the competitor tables quantify those cases.
- **Intent bonus:** the zero-bonus ablation changes aggregate metrics and several target ranks, so it is a material part of current ordering for this set. It can address near-tie ranking but cannot fix candidate absence; any tuning needs broader validation.
- **Overall:** likely a combination of candidate-generation misses and fusion competition, not a single global cause. The report distinguishes these observable cases and avoids assigning semantic causation.
- **RRF_K=60:** lower K raises R@3/R@10 but lowers R@1/MRR here, without changing comparison coverage. That tradeoff makes K a possible general sensitivity parameter, not a proven improvement; it needs independent validation.

## 10. Generalizable recommendations for a possible future change

1. Separate candidate absence from fusion displacement in subsequent experiments; only test candidate generation when the target is missing from the global union.
2. If testing fusion, compare a small set of principled rank-fusion alternatives on fixed candidate pools, with full-query metrics and per-category safeguards.
3. Retain deterministic tie-breaking and evaluate source-specific rank changes, not only aggregate recall.
4. Assess effects on explicit provisions, comparison evidence, jurisdiction filters, and non-answerable queries before accepting a change.
5. Validate any promising result on a separate, unchanged holdout or newly authored evaluation set before changing production.

### Approaches that would overfit and should not be used

- boosts keyed to evaluation IDs, query text, treaty/document names, specific sections/articles, or individual expected targets;
- a blanket India preference or a manual score boost for one jurisdiction;
- choosing a new K solely because it improves these 35 answerable queries;
- changing the evaluation labels or set to make a proposed ranker pass;
- interpreting rank overlap or RRF score as a legal correctness judgment.

## 11. Validation and unchanged-state checks

- Exact reproduction check against `retrieve()` Top-10: **35/35** matches; no mismatches.
- The script performs retrieval queries only; it does not call Chroma add/update/delete operations.
- It reads `eval_set.json` and chunks through the current retriever; it writes only this Markdown report.
- Current full evaluation baseline: R@1 **0.3857**, R@3 **0.5952**, R@5 **0.7381**, R@10 **0.8810**, MRR **0.5711**.
- `RRF_K=60` and production retrieval behavior were not changed.
