# Stage 6I Morphology Ablation Analysis

## 1. Executive summary

Analyzed **35 answerable queries** and **40 expected targets**. The main morphology arm reuses Stage 6H's existing corpus-attested suffix variant function and five-term cap. No target metadata or target text participates in expansion generation.

## 2. Baseline reproduction

The current Stage 6D retriever was evaluated unchanged before this analysis. Its reproduced metrics appear in the table below.

## 3. Morphology reproduction and 4. Overall metric comparison

| Variant | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| Baseline | 0.3857 | 0.5952 | 0.7381 | 0.8810 | 0.5711 |
| Current morphology | 0.4429 | 0.6524 | 0.7952 | 0.9238 | 0.6121 |
| Conservative morphology | 0.4143 | 0.6238 | 0.7667 | 0.8524 | 0.5937 |

Expected baseline: 0.3857 / 0.5952 / 0.7381 / 0.8810 / 0.5711. Expected Stage 6H morphology: 0.4429 / 0.6524 / 0.7952 / 0.9238 / 0.6121. Any discrepancy is visible above and must be investigated; this report does not silently substitute the earlier values.

## 5. Category-level comparison

Metrics are macro averages using the evaluator's target-fraction Recall and earliest-target MRR convention. Delta columns are morphology or conservative minus baseline.

| Category | Variant | R@1 (Δ) | R@3 (Δ) | R@5 (Δ) | R@10 (Δ) | MRR (Δ) |
|---|---|---:|---:|---:|---:|---:|
| Definitions | Baseline | 0.5000 (+0.0000) | 0.7500 (+0.0000) | 0.7500 (+0.0000) | 0.7500 (+0.0000) | 0.6250 (+0.0000) |
| Definitions | Current morphology | 0.5000 (+0.0000) | 0.7500 (+0.0000) | 0.7500 (+0.0000) | 0.7500 (+0.0000) | 0.6250 (+0.0000) |
| Definitions | Conservative morphology | 0.5000 (+0.0000) | 0.7500 (+0.0000) | 0.7500 (+0.0000) | 0.7500 (+0.0000) | 0.6250 (+0.0000) |
| Patentability | Baseline | 0.6667 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.8333 (+0.0000) |
| Patentability | Current morphology | 0.6667 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.7778 (-0.0555) |
| Patentability | Conservative morphology | 0.6667 (+0.0000) | 0.6667 (-0.3333) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.7500 (-0.0833) |
| Patent procedure | Baseline | 0.0000 (+0.0000) | 0.0000 (+0.0000) | 0.3333 (+0.0000) | 1.0000 (+0.0000) | 0.1560 (+0.0000) |
| Patent procedure | Current morphology | 0.3333 (+0.3333) | 0.3333 (+0.3333) | 0.6667 (+0.3334) | 1.0000 (+0.0000) | 0.4583 (+0.3023) |
| Patent procedure | Conservative morphology | 0.0000 (+0.0000) | 0.3333 (+0.3333) | 0.6667 (+0.3334) | 0.6667 (-0.3333) | 0.1778 (+0.0218) |
| Trademarks | Baseline | 0.3333 (+0.0000) | 0.3333 (+0.0000) | 0.6667 (+0.0000) | 0.6667 (+0.0000) | 0.4000 (+0.0000) |
| Trademarks | Current morphology | 0.0000 (-0.3333) | 0.3333 (+0.0000) | 0.6667 (+0.0000) | 1.0000 (+0.3333) | 0.2667 (-0.1333) |
| Trademarks | Conservative morphology | 0.3333 (+0.0000) | 0.3333 (+0.0000) | 0.6667 (+0.0000) | 0.6667 (+0.0000) | 0.4000 (+0.0000) |
| Geographical indications | Baseline | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) |
| Geographical indications | Current morphology | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) |
| Geographical indications | Conservative morphology | 0.5000 (-0.5000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.7500 (-0.2500) |
| Designs | Baseline | 0.0000 (+0.0000) | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.3500 (+0.0000) |
| Designs | Current morphology | 0.0000 (+0.0000) | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.2667 (-0.0833) |
| Designs | Conservative morphology | 0.0000 (+0.0000) | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.3500 (+0.0000) |
| Biological diversity | Baseline | 0.6667 (+0.0000) | 0.6667 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.7333 (+0.0000) |
| Biological diversity | Current morphology | 1.0000 (+0.3333) | 1.0000 (+0.3333) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.2667) |
| Biological diversity | Conservative morphology | 1.0000 (+0.3333) | 1.0000 (+0.3333) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.2667) |
| Traditional knowledge | Baseline | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.7500 (+0.0000) |
| Traditional knowledge | Current morphology | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.7500 (+0.0000) |
| Traditional knowledge | Conservative morphology | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.7500 (+0.0000) |
| Ayurveda/food/regulatory | Baseline | 0.0000 (+0.0000) | 0.0000 (+0.0000) | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 0.1833 (+0.0000) |
| Ayurveda/food/regulatory | Current morphology | 0.0000 (+0.0000) | 0.0000 (+0.0000) | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 0.1833 (+0.0000) |
| Ayurveda/food/regulatory | Conservative morphology | 0.0000 (+0.0000) | 0.0000 (+0.0000) | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 0.1875 (+0.0042) |
| International treaties | Baseline | 0.0000 (+0.0000) | 0.5000 (+0.0000) | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 0.2639 (+0.0000) |
| International treaties | Current morphology | 0.2500 (+0.2500) | 0.5000 (+0.0000) | 0.7500 (+0.2500) | 1.0000 (+0.0000) | 0.4625 (+0.1986) |
| International treaties | Conservative morphology | 0.2500 (+0.2500) | 0.5000 (+0.0000) | 0.5000 (+0.0000) | 1.0000 (+0.0000) | 0.4306 (+0.1667) |
| Comparisons | Baseline | 0.1250 (+0.0000) | 0.4583 (+0.0000) | 0.4583 (+0.0000) | 0.4583 (+0.0000) | 0.6250 (+0.0000) |
| Comparisons | Current morphology | 0.1250 (+0.0000) | 0.4583 (+0.0000) | 0.4583 (+0.0000) | 0.5833 (+0.1250) | 0.5417 (-0.0833) |
| Comparisons | Conservative morphology | 0.1250 (+0.0000) | 0.4583 (+0.0000) | 0.4583 (+0.0000) | 0.4583 (+0.0000) | 0.6250 (+0.0000) |
| Explicit provisions | Baseline | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) |
| Explicit provisions | Current morphology | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) |
| Explicit provisions | Conservative morphology | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) |

### Category interpretation

- Clear overall gains across several metrics without a metric regression: Patent procedure, Biological diversity, International treaties.
- Neutral across all reported metrics: Definitions, Geographical indications, Traditional knowledge, Ayurveda/food/regulatory, Explicit provisions.
- Mixed or concerning tradeoffs: Patentability, Trademarks, Designs, Comparisons. A single metric change is not treated as a categorical win/loss.

## 6. Query-by-query rank changes

Ranks refer to the target's first matching result within Top-10. Status columns state whether each target is within that cutoff.

| ID | Category | Jurisdiction | Intent | Original query | Expanded query | Added terms (n) | Expected targets | Baseline ranks | Morphology ranks |
|---|---|---|---|---|---|---:|---|---|---|
| eval_001 | definitions | India | definition | How does the Patents Act define an invention and related patent terms? | How does the Patents Act define an invention and related patent terms? inventions term | inventions, term (2) | Patent Act 2024 section 2 | 1 | 1 |
| eval_002 | definitions | India | definition | For biodiversity research in India, how does the Act define biological resources? | For biodiversity research in India, how does the Act define biological resources? resource | resource (1) | Biological Diversity Act 2002 section 2 | — | — |
| eval_003 | definitions | India | definition | How does Indian law define a magic remedy or related terms used in drug advertisements? | How does Indian law define a magic remedy or related terms used in drug advertisements? indians term drugs advertisement | indians, term, drugs, advertisement (4) | Drugs Magic Remedies Act section 2 | 1 | 1 |
| eval_004 | definitions | India | general | What does the Geographical Indications Act mean by a geographical indication? | What does the Geographical Indications Act mean by a geographical indication? | — (0) | Gi Act section 2 | 2 | 2 |
| eval_005 | patentability | India | prohibition | Which kinds of subject matter are not inventions under Indian patent law? | Which kinds of subject matter are not inventions under Indian patent law? kind matters invention indians patents | kind, matters, invention, indians, patents (5) | Patent Act 2024 section 3 | 1 | 1 |
| eval_006 | patentability | India | general | Can an invention relating to atomic energy be patented in India? | Can an invention relating to atomic energy be patented in India? inventions | inventions (1) | Patent Act 2024 section 4 | 1 | 1 |
| eval_007 | patentability | International | general | How does TRIPS describe the subject matter that members must make eligible for patent protection? | How does TRIPS describe the subject matter that members must make eligible for patent protection? matters member makes patents protections | matters, member, makes, patents, protections (5) | Trips Agreement article 27 | 2 | 3 |
| eval_008 | patent_procedure | India | general | Who is entitled to apply for a patent in India, including an assignee? | Who is entitled to apply for a patent in India, including an assignee? patents assignees | patents, assignees (2) | Patent Act 2024 section 6 | 5 | 4 |
| eval_009 | patent_procedure | India | general | What information belongs in a patent specification filed in India? | What information belongs in a patent specification filed in India? belong patents specifications | belong, patents, specifications (3) | Patent Act 2024 section 10 | 8 | 8 |
| eval_010 | patent_procedure | India | general | What legal effect follows when the Controller grants a patent? | What legal effect follows when the Controller grants a patent? effects follow controllers grant patents | effects, follow, controllers, grant, patents (5) | Patent Act 2024 section 43 | 7 | 1 |
| eval_011 | trademarks | India | general | What grounds could prevent registration of a proposed brand name as a trademark? | What grounds could prevent registration of a proposed brand name as a trademark? ground registrations names trademarks | ground, registrations, names, trademarks (4) | Trademarks Act section 9 | — | 10 |
| eval_012 | trademarks | India | general | How are conflicting trademark applications or earlier marks considered during registration? | How are conflicting trademark applications or earlier marks considered during registration? trademarks mark registrations | trademarks, mark, registrations (3) | Trademarks Act section 11 | 1 | 2 |
| eval_013 | trademarks | India | general | What happens after a trademark application has been accepted for registration? | What happens after a trademark application has been accepted for registration? trademarks registrations | trademarks, registrations (2) | Trademarks Act section 19 | 5 | 5 |
| eval_014 | geographical_indications | India | general | What makes a product name eligible for protection as a geographical indication? | What makes a product name eligible for protection as a geographical indication? make products names protections indications | make, products, names, protections, indications (5) | Gi Act section 9 | 1 | 1 |
| eval_015 | geographical_indications | India | general | What rights does registration give the authorized users of a geographical indication? | What rights does registration give the authorized users of a geographical indication? right registrations gives user indications | right, registrations, gives, user, indications (5) | Gi Act section 21 | 1 | 1 |
| eval_016 | designs | India | definition | What features are excluded from the legal definition of a registrable design? | What features are excluded from the legal definition of a registrable design? feature definitions designs | feature, definitions, designs (3) | Designs Act section 2 | 2 | 3 |
| eval_017 | designs | India | general | How long does registration of an industrial design protect it under the Designs Act? | How long does registration of an industrial design protect it under the Designs Act? registrations | registrations (1) | Designs Act section 11 | 5 | 5 |
| eval_018 | biological_diversity | India | general | When must a person obtain approval before accessing biological resources in India? | When must a person obtain approval before accessing biological resources in India? obtains approvals resource | obtains, approvals, resource (3) | Biological Diversity Act 2002 section 3 | 1 | 1 |
| eval_019 | biological_diversity | India | general | What approval is required before seeking an intellectual property right based on biological resources? | What approval is required before seeking an intellectual property right based on biological resources? approvals rights resource | approvals, rights, resource (3) | Biological Diversity Act 2002 section 6 | 1 | 1 |
| eval_020 | biological_diversity | India | general | How may benefits from using biological resources be shared fairly? | How may benefits from using biological resources be shared fairly? benefit resource | benefit, resource (2) | Biological Diversity Act 2002 section 21 | 5 | 1 |
| eval_021 | traditional_knowledge | International | general | What does the Nagoya Protocol say about access to traditional knowledge associated with genetic resources? | What does the Nagoya Protocol say about access to traditional knowledge associated with genetic resources? protocols resource | protocols, resource (2) | Nagoya Protocol article 7 | 1 | 2 |
| eval_022 | traditional_knowledge | International | general | What role should communities and customary laws have when traditional knowledge is accessed? | What role should communities and customary laws have when traditional knowledge is accessed? community | community (1) | Nagoya Protocol article 12 | 2 | 1 |
| eval_023 | ayurveda_food_regulatory | India | general | What does the Ayurveda Aahara regulation require for labeling these products? | What does the Ayurveda Aahara regulation require for labeling these products? requires product | requires, product (2) | Fssai Ayurveda Aahara Regulations 2022 section 12 | 6 | 6 |
| eval_024 | ayurveda_food_regulatory | India | purpose | Can a seller make disease-treatment claims for an Ayurveda Aahara product? | Can a seller make disease-treatment claims for an Ayurveda Aahara product? makes diseases treatments claim products | makes, diseases, treatments, claim, products (5) | Fssai Ayurveda Aahara Regulations 2022 section 8 | 5 | 5 |
| eval_025 | international_treaties | International | purpose | What is the objective of the Nagoya Protocol on access and benefit-sharing? | What is the objective of the Nagoya Protocol on access and benefit-sharing? objectives protocols benefits | objectives, protocols, benefits (3) | Nagoya Protocol article 1 | 2 | 2 |
| eval_026 | international_treaties | International | general | How does the Budapest Treaty make deposits of microorganisms recognizable across countries? | How does the Budapest Treaty make deposits of microorganisms recognizable across countries? makes deposit microorganism country | makes, deposit, microorganism, country (4) | Budapest Treaty article 3 | 3 | 1 |
| eval_027 | international_treaties | International | definition | What is the effect of an international patent application under the PCT? | What is the effect of an international patent application under the PCT? effects patents | effects, patents (2) | Pct article 11 | 9 | 10 |
| eval_028 | international_treaties | International | general | What effect does an international trademark registration have under the Madrid Protocol? | What effect does an international trademark registration have under the Madrid Protocol? effects trademarks registrations protocols | effects, trademarks, registrations, protocols (4) | Madrid Protocol article 4 | 9 | 4 |
| eval_029 | comparisons | all | comparison | Compare India?s exclusions from patentability with TRIPS rules on patentable subject matter. | Compare India?s exclusions from patentability with TRIPS rules on patentable subject matter. exclusion matters | exclusion, matters (2) | Patent Act 2024 section 3; Trips Agreement article 27 | —, 2 | —, 2 |
| eval_030 | comparisons | all | general | How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts? | How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts? indians approvals resource relates protocols | indians, approvals, resource, relates, protocols (5) | Biological Diversity Act 2002 section 6; Nagoya Protocol article 6; Nagoya Protocol article 5 | —, 2, — | —, 3, — |
| eval_031 | comparisons | all | comparison | Compare Indian protection criteria for geographical indications with TRIPS protection of GIs. | Compare Indian protection criteria for geographical indications with TRIPS protection of GIs. indians protections indication | indians, protections, indication (3) | Gi Act section 9; Trips Agreement article 22 | —, 2 | —, 3 |
| eval_032 | comparisons | all | comparison | How does India?s design protection framework compare with the Hague Agreement?s international registration effects? | How does India?s design protection framework compare with the Hague Agreement?s international registration effects? designs protections agreements registrations effect | designs, protections, agreements, registrations, effect (5) | Designs Act section 4; Hague Agreement article 14 | —, 1 | 10, 1 |
| eval_033 | explicit_provisions | India | explicit_provision | What does Section 83 of the Patents Act say about working patents and public needs? | What does Section 83 of the Patents Act say about working patents and public needs? patent need | patent, need (2) | Patent Act 2024 section 83 | 1 | 1 |
| eval_034 | explicit_provisions | International | explicit_provision | What is the purpose of Article 6 of the Nagoya Protocol on access to genetic resources? | What is the purpose of Article 6 of the Nagoya Protocol on access to genetic resources? purposes protocols resource | purposes, protocols, resource (3) | Nagoya Protocol article 6 | 1 | 1 |
| eval_035 | explicit_provisions | India | explicit_provision | What does Section 34 of the Trade Marks Act protect when someone has used a mark earlier? | What does Section 34 of the Trade Marks Act protect when someone has used a mark earlier? trades | trades (1) | Trademarks Act section 34 | 1 | 1 |

### Per-target ranks, deltas, cutoff status, and classification

Rank delta is morphology rank minus baseline rank when both are present. A negative value is an upward rank movement. Newly recovered/lost refers to entering/leaving Top-10.

| ID | Target | Baseline | Morphology | Δ rank | Baseline @1/@3/@5/@10 | Morph @1/@3/@5/@10 | State |
|---|---|---:|---:|---:|---|---|---|
| eval_001 | Patent Act 2024 section 2 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_002 | Biological Diversity Act 2002 section 2 | — | — | — | N/N/N/N | N/N/N/N | unchanged |
| eval_003 | Drugs Magic Remedies Act section 2 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_004 | Gi Act section 2 | 2 | 2 | 0 | N/Y/Y/Y | N/Y/Y/Y | unchanged |
| eval_005 | Patent Act 2024 section 3 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_006 | Patent Act 2024 section 4 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_007 | Trips Agreement article 27 | 2 | 3 | 1 | N/Y/Y/Y | N/Y/Y/Y | degraded |
| eval_008 | Patent Act 2024 section 6 | 5 | 4 | -1 | N/N/Y/Y | N/N/Y/Y | improved |
| eval_009 | Patent Act 2024 section 10 | 8 | 8 | 0 | N/N/N/Y | N/N/N/Y | unchanged |
| eval_010 | Patent Act 2024 section 43 | 7 | 1 | -6 | N/N/N/Y | Y/Y/Y/Y | improved |
| eval_011 | Trademarks Act section 9 | — | 10 | — | N/N/N/N | N/N/N/Y | newly recovered |
| eval_012 | Trademarks Act section 11 | 1 | 2 | 1 | Y/Y/Y/Y | N/Y/Y/Y | degraded |
| eval_013 | Trademarks Act section 19 | 5 | 5 | 0 | N/N/Y/Y | N/N/Y/Y | unchanged |
| eval_014 | Gi Act section 9 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_015 | Gi Act section 21 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_016 | Designs Act section 2 | 2 | 3 | 1 | N/Y/Y/Y | N/Y/Y/Y | degraded |
| eval_017 | Designs Act section 11 | 5 | 5 | 0 | N/N/Y/Y | N/N/Y/Y | unchanged |
| eval_018 | Biological Diversity Act 2002 section 3 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_019 | Biological Diversity Act 2002 section 6 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_020 | Biological Diversity Act 2002 section 21 | 5 | 1 | -4 | N/N/Y/Y | Y/Y/Y/Y | improved |
| eval_021 | Nagoya Protocol article 7 | 1 | 2 | 1 | Y/Y/Y/Y | N/Y/Y/Y | degraded |
| eval_022 | Nagoya Protocol article 12 | 2 | 1 | -1 | N/Y/Y/Y | Y/Y/Y/Y | improved |
| eval_023 | Fssai Ayurveda Aahara Regulations 2022 section 12 | 6 | 6 | 0 | N/N/N/Y | N/N/N/Y | unchanged |
| eval_024 | Fssai Ayurveda Aahara Regulations 2022 section 8 | 5 | 5 | 0 | N/N/Y/Y | N/N/Y/Y | unchanged |
| eval_025 | Nagoya Protocol article 1 | 2 | 2 | 0 | N/Y/Y/Y | N/Y/Y/Y | unchanged |
| eval_026 | Budapest Treaty article 3 | 3 | 1 | -2 | N/Y/Y/Y | Y/Y/Y/Y | improved |
| eval_027 | Pct article 11 | 9 | 10 | 1 | N/N/N/Y | N/N/N/Y | degraded |
| eval_028 | Madrid Protocol article 4 | 9 | 4 | -5 | N/N/N/Y | N/N/Y/Y | improved |
| eval_029 | Patent Act 2024 section 3 | — | — | — | N/N/N/N | N/N/N/N | unchanged |
| eval_029 | Trips Agreement article 27 | 2 | 2 | 0 | N/Y/Y/Y | N/Y/Y/Y | unchanged |
| eval_030 | Biological Diversity Act 2002 section 6 | — | — | — | N/N/N/N | N/N/N/N | unchanged |
| eval_030 | Nagoya Protocol article 6 | 2 | 3 | 1 | N/Y/Y/Y | N/Y/Y/Y | degraded |
| eval_030 | Nagoya Protocol article 5 | — | — | — | N/N/N/N | N/N/N/N | unchanged |
| eval_031 | Gi Act section 9 | — | — | — | N/N/N/N | N/N/N/N | unchanged |
| eval_031 | Trips Agreement article 22 | 2 | 3 | 1 | N/Y/Y/Y | N/Y/Y/Y | degraded |
| eval_032 | Designs Act section 4 | — | 10 | — | N/N/N/N | N/N/N/Y | newly recovered |
| eval_032 | Hague Agreement article 14 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_033 | Patent Act 2024 section 83 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_034 | Nagoya Protocol article 6 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |
| eval_035 | Trademarks Act section 34 | 1 | 1 | 0 | Y/Y/Y/Y | Y/Y/Y/Y | unchanged |

## 7. Newly recovered targets

### eval_011 — Trademarks Act section 9
- Query: What grounds could prevent registration of a proposed brand name as a trademark?
- Baseline rank —; morphology rank 10; state: newly recovered.
- Added terms: ground, registrations, names, trademarks.
- New Top-5 competitors: Trademarks Act section 31.
- Interpretation: newly present in Top-10 after expansion; observed ranking association, not proof that a specific term caused recovery.
### eval_032 — Designs Act section 4
- Query: How does India?s design protection framework compare with the Hague Agreement?s international registration effects?
- Baseline rank —; morphology rank 10; state: newly recovered.
- Added terms: designs, protections, agreements, registrations, effect.
- New Top-5 competitors: Hague Agreement article 17.
- Interpretation: newly present in Top-10 after expansion; observed ranking association, not proof that a specific term caused recovery.

## 8. Newly lost/degraded targets

For each target, new Top-5 rows absent from baseline Top-5 are listed as observed competitors. This documents ranking changes; it does not establish semantic causation.

### eval_007 — Trips Agreement article 27
- Query: How does TRIPS describe the subject matter that members must make eligible for patent protection?
- Baseline rank 2; morphology rank 3; state: degraded.
- Added terms: matters, member, makes, patents, protections.
- New Top-5 competitors: Trips Agreement article 4.
- Interpretation: observed displacement after the query changed; the rank evidence alone does not isolate which added term or establish semantic cause.
### eval_012 — Trademarks Act section 11
- Query: How are conflicting trademark applications or earlier marks considered during registration?
- Baseline rank 1; morphology rank 2; state: degraded.
- Added terms: trademarks, mark, registrations.
- New Top-5 competitors: Trademarks Act section 31.
- Interpretation: observed displacement after the query changed; the rank evidence alone does not isolate which added term or establish semantic cause.
### eval_016 — Designs Act section 2
- Query: What features are excluded from the legal definition of a registrable design?
- Baseline rank 2; morphology rank 3; state: degraded.
- Added terms: feature, definitions, designs.
- New Top-5 competitors: Designs Act section 23.
- Interpretation: observed displacement after the query changed; the rank evidence alone does not isolate which added term or establish semantic cause.
### eval_021 — Nagoya Protocol article 7
- Query: What does the Nagoya Protocol say about access to traditional knowledge associated with genetic resources?
- Baseline rank 1; morphology rank 2; state: degraded.
- Added terms: protocols, resource.
- New Top-5 competitors: none.
- Interpretation: observed displacement after the query changed; the rank evidence alone does not isolate which added term or establish semantic cause.
### eval_027 — Pct article 11
- Query: What is the effect of an international patent application under the PCT?
- Baseline rank 9; morphology rank 10; state: degraded.
- Added terms: effects, patents.
- New Top-5 competitors: Pct article 2, Hague Agreement article 14, Pct article 29.
- Interpretation: observed displacement after the query changed; the rank evidence alone does not isolate which added term or establish semantic cause.
### eval_030 — Nagoya Protocol article 6
- Query: How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts?
- Baseline rank 2; morphology rank 3; state: degraded.
- Added terms: indians, approvals, resource, relates, protocols.
- New Top-5 competitors: none.
- Interpretation: observed displacement after the query changed; the rank evidence alone does not isolate which added term or establish semantic cause.
### eval_031 — Trips Agreement article 22
- Query: Compare Indian protection criteria for geographical indications with TRIPS protection of GIs.
- Baseline rank 2; morphology rank 3; state: degraded.
- Added terms: indians, protections, indication.
- New Top-5 competitors: Gi Act section 11.
- Interpretation: observed displacement after the query changed; the rank evidence alone does not isolate which added term or establish semantic cause.

## 9. Expansion-term analysis

Term-level query outcome counts can overlap if a multi-target query has both upward and downward target movements. They are associations, not causal attribution.

| Added term | Queries added | Queries with improved target | Degraded target | No observable target-rank effect |
|---|---:|---:|---:|---:|
| registrations | 7 | 3 | 1 | 3 |
| patents | 6 | 2 | 2 | 2 |
| effects | 3 | 2 | 1 | 0 |
| trademarks | 4 | 2 | 1 | 1 |
| protections | 4 | 1 | 2 | 1 |
| protocols | 5 | 1 | 2 | 2 |
| resource | 7 | 1 | 2 | 4 |
| designs | 2 | 1 | 1 | 0 |
| makes | 3 | 1 | 1 | 1 |
| agreements | 1 | 1 | 0 | 0 |
| assignees | 1 | 1 | 0 | 0 |
| benefit | 1 | 1 | 0 | 0 |
| community | 1 | 1 | 0 | 0 |
| controllers | 1 | 1 | 0 | 0 |
| country | 1 | 1 | 0 | 0 |
| deposit | 1 | 1 | 0 | 0 |
| effect | 1 | 1 | 0 | 0 |
| follow | 1 | 1 | 0 | 0 |
| grant | 1 | 1 | 0 | 0 |
| ground | 1 | 1 | 0 | 0 |
| microorganism | 1 | 1 | 0 | 0 |
| names | 2 | 1 | 0 | 1 |
| indians | 4 | 0 | 2 | 2 |
| approvals | 3 | 0 | 1 | 2 |
| definitions | 1 | 0 | 1 | 0 |
| feature | 1 | 0 | 1 | 0 |
| indication | 1 | 0 | 1 | 0 |
| mark | 1 | 0 | 1 | 0 |
| matters | 3 | 0 | 1 | 2 |
| member | 1 | 0 | 1 | 0 |
| relates | 1 | 0 | 1 | 0 |
| advertisement | 1 | 0 | 0 | 1 |
| belong | 1 | 0 | 0 | 1 |
| benefits | 1 | 0 | 0 | 1 |
| claim | 1 | 0 | 0 | 1 |
| diseases | 1 | 0 | 0 | 1 |
| drugs | 1 | 0 | 0 | 1 |
| exclusion | 1 | 0 | 0 | 1 |
| gives | 1 | 0 | 0 | 1 |
| indications | 2 | 0 | 0 | 2 |
| invention | 1 | 0 | 0 | 1 |
| inventions | 2 | 0 | 0 | 2 |
| kind | 1 | 0 | 0 | 1 |
| make | 1 | 0 | 0 | 1 |
| need | 1 | 0 | 0 | 1 |
| objectives | 1 | 0 | 0 | 1 |
| obtains | 1 | 0 | 0 | 1 |
| patent | 1 | 0 | 0 | 1 |
| product | 1 | 0 | 0 | 1 |
| products | 2 | 0 | 0 | 2 |
| purposes | 1 | 0 | 0 | 1 |
| requires | 1 | 0 | 0 | 1 |
| right | 1 | 0 | 0 | 1 |
| rights | 1 | 0 | 0 | 1 |
| specifications | 1 | 0 | 0 | 1 |
| term | 2 | 0 | 0 | 2 |
| trades | 1 | 0 | 0 | 1 |
| treatments | 1 | 0 | 0 | 1 |
| user | 1 | 0 | 0 | 1 |

- Consistently useful by this descriptive rule (added in ≥2 queries, all associated queries improved): none.
- Neutral in all observed uses: advertisement, belong, benefits, claim, diseases, drugs, exclusion, gives, indications, invention, inventions, kind, make, need, objectives, obtains, patent, product, products, purposes, requires, right, rights, specifications, term, trades, treatments, user.
- Potentially harmful/uncertain (associated with at least one degraded target): approvals, definitions, designs, effects, feature, indians, indication, makes, mark, matters, member, patents, protections, protocols, registrations, relates, resource, trademarks.
These labels do not establish per-term causation. No terms are removed on this basis.

## 10. Query-type analysis

| Query type | n | Baseline R@1/R@3/R@5/R@10/MRR | Morphology R@1/R@3/R@5/R@10/MRR |
|---|---:|---|---|
| Comparison | 4 | 0.1250/0.4583/0.4583/0.4583/0.6250 | 0.1250/0.4583/0.4583/0.5833/0.5417 |
| Definition | 4 | 0.5000/0.7500/0.7500/0.7500/0.6250 | 0.5000/0.7500/0.7500/0.7500/0.6250 |
| Explicit provision | 3 | 1.0000/1.0000/1.0000/1.0000/1.0000 | 1.0000/1.0000/1.0000/1.0000/1.0000 |
| General | 18 | 0.3333/0.5556/0.7778/0.9444/0.5012 | 0.3889/0.6111/0.8333/1.0000/0.5583 |
| Patentability | 3 | 0.6667/1.0000/1.0000/1.0000/0.8333 | 0.6667/1.0000/1.0000/1.0000/0.7778 |
| Procedure | 3 | 0.0000/0.0000/0.3333/1.0000/0.1560 | 0.3333/0.3333/0.6667/1.0000/0.4583 |

## 11. Explicit-provision safety

| Evaluation ID | Explicit reference | Baseline rank | Morphology rank | Conservative rank |
|---|---|---:|---:|---:|
| eval_033 | {'type': 'section', 'number': '83'} | 1 | 1 | 1 |
| eval_034 | {'type': 'article', 'number': '6'} | 1 | 1 | 1 |
| eval_035 | {'type': 'section', 'number': '34'} | 1 | 1 | 1 |
All three named provisions are expected at rank 1 in the accepted baseline; the run below confirms actual ranks. This is a safety check on the existing evaluator, not a guarantee for arbitrary explicit references.

## 12. Comparison-query analysis

Coverage counts expected targets retrieved, while jurisdiction representation counts results in the returned top-k. Jurisdiction presence alone is not target success.

| ID | Variant | Target coverage @5 | Target coverage @10 | Expected jurisdictions found @5 / @10 | Returned jurisdiction counts @5 / @10 |
|---|---|---:|---:|---|---|
| eval_029 | Baseline | 1/2 | 1/2 | International / International | {'India': 3, 'International': 2} / {'India': 7, 'International': 3} |
| eval_029 | Current morphology | 1/2 | 1/2 | International / International | {'India': 3, 'International': 2} / {'India': 7, 'International': 3} |
| eval_029 | Conservative morphology | 1/2 | 1/2 | International / International | {'India': 3, 'International': 2} / {'India': 7, 'International': 3} |
| eval_030 | Baseline | 1/3 | 1/3 | International / International | {'International': 5} / {'International': 10} |
| eval_030 | Current morphology | 1/3 | 1/3 | International / International | {'International': 5} / {'International': 9, 'India': 1} |
| eval_030 | Conservative morphology | 1/3 | 1/3 | International / International | {'International': 5} / {'International': 9, 'India': 1} |
| eval_031 | Baseline | 1/2 | 1/2 | International / International | {'India': 3, 'International': 2} / {'India': 7, 'International': 3} |
| eval_031 | Current morphology | 1/2 | 1/2 | International / International | {'India': 3, 'International': 2} / {'India': 8, 'International': 2} |
| eval_031 | Conservative morphology | 1/2 | 1/2 | International / International | {'India': 3, 'International': 2} / {'India': 8, 'International': 2} |
| eval_032 | Baseline | 1/2 | 1/2 | International / International | {'International': 5} / {'International': 8, 'India': 2} |
| eval_032 | Current morphology | 1/2 | 2/2 | International / India, International | {'International': 5} / {'International': 7, 'India': 3} |
| eval_032 | Conservative morphology | 1/2 | 1/2 | International / International | {'International': 5} / {'International': 8, 'India': 2} |

## 13. Query-length analysis

Length uses Stage 6H's substantive query tokenization. Groups: short 1–5, medium 6–10, long >10.

| Length group | Queries | Baseline R@1/R@3/R@5/R@10/MRR | Morphology R@1/R@3/R@5/R@10/MRR |
|---|---:|---|---|
| short | 6 | 0.1667/0.3333/0.6667/1.0000/0.3630 | 0.1667/0.3333/0.6667/1.0000/0.3694 |
| medium | 28 | 0.4464/0.6607/0.7679/0.8750/0.6183 | 0.5179/0.7321/0.8393/0.9286/0.6741 |
| long | 1 | 0.0000/0.3333/0.3333/0.3333/0.5000 | 0.0000/0.3333/0.3333/0.3333/0.3333 |

## 14. Query-drift analysis

Queries adding three or more terms are shown with their Top-5 documents before and after. A changed list signals retrieval drift, not necessarily irrelevance.

- eval_003: `How does Indian law define a magic remedy or related terms used in drug advertisements?`; expanded `How does Indian law define a magic remedy or related terms used in drug advertisements? indians term drugs advertisement`; +4 terms (indians, term, drugs, advertisement); target ranks [1] → [1].
  - Baseline Top-5: Drugs Magic Remedies Act section 2, Drugs Cosmetics Act section 3, Drugs Magic Remedies Act section 5, Drugs Magic Remedies Act, Drugs Magic Remedies Act section 4
  - Morphology Top-5: Drugs Magic Remedies Act section 2, Drugs Cosmetics Act section 3, Drugs Magic Remedies Act section 4, Drugs Magic Remedies Act section 5, Drugs Magic Remedies Act section 1
- eval_005: `Which kinds of subject matter are not inventions under Indian patent law?`; expanded `Which kinds of subject matter are not inventions under Indian patent law? kind matters invention indians patents`; +5 terms (kind, matters, invention, indians, patents); target ranks [1] → [1].
  - Baseline Top-5: Patent Act 2024 section 3, Patent Act 2024 section 49, Patent Act 2024 section 39, Patent Act 2024 section 25, Patent Act 2024 section 89
  - Morphology Top-5: Patent Act 2024 section 3, Patent Act 2024 section 39, Patent Act 2024 section 49, Patent Act 2024 section 25, Patent Act 2024 section 89
- eval_007: `How does TRIPS describe the subject matter that members must make eligible for patent protection?`; expanded `How does TRIPS describe the subject matter that members must make eligible for patent protection? matters member makes patents protections`; +5 terms (matters, member, makes, patents, protections); target ranks [2] → [3].
  - Baseline Top-5: Trips Agreement article 28, Trips Agreement article 27, Trips Agreement article 40, Trips Agreement article 1, Trips Agreement article 34
  - Morphology Top-5: Trips Agreement article 40, Trips Agreement article 28, Trips Agreement article 27, Trips Agreement article 34, Trips Agreement article 4
- eval_009: `What information belongs in a patent specification filed in India?`; expanded `What information belongs in a patent specification filed in India? belong patents specifications`; +3 terms (belong, patents, specifications); target ranks [8] → [8].
  - Baseline Top-5: Patent Act 2024 section 13, Patent Act 2024 section 8, Patent Act 2024 section 33, Patent Act 2024 section 25, Patent Rules 2024
  - Morphology Top-5: Patent Act 2024 section 13, Patent Act 2024 section 8, Patent Act 2024 section 25, Patent Act 2024 section 9, Patent Act 2024 section 138
- eval_010: `What legal effect follows when the Controller grants a patent?`; expanded `What legal effect follows when the Controller grants a patent? effects follow controllers grant patents`; +5 terms (effects, follow, controllers, grant, patents); target ranks [7] → [1].
  - Baseline Top-5: Patent Act 2024 section 20, Patent Act 2024 section 117E, Patent Act 2024 section 51, Patent Act 2024 section 44, Patent Act 2024 section 132
  - Morphology Top-5: Patent Act 2024 section 43, Patent Act 2024 section 91, Patent Act 2024 section 117E, Patent Act 2024 section 51, Patent Act 2024 section 88
- eval_011: `What grounds could prevent registration of a proposed brand name as a trademark?`; expanded `What grounds could prevent registration of a proposed brand name as a trademark? ground registrations names trademarks`; +4 terms (ground, registrations, names, trademarks); target ranks [None] → [10].
  - Baseline Top-5: Trademarks Act section 11, Trademarks Act section 11, Trademarks Act section 27, Trademarks Act section 70, Trademarks Act section 36
  - Morphology Top-5: Trademarks Act section 11, Trademarks Act section 11, Trademarks Act section 70, Trademarks Act section 27, Trademarks Act section 31
- eval_012: `How are conflicting trademark applications or earlier marks considered during registration?`; expanded `How are conflicting trademark applications or earlier marks considered during registration? trademarks mark registrations`; +3 terms (trademarks, mark, registrations); target ranks [1] → [2].
  - Baseline Top-5: Trademarks Act section 11, Trademarks Act section 11, Trademarks Act section 33, Trademarks Act section 34, Trademarks Act section 27
  - Morphology Top-5: Trademarks Act section 31, Trademarks Act section 11, Trademarks Act section 33, Trademarks Act section 34, Trademarks Act section 27
- eval_014: `What makes a product name eligible for protection as a geographical indication?`; expanded `What makes a product name eligible for protection as a geographical indication? make products names protections indications`; +5 terms (make, products, names, protections, indications); target ranks [1] → [1].
  - Baseline Top-5: Gi Act section 9, Gi Act section 37, Gi Act section 2, Gi Act section 38, Gi Act section 26
  - Morphology Top-5: Gi Act section 9, Gi Act section 2, Gi Act section 37, Gi Act section 25, Gi Act section 38
- eval_015: `What rights does registration give the authorized users of a geographical indication?`; expanded `What rights does registration give the authorized users of a geographical indication? right registrations gives user indications`; +5 terms (right, registrations, gives, user, indications); target ranks [1] → [1].
  - Baseline Top-5: Gi Act section 21, Gi Act section 16, Gi Act section 42, Gi Act section 85, Gi Act section 28
  - Morphology Top-5: Gi Act section 21, Gi Act section 16, Gi Act section 23, Gi Act section 28, Gi Act section 42
- eval_016: `What features are excluded from the legal definition of a registrable design?`; expanded `What features are excluded from the legal definition of a registrable design? feature definitions designs`; +3 terms (feature, definitions, designs); target ranks [2] → [3].
  - Baseline Top-5: Designs Act section 21, Designs Act section 2, Designs Act section 19, Trademarks Act section 2, Patent Act 2024 section 2
  - Morphology Top-5: Designs Act section 23, Designs Act section 21, Designs Act section 2, Patent Act 2024 section 2, Designs Act section 19
- eval_018: `When must a person obtain approval before accessing biological resources in India?`; expanded `When must a person obtain approval before accessing biological resources in India? obtains approvals resource`; +3 terms (obtains, approvals, resource); target ranks [1] → [1].
  - Baseline Top-5: Biological Diversity Act 2002 section 3, Biological Diversity Act 2002 section 6, Biological Diversity Act 2002 section 19, Biological Diversity Amendment 2023 section 9, Biological Diversity Amendment 2023 section 19
  - Morphology Top-5: Biological Diversity Act 2002 section 3, Biological Diversity Act 2002 section 19, Biological Diversity Act 2002 section 6, Biological Diversity Amendment 2023 section 9, Biological Diversity Amendment 2023 section 19
- eval_019: `What approval is required before seeking an intellectual property right based on biological resources?`; expanded `What approval is required before seeking an intellectual property right based on biological resources? approvals rights resource`; +3 terms (approvals, rights, resource); target ranks [1] → [1].
  - Baseline Top-5: Biological Diversity Act 2002 section 6, Biological Diversity Amendment 2023 section 9, Biological Diversity Act 2002 section 21, Biological Diversity Act 2002 section 19, Biological Diversity Amendment 2023 section 6
  - Morphology Top-5: Biological Diversity Act 2002 section 6, Biological Diversity Amendment 2023 section 9, Biological Diversity Amendment 2023 section 6, Biological Diversity Act 2002 section 21, Biological Diversity Act 2002
- eval_024: `Can a seller make disease-treatment claims for an Ayurveda Aahara product?`; expanded `Can a seller make disease-treatment claims for an Ayurveda Aahara product? makes diseases treatments claim products`; +5 terms (makes, diseases, treatments, claim, products); target ranks [5] → [5].
  - Baseline Top-5: Fssai Ayurveda Aahara Regulations 2022 section 13, Fssai Ayurveda Aahara Regulations 2022 section 71, Fssai Ayurveda Aahara Regulations 2022 section 2, Fssai Ayurveda Aahara Regulations 2022 section 9, Fssai Ayurveda Aahara Regulations 2022 section 8
  - Morphology Top-5: Fssai Ayurveda Aahara Regulations 2022 section 13, Fssai Ayurveda Aahara Regulations 2022 section 71, Fssai Ayurveda Aahara Regulations 2022 section 2, Fssai Ayurveda Aahara Regulations 2022 section 9, Fssai Ayurveda Aahara Regulations 2022 section 8
- eval_025: `What is the objective of the Nagoya Protocol on access and benefit-sharing?`; expanded `What is the objective of the Nagoya Protocol on access and benefit-sharing? objectives protocols benefits`; +3 terms (objectives, protocols, benefits); target ranks [2] → [2].
  - Baseline Top-5: Nagoya Protocol article 6, Nagoya Protocol article 1, Nagoya Protocol article 3, Nagoya Protocol article 14, Nagoya Protocol article 4
  - Morphology Top-5: Nagoya Protocol article 6, Nagoya Protocol article 1, Nagoya Protocol article 14, Nagoya Protocol article 3, Nagoya Protocol article 4
- eval_026: `How does the Budapest Treaty make deposits of microorganisms recognizable across countries?`; expanded `How does the Budapest Treaty make deposits of microorganisms recognizable across countries? makes deposit microorganism country`; +4 terms (makes, deposit, microorganism, country); target ranks [3] → [1].
  - Baseline Top-5: Budapest Treaty, Budapest Treaty article 1, Budapest Treaty article 3, Budapest Treaty article 5, Budapest Treaty article 12
  - Morphology Top-5: Budapest Treaty article 3, Budapest Treaty, Budapest Treaty article 1, Budapest Treaty article 5, Budapest Treaty article 4
- eval_028: `What effect does an international trademark registration have under the Madrid Protocol?`; expanded `What effect does an international trademark registration have under the Madrid Protocol? effects trademarks registrations protocols`; +4 terms (effects, trademarks, registrations, protocols); target ranks [9] → [4].
  - Baseline Top-5: Madrid Protocol, Madrid Protocol, Madrid Protocol article 1, Madrid Protocol article 9, Madrid Protocol article 9bis
  - Morphology Top-5: Madrid Protocol, Madrid Protocol, Madrid Protocol article 1, Madrid Protocol article 4, Madrid Protocol article 9
- eval_030: `How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts?`; expanded `How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts? indians approvals resource relates protocols`; +5 terms (indians, approvals, resource, relates, protocols); target ranks [None, 2, None] → [None, 3, None].
  - Baseline Top-5: Nagoya Protocol article 16, Nagoya Protocol article 6, Nagoya Protocol article 2, Nagoya Protocol article 10, Nagoya Protocol article 32
  - Morphology Top-5: Nagoya Protocol article 16, Nagoya Protocol article 2, Nagoya Protocol article 6, Nagoya Protocol article 10, Nagoya Protocol article 32
- eval_031: `Compare Indian protection criteria for geographical indications with TRIPS protection of GIs.`; expanded `Compare Indian protection criteria for geographical indications with TRIPS protection of GIs. indians protections indication`; +3 terms (indians, protections, indication); target ranks [None, 2] → [None, 3].
  - Baseline Top-5: Gi Act section 1, Trips Agreement article 22, Gi Act section 21, Trips Agreement article 24, Gi Act section 5
  - Morphology Top-5: Gi Act section 21, Gi Act section 1, Trips Agreement article 22, Trips Agreement article 24, Gi Act section 11
- eval_032: `How does India?s design protection framework compare with the Hague Agreement?s international registration effects?`; expanded `How does India?s design protection framework compare with the Hague Agreement?s international registration effects? designs protections agreements registrations effect`; +5 terms (designs, protections, agreements, registrations, effect); target ranks [None, 1] → [10, 1].
  - Baseline Top-5: Hague Agreement article 14, Hague Agreement article 12, Hague Agreement article 1, Hague Agreement, Madrid Protocol article 4
  - Morphology Top-5: Hague Agreement article 14, Hague Agreement article 1, Hague Agreement article 12, Hague Agreement, Hague Agreement article 17
- eval_034: `What is the purpose of Article 6 of the Nagoya Protocol on access to genetic resources?`; expanded `What is the purpose of Article 6 of the Nagoya Protocol on access to genetic resources? purposes protocols resource`; +3 terms (purposes, protocols, resource); target ranks [1] → [1].
  - Baseline Top-5: Nagoya Protocol article 6, Trips Agreement article 6, Pct article 6, Wipo Gratk Treaty 2024 article 6, Budapest Treaty article 6
  - Morphology Top-5: Nagoya Protocol article 6, Trips Agreement article 6, Pct article 6, Wipo Gratk Treaty 2024 article 6, Budapest Treaty article 6

## 15. Expansion-strength ablation

A is no expansion. B exactly reuses the Stage 6H function (up to five corpus-attested singular/plural forms). C keeps only direct suffix-removal variants from that same function and vocabulary. D is not applicable: Stage 6H defines no stronger mode beyond its existing five-term cap, and adding rules would violate the no-redesign constraint.

Overall and category metrics are reported in Sections 3–5; the conservative column isolates one smaller subset of existing variants without adding an expansion rule.

| Variant vs baseline | Improved | Unchanged | Degraded | Newly recovered | Newly lost |
|---|---:|---:|---:|---:|---:|
| Current morphology | 6 | 25 | 7 | 2 | 0 |
| Conservative morphology | 5 | 30 | 4 | 0 | 1 |

Conservative-arm interpretation: deltas vs baseline are recall@1 +0.0286, recall@3 +0.0286, recall@5 +0.0286, recall@10 -0.0286, mrr +0.0226. It has fewer degraded rank transitions than the full variant (4 vs 7), but it introduces 1 newly lost target(s). This is a possible future conditional design to study, not evidence that it is already safer.

## 16. Holdout/generalization diagnostic

Deterministic split by original evaluation order: odd-position answerable queries are the analysis subset; even-position queries are holdout. This is small and not statistically significant.

| Split | n | Baseline R@1/R@3/R@5/R@10/MRR | Morphology R@1/R@3/R@5/R@10/MRR |
|---|---:|---|---|
| Analysis (odd order) | 18 | 0.4444/0.6111/0.7222/0.8889/0.6002 | 0.3889/0.6111/0.7222/0.9444/0.5588 |
| Holdout (even order) | 17 | 0.3235/0.5784/0.7549/0.8725/0.5404 | 0.5000/0.6961/0.8725/0.9020/0.6686 |

## 17. Root-cause interpretation

Observed target-level changes: 6 improved, 25 unchanged, 7 degraded, 2 newly recovered, and 0 newly lost. New competing rows are reported for regressions. These are rank associations: per-term counts do not prove which token caused a result to move.

## 18. Recommendation

Recommendation: **B. Morphology expansion is promising but requires a conservative/conditional design before production.** The overall reproduction and holdout split should be weighed alongside explicit-provision safety, category-level regressions, comparison target coverage, and term-level associations. This analysis does not authorize or implement a production change.

## Validation and unchanged-state checks

Integrity check: PASS; Chroma count 1349; protected hashes unchanged.
- `corpus (recursive manifest)`: `1e37b22815e50793bf606fc5ce9cd7ee7e5575af3b5aec2dc28851df553e5dbe`
- `rag-service/app (recursive source manifest)`: `73257f6c4ef9e6555b65b536b18d8129abb3a8a9e4494b31588e9c1f1ea54706`
- `rag-service\app\retriever.py`: `3beb69805338d0901ce45f257bf98181cdb62f0426f2a1f895389ca43374f679`
- `rag-service\data\chunks.json`: `521d427fabfbec7ba22e34aaf200f62e0a437a9e719a6832ea31329218444e8c`
- `rag-service\data\extracted_documents.json`: `d48f09a7e79a559974c624af318f27e0f8a2dce21463d312852b7a4307488f32`
- `rag-service\tests\eval_set.json`: `a8bb0dc4deeb9bbc03a483c1fee4af123db79d2133192b70c9b1d341b4e8b664`