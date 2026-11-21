# Stage 6K Holdout / Generalization Evaluation

## Dataset composition

- New queries: 49; answerable: 43; abstention/out-of-scope: 6.
- Categories: {'patentability': 4, 'patent_procedure': 5, 'trademarks': 4, 'geographical_indications': 3, 'designs': 3, 'biological_diversity': 5, 'traditional_knowledge': 3, 'ayurveda_food_regulatory': 3, 'international_treaties': 5, 'comparisons': 4, 'explicit_provisions': 4, 'insufficient_evidence': 5, 'out_of_scope': 1}.
- Query types: {'normal': 35, 'comparison': 4, 'explicit_provision': 4, 'abstention': 6}.
- Jurisdictions: {'India': 30, 'International': 14, 'all': 5}.
- Target provisions were resolved from existing chunks and checked against indexed Chroma records.
- Query text was authored for this holdout; the existing 42-query set was not changed.

## Stage 6D and Stage 6J results

Stage 6D is the same production code with morphology disabled. Stage 6J uses the same set and settings with only the morphology flag enabled.

| Metric | Stage 6D (disabled) | Stage 6J (enabled) | Delta |
|---|---:|---:|---:|
| recall@1 | 0.3953 | 0.4651 | +0.0698 |
| recall@3 | 0.6395 | 0.5930 | -0.0465 |
| recall@5 | 0.6395 | 0.6628 | +0.0233 |
| recall@10 | 0.7209 | 0.7209 | +0.0000 |
| mrr | 0.5279 | 0.5586 | +0.0307 |

## Category-level comparison

| Category | Stage 6D (R@1/R@3/R@5/R@10/MRR) | Stage 6J (R@1/R@3/R@5/R@10/MRR) | Assessment |
|---|---|---|---|
| ayurveda_food_regulatory | 0.6667 / 0.6667 / 0.6667 / 0.6667 / 0.6667 | 0.6667 / 0.6667 / 0.6667 / 0.6667 / 0.6667 | unchanged |
| biological_diversity | 0.4000 / 1.0000 / 1.0000 / 1.0000 / 0.6667 | 0.8000 / 1.0000 / 1.0000 / 1.0000 / 0.9000 | improved |
| comparisons | 0.0000 / 0.1250 / 0.1250 / 0.5000 / 0.2170 | 0.0000 / 0.1250 / 0.1250 / 0.5000 / 0.2170 | unchanged |
| designs | 0.3333 / 0.6667 / 0.6667 / 1.0000 / 0.5556 | 0.3333 / 0.6667 / 1.0000 / 1.0000 / 0.5667 | improved |
| explicit_provisions | 0.7500 / 0.7500 / 0.7500 / 0.7500 / 0.7500 | 0.7500 / 0.7500 / 0.7500 / 0.7500 / 0.7500 | unchanged |
| geographical_indications | 0.6667 / 0.6667 / 0.6667 / 0.6667 / 0.6667 | 0.3333 / 0.6667 / 0.6667 / 1.0000 / 0.5000 | mixed/regressed |
| international_treaties | 0.2000 / 0.8000 / 0.8000 / 1.0000 / 0.5333 | 0.4000 / 0.6000 / 0.8000 / 0.8000 / 0.5400 | mixed/regressed |
| patent_procedure | 0.2000 / 0.2000 / 0.2000 / 0.2000 / 0.2000 | 0.2000 / 0.2000 / 0.2000 / 0.2000 / 0.2000 | unchanged |
| patentability | 0.2500 / 0.2500 / 0.2500 / 0.2500 / 0.2500 | 0.2500 / 0.2500 / 0.2500 / 0.2500 / 0.2500 | unchanged |
| trademarks | 0.5000 / 1.0000 / 1.0000 / 1.0000 / 0.7083 | 0.7500 / 0.7500 / 1.0000 / 1.0000 / 0.8125 | mixed/regressed |
| traditional_knowledge | 0.6667 / 1.0000 / 1.0000 / 1.0000 / 0.7778 | 0.6667 / 1.0000 / 1.0000 / 1.0000 / 0.8333 | improved |

## Query-type comparison

| Query type | Stage 6D | Stage 6J |
|---|---|---|
| comparison (n=4/4) | recall@1 0.0000, recall@3 0.1250, recall@5 0.1250, recall@10 0.5000, mrr 0.2170 | recall@1 0.0000, recall@3 0.1250, recall@5 0.1250, recall@10 0.5000, mrr 0.2170 |
| explicit_provision (n=4/4) | recall@1 0.7500, recall@3 0.7500, recall@5 0.7500, recall@10 0.7500, mrr 0.7500 | recall@1 0.7500, recall@3 0.7500, recall@5 0.7500, recall@10 0.7500, mrr 0.7500 |
| normal (n=35/35) | recall@1 0.4000, recall@3 0.6857, recall@5 0.6857, recall@10 0.7429, mrr 0.5381 | recall@1 0.4857, recall@3 0.6286, recall@5 0.7143, recall@10 0.7429, mrr 0.5757 |

## Morphology wins, baseline wins, and ties

- Wins by query-level earliest-target reciprocal rank: morphology 7, baseline 4, ties 32.
- Morphology wins: holdout_011, holdout_014, holdout_018, holdout_020, holdout_023, holdout_027, holdout_034.
- Baseline wins: holdout_013, holdout_015, holdout_031, holdout_032.
- Ties: holdout_001, holdout_002, holdout_003, holdout_004, holdout_005, holdout_006, holdout_007, holdout_008, holdout_009, holdout_010, holdout_012, holdout_016, holdout_017, holdout_019, holdout_021, holdout_022, holdout_024, holdout_025, holdout_026, holdout_028, holdout_029, holdout_030, holdout_033, holdout_035, holdout_036, holdout_037, holdout_038, holdout_039, holdout_040, holdout_041, holdout_042, holdout_043.
- A query is a win when its earliest expected target has a better reciprocal rank; comparisons therefore also report target coverage separately.

## Changed target ranks

| Query | Expected target | Stage 6D rank | Stage 6J rank | Morphology applied | Added terms |
|---|---|---:|---:|---|---|
| holdout_011: Can an earlier registered sign prevent registration of a later mark likely to confuse consumers? | Trademarks Act section 11 (India) | 2 | 1 | True | signs registrations marks consumer |
| holdout_013: Can a trader who used a mark first resist the rights of a later registrant? | Trademarks Act section 34 (India) | 3 | 4 | True | marks right |
| holdout_014: What standards govern whether a place-linked product name can be entered as a geographical indication? | Gi Act section 9 (India) | not in Top 10 | 6 | True | standard places products names indications |
| holdout_015: Which body or association can seek registration of a regional product designation? | Gi Act section 11 (India) | 1 | 3 | True | associations seeks registrations products designations |
| holdout_018: For what period does Indian law protect a registered design? | Designs Act section 11 (India) | 6 | 5 | True | periods indians designs |
| holdout_020: May a person who is not an Indian citizen obtain Indian biological resources for research without prior approval? | Biological Diversity Act 2002 section 3 (India) | 3 | 1 | True | indians citizens obtains resource approvals |
| holdout_023: How are fair and equitable benefits determined when biological resources are used? | Biological Diversity Act 2002 section 21 (India) | 2 | 1 | True | fairs benefit resource |
| holdout_027: How are benefits from the utilization of genetic resources shared under the Nagoya framework? | Nagoya Protocol article 5 (International) | 3 | 2 | True | benefit resource |
| holdout_031: Which treaty stage involves an international search of an application for patent protection? | Pct article 15 (International) | 2 | 5 | True | involve patents protections |
| holdout_032: How can an international trademark applicant request protection in additional Madrid Union countries? | Madrid Protocol article 3ter (International) | 6 | not in Top 10 | True | trademarks applicants requests protections unions |
| holdout_034: What patent-application disclosure does the WIPO treaty on genetic resources address? | Wipo Gratk Treaty 2024 article 3 (International) | 2 | 1 | True | patents disclosures resource |

## Explicit provision safety

- Stage 6D rank-1 accuracy: 3/4.
- Stage 6J rank-1 accuracy: 3/4.
- Explicit target ranks are included in the changed-target table above when they differ.

## Comparison-query behavior

| Query | Stage 6D target coverage @5/@10 | Stage 6J target coverage @5/@10 | Stage 6D jurisdictions @5/@10 | Stage 6J jurisdictions @5/@10 |
|---|---|---|---|---|
| holdout_036: How do Indian exclusions from patentability compare with the international treaty rule on patentable subject matter in TRIPS? | 0.00/0.50 | 0.00/0.50 | ['India'] / ['India', 'International'] | ['India'] / ['India', 'International'] |
| holdout_037: Compare the Indian registration test for geographical indications with the international GI obligation in TRIPS. | 0.00/0.50 | 0.00/0.50 | ['India'] / ['India', 'International'] | ['India'] / ['India', 'International'] |
| holdout_038: Compare Indian prior-approval requirements for biological resources with Nagoya Protocol access rules. | 0.50/0.50 | 0.50/0.50 | ['International'] / ['India', 'International'] | ['International'] / ['India', 'International'] |
| holdout_039: Compare Indian patent-specification disclosure duties with the description required in an international PCT application. | 0.00/0.50 | 0.00/0.50 | ['India', 'International'] / ['India', 'International'] | ['India', 'International'] / ['India', 'International'] |

## Jurisdiction and determinism

- Stage 6D jurisdiction-filter violations: 0.
- Stage 6J jurisdiction-filter violations: 0.
- Stage 6D deterministic repeated rankings: True (mismatches: []).
- Stage 6J deterministic repeated rankings: True (mismatches: []).

## Existing regression checks (run after holdout evaluation)

- unit_tests: PASS (exit 0).
  Ran 196 tests in 7.521s
  OK
- stage_5a_1: PASS (exit 0).
  Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
  Macro metrics (query-aware hybrid):
  Recall@1: 0.0500
  Recall@3: 0.3500
  Recall@5: 0.4000
  MRR: 0.3750
- stage_6d_42_query: PASS (exit 0).
  Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
  - RECALL@1: 0.3286
  - RECALL@3: 0.4810
  - RECALL@5: 0.5095
  - RECALL@10: 0.5952
  - MRR: 0.4564
  - definitions: n=4; RECALL@1=0.5000; RECALL@3=0.5000; RECALL@5=0.5000; RECALL@10=0.7500; MRR=0.5250
  - patentability: n=3; RECALL@1=0.0000; RECALL@3=0.3333; RECALL@5=0.3333; RECALL@10=0.3333; MRR=0.1667
  - patent_procedure: n=3; RECALL@1=0.0000; RECALL@3=0.0000; RECALL@5=0.0000; RECALL@10=0.0000; MRR=0.0000
  - trademarks: n=3; RECALL@1=0.6667; RECALL@3=0.6667; RECALL@5=0.6667; RECALL@10=0.6667; MRR=0.6667
  - geographical_indications: n=2; RECALL@1=1.0000; RECALL@3=1.0000; RECALL@5=1.0000; RECALL@10=1.0000; MRR=1.0000
  - designs: n=2; RECALL@1=0.0000; RECALL@3=0.0000; RECALL@5=0.5000; RECALL@10=1.0000; MRR=0.1875
  - biological_diversity: n=3; RECALL@1=0.6667; RECALL@3=0.6667; RECALL@5=0.6667; RECALL@10=1.0000; MRR=0.7222
  - traditional_knowledge: n=2; RECALL@1=0.5000; RECALL@3=1.0000; RECALL@5=1.0000; RECALL@10=1.0000; MRR=0.7500
  - ayurveda_food_regulatory: n=2; RECALL@1=0.0000; RECALL@3=0.0000; RECALL@5=0.0000; RECALL@10=0.0000; MRR=0.0000
  - international_treaties: n=4; RECALL@1=0.0000; RECALL@3=0.5000; RECALL@5=0.5000; RECALL@10=0.5000; MRR=0.2083
  - comparisons: n=4; RECALL@1=0.1250; RECALL@3=0.4583; RECALL@5=0.4583; RECALL@10=0.4583; MRR=0.6250
  - explicit_provisions: n=3; RECALL@1=0.6667; RECALL@3=0.6667; RECALL@5=0.6667; RECALL@10=0.6667; MRR=0.6667
  - Violations: 0
  - Deterministic: PASS
  - Ranking mismatches across 42 repeated queries: 0

## Recommendation

PASS WITH TRADEOFF: aggregate metrics improve, but some categories regress; retain the current default and analyze those categories before any default change.

Stage 6J recommendation: **KEEP DISABLED BY DEFAULT**. The production default remains unchanged (`MORPHOLOGY_EXPANSION_ENABLED=false`).

STAGE 6K STATUS: PASS
