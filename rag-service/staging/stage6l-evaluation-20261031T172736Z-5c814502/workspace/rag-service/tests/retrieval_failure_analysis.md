# Stage 6C Retrieval Failure Analysis

## 1. Executive summary

Analyzed 12 non-abstention queries with at least one expected target missing from hybrid top 5 or found only at ranks 6-10. Dense, BM25, and hybrid rankings were generated through the existing retriever methods. This is diagnostic analysis only; observations do not establish legal correctness.

Stage 6B reference metrics: Recall@1 0.4000; Recall@3 0.4952; Recall@5 0.7095; Recall@10 0.8381; MRR 0.5501.

## 2. Overall failure count

- Failed queries (one or more expected targets outside top 5): **12 / 35**.
- Failed expected-target instances by candidate pattern: {'BM25 only in top 10': 3, 'neither dense nor BM25 top 10': 6, 'dense only in top 10': 4}.

## 3. Failure table

| ID | Category | Jurisdiction | Intent | Query | Expected targets and hybrid ranks |
|---|---|---|---|---|---|
| eval_007 | patentability | International | general | How does TRIPS describe the subject matter that members must make eligible for patent protection? | Trips Agreement article 27: rank None (R1=False, R3=False, R5=False, R10=False) |
| eval_009 | patent_procedure | India | general | What information belongs in a patent specification filed in India? | Patent Act 2024 section 10: rank None (R1=False, R3=False, R5=False, R10=False) |
| eval_011 | trademarks | India | general | What grounds could prevent registration of a proposed brand name as a trademark? | Trademarks Act section 9: rank None (R1=False, R3=False, R5=False, R10=False) |
| eval_017 | designs | India | general | How long does registration of an industrial design protect it under the Designs Act? | Designs Act section 11: rank 7 (R1=False, R3=False, R5=False, R10=True) |
| eval_023 | ayurveda_food_regulatory | India | general | What does the Ayurveda Aahara regulation require for labeling these products? | Fssai Ayurveda Aahara Regulations 2022 section 12: rank 6 (R1=False, R3=False, R5=False, R10=True) |
| eval_025 | international_treaties | International | purpose | What is the objective of the Nagoya Protocol on access and benefit-sharing? | Nagoya Protocol article 1: rank 7 (R1=False, R3=False, R5=False, R10=True) |
| eval_027 | international_treaties | International | general | What is the effect of an international patent application under the PCT? | Pct article 11: rank 6 (R1=False, R3=False, R5=False, R10=True) |
| eval_028 | international_treaties | International | general | What effect does an international trademark registration have under the Madrid Protocol? | Madrid Protocol article 4: rank None (R1=False, R3=False, R5=False, R10=False) |
| eval_029 | comparisons | all | comparison | Compare India?s exclusions from patentability with TRIPS rules on patentable subject matter. | Patent Act 2024 section 3: rank None (R1=False, R3=False, R5=False, R10=False)<br>Trips Agreement article 27: rank 1 (R1=True, R3=True, R5=True, R10=True) |
| eval_030 | comparisons | all | comparison | How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts? | Biological Diversity Act 2002 section 6: rank None (R1=False, R3=False, R5=False, R10=False)<br>Nagoya Protocol article 6: rank 2 (R1=False, R3=True, R5=True, R10=True)<br>Nagoya Protocol article 5: rank None (R1=False, R3=False, R5=False, R10=False) |
| eval_031 | comparisons | all | comparison | Compare Indian protection criteria for geographical indications with TRIPS protection of GIs. | Gi Act section 9: rank 8 (R1=False, R3=False, R5=False, R10=True)<br>Trips Agreement article 22: rank 5 (R1=False, R3=False, R5=True, R10=True) |
| eval_032 | comparisons | all | comparison | How does India?s design protection framework compare with the Hague Agreement?s international registration effects? | Designs Act section 4: rank None (R1=False, R3=False, R5=False, R10=False)<br>Hague Agreement article 14: rank 1 (R1=True, R3=True, R5=True, R10=True) |

### Per-failure target ranks and top-10 retrieved results

#### eval_007 (patentability)
Query: How does TRIPS describe the subject matter that members must make eligible for patent protection?  
Jurisdiction: International; intent: general.
- Expected Trips Agreement (international:international/trips_agreement), article 27 (Patentable Subject Matter); rank=None; top1=False; top3=False; top5=False; top10=False; dense=None; BM25=6; BM25 only in top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Trips Agreement | international:international/trips_agreement | International | article | 28 | Rights Conferred | 0.03036576949620428 | 9 | 3 |
| 2 | Trips Agreement | international:international/trips_agreement | International | article | 70 | Protection of Existing Subject Matter | 0.01639344262295082 |  | 1 |
| 3 | Trips Agreement | international:international/trips_agreement | International | article | 29 | Conditions on Patent Applicants | 0.01639344262295082 | 1 |  |
| 4 | Trips Agreement | international:international/trips_agreement | International | article | 15 | Protectable Subject Matter | 0.016129032258064516 |  | 2 |
| 5 | Pct | international:international/pct | International | article | 44 | Seeking Two Kinds of Protection | 0.016129032258064516 | 2 |  |
| 6 | Trips Agreement | international:international/trips_agreement | International | article | 26 | Protection | 0.015873015873015872 | 3 |  |
| 7 | Trips Agreement | international:international/trips_agreement | International | article | 23 | Additional Protection for Geographical Indications | 0.015625 |  | 4 |
| 8 | Trips Agreement | international:international/trips_agreement | International | article | 30 | Exceptions to Rights Conferred | 0.015625 | 4 |  |
| 9 | Cbd | international:international/cbd | International | article | 15 | The final decision of the arbitral tribunal shall be confined to the subject-matter of the | 0.015384615384615385 |  | 5 |
| 10 | Trips Agreement | international:international/trips_agreement | International | article | 68 | Council for Trade-Related Aspects of | 0.015384615384615385 | 5 |  |

#### eval_009 (patent_procedure)
Query: What information belongs in a patent specification filed in India?  
Jurisdiction: India; intent: general.
- Expected Patent Act 2024 (india:national/patent_act_2024), section 10 (Contents of specifications); rank=None; top1=False; top3=False; top5=False; top10=False; dense=None; BM25=None; neither dense nor BM25 top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 13 | Search for anticipation by previous publication and by prior | 0.031544957774465976 | 6 | 1 |
| 2 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 8 | Information and undertaking regarding foreign applications. (1) | 0.03057889822595705 | 3 | 8 |
| 3 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 25 | Opposition to the patent | 0.029910714285714284 | 4 | 10 |
| 4 | Patent Rules 2024 | india:national/patent-rules-2024 | India |  |  |  | 0.029418126757516764 | 9 | 7 |
| 5 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 138 | Supplementary provisions as to convention applications | 0.01639344262295082 | 1 |  |
| 6 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 33 | Anticipation by use and publication after provisional | 0.016129032258064516 |  | 2 |
| 7 | Patent Rules 2024 | india:national/patent-rules-2024 | India |  |  |  | 0.016129032258064516 | 2 |  |
| 8 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 25 | Opposition to the patent | 0.015873015873015872 |  | 3 |
| 9 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 42 | Savings respecting disclosure to Government | 0.015625 |  | 4 |
| 10 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 29 | Anticipation by previous publication | 0.015384615384615385 |  | 5 |

#### eval_011 (trademarks)
Query: What grounds could prevent registration of a proposed brand name as a trademark?  
Jurisdiction: India; intent: general.
- Expected Trademarks Act (india:national/trademarks_act), section 9 (None); rank=None; top1=False; top3=False; top5=False; top10=False; dense=None; BM25=None; neither dense nor BM25 top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Trademarks Act | india:national/trademarks_act | India | section | 11 |  | 0.03177805800756621 | 1 | 5 |
| 2 | Trademarks Act | india:national/trademarks_act | India | section | 11 |  | 0.03128054740957967 | 6 | 2 |
| 3 | Trademarks Act | india:national/trademarks_act | India | section | 70 | A mark shall not be registrable as a certification trade mark in the name of a | 0.01639344262295082 |  | 1 |
| 4 | Drugs Cosmetics Act | india:national/drugs_cosmetics_act | India | section | 9D | Spurious cosmetics | 0.016129032258064516 | 2 |  |
| 5 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 13 | Other requirement for Ayurveda Aahara .- Every label of Ayurveda Aahara shall specify the | 0.015873015873015872 |  | 3 |
| 6 | Trademarks Act | india:national/trademarks_act | India | section | 27 |  | 0.015873015873015872 | 3 |  |
| 7 | Trademarks Act | india:national/trademarks_act | India | section | 49 |  | 0.015625 |  | 4 |
| 8 | Trademarks Act | india:national/trademarks_act | India | section | 35 | Nothing in this Act shall entitle the proprietor or a registered user of a registered | 0.015625 | 4 |  |
| 9 | Trademarks Act | india:national/trademarks_act | India | section | 59 |  | 0.015384615384615385 | 5 |  |
| 10 | Trademarks Act | india:national/trademarks_act | India | section | 2 |  | 0.015151515151515152 |  | 6 |

#### eval_017 (designs)
Query: How long does registration of an industrial design protect it under the Designs Act?  
Jurisdiction: India; intent: general.
- Expected Designs Act (india:national/designs_act), section 11 (None); rank=7; top1=False; top3=False; top5=False; top10=True; dense=4; BM25=None; dense only in top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Designs Act | india:national/designs_act | India | section | 21 | The exhibition of a design, or of any article to which a design is | 0.03225806451612903 | 2 | 2 |
| 2 | Designs Act | india:national/designs_act | India | section | 48 |  | 0.03177805800756621 | 5 | 1 |
| 3 | Designs Act | india:national/designs_act | India | section | 1 |  | 0.030776515151515152 | 6 | 4 |
| 4 | Designs Act | india:national/designs_act | India | section | 14 |  | 0.03057889822595705 | 3 | 8 |
| 5 | Designs Act | india:national/designs_act | India | section | 20 | A registered design shall have to all intents the like effect as | 0.01639344262295082 | 1 |  |
| 6 | Patent Rules 2024 | india:national/patent-rules-2024 | India |  |  |  | 0.015873015873015872 |  | 3 |
| 7 | Designs Act | india:national/designs_act | India | section | 11 |  | 0.015625 | 4 |  |
| 8 | Designs Act | india:national/designs_act | India | section | 7 | The Controller shall, as soon as may be after the registration of a design, cause | 0.015384615384615385 |  | 5 |
| 9 | Designs Act | india:national/designs_act | India | section | 19 |  | 0.015151515151515152 |  | 6 |
| 10 | Designs Act | india:national/designs_act | India | section | 46 | Notwithstanding anything contained in this Act, the Controller | 0.014925373134328358 |  | 7 |

#### eval_023 (ayurveda_food_regulatory)
Query: What does the Ayurveda Aahara regulation require for labeling these products?  
Jurisdiction: India; intent: general.
- Expected Fssai Ayurveda Aahara Regulations 2022 (india:national/fssai_ayurveda_aahara_regulations_2022), section 12 (Labelling of Ayurveda Aahara .- The labelling of Ayurveda Aahara shall be in accordance wi th); rank=6; top1=False; top3=False; top5=False; top10=True; dense=1; BM25=None; dense only in top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 3 | General requirements.- (1) Food Business Operators shall formulate Ayurveda Aahara in accordance | 0.03177805800756621 | 5 | 1 |
| 2 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 14 | Information by the Food Business Operator to Food Authority. - The Food Business Operator | 0.031754032258064516 | 4 | 2 |
| 3 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 13 | Other requirement for Ayurveda Aahara .- Every label of Ayurveda Aahara shall specify the | 0.03125763125763126 | 3 | 5 |
| 4 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 2 | Definitions.- (a) “Act” means the Food Safety and Standards Act, 2006 (34 of 2006) | 0.030117753623188408 | 9 | 4 |
| 5 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 71 | Yogaratna Samgraha | 0.029631255487269532 | 8 | 7 |
| 6 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 12 | Labelling of Ayurveda Aahara .- The labelling of Ayurveda Aahara shall be in accordance wi th | 0.01639344262295082 | 1 |  |
| 7 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 6 | Packaging.- Ayurveda Aahara shall conform to the Food Safety and Standards (Packaging) | 0.016129032258064516 | 2 |  |
| 8 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 10 | Prior approval for Ayurveda Aahara . - If Ayurveda Aahara need prior approval as per Schedule | 0.015873015873015872 |  | 3 |
| 9 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 5 | Contaminants.- The products cover ed under these regulations shall conform to the safety | 0.015151515151515152 |  | 6 |
| 10 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 1 |  | 0.015151515151515152 | 6 |  |

#### eval_025 (international_treaties)
Query: What is the objective of the Nagoya Protocol on access and benefit-sharing?  
Jurisdiction: International; intent: purpose.
- Expected Nagoya Protocol (international:international/nagoya-protocol), article 1 (OBJECTIVE); rank=7; top1=False; top3=False; top5=False; top10=True; dense=None; BM25=6; BM25 only in top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 6 | ACCESS TO GENETIC RESOURCES | 0.03252247488101534 | 2 | 1 |
| 2 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 14 | THE ACCESS AND BENEFIT-SHARING CLEARING-HOUSE | 0.029857397504456328 | 6 | 8 |
| 3 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 10 | GLOBAL MULTILATERAL BENEFIT-SHARING MECHANISM | 0.032018442622950824 | 1 | 4 |
| 4 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 16 | COMPLIANCE WITH DOMESTIC LEGISLATION OR | 0.031009615384615385 | 4 | 5 |
| 5 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 25 | FINANCIAL MECHANISM AND RESOURCES | 0.030798389007344232 | 3 | 7 |
| 6 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 18 | COMPLIANCE WITH MUTUALLY AGREED TERMS | 0.029877369007803793 | 5 | 9 |
| 7 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 1 | OBJECTIVE | 0.015151515151515152 |  | 6 |
| 8 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 3 | SCOPE | 0.016129032258064516 |  | 2 |
| 9 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 3 | SCOPE | 0.015873015873015872 |  | 3 |
| 10 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 4 | RELATIONSHIP WITH INTERNATIONAL | 0.014925373134328358 | 7 |  |

#### eval_027 (international_treaties)
Query: What is the effect of an international patent application under the PCT?  
Jurisdiction: International; intent: general.
- Expected Pct (international:international/pct), article 11 (Filing Date and Effects of the International Application); rank=6; top1=False; top3=False; top5=False; top10=True; dense=None; BM25=3; BM25 only in top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Pct | international:international/pct | International | article | 45 | Regional Patent Treaties | 0.032018442622950824 | 1 | 4 |
| 2 | Pct | international:international/pct | International | article | 4 | The Request | 0.029437229437229435 | 6 | 10 |
| 3 | Budapest Treaty | international:international/budapest_treaty | International | article | 2 | Definitions | 0.015384615384615385 |  | 5 |
| 4 | Pct | international:international/pct | International | article | 35 | The International Preliminary Examination Report | 0.015384615384615385 | 5 |  |
| 5 | Pct | international:international/pct | International | article | 2 | Definitions | 0.014925373134328358 | 7 |  |
| 6 | Pct | international:international/pct | International | article | 11 | Filing Date and Effects of the International Application | 0.015873015873015872 |  | 3 |
| 7 | Madrid Protocol | international:international/madrid_protocol | International | article | 15 | Denunciation | 0.014925373134328358 |  | 7 |
| 8 | Pct | international:international/pct | International | article | 8 | Claiming Priority | 0.01639344262295082 |  | 1 |
| 9 | Budapest Treaty | international:international/budapest_treaty | International | article | 3 | Recognition and Effect of the Deposit | 0.016129032258064516 |  | 2 |
| 10 | Pct | international:international/pct | International | article | 1 | Establishment of a Union | 0.016129032258064516 | 2 |  |

#### eval_028 (international_treaties)
Query: What effect does an international trademark registration have under the Madrid Protocol?  
Jurisdiction: International; intent: general.
- Expected Madrid Protocol (international:international/madrid_protocol), article 4 (Effects of International Registration); rank=None; top1=False; top3=False; top5=False; top10=False; dense=8; BM25=None; dense only in top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Madrid Protocol | international:international/madrid_protocol | International |  |  |  | 0.03278688524590164 | 1 | 1 |
| 2 | Madrid Protocol | international:international/madrid_protocol | International |  |  |  | 0.03225806451612903 | 2 | 2 |
| 3 | Madrid Protocol | international:international/madrid_protocol | International | article | 1 | Membership in the Madrid Union | 0.03149801587301587 | 3 | 4 |
| 4 | Madrid Protocol | international:international/madrid_protocol | International | article | 9 | Recordal of Change in the Ownership of an International Registration | 0.03007688828584351 | 7 | 6 |
| 5 | Madrid Protocol | international:international/madrid_protocol | International | article | 5 | (2)(b), Article 5(2)(c) or Article 8(7) of this Protocol, by | 0.015873015873015872 |  | 3 |
| 6 | Trips Agreement | international:international/trips_agreement | International | article | 15 | Protectable Subject Matter | 0.015625 | 4 |  |
| 7 | Madrid Protocol | international:international/madrid_protocol | International | article | 9sexies | Relations Between States Party to both this Protocol and the Madrid | 0.015384615384615385 |  | 5 |
| 8 | Madrid Protocol | international:international/madrid_protocol | International | article | 2 | Securing Protection through International Registration | 0.015384615384615385 | 5 |  |
| 9 | Madrid Protocol | international:international/madrid_protocol | International | article | 16 | Signature; Languages; Depositary Functions | 0.015151515151515152 | 6 |  |
| 10 | Madrid Protocol | international:international/madrid_protocol | International | article | 4bis | Replacement of a National or Regional Registration by an | 0.014925373134328358 |  | 7 |

#### eval_029 (comparisons)
Query: Compare India?s exclusions from patentability with TRIPS rules on patentable subject matter.  
Jurisdiction: all; intent: comparison.
- Expected Patent Act 2024 (india:national/patent_act_2024), section 3 (What are not inventions); rank=None; top1=False; top3=False; top5=False; top10=False; dense=None; BM25=None; neither dense nor BM25 top 10.
- Expected Trips Agreement (international:international/trips_agreement), article 27 (Patentable Subject Matter); rank=1; top1=True; top3=True; top5=True; top10=True; dense=None; BM25=1; BM25 only in top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Trips Agreement | international:international/trips_agreement | International | article | 27 | Patentable Subject Matter | 0.01639344262295082 |  | 1 |
| 2 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 83 | General principles applicable to working of patented inventions | 0.01639344262295082 | 1 |  |
| 3 | Trips Agreement | international:international/trips_agreement | International | article | 28 | Rights Conferred | 0.016129032258064516 |  | 2 |
| 4 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 84 | Compulsory licences | 0.016129032258064516 | 2 |  |
| 5 | Trips Agreement | international:international/trips_agreement | International | article | 44 | Injunctions | 0.015873015873015872 |  | 3 |
| 6 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 25 | Opposition to the patent | 0.015873015873015872 | 3 |  |
| 7 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 48 | Rights of patentees | 0.015625 |  | 4 |
| 8 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 39 | Residents not to apply for patents outside India without prior | 0.015625 | 4 |  |
| 9 | Tkdl Background 2021 | india:national/tkdl_background_2021 | India |  |  |  | 0.015384615384615385 |  | 5 |
| 10 | Patent Rules 2024 | india:national/patent-rules-2024 | India |  |  |  | 0.015384615384615385 | 5 |  |

#### eval_030 (comparisons)
Query: How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts?  
Jurisdiction: all; intent: comparison.
- Expected Biological Diversity Act 2002 (india:national/biological_diversity_act_2002), section 6 (Application for intellectual property rights not to be made without approval of National); rank=None; top1=False; top3=False; top5=False; top10=False; dense=None; BM25=None; neither dense nor BM25 top 10.
- Expected Nagoya Protocol (international:international/nagoya-protocol), article 6 (ACCESS TO GENETIC RESOURCES); rank=2; top1=False; top3=True; top5=True; top10=True; dense=1; BM25=4; both dense and BM25 candidates.
- Expected Nagoya Protocol (international:international/nagoya-protocol), article 5 (FAIR AND EQUITABLE BENEFIT-SHARING); rank=None; top1=False; top3=False; top5=False; top10=False; dense=None; BM25=None; neither dense nor BM25 top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 16 | COMPLIANCE WITH DOMESTIC LEGISLATION OR | 0.032018442622950824 | 4 | 1 |
| 2 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 6 | ACCESS TO GENETIC RESOURCES | 0.032018442622950824 | 1 | 4 |
| 3 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 2 | USE OF TERMS | 0.03200204813108039 | 3 | 2 |
| 4 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 10 | GLOBAL MULTILATERAL BENEFIT-SHARING MECHANISM | 0.03200204813108039 | 2 | 3 |
| 5 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 32 | SIGNATURE | 0.030536130536130537 | 5 | 6 |
| 6 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 13 | NATIONAL FOCAL POINTS AND COMPETENT | 0.015384615384615385 |  | 5 |
| 7 | Biological Diversity Amendment 2023 | india:national/biological_diversity_amendment_2023 | India | section | 19 | In section 21 of the principal Act, | 0.015151515151515152 | 6 |  |
| 8 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 3 | SCOPE | 0.014925373134328358 |  | 7 |
| 9 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 3 | SCOPE | 0.014925373134328358 | 7 |  |
| 10 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 18 | COMPLIANCE WITH MUTUALLY AGREED TERMS | 0.014705882352941176 |  | 8 |

#### eval_031 (comparisons)
Query: Compare Indian protection criteria for geographical indications with TRIPS protection of GIs.  
Jurisdiction: all; intent: comparison.
- Expected Gi Act (india:national/gi_act), section 9 (A geographical indication); rank=8; top1=False; top3=False; top5=False; top10=True; dense=4; BM25=None; dense only in top 10.
- Expected Trips Agreement (international:international/trips_agreement), article 22 (Protection of Geographical Indications); rank=5; top1=False; top3=False; top5=True; top10=True; dense=None; BM25=2; BM25 only in top 10.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Gi Act | india:national/gi_act | India | section | 1 |  | 0.031754032258064516 | 2 | 4 |
| 2 | Trips Agreement | international:international/trips_agreement | International | article | 24 | International Negotiations; Exceptions | 0.029418126757516764 | 7 | 9 |
| 3 | Trips Agreement | international:international/trips_agreement | International | article | 23 | Additional Protection for Geographical Indications | 0.01639344262295082 |  | 1 |
| 4 | Gi Act | india:national/gi_act | India | section | 21 |  | 0.01639344262295082 | 1 |  |
| 5 | Trips Agreement | international:international/trips_agreement | International | article | 22 | Protection of Geographical Indications | 0.016129032258064516 |  | 2 |
| 6 | Gi Act | india:national/gi_act | India | section | 6 |  | 0.015873015873015872 |  | 3 |
| 7 | Gi Act | india:national/gi_act | India | section | 11 |  | 0.015873015873015872 | 3 |  |
| 8 | Gi Act | india:national/gi_act | India | section | 9 | A geographical indication | 0.015625 | 4 |  |
| 9 | Trips Agreement | international:international/trips_agreement | International | article | 70 | Protection of Existing Subject Matter | 0.015384615384615385 |  | 5 |
| 10 | Gi Act | india:national/gi_act | India | section | 87 |  | 0.015384615384615385 | 5 |  |

#### eval_032 (comparisons)
Query: How does India?s design protection framework compare with the Hague Agreement?s international registration effects?  
Jurisdiction: all; intent: comparison.
- Expected Designs Act (india:national/designs_act), section 4 (A design which); rank=None; top1=False; top3=False; top5=False; top10=False; dense=None; BM25=None; neither dense nor BM25 top 10.
- Expected Hague Agreement (international:international/hague_agreement), article 14 (Effects of the International Registration); rank=1; top1=True; top3=True; top5=True; top10=True; dense=1; BM25=2; both dense and BM25 candidates.
Top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Hague Agreement | international:international/hague_agreement | International | article | 14 | Effects of the International Registration | 0.03252247488101534 | 1 | 2 |
| 2 | Hague Agreement | international:international/hague_agreement | International | article | 12 | , the international registration shall have the same effect as a grant of protection for | 0.031009615384615385 | 4 | 5 |
| 3 | Hague Agreement | international:international/hague_agreement | International | article | 1 | Abbreviated Expressions | 0.030886196246139225 | 9 | 1 |
| 4 | Hague Agreement | international:international/hague_agreement | International |  |  |  | 0.03057889822595705 | 8 | 3 |
| 5 | Designs Act | india:national/designs_act | India | section | 44 |  | 0.016129032258064516 | 2 |  |
| 6 | Madrid Protocol | international:international/madrid_protocol | International | article | 4 | Effects of International Registration | 0.015873015873015872 | 3 |  |
| 7 | Hague Agreement | international:international/hague_agreement | International | article | 12 | Refusal | 0.015625 |  | 4 |
| 8 | Designs Act | india:national/designs_act | India | section | 46 | Notwithstanding anything contained in this Act, the Controller | 0.015384615384615385 | 5 |  |
| 9 | Hague Agreement | international:international/hague_agreement | International | article | 20 | Membership of the Hague Union | 0.015151515151515152 |  | 6 |
| 10 | Trademarks Act | india:national/trademarks_act | India | section | 154 |  | 0.015151515151515152 | 6 |  |


## 4. International treaty analysis

### eval_007: How does TRIPS describe the subject matter that members must make eligible for patent protection?
- Expected Trips Agreement Article 27; document name occurs in query: False; no explicit expected article number in query; title/query token overlap: ['matter', 'subject'].
  Dense rank=None; BM25 rank=6; hybrid rank=None; pattern: BM25 only in top 10.
- Retrieved top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Trips Agreement | international:international/trips_agreement | International | article | 28 | Rights Conferred | 0.03036576949620428 | 9 | 3 |
| 2 | Trips Agreement | international:international/trips_agreement | International | article | 70 | Protection of Existing Subject Matter | 0.01639344262295082 |  | 1 |
| 3 | Trips Agreement | international:international/trips_agreement | International | article | 29 | Conditions on Patent Applicants | 0.01639344262295082 | 1 |  |
| 4 | Trips Agreement | international:international/trips_agreement | International | article | 15 | Protectable Subject Matter | 0.016129032258064516 |  | 2 |
| 5 | Pct | international:international/pct | International | article | 44 | Seeking Two Kinds of Protection | 0.016129032258064516 | 2 |  |
| 6 | Trips Agreement | international:international/trips_agreement | International | article | 26 | Protection | 0.015873015873015872 | 3 |  |
| 7 | Trips Agreement | international:international/trips_agreement | International | article | 23 | Additional Protection for Geographical Indications | 0.015625 |  | 4 |
| 8 | Trips Agreement | international:international/trips_agreement | International | article | 30 | Exceptions to Rights Conferred | 0.015625 | 4 |  |
| 9 | Cbd | international:international/cbd | International | article | 15 | The final decision of the arbitral tribunal shall be confined to the subject-matter of the | 0.015384615384615385 |  | 5 |
| 10 | Trips Agreement | international:international/trips_agreement | International | article | 68 | Council for Trade-Related Aspects of | 0.015384615384615385 | 5 |  |

### eval_025: What is the objective of the Nagoya Protocol on access and benefit-sharing?
- Expected Nagoya Protocol Article 1; document name occurs in query: True; no explicit expected article number in query; title/query token overlap: ['objective'].
  Dense rank=None; BM25 rank=6; hybrid rank=7; pattern: BM25 only in top 10.
- Retrieved top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 6 | ACCESS TO GENETIC RESOURCES | 0.03252247488101534 | 2 | 1 |
| 2 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 14 | THE ACCESS AND BENEFIT-SHARING CLEARING-HOUSE | 0.029857397504456328 | 6 | 8 |
| 3 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 10 | GLOBAL MULTILATERAL BENEFIT-SHARING MECHANISM | 0.032018442622950824 | 1 | 4 |
| 4 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 16 | COMPLIANCE WITH DOMESTIC LEGISLATION OR | 0.031009615384615385 | 4 | 5 |
| 5 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 25 | FINANCIAL MECHANISM AND RESOURCES | 0.030798389007344232 | 3 | 7 |
| 6 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 18 | COMPLIANCE WITH MUTUALLY AGREED TERMS | 0.029877369007803793 | 5 | 9 |
| 7 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 1 | OBJECTIVE | 0.015151515151515152 |  | 6 |
| 8 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 3 | SCOPE | 0.016129032258064516 |  | 2 |
| 9 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 3 | SCOPE | 0.015873015873015872 |  | 3 |
| 10 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 4 | RELATIONSHIP WITH INTERNATIONAL | 0.014925373134328358 | 7 |  |

### eval_027: What is the effect of an international patent application under the PCT?
- Expected Pct Article 11; document name occurs in query: True; no explicit expected article number in query; title/query token overlap: ['application', 'international'].
  Dense rank=None; BM25 rank=3; hybrid rank=6; pattern: BM25 only in top 10.
- Retrieved top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Pct | international:international/pct | International | article | 45 | Regional Patent Treaties | 0.032018442622950824 | 1 | 4 |
| 2 | Pct | international:international/pct | International | article | 4 | The Request | 0.029437229437229435 | 6 | 10 |
| 3 | Budapest Treaty | international:international/budapest_treaty | International | article | 2 | Definitions | 0.015384615384615385 |  | 5 |
| 4 | Pct | international:international/pct | International | article | 35 | The International Preliminary Examination Report | 0.015384615384615385 | 5 |  |
| 5 | Pct | international:international/pct | International | article | 2 | Definitions | 0.014925373134328358 | 7 |  |
| 6 | Pct | international:international/pct | International | article | 11 | Filing Date and Effects of the International Application | 0.015873015873015872 |  | 3 |
| 7 | Madrid Protocol | international:international/madrid_protocol | International | article | 15 | Denunciation | 0.014925373134328358 |  | 7 |
| 8 | Pct | international:international/pct | International | article | 8 | Claiming Priority | 0.01639344262295082 |  | 1 |
| 9 | Budapest Treaty | international:international/budapest_treaty | International | article | 3 | Recognition and Effect of the Deposit | 0.016129032258064516 |  | 2 |
| 10 | Pct | international:international/pct | International | article | 1 | Establishment of a Union | 0.016129032258064516 | 2 |  |

### eval_028: What effect does an international trademark registration have under the Madrid Protocol?
- Expected Madrid Protocol Article 4; document name occurs in query: True; no explicit expected article number in query; title/query token overlap: ['international', 'registration'].
  Dense rank=8; BM25 rank=None; hybrid rank=None; pattern: dense only in top 10.
- Retrieved top 10:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Madrid Protocol | international:international/madrid_protocol | International |  |  |  | 0.03278688524590164 | 1 | 1 |
| 2 | Madrid Protocol | international:international/madrid_protocol | International |  |  |  | 0.03225806451612903 | 2 | 2 |
| 3 | Madrid Protocol | international:international/madrid_protocol | International | article | 1 | Membership in the Madrid Union | 0.03149801587301587 | 3 | 4 |
| 4 | Madrid Protocol | international:international/madrid_protocol | International | article | 9 | Recordal of Change in the Ownership of an International Registration | 0.03007688828584351 | 7 | 6 |
| 5 | Madrid Protocol | international:international/madrid_protocol | International | article | 5 | (2)(b), Article 5(2)(c) or Article 8(7) of this Protocol, by | 0.015873015873015872 |  | 3 |
| 6 | Trips Agreement | international:international/trips_agreement | International | article | 15 | Protectable Subject Matter | 0.015625 | 4 |  |
| 7 | Madrid Protocol | international:international/madrid_protocol | International | article | 9sexies | Relations Between States Party to both this Protocol and the Madrid | 0.015384615384615385 |  | 5 |
| 8 | Madrid Protocol | international:international/madrid_protocol | International | article | 2 | Securing Protection through International Registration | 0.015384615384615385 | 5 |  |
| 9 | Madrid Protocol | international:international/madrid_protocol | International | article | 16 | Signature; Languages; Depositary Functions | 0.015151515151515152 | 6 |  |
| 10 | Madrid Protocol | international:international/madrid_protocol | International | article | 4bis | Replacement of a National or Regional Registration by an | 0.014925373134328358 |  | 7 |

## 5. Patent procedure analysis

### eval_009: What information belongs in a patent specification filed in India?
- Expected Section 10 (Contents of specifications); dense=None, BM25=None, hybrid=None; neither dense nor BM25 top 10.
- Top 10 results:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 13 | Search for anticipation by previous publication and by prior | 0.031544957774465976 | 6 | 1 |
| 2 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 8 | Information and undertaking regarding foreign applications. (1) | 0.03057889822595705 | 3 | 8 |
| 3 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 25 | Opposition to the patent | 0.029910714285714284 | 4 | 10 |
| 4 | Patent Rules 2024 | india:national/patent-rules-2024 | India |  |  |  | 0.029418126757516764 | 9 | 7 |
| 5 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 138 | Supplementary provisions as to convention applications | 0.01639344262295082 | 1 |  |
| 6 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 33 | Anticipation by use and publication after provisional | 0.016129032258064516 |  | 2 |
| 7 | Patent Rules 2024 | india:national/patent-rules-2024 | India |  |  |  | 0.016129032258064516 | 2 |  |
| 8 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 25 | Opposition to the patent | 0.015873015873015872 |  | 3 |
| 9 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 42 | Savings respecting disclosure to Government | 0.015625 |  | 4 |
| 10 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 29 | Anticipation by previous publication | 0.015384615384615385 |  | 5 |

## 6. Ayurveda / regulatory analysis

### eval_023: What does the Ayurveda Aahara regulation require for labeling these products?
- Expected Fssai Ayurveda Aahara Regulations 2022 Section 12 (Labelling of Ayurveda Aahara .- The labelling of Ayurveda Aahara shall be in accordance wi th); dense=1, BM25=None, hybrid=6; dense only in top 10.
- Top 10 results:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 3 | General requirements.- (1) Food Business Operators shall formulate Ayurveda Aahara in accordance | 0.03177805800756621 | 5 | 1 |
| 2 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 14 | Information by the Food Business Operator to Food Authority. - The Food Business Operator | 0.031754032258064516 | 4 | 2 |
| 3 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 13 | Other requirement for Ayurveda Aahara .- Every label of Ayurveda Aahara shall specify the | 0.03125763125763126 | 3 | 5 |
| 4 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 2 | Definitions.- (a) “Act” means the Food Safety and Standards Act, 2006 (34 of 2006) | 0.030117753623188408 | 9 | 4 |
| 5 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 71 | Yogaratna Samgraha | 0.029631255487269532 | 8 | 7 |
| 6 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 12 | Labelling of Ayurveda Aahara .- The labelling of Ayurveda Aahara shall be in accordance wi th | 0.01639344262295082 | 1 |  |
| 7 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 6 | Packaging.- Ayurveda Aahara shall conform to the Food Safety and Standards (Packaging) | 0.016129032258064516 | 2 |  |
| 8 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 10 | Prior approval for Ayurveda Aahara . - If Ayurveda Aahara need prior approval as per Schedule | 0.015873015873015872 |  | 3 |
| 9 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 5 | Contaminants.- The products cover ed under these regulations shall conform to the safety | 0.015151515151515152 |  | 6 |
| 10 | Fssai Ayurveda Aahara Regulations 2022 | india:national/fssai_ayurveda_aahara_regulations_2022 | India | section | 1 |  | 0.015151515151515152 | 6 |  |

## 7. Comparison analysis

### eval_029: Compare India?s exclusions from patentability with TRIPS rules on patentable subject matter.
- Jurisdiction distribution: top 5 {'International': 3, 'India': 2}; top 10 {'International': 3, 'India': 7}.
- Expected India Patent Act 2024 section 3: hybrid rank None; dense None; BM25 None (neither dense nor BM25 top 10).
- Expected International Trips Agreement article 27: hybrid rank 1; dense None; BM25 1 (BM25 only in top 10).
- Full top 10 results:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Trips Agreement | international:international/trips_agreement | International | article | 27 | Patentable Subject Matter | 0.01639344262295082 |  | 1 |
| 2 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 83 | General principles applicable to working of patented inventions | 0.01639344262295082 | 1 |  |
| 3 | Trips Agreement | international:international/trips_agreement | International | article | 28 | Rights Conferred | 0.016129032258064516 |  | 2 |
| 4 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 84 | Compulsory licences | 0.016129032258064516 | 2 |  |
| 5 | Trips Agreement | international:international/trips_agreement | International | article | 44 | Injunctions | 0.015873015873015872 |  | 3 |
| 6 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 25 | Opposition to the patent | 0.015873015873015872 | 3 |  |
| 7 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 48 | Rights of patentees | 0.015625 |  | 4 |
| 8 | Patent Act 2024 | india:national/patent_act_2024 | India | section | 39 | Residents not to apply for patents outside India without prior | 0.015625 | 4 |  |
| 9 | Tkdl Background 2021 | india:national/tkdl_background_2021 | India |  |  |  | 0.015384615384615385 |  | 5 |
| 10 | Patent Rules 2024 | india:national/patent-rules-2024 | India |  |  |  | 0.015384615384615385 | 5 |  |

### eval_030: How do Indian approval rules for biological resources relate to Nagoya Protocol access and benefit-sharing concepts?
- Jurisdiction distribution: top 5 {'International': 5}; top 10 {'International': 9, 'India': 1}.
- Expected India Biological Diversity Act 2002 section 6: hybrid rank None; dense None; BM25 None (neither dense nor BM25 top 10).
- Expected International Nagoya Protocol article 6: hybrid rank 2; dense 1; BM25 4 (both dense and BM25 candidates).
- Expected International Nagoya Protocol article 5: hybrid rank None; dense None; BM25 None (neither dense nor BM25 top 10).
- Full top 10 results:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 16 | COMPLIANCE WITH DOMESTIC LEGISLATION OR | 0.032018442622950824 | 4 | 1 |
| 2 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 6 | ACCESS TO GENETIC RESOURCES | 0.032018442622950824 | 1 | 4 |
| 3 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 2 | USE OF TERMS | 0.03200204813108039 | 3 | 2 |
| 4 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 10 | GLOBAL MULTILATERAL BENEFIT-SHARING MECHANISM | 0.03200204813108039 | 2 | 3 |
| 5 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 32 | SIGNATURE | 0.030536130536130537 | 5 | 6 |
| 6 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 13 | NATIONAL FOCAL POINTS AND COMPETENT | 0.015384615384615385 |  | 5 |
| 7 | Biological Diversity Amendment 2023 | india:national/biological_diversity_amendment_2023 | India | section | 19 | In section 21 of the principal Act, | 0.015151515151515152 | 6 |  |
| 8 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 3 | SCOPE | 0.014925373134328358 |  | 7 |
| 9 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 3 | SCOPE | 0.014925373134328358 | 7 |  |
| 10 | Nagoya Protocol | international:international/nagoya-protocol | International | article | 18 | COMPLIANCE WITH MUTUALLY AGREED TERMS | 0.014705882352941176 |  | 8 |

### eval_031: Compare Indian protection criteria for geographical indications with TRIPS protection of GIs.
- Jurisdiction distribution: top 5 {'India': 2, 'International': 3}; top 10 {'India': 6, 'International': 4}.
- Expected India Gi Act section 9: hybrid rank 8; dense 4; BM25 None (dense only in top 10).
- Expected International Trips Agreement article 22: hybrid rank 5; dense None; BM25 2 (BM25 only in top 10).
- Full top 10 results:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Gi Act | india:national/gi_act | India | section | 1 |  | 0.031754032258064516 | 2 | 4 |
| 2 | Trips Agreement | international:international/trips_agreement | International | article | 24 | International Negotiations; Exceptions | 0.029418126757516764 | 7 | 9 |
| 3 | Trips Agreement | international:international/trips_agreement | International | article | 23 | Additional Protection for Geographical Indications | 0.01639344262295082 |  | 1 |
| 4 | Gi Act | india:national/gi_act | India | section | 21 |  | 0.01639344262295082 | 1 |  |
| 5 | Trips Agreement | international:international/trips_agreement | International | article | 22 | Protection of Geographical Indications | 0.016129032258064516 |  | 2 |
| 6 | Gi Act | india:national/gi_act | India | section | 6 |  | 0.015873015873015872 |  | 3 |
| 7 | Gi Act | india:national/gi_act | India | section | 11 |  | 0.015873015873015872 | 3 |  |
| 8 | Gi Act | india:national/gi_act | India | section | 9 | A geographical indication | 0.015625 | 4 |  |
| 9 | Trips Agreement | international:international/trips_agreement | International | article | 70 | Protection of Existing Subject Matter | 0.015384615384615385 |  | 5 |
| 10 | Gi Act | india:national/gi_act | India | section | 87 |  | 0.015384615384615385 | 5 |  |

### eval_032: How does India?s design protection framework compare with the Hague Agreement?s international registration effects?
- Jurisdiction distribution: top 5 {'International': 4, 'India': 1}; top 10 {'International': 7, 'India': 3}.
- Expected India Designs Act section 4: hybrid rank None; dense None; BM25 None (neither dense nor BM25 top 10).
- Expected International Hague Agreement article 14: hybrid rank 1; dense 1; BM25 2 (both dense and BM25 candidates).
- Full top 10 results:
| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |
|---:|---|---|---|---|---|---|---:|---:|---:|
| 1 | Hague Agreement | international:international/hague_agreement | International | article | 14 | Effects of the International Registration | 0.03252247488101534 | 1 | 2 |
| 2 | Hague Agreement | international:international/hague_agreement | International | article | 12 | , the international registration shall have the same effect as a grant of protection for | 0.031009615384615385 | 4 | 5 |
| 3 | Hague Agreement | international:international/hague_agreement | International | article | 1 | Abbreviated Expressions | 0.030886196246139225 | 9 | 1 |
| 4 | Hague Agreement | international:international/hague_agreement | International |  |  |  | 0.03057889822595705 | 8 | 3 |
| 5 | Designs Act | india:national/designs_act | India | section | 44 |  | 0.016129032258064516 | 2 |  |
| 6 | Madrid Protocol | international:international/madrid_protocol | International | article | 4 | Effects of International Registration | 0.015873015873015872 | 3 |  |
| 7 | Hague Agreement | international:international/hague_agreement | International | article | 12 | Refusal | 0.015625 |  | 4 |
| 8 | Designs Act | india:national/designs_act | India | section | 46 | Notwithstanding anything contained in this Act, the Controller | 0.015384615384615385 | 5 |  |
| 9 | Hague Agreement | international:international/hague_agreement | International | article | 20 | Membership of the Hague Union | 0.015151515151515152 |  | 6 |
| 10 | Trademarks Act | india:national/trademarks_act | India | section | 154 |  | 0.015151515151515152 | 6 |  |

## 8. Dense vs BM25 vs hybrid analysis

Target ranks below are 1-based ranks within each source's top 10. `None` means the target was not present in that candidate list.

| ID | Expected target | Dense | BM25 | Hybrid | Observable candidate pattern |
|---|---|---:|---:|---:|---|
| eval_007 | Trips Agreement article 27 | None | 6 | None | BM25 only in top 10 |
| eval_009 | Patent Act 2024 section 10 | None | None | None | neither dense nor BM25 top 10 |
| eval_011 | Trademarks Act section 9 | None | None | None | neither dense nor BM25 top 10 |
| eval_017 | Designs Act section 11 | 4 | None | 7 | dense only in top 10 |
| eval_023 | Fssai Ayurveda Aahara Regulations 2022 section 12 | 1 | None | 6 | dense only in top 10 |
| eval_025 | Nagoya Protocol article 1 | None | 6 | 7 | BM25 only in top 10 |
| eval_027 | Pct article 11 | None | 3 | 6 | BM25 only in top 10 |
| eval_028 | Madrid Protocol article 4 | 8 | None | None | dense only in top 10 |
| eval_029 | Patent Act 2024 section 3 | None | None | None | neither dense nor BM25 top 10 |
| eval_030 | Biological Diversity Act 2002 section 6 | None | None | None | neither dense nor BM25 top 10 |
| eval_030 | Nagoya Protocol article 5 | None | None | None | neither dense nor BM25 top 10 |
| eval_031 | Gi Act section 9 | 4 | None | 8 | dense only in top 10 |
| eval_032 | Designs Act section 4 | None | None | None | neither dense nor BM25 top 10 |

Interpretation is limited to returned ranks: a target in both dense and BM25 top 10 but below hybrid top 5 is consistent with fusion/ranking competition; presence in only one candidate list indicates source asymmetry; absence from both top 10 means this run does not show either source retrieving it strongly. These patterns do not prove the underlying cause.

## 9. Common failure patterns

- **international_treaties:** failures eval_025, eval_027, eval_028.
  - Observed: treaty documents are often present among top results while requested articles are at ranks 6-7 or absent. PCT Article 11 is BM25 rank 3, absent from dense top 10, and hybrid rank 6 while other PCT provisions receive both signals. Nagoya Article 1 is BM25-only at rank 6 and hybrid rank 7. Madrid Protocol Article 4 is dense-only at rank 8 and absent from hybrid top 10 despite multiple Madrid provisions in results. These indicate provision-level misses and source asymmetry; Article numbers are absent from those queries, so an exact-reference boost is unavailable. The observation does not prove semantic terminology mismatch.
- **patent_procedure:** failures eval_009.
  - Observed: eval_009 Section 10 is absent from both dense and BM25 top 10. Other Patent Act sections and Patent Rules chunks appear, so the document family is retrieved but the expected provision is not a strong candidate in this run. The query wording ('what information belongs in a patent specification') differs from the provision title ('Contents of specifications'); terminology mismatch is plausible, not proven.
- **ayurveda_food_regulatory:** failures eval_023.
  - Observed: eval_023 Section 12 is dense rank 1, absent from BM25 top 10, and hybrid rank 6; all top 10 results are from the same regulation document. The title uses 'Labelling' while the query uses 'labeling', a plausible lexical mismatch. The rank drop is consistent with single-source RRF competition against provisions with both dense and BM25 ranks.
- **comparisons:** failures eval_029, eval_030, eval_031, eval_032.
  - Observed: both jurisdictions appear in each top 10, but expected provisions are often missing. Eval_030 has only International results in top 5 and one India result in top 10, which is not the expected Biological Diversity Act Section 6. In eval_029, TRIPS Article 27 is BM25 rank 1 while Patent Act Section 3 is absent from both candidate top 10s. This is target-level coverage loss, not a jurisdiction-filter violation; the results do not prove why candidates were missed.
- **Queries without explicit Section/Article reference:** 12 of 12 failure queries lack an explicit provision reference; exact-reference boosts therefore do not apply to these queries.
- **Expected target at ranks 6-10:** 5 target instance(s).
- **Expected target absent from hybrid top 10:** 8 target instance(s).
- **Jurisdiction ranking:** comparison top-5/top-10 distributions are reported per query above; targets missing despite both jurisdictions appearing should be inspected as provision-ranking misses, not assumed jurisdiction-filter failures.
- **BM25 weakness / dense weakness / RRF competition:** consult the source ranks table; no cause is assigned where candidate ranks do not distinguish these possibilities.
- **Query-intent, expansion, or terminology mismatch:** only surface term overlap and existing ranks are observable here. The report does not infer semantic mismatch solely from a miss. Eval_029 and eval_032 contain literal question marks where apostrophes appear intended; those evaluation-set strings were left unchanged.

## 10. Recommended general improvements (not implemented)

1. Evaluate broader dense and BM25 candidate pools before fusion, then measure whether relevant targets are recovered without adding provision-specific boosts.
2. Test general legal-domain synonym/phrase expansion against a held-out set, especially procedural verbs and regulatory terms; preserve the original query and compare ablations.
3. Audit chunk boundaries and provision metadata for provisions with low target retrieval, without rewriting source text.
4. Run retrieval ablations (dense-only, BM25-only, RRF) on the same fixed set to quantify the contribution of each stage.
5. For comparison queries, evaluate target coverage by jurisdiction separately and test general diversity strategies without assuming equivalence between legal systems.
6. Add query-level examples and confidence intervals or per-query reporting to avoid over-interpreting small category samples.

No retrieval, ranking, corpus, chunk, index, or evaluation-set changes were made by this analysis script.
