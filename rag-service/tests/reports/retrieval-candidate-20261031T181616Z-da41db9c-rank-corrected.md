# Candidate retrieval evaluation

> Corrected presentation copy of `retrieval-candidate-20261031T181453Z-cdea8289.md`. The retriever returns ordered rows without a `rank` field; row ranks below are their 1-based list positions. Original report preserved unchanged.

- Run time (UTC): 2026-10-31T18:14:53.830959+00:00
- Evaluation set: `rag-service/tests/eval_set.json` (37311e90be445404b3d2a5fc18809248f8f050217972d3c8dff421a20d629513)
- Candidate chunk map: `rag-service/staging/chunk-refresh-regulation-20261031T140000Z-audit/chunks.candidate.json` (efd89919dde975cf0427152d7d62d06c1c5b2e513dd9d3073ced72449c7a2a76; 1322 IDs)
- Validated index source: `rag-service/staging/fresh-chroma-rebuild-20261031T165532Z-3661e3fe`
- Source SQLite SHA-256: `6f64f635fe0f0f430d52620284c8c05d3117cc1bb7501d357ffea7418663aad1`
- Source build-manifest SHA-256: `d47fb79805394178fadb4324c2537a3cbcda462ca39911c38823fa0c461148fe`
- Disposable retrieval index: `rag-service/staging/retrieval-eval-candidate-20261031T181433Z-e5c13bc0`
- Effective configured pair: `CHROMA_PATH=rag-service/staging/retrieval-eval-candidate-20261031T181433Z-e5c13bc0`, `CHUNKS_PATH=rag-service/staging/chunk-refresh-regulation-20261031T140000Z-audit/chunks.candidate.json`
- Collection: `ip_sakti_legal`; records `1322`; embedding model `sentence-transformers/all-MiniLM-L6-v2` (validated build dimension: 384)
- Pair validation: passed in `LegalRetriever` initialization (configured collection IDs matched candidate-map IDs).
- Retrieval: existing `evaluate_full_retrieval` matching and metric functions; Top 10; each of 42 queries run twice for determinism.
- LLM calls: none.

## Overall metrics

- Evaluated answerable queries: 35 of 42 total (7 abstention cases excluded from recall/MRR).
- RECALL@1: 0.4429
- RECALL@3: 0.6238
- RECALL@5: 0.7095
- RECALL@10: 0.8524
- MRR: 0.6010

- Determinism: PASS; changed rankings: 0/42.

## Category metrics

| Category | Queries | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| definitions | 4 | 0.7500 | 0.7500 | 0.7500 | 1.0000 | 0.7750 |
| patentability | 3 | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.8333 |
| patent_procedure | 3 | 0.0000 | 0.0000 | 0.3333 | 1.0000 | 0.1759 |
| trademarks | 3 | 0.6667 | 0.6667 | 0.6667 | 0.6667 | 0.6667 |
| geographical_indications | 2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| designs | 2 | 0.0000 | 0.0000 | 0.5000 | 1.0000 | 0.1875 |
| biological_diversity | 3 | 0.6667 | 0.6667 | 0.6667 | 1.0000 | 0.7222 |
| traditional_knowledge | 2 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.7500 |
| ayurveda_food_regulatory | 2 | 0.0000 | 0.5000 | 1.0000 | 1.0000 | 0.2667 |
| international_treaties | 4 | 0.0000 | 0.5000 | 0.5000 | 0.5000 | 0.2083 |
| comparisons | 4 | 0.1250 | 0.4583 | 0.4583 | 0.4583 | 0.6250 |
| explicit_provisions | 3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## Queries with at least one expected target missing from Top 10

### eval_011 ? trademarks

- Query: What grounds could prevent registration of a proposed brand name as a trademark?
- Jurisdiction filter: India
- Missing expected target(s): Trademarks Act ? section 9 (India)
- Expected-target ranks (target order): `[None]`

Top 10 returned provisions:

- 1. Trademarks Act ? section 11 (India), pp. 9?11; source `india:national/trademarks_act`, score `0.032018442622950824`
- 2. Trademarks Act ? section 11 (India), pp. 7?9; source `india:national/trademarks_act`, score `0.031054405392392875`
- 3. Trademarks Act ? section 27 (India), pp. 14?16; source `india:national/trademarks_act`, score `0.029513888888888888`
- 4. Trademarks Act ? section 70 (India), pp. 28?28; source `india:national/trademarks_act`, score `0.02889344262295082`
- 5. Trademarks Act ? section 36 (India), pp. 18?18; source `india:national/trademarks_act`, score `0.027692895339954164`
- 6. Drugs Cosmetics Act ? section 17D (India), pp. 17?18; source `india:national/drugs_cosmetics_act`, score `0.016129032258064516`
- 7. Trademarks Act ? section 49 (India), pp. 22?24; source `india:national/trademarks_act`, score `0.015873015873015872`
- 8. Drugs Cosmetics Act ? section 9D (India), pp. 12?12; source `india:national/drugs_cosmetics_act`, score `0.015873015873015872`
- 9. Trademarks Act ? section 2 (India), pp. 1?4; source `india:national/trademarks_act`, score `0.015384615384615385`
- 10. Trademarks Act ? section 35 (India), pp. 17?18; source `india:national/trademarks_act`, score `0.015384615384615385`

### eval_027 ? international_treaties

- Query: What is the effect of an international patent application under the PCT?
- Jurisdiction filter: International
- Missing expected target(s): Pct ? article 11 (International)
- Expected-target ranks (target order): `[None]`

Top 10 returned provisions:

- 1. Pct ? article 2 (International), pp. 7?9; source `international:international/pct`, score `0.033425373134328355`
- 2. Pct ? article 45 (International), pp. 34?34; source `international:international/pct`, score `0.03177805800756621`
- 3. Pct ? article 4 (International), pp. 9?10; source `international:international/pct`, score `0.029857397504456328`
- 4. Hague Agreement ? article 14 (International), pp. 12?12; source `international:international/hague_agreement`, score `0.02886002886002886`
- 5. Wipo Gratk Treaty 2024 ? article 10 (International), pp. 6?8; source `international:international/wipo_gratk_treaty_2024`, score `0.028438886647841874`
- 6. Pct ? article 24 (International), pp. 20?21; source `international:international/pct`, score `0.02817460317460317`
- 7. Wipo Gratk Treaty 2024 ? article 19 (International), pp. 10?10; source `international:international/wipo_gratk_treaty_2024`, score `0.027313266443701224`
- 8. Pct ? article 35 (International), pp. 29?30; source `international:international/pct`, score `0.021384615384615384`
- 9. Budapest Treaty ? article 2 (International), pp. 2?3; source `international:international/budapest_treaty`, score `0.02115151515151515`
- 10. Hague Agreement ? article 1 (International), pp. 3?4; source `international:international/hague_agreement`, score `0.02008450704225352`

### eval_028 ? international_treaties

- Query: What effect does an international trademark registration have under the Madrid Protocol?
- Jurisdiction filter: International
- Missing expected target(s): Madrid Protocol ? article 4 (International)
- Expected-target ranks (target order): `[None]`

Top 10 returned provisions:

- 1. Madrid Protocol ?   (International), pp. 1?1; source `international:international/madrid_protocol`, score `0.08278688524590164`
- 2. Madrid Protocol ?   (International), pp. 2?2; source `international:international/madrid_protocol`, score `0.08225806451612903`
- 3. Madrid Protocol ? article 1 (International), pp. 3?3; source `international:international/madrid_protocol`, score `0.08125763125763126`
- 4. Madrid Protocol ? article 9 (International), pp. 17?17; source `international:international/madrid_protocol`, score `0.08007688828584351`
- 5. Madrid Protocol ? article 9bis (International), pp. 17?18; source `international:international/madrid_protocol`, score `0.07837022132796781`
- 6. Madrid Protocol ? article 16 (International), pp. 28?31; source `international:international/madrid_protocol`, score `0.07830940988835726`
- 7. Madrid Protocol ? article 5 (International), pp. 20?20; source `international:international/madrid_protocol`, score `0.078125`
- 8. Madrid Protocol ? article 4bis (International), pp. 8?8; source `international:international/madrid_protocol`, score `0.07769289533995416`
- 9. Madrid Protocol ? article 3bis (International), pp. 6?6; source `international:international/madrid_protocol`, score `0.07702702702702703`
- 10. Madrid Protocol ? article 9quinquies (International), pp. 19?19; source `international:international/madrid_protocol`, score `0.07685652487382841`

### eval_029 ? comparisons

- Query: Compare India?s exclusions from patentability with TRIPS rules on patentable subject matter.
- Jurisdiction filter: all
- Missing expected target(s): The Patents Act, 1970 ? section 3 (India)
- Expected-target ranks (target order): `[None, 2]`

Top 10 returned provisions:

- 1. The Patents Act, 1970 ? section 25 (India), pp. 30?32; source `india:national/patent_act_2024`, score `0.02690501986276634`
- 2. Trips Agreement ? article 27 (International), pp. 13?14; source `international:international/trips_agreement`, score `0.01639344262295082`
- 3. The Patents Act, 1970 ? section 83 (India), pp. 69?69; source `india:national/patent_act_2024`, score `0.01639344262295082`
- 4. Trips Agreement ? article 28 (International), pp. 14?14; source `international:international/trips_agreement`, score `0.016129032258064516`
- 5. The Patents Act, 1970 ? section 84 (India), pp. 69?72; source `india:national/patent_act_2024`, score `0.016129032258064516`
- 6. The Patents Act, 1970 ? section 48 (India), pp. 44?45; source `india:national/patent_act_2024`, score `0.015873015873015872`
- 7. The Patents Act, 1970 ? section 39 (India), pp. 41?41; source `india:national/patent_act_2024`, score `0.015873015873015872`
- 8. Trips Agreement ? article 44 (International), pp. 21?22; source `international:international/trips_agreement`, score `0.015625`
- 9. Patent Rules 2024 ?   (India), pp. 1?1; source `india:national/patent-rules-2024`, score `0.015625`
- 10. Tkdl Background 2021 ? None None (India), pp. 1?2; source `india:national/tkdl_background_2021`, score `0.015384615384615385`

### eval_030 ? comparisons

- Query: How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts?
- Jurisdiction filter: all
- Missing expected target(s): Biological Diversity Act 2002 ? section 6 (India); Nagoya Protocol ? article 5 (International)
- Expected-target ranks (target order): `[None, 2, None]`

Top 10 returned provisions:

- 1. Nagoya Protocol ? article 16 (International), pp. 9?10; source `international:international/nagoya-protocol`, score `0.08201844262295083`
- 2. Nagoya Protocol ? article 6 (International), pp. 6?7; source `international:international/nagoya-protocol`, score `0.08201844262295083`
- 3. Nagoya Protocol ? article 2 (International), pp. 5?6; source `international:international/nagoya-protocol`, score `0.08200204813108039`
- 4. Nagoya Protocol ? article 10 (International), pp. 7?8; source `international:international/nagoya-protocol`, score `0.08200204813108039`
- 5. Nagoya Protocol ? article 32 (International), pp. 14?15; source `international:international/nagoya-protocol`, score `0.08030998851894375`
- 6. Nagoya Protocol ?   (International), pp. 1?4; source `international:international/nagoya-protocol`, score `0.07900988017658188`
- 7. Nagoya Protocol ? article 15 (International), pp. 9?9; source `international:international/nagoya-protocol`, score `0.07859477124183006`
- 8. Nagoya Protocol ? article 4 (International), pp. 5?5; source `international:international/nagoya-protocol`, score `0.07778313717923982`
- 9. Nagoya Protocol ? article 18 (International), pp. 10?11; source `international:international/nagoya-protocol`, score `0.077526395173454`
- 10. Nagoya Protocol ? article 13 (International), pp. 8?9; source `international:international/nagoya-protocol`, score `0.06538461538461539`

### eval_031 ? comparisons

- Query: Compare Indian protection criteria for geographical indications with TRIPS protection of GIs.
- Jurisdiction filter: all
- Missing expected target(s): Gi Act ? section 9 (India)
- Expected-target ranks (target order): `[None, 2]`

Top 10 returned provisions:

- 1. Gi Act ? section 85 (India), pp. 35?35; source `india:national/gi_act`, score `0.031754032258064516`
- 2. Trips Agreement ? article 22 (International), pp. 10?11; source `international:international/trips_agreement`, score `0.03021353930031804`
- 3. Gi Act ? section 21 (India), pp. 11?12; source `india:national/gi_act`, score `0.029726775956284153`
- 4. Trips Agreement ? article 24 (International), pp. 11?12; source `international:international/trips_agreement`, score `0.029418126757516764`
- 5. Gi Act ? section 5 (India), pp. 4?4; source `india:national/gi_act`, score `0.028404512489927477`
- 6. Gi Act ?   (India), pp. 1?1; source `india:national/gi_act`, score `0.027972027972027972`
- 7. Gi Act ? section 3 (India), pp. 3?4; source `india:national/gi_act`, score `0.027071520029266508`
- 8. Gi Act ? section 1 (India), pp. 1?2; source `india:national/gi_act`, score `0.026013513513513515`
- 9. Trips Agreement ? article 23 (International), pp. 11?11; source `international:international/trips_agreement`, score `0.01639344262295082`
- 10. Trips Agreement ? None None (International), pp. 1?1; source `international:international/trips_agreement`, score `0.015873015873015872`

### eval_032 ? comparisons

- Query: How does India?s design protection framework compare with the Hague Agreement?s international registration effects?
- Jurisdiction filter: all
- Missing expected target(s): Designs Act ? section 4 (India)
- Expected-target ranks (target order): `[None, 1]`

Top 10 returned provisions:

- 1. Hague Agreement ? article 14 (International), pp. 12?12; source `international:international/hague_agreement`, score `0.08252247488101534`
- 2. Hague Agreement ? article 1 (International), pp. 3?4; source `international:international/hague_agreement`, score `0.08201844262295083`
- 3. Hague Agreement ? article 12 (International), pp. 12?13; source `international:international/hague_agreement`, score `0.08076923076923077`
- 4. Hague Agreement ?   (International), pp. 1?1; source `international:international/hague_agreement`, score `0.08036576949620428`
- 5. Hague Agreement ? article 17 (International), pp. 14?15; source `international:international/hague_agreement`, score `0.0787903893951947`
- 6. Hague Agreement ? article 11 (International), pp. 9?9; source `international:international/hague_agreement`, score `0.0759915611814346`
- 7. Hague Agreement ? article 12 (International), pp. 11?11; source `international:international/hague_agreement`, score `0.065625`
- 8. Hague Agreement ? article 15 (International), pp. 13?13; source `international:international/hague_agreement`, score `0.06515151515151515`
- 9. Designs Act ? section 44 (India), pp. 14?15; source `india:national/designs_act`, score `0.016129032258064516`
- 10. Designs Act ? section 46 (India), pp. 16?16; source `india:national/designs_act`, score `0.015151515151515152`

## Limits

- This is a retrieval-only evaluation; it does not measure generated answer quality, citation correctness, confidence, or abstention decisions.
- The hardcoded Stage 6D gate was not changed or used. These metrics use the corrected evaluation targets and are not a newly approved baseline.
