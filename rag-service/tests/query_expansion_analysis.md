# Stage 6H Query Expansion Analysis

## 1. Executive summary

The deterministic analysis covered **35 answerable queries**, **40 expected targets**, and **1349 chunks**. Expansion variants were generated without reading expected target metadata. This is retrieval diagnostics only; it does not establish semantic or legal correctness.

## 2. Baseline and methodology

The Original variant uses unchanged Stage 6D `retrieve()` (dense + BM25, current RRF, intent/explicit handling, candidate depth, jurisdiction filter and comparison balancing). Lexical/morphology adds only corpus-attested singular/plural forms of query tokens. Corpus-derived adds up to three substantive terms that co-occur with query terms across at least two corpus provision units and are at or above median corpus IDF. The target itself is never consulted to construct either query.

Target-term IDF and corpus expansion statistics aggregate source chunks into provision units by document/provision identity; non-provision chunks remain separate. Document and jurisdiction frequencies are reported as separate counts. Token removal is generic stopwords, legal boilerplate, punctuation and numerals.

| Variant | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| Original | 0.3857 | 0.5952 | 0.7381 | 0.8810 | 0.5711 |
| Lexical/morphology | 0.4429 | 0.6524 | 0.7952 | 0.9238 | 0.6121 |
| Corpus-derived | 0.4429 | 0.5952 | 0.6810 | 0.8810 | 0.5943 |

Accepted Stage 6D baseline: R@1 **0.3857**, R@3 **0.5952**, R@5 **0.7381**, R@10 **0.8810**, MRR **0.5711**. The Original reproduction above is the direct analysis-run baseline.

## 3. Query/target terminology analysis

Each row is one expected target; term lists are corpus-derived and capped for readability. `Target terms` shows the highest-IDF target-only terms. `Target provision chunks` indicates how much source text was available for comparison.

| Query ID / intent | Expected target | Query terms | Important query terms | Important target-only terms | Shared terms | Query-only terms | Chunks |
|---|---|---|---|---|---|---|---:|
| eval_001 / definition | Patent Act 2024 section 2 | define, invention, patent, patents, related, terms | define, related, terms, invention, patents, patent | confers, skilled, corporation, feature, involves, provincial, compared, engaged, estate, fallen | invention, patent, patents | define, related, terms | 1 |
| eval_002 / definition | Biological Diversity Act 2002 section 2 | biodiversity, biological, define, india, research, resources | define, research, resources, biodiversity, biological, india | bioassay, breeding, characteris, conventional, crops, dairy, emulsifiers, enzymes, equita, etary | biodiversity, biological, india, research, resources | define | 1 |
| eval_003 / definition | Drugs Magic Remedies Act section 2 | advertisements, define, drug, indian, magic, related, remedy, terms, used | define, advertisements, remedy, magic, indian, related, drug, used | charm, circular, degrees, influencing, instance, kavacha, mantra, miraculous, orally, organic | drug, indian, magic, remedy, used | advertisements, define, related, terms | 1 |
| eval_004 / general | Gi Act section 2 | geographical, indication, indications, mean | mean, indications, indication, geographical | deals, exploits, identifies, suggesting, trades, abbreviation, band, bottle, capsule, casket | geographical, indication, indications | mean | 1 |
| eval_005 / prohibition | Patent Act 2024 section 3 | indian, inventions, kinds, matter, patent, subject | kinds, inventions, indian, matter, subject, patent | admixture, aggregation, algorithms, curative, duplication, employs, esters, ethers, frivolous, game | inventions | indian, kinds, matter, patent, subject | 1 |
| eval_006 / general | Patent Act 2024 section 4 | atomic, energy, india, invention, patented, relating | atomic, energy, patented, invention, relating, india | patentable, falling, inventions, granted, within, respect, patent | atomic, energy, invention, relating | india, patented | 1 |
| eval_007 / general | Trips Agreement article 27 | describe, eligible, make, matter, members, must, patent, protection, subject, trips | describe, must, eligible, trips, members, matter, protection, make | locally, ordre, synonymous, enjoyable, fields, generis, humans, surgical, diagnostic, discrimination | matter, members, patent, protection, subject | describe, eligible, make, must, trips | 1 |
| eval_008 / general | Patent Act 2024 section 6 | apply, assignee, entitled, india, patent | assignee, entitled, apply, india, patent | death, alone, jointly, deceased, inventor, claiming, representative, true, immediately, legal | apply, assignee, entitled, patent | india | 1 |
| eval_009 / general | Patent Act 2024 section 10 | belongs, filed, india, information, patent, specification | belongs, specification, filed, information, india, patent | begin, correctly, defining, illustrating, linked, succinct, supplemented, concept, depositing, depository | filed, india, information, patent, specification | belongs | 1 |
| eval_010 / general | Patent Act 2024 section 43 | controller, effect, follows, grants, legal, patent | grants, follows, legal, effect, controller, patent | expeditiously, thereby, jointly, thereupon, vested, seal, joint, refused, applicants, virtue | controller, patent | effect, follows, grants, legal | 1 |
| eval_011 / general | Trademarks Act section 9 | brand, grounds, name, prevent, proposed, registration, trademark | brand, trademark, proposed, grounds, prevent, name, registration | current, devoid, emblems, improper, religious, susceptibilities, hurt, obscene, scandalous, shape | proposed, registration | brand, grounds, name, prevent, trademark | 1 |
| eval_012 / general | Trademarks Act section 11 | applications, conflicting, considered, earlier, marks, registration, trademark | trademark, earlier, considered, marks, applications, registration, conflicting | absolute, consents, determing, disclosing, dissolve, fairs, forming, incidents, internaltional, mixture | applications, earlier, marks, registration, trademark | conflicting, considered | 3 |
| eval_013 / general | Trademarks Act section 19 | accepted, happens, registration, trademark | happens, trademark, accepted, registration | situate, arriving, conditional, registering, absolutely, desirous, accept, duration, materials, desires | accepted, registration | happens, trademark | 1 |
| eval_014 / general | Gi Act section 9 | eligible, geographical, indication, makes, name, product, protection | eligible, product, makes, indication, geographical, name, protection | disentitled, generic, disuse, originates, religious, susceptibilities, although, hurt, literally, obscene | geographical, indication, name, protection | eligible, makes, product | 1 |
| eval_015 / general | Gi Act section 21 | authorized, geographical, give, indication, registration, rights, users | authorized, users, indication, geographical, give, rights, registration | gement, infrin, anyone, resemble, sole, unregistered, respective, nearly, merely, limitation | geographical, give, indication, registration, rights, users | authorized | 1 |
| eval_016 / definition | Designs Act section 2 | definition, design, excluded, features, legal, registrable | excluded, features, definition, registrable, design, legal | acquires, artificial, combined, debt, devolved, elects, executes, judged, mechanical, ornament | definition, design, features, legal | excluded, registrable | 2 |
| eval_017 / general | Designs Act section 11 | design, designs, industrial, long, protect, registration | long, protect, design, industrial, designs, registration | extension, copyright, second, five, expiration, original, extend, payment, proprietor, years | design, designs, registration | industrial, long, protect | 1 |
| eval_018 / general | Biological Diversity Act 2002 section 3 | accessing, approval, biological, india, must, obtain, resources | accessing, must, obtain, approval, resources, biological, india | secti, foreigner, seminar, workshop, side, citizen, income, indians, controlled, codified | approval, biological, india, obtain, resources | accessing, must | 1 |
| eval_019 / general | Biological Diversity Act 2002 section 6 | approval, based, biological, intellectual, property, required, resources, right, seeking | seeking, based, approval, intellectual, resources, property, right, required | comme, depos, endorse, hich, intellectua, ited, rcial, cultivators, growers, practicing | approval, based, biological, intellectual, property, right | required, resources, seeking | 1 |
| eval_020 / general | Biological Diversity Act 2002 section 21 | benefits, biological, fairly, resources, shared, using | fairly, shared, using, benefits, resources, biological | aiding, indi, natio, sharin, venture, viduals, location, secures, commit, frame | benefits, biological, resources | fairly, shared, using | 1 |
| eval_021 / general | Nagoya Protocol article 7 | access, associated, genetic, knowledge, nagoya, protocol, resources, traditional | genetic, nagoya, traditional, access, associated, resources, protocol, knowledge | ensuring, involvement, domestic, held, accessed, communities, informed, indigenous, mutually, agreed | access, associated, genetic, knowledge, resources, traditional | nagoya, protocol | 1 |
| eval_022 / general | Nagoya Protocol article 12 | accessed, communities, customary, knowledge, laws, role, traditional | role, customary, accessed, communities, laws, traditional, knowledge | mechanisms, model, contractual, endeavour, community, minimum, women, clearing, protocols, implementing | communities, customary, knowledge, laws, traditional | accessed, role | 1 |
| eval_023 / general | Fssai Ayurveda Aahara Regulations 2022 section 12 | aahara, ayurveda, labeling, products, require | labeling, products, aahara, ayurveda, require | bangasena, display, labelling, safety, specific, standards, food, requirements, extraordinary, accordance | aahara, ayurveda | labeling, products, require | 5 |
| eval_024 / purpose | Fssai Ayurveda Aahara Regulations 2022 section 8 | aahara, ayurveda, claims, disease, make, product, seller, treatment | seller, disease, treatment, product, claims, aahara, ayurveda, make | curing, treating, kalpadruma, preventing, properties, labelling, presentation, refer, human, advertisement | aahara, ayurveda, disease | claims, make, product, seller, treatment | 5 |
| eval_025 / purpose | Nagoya Protocol article 1 | access, benefit, nagoya, objective, protocol, sharing | objective, nagoya, access, sharing, benefit, protocol | contributing, funding, technologies, thereby, utilization, components, taking, genetic, equitable, fair | access, objective, protocol, sharing | benefit, nagoya | 1 |
| eval_026 / general | Budapest Treaty article 3 | across, budapest, countries, deposits, make, microorganisms, recognizable, treaty | across, recognizable, deposits, microorganisms, budapest, countries, treaty, make | recognize, regulated, microorganism, substantive, sample, recognition, compliance, deposit, different, depositary | microorganisms, treaty | across, budapest, countries, deposits, make, recognizable | 1 |
| eval_027 / definition | Pct article 11 | effect, international, patent | effect, international, patent | anindicationthatitisintendedasaninternationalapplication, apartwhichonthefaceofitappearstobeaclaimorclaims, apartwhichonthefaceofitappearstobeadescription, astheinternationalfilingdatethedate, atthetimeofreceipt, consideredtobetheactualfilingdateineachdesignatedstate, dateofreceiptoftherequiredcorrection, invitetheapplicanttofiletherequiredcorrection, thedesignationofatleastonecontractingstate, theinternationalapplicationcontainsatleastthefollowingelements | effect, international | patent | 1 |
| eval_028 / general | Madrid Protocol article 4 | effect, international, madrid, protocol, registration, trademark | trademark, madrid, protocol, effect, international, registration | interna, tional, recordal, refusal, effects, effected, deposited, notified, direct, bureau | international, registration | effect, madrid, protocol, trademark | 1 |
| eval_029 / comparison | Patent Act 2024 section 3 | compare, exclusions, india, matter, patentability, patentable, subject, trips | patentability, patentable, trips, matter, india, subject, compare, exclusions | admixture, aggregation, algorithms, curative, duplication, employs, esters, ethers, frivolous, game | patentable | compare, exclusions, india, matter, patentability, subject, trips | 1 |
| eval_029 / comparison | Trips Agreement article 27 | compare, exclusions, india, matter, patentability, patentable, subject, trips | patentability, patentable, trips, matter, india, subject, compare, exclusions | locally, ordre, synonymous, enjoyable, fields, generis, humans, surgical, diagnostic, discrimination | matter, patentability, patentable, subject | compare, exclusions, india, trips | 1 |
| eval_030 / general | Biological Diversity Act 2002 section 6 | access, approval, benefit, biological, concepts, indian, nagoya, protocol, relate, resources, sharing | concepts, relate, nagoya, indian, approval, access, sharing, benefit | comme, depos, endorse, hich, intellectua, ited, rcial, cultivators, growers, practicing | access, approval, benefit, biological, indian, sharing | concepts, nagoya, protocol, relate, resources | 1 |
| eval_030 / general | Nagoya Protocol article 6 | access, approval, benefit, biological, concepts, indian, nagoya, protocol, relate, resources, sharing | concepts, relate, nagoya, indian, approval, access, sharing, benefit | instances, transboundary, shared, ensuring, endeavour, sovereign, involvement, objective, regulatory, situ | access, approval, benefit, nagoya, protocol, resources, sharing | biological, concepts, indian, relate | 1 |
| eval_030 / general | Nagoya Protocol article 5 | access, approval, benefit, biological, concepts, indian, nagoya, protocol, relate, resources, sharing | concepts, relate, nagoya, indian, approval, access, sharing, benefit | commercialization, shared, ensuring, monetary, annex, holding, implement, listed, legislative, limited | benefit, resources, sharing | access, approval, biological, concepts, indian, nagoya, protocol, relate | 1 |
| eval_031 / comparison | Gi Act section 9 | compare, criteria, geographical, indian, indications, protection, trips | criteria, indian, indications, geographical, trips, protection, compare | disentitled, generic, disuse, originates, religious, susceptibilities, although, hurt, literally, obscene | geographical, indications, protection | compare, criteria, indian, trips | 1 |
| eval_031 / comparison | Trips Agreement article 22 | compare, criteria, geographical, indian, indications, protection, trips | criteria, indian, indications, geographical, trips, protection, compare | misleads, originates, although, literally, suggests, characteristic, competition, indicates, originate, reputation | geographical, indications, protection | compare, criteria, indian, trips | 1 |
| eval_032 / comparison | Designs Act section 4 | agreement, compare, design, effects, framework, hague, india, international, protection, registration | framework, effects, hague, design, protection, agreement, international, registration | anywhere, distinguishable, tangible, obscene, scandalous, comprises, significantly, combination, prohibition, disclosed | design, india, registration | agreement, compare, effects, framework, hague, international, protection | 1 |
| eval_032 / comparison | Hague Agreement article 14 | agreement, compare, design, effects, framework, hague, india, international, protection, registration | framework, effects, hague, design, protection, agreement, international, registration | iled, regularly, refusal, communicated, least, designated, industrial, applicable, grant, contracting | design, effects, international, protection, registration | agreement, compare, framework, hague, india | 1 |
| eval_033 / explicit_provision | Patent Act 2024 section 83 | needs, patents, public, working | needs, working, patents, public | monopoly, conducive, nutrition, sectors, abused, impede, balance, considerations, prices, resort | patents, public, working | needs | 1 |
| eval_034 / explicit_provision | Nagoya Protocol article 6 | access, genetic, nagoya, protocol, purpose, resources | genetic, nagoya, access, resources, protocol, purpose | instances, transboundary, shared, ensuring, endeavour, sovereign, involvement, objective, regulatory, situ | access, genetic, nagoya, protocol, resources | purpose | 1 |
| eval_035 / explicit_provision | Trademarks Act section 34 | earlier, mark, marks, protect, someone, trade, used | protect, earlier, marks, used, mark, trade, someone | continuously, interfere, prodecessor, restrain, entitle, resembling, predecessor, nearly, proved, identical | earlier, mark, trade, used | marks, protect, someone | 1 |

## 4. Missed-target analysis

Missed means original Stage 6D rank is outside Top-5 (including not returned). Source ranks were rechecked using the original query and current candidate methods. These labels describe observable rank/candidate patterns; `lexical_gap` remains a term-overlap heuristic, not a semantic judgment.

| Query | Target | Dense rank | BM25 rank | Hybrid rank | Diagnostic | Query terms | Target-only terms | Shared |
|---|---|---:|---:|---:|---|---|---|---|
| eval_002 | Biological Diversity Act 2002 section 2 | — | — | — | candidate_absence | biodiversity, biological, define, india, research, resources | bioassay, breeding, characteris, conventional, crops, dairy, emulsifiers, enzymes | biodiversity, biological, india, research, resources |
| eval_009 | Patent Act 2024 section 10 | 14 | 17 | 8 | candidate_depth | belongs, filed, india, information, patent, specification | begin, correctly, defining, illustrating, linked, succinct, supplemented, concept | filed, india, information, patent, specification |
| eval_010 | Patent Act 2024 section 43 | 1 | — | 7 | mixed | controller, effect, follows, grants, legal, patent | expeditiously, thereby, jointly, thereupon, vested, seal, joint, refused | controller, patent |
| eval_011 | Trademarks Act section 9 | — | — | — | candidate_absence + lexical_gap | brand, grounds, name, prevent, proposed, registration, trademark | current, devoid, emblems, improper, religious, susceptibilities, hurt, obscene | proposed, registration |
| eval_023 | Fssai Ayurveda Aahara Regulations 2022 section 12 | 1 | 14 | 6 | mixed | aahara, ayurveda, labeling, products, require | bangasena, display, labelling, safety, specific, standards, food, requirements | aahara, ayurveda |
| eval_027 | Pct article 11 | — | 3 | 9 | mixed | effect, international, patent | anindicationthatitisintendedasaninternationalapplication, apartwhichonthefaceofitappearstobeaclaimorclaims, apartwhichonthefaceofitappearstobeadescription, astheinternationalfilingdatethedate, atthetimeofreceipt, consideredtobetheactualfilingdateineachdesignatedstate, dateofreceiptoftherequiredcorrection, invitetheapplicanttofiletherequiredcorrection | effect, international |
| eval_028 | Madrid Protocol article 4 | 8 | 17 | 9 | mixed | effect, international, madrid, protocol, registration, trademark | interna, tional, recordal, refusal, effects, effected, deposited, notified | international, registration |
| eval_029 | Patent Act 2024 section 3 | — | — | — | candidate_absence + lexical_gap | compare, exclusions, india, matter, patentability, patentable, subject, trips | admixture, aggregation, algorithms, curative, duplication, employs, esters, ethers | patentable |
| eval_030 | Biological Diversity Act 2002 section 6 | — | — | — | candidate_absence | access, approval, benefit, biological, concepts, indian, nagoya, protocol | comme, depos, endorse, hich, intellectua, ited, rcial, cultivators | access, approval, benefit, biological, indian, sharing |
| eval_030 | Nagoya Protocol article 5 | — | — | — | candidate_absence | access, approval, benefit, biological, concepts, indian, nagoya, protocol | commercialization, shared, ensuring, monetary, annex, holding, implement, listed | benefit, resources, sharing |
| eval_031 | Gi Act section 9 | — | — | — | candidate_absence | compare, criteria, geographical, indian, indications, protection, trips | disentitled, generic, disuse, originates, religious, susceptibilities, although, hurt | geographical, indications, protection |
| eval_032 | Designs Act section 4 | — | — | — | candidate_absence | agreement, compare, design, effects, framework, hague, india, international | anywhere, distinguishable, tangible, obscene, scandalous, comprises, significantly, combination | design, india, registration |

Specific focus: eval_029 Patent Act §3, eval_030 Biological Diversity Act §6, eval_031 GI Act §9 and eval_032 Designs Act §4 are included above when their reproduced baseline rank falls outside Top-5. Presence in a rank list does not prove semantic fit. A target absent from both candidate pools is a candidate-generation issue; terms alone cannot determine whether it is fundamentally semantic.

## 5. Corpus-level discriminative term analysis

Corpus units: **1123**; distinct terms: **6577**. IDF is `log((N + 1)/(provision_df + 1)) + 1`. Bands are high IDF ≥ 6, moderate 4 ≤ IDF < 6, generic IDF < 4; terms occurring in only one unit are omitted from the example lists to reduce one-off extraction noise. These are retrieval-discrimination bands, not legal-importance labels.

| Band | Term | IDF | Provision frequency | Document frequency | Jurisdiction frequency |
|---|---|---:|---:|---:|---|
| High | zone | 6.926 | 2 | 2 | India:2 |
| High | yyyy | 6.926 | 2 | 1 | India:2 |
| High | yies | 6.926 | 2 | 1 | India:2 |
| High | yeast | 6.926 | 2 | 1 | India:2 |
| High | yards | 6.926 | 2 | 1 | India:2 |
| High | xxxgidhxxx | 6.926 | 2 | 2 | India:2 |
| High | xxxgidexxx | 6.926 | 2 | 2 | India:2 |
| High | wrapping | 6.926 | 2 | 2 | India:2 |
| High | woven | 6.926 | 2 | 2 | India:2 |
| High | workshop | 6.926 | 2 | 2 | India:2 |
| High | withthesaidauthority | 6.926 | 2 | 1 | International:2 |
| High | withdraws | 6.926 | 2 | 2 | International:2 |
| High | whereon | 6.926 | 2 | 1 | India:2 |
| High | whereof | 6.926 | 2 | 2 | International:2 |
| High | whence | 6.926 | 2 | 2 | India:2 |
| High | ways | 6.926 | 2 | 1 | International:2 |
| High | wastes | 6.926 | 2 | 2 | India:2 |
| High | warranty | 6.926 | 2 | 2 | India:2 |
| High | waived | 6.926 | 2 | 2 | India:1, International:1 |
| High | volume | 6.926 | 2 | 2 | India:2 |
| Moderate | witness | 5.945 | 7 | 6 | India:5, International:2 |
| Moderate | whatsoever | 5.945 | 7 | 5 | India:6, International:1 |
| Moderate | vide | 5.945 | 7 | 4 | India:7 |
| Moderate | unreasonably | 5.945 | 7 | 2 | India:1, International:6 |
| Moderate | unions | 5.945 | 7 | 4 | International:7 |
| Moderate | undertaken | 5.945 | 7 | 4 | India:1, International:6 |
| Moderate | transmissions | 5.945 | 7 | 3 | India:7 |
| Moderate | therapeutic | 5.945 | 7 | 3 | India:6, International:1 |
| Moderate | textile | 5.945 | 7 | 3 | India:6, International:1 |
| Moderate | technologies | 5.945 | 7 | 3 | International:7 |
| Moderate | suspension | 5.945 | 7 | 2 | India:3, International:4 |
| Moderate | superintendence | 5.945 | 7 | 4 | India:7 |
| Moderate | successive | 5.945 | 7 | 7 | India:7 |
| Moderate | substances | 5.945 | 7 | 2 | India:7 |
| Moderate | submission | 5.945 | 7 | 5 | India:5, International:2 |
| Moderate | structure | 5.945 | 7 | 3 | India:4, International:3 |
| Moderate | strategies | 5.945 | 7 | 3 | India:5, International:2 |
| Moderate | stated | 5.945 | 7 | 5 | India:5, International:2 |
| Moderate | startup | 5.945 | 7 | 1 | India:7 |
| Moderate | sovereign | 5.945 | 7 | 3 | India:1, International:6 |
| Generic | made | 2.125 | 364 | 18 | India:307, International:57 |
| Generic | patent | 2.338 | 294 | 12 | India:260, International:34 |
| Generic | respect | 2.408 | 274 | 18 | India:191, International:83 |
| Generic | subject | 2.408 | 274 | 17 | India:172, International:102 |
| Generic | time | 2.449 | 263 | 18 | India:193, International:70 |
| Generic | within | 2.483 | 254 | 18 | India:180, International:74 |
| Generic | case | 2.491 | 252 | 18 | India:197, International:55 |
| Generic | date | 2.499 | 250 | 18 | India:166, International:84 |
| Generic | prescribed | 2.511 | 247 | 16 | India:209, International:38 |
| Generic | india | 2.582 | 230 | 11 | India:230 |
| Generic | referred | 2.678 | 209 | 18 | India:126, International:83 |
| Generic | without | 2.772 | 190 | 18 | India:139, International:51 |
| Generic | controller | 2.783 | 188 | 8 | India:188 |
| Generic | purposes | 2.788 | 187 | 17 | India:137, International:50 |
| Generic | registration | 2.788 | 187 | 13 | India:139, International:48 |
| Generic | manner | 2.794 | 186 | 15 | India:167, International:19 |
| Generic | international | 2.821 | 181 | 16 | India:29, International:152 |
| Generic | apply | 2.854 | 175 | 18 | India:131, International:44 |
| Generic | party | 2.883 | 170 | 15 | India:45, International:125 |
| Generic | order | 2.889 | 169 | 16 | India:143, International:26 |

## 6. Query-to-target lexical gaps

Missed-target count: **12**. Of these, 6 have no more than two substantive exact-token overlaps; this does not establish synonymy or semantic mismatch. Target text may include multiple chunks and extraction artifacts.

## 7. Proposed generic expansion mechanism

The only tested corpus-derived mechanism is query-term co-occurrence across legal provision units, constrained to terms with at least two supporting units and median-or-higher IDF, with at most three added tokens. This is generic and reproducible, but co-occurrence does not imply synonymy. Morphology is limited to corpus-attested simple singular/plural variants. Neither expansion injects a document name, provision number, evaluation target text, or target metadata.

## 8. Offline expansion experiment

The same unchanged retrieval method and final Top-10 were used for all variants. Expanded strings flow through dense and BM25 candidate generation; Stage 6D scoring/filtering remains intact. This is an ablation, not a production change.

| Variant | Queries with ≥1 added token | Added lexical forms | Added corpus terms |
|---|---:|---:|---:|
| Original | 35 | 0 | 0 |
| Lexical/morphology | 34 | 103 | 0 |
| Corpus-derived | 35 | 103 | 105 |

### Expected-target ranks by variant

| Query | Expected target | Original | Lexical/morphology | Corpus-derived |
|---|---|---:|---:|---:|
| eval_001 | Patent Act 2024 section 2 | 1 | 1 | 9 |
| eval_002 | Biological Diversity Act 2002 section 2 | — | — | — |
| eval_003 | Drugs Magic Remedies Act section 2 | 1 | 1 | 1 |
| eval_004 | Gi Act section 2 | 2 | 2 | 6 |
| eval_005 | Patent Act 2024 section 3 | 1 | 1 | 1 |
| eval_006 | Patent Act 2024 section 4 | 1 | 1 | 1 |
| eval_007 | Trips Agreement article 27 | 2 | 3 | 2 |
| eval_008 | Patent Act 2024 section 6 | 5 | 4 | 4 |
| eval_009 | Patent Act 2024 section 10 | 8 | 8 | 9 |
| eval_010 | Patent Act 2024 section 43 | 7 | 1 | 1 |
| eval_011 | Trademarks Act section 9 | — | 10 | — |
| eval_012 | Trademarks Act section 11 | 1 | 2 | 2 |
| eval_013 | Trademarks Act section 19 | 5 | 5 | 6 |
| eval_014 | Gi Act section 9 | 1 | 1 | 1 |
| eval_015 | Gi Act section 21 | 1 | 1 | 1 |
| eval_016 | Designs Act section 2 | 2 | 3 | 3 |
| eval_017 | Designs Act section 11 | 5 | 5 | 7 |
| eval_018 | Biological Diversity Act 2002 section 3 | 1 | 1 | 1 |
| eval_019 | Biological Diversity Act 2002 section 6 | 1 | 1 | 1 |
| eval_020 | Biological Diversity Act 2002 section 21 | 5 | 1 | 1 |
| eval_021 | Nagoya Protocol article 7 | 1 | 2 | 1 |
| eval_022 | Nagoya Protocol article 12 | 2 | 1 | 1 |
| eval_023 | Fssai Ayurveda Aahara Regulations 2022 section 12 | 6 | 6 | 8 |
| eval_024 | Fssai Ayurveda Aahara Regulations 2022 section 8 | 5 | 5 | 5 |
| eval_025 | Nagoya Protocol article 1 | 2 | 2 | 2 |
| eval_026 | Budapest Treaty article 3 | 3 | 1 | 1 |
| eval_027 | Pct article 11 | 9 | 10 | 9 |
| eval_028 | Madrid Protocol article 4 | 9 | 4 | 4 |
| eval_029 | Patent Act 2024 section 3 | — | — | — |
| eval_029 | Trips Agreement article 27 | 2 | 2 | 1 |
| eval_030 | Biological Diversity Act 2002 section 6 | — | — | — |
| eval_030 | Nagoya Protocol article 6 | 2 | 3 | 2 |
| eval_030 | Nagoya Protocol article 5 | — | — | — |
| eval_031 | Gi Act section 9 | — | — | — |
| eval_031 | Trips Agreement article 22 | 2 | 3 | 3 |
| eval_032 | Designs Act section 4 | — | 10 | — |
| eval_032 | Hague Agreement article 14 | 1 | 1 | 2 |
| eval_033 | Patent Act 2024 section 83 | 1 | 1 | 1 |
| eval_034 | Nagoya Protocol article 6 | 1 | 1 | 1 |
| eval_035 | Trademarks Act section 34 | 1 | 1 | 1 |

## 9. Overall metric comparison

Metrics are macro-averaged over the 35 answerable queries with the evaluator's target-fraction Recall convention.

| Variant | R@1 | Δ | R@3 | Δ | R@5 | Δ | R@10 | Δ | MRR | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Original | 0.3857 | +0.0000 | 0.5952 | +0.0000 | 0.7381 | +0.0000 | 0.8810 | +0.0000 | 0.5711 | +0.0000 |
| Lexical/morphology | 0.4429 | +0.0572 | 0.6524 | +0.0572 | 0.7952 | +0.0571 | 0.9238 | +0.0428 | 0.6121 | +0.0410 |
| Corpus-derived | 0.4429 | +0.0572 | 0.5952 | +0.0000 | 0.6810 | -0.0571 | 0.8810 | +0.0000 | 0.5943 | +0.0232 |

## 10. Category-level comparison

| Category | Variant | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---|---:|---:|---:|---:|---:|
| ayurveda_food_regulatory | Original | 0.0000 | 0.0000 | 0.5000 | 1.0000 | 0.1833 |
| ayurveda_food_regulatory | Lexical/morphology | 0.0000 | 0.0000 | 0.5000 | 1.0000 | 0.1833 |
| ayurveda_food_regulatory | Corpus-derived | 0.0000 | 0.0000 | 0.5000 | 1.0000 | 0.1625 |
| biological_diversity | Original | 0.6667 | 0.6667 | 1.0000 | 1.0000 | 0.7333 |
| biological_diversity | Lexical/morphology | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| biological_diversity | Corpus-derived | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| comparisons | Original | 0.1250 | 0.4583 | 0.4583 | 0.4583 | 0.6250 |
| comparisons | Lexical/morphology | 0.1250 | 0.4583 | 0.4583 | 0.5833 | 0.5417 |
| comparisons | Corpus-derived | 0.1250 | 0.4583 | 0.4583 | 0.4583 | 0.5833 |
| definitions | Original | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 |
| definitions | Lexical/morphology | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 |
| definitions | Corpus-derived | 0.2500 | 0.2500 | 0.2500 | 0.7500 | 0.3194 |
| designs | Original | 0.0000 | 0.5000 | 1.0000 | 1.0000 | 0.3500 |
| designs | Lexical/morphology | 0.0000 | 0.5000 | 1.0000 | 1.0000 | 0.2667 |
| designs | Corpus-derived | 0.0000 | 0.5000 | 0.5000 | 1.0000 | 0.2381 |
| explicit_provisions | Original | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| explicit_provisions | Lexical/morphology | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| explicit_provisions | Corpus-derived | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| geographical_indications | Original | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| geographical_indications | Lexical/morphology | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| geographical_indications | Corpus-derived | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| international_treaties | Original | 0.0000 | 0.5000 | 0.5000 | 1.0000 | 0.2639 |
| international_treaties | Lexical/morphology | 0.2500 | 0.5000 | 0.7500 | 1.0000 | 0.4625 |
| international_treaties | Corpus-derived | 0.2500 | 0.5000 | 0.7500 | 1.0000 | 0.4653 |
| patent_procedure | Original | 0.0000 | 0.0000 | 0.3333 | 1.0000 | 0.1560 |
| patent_procedure | Lexical/morphology | 0.3333 | 0.3333 | 0.6667 | 1.0000 | 0.4583 |
| patent_procedure | Corpus-derived | 0.3333 | 0.3333 | 0.6667 | 1.0000 | 0.4537 |
| patentability | Original | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.8333 |
| patentability | Lexical/morphology | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.7778 |
| patentability | Corpus-derived | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.8333 |
| trademarks | Original | 0.3333 | 0.3333 | 0.6667 | 0.6667 | 0.4000 |
| trademarks | Lexical/morphology | 0.0000 | 0.3333 | 0.6667 | 1.0000 | 0.2667 |
| trademarks | Corpus-derived | 0.0000 | 0.3333 | 0.3333 | 0.6667 | 0.2222 |
| traditional_knowledge | Original | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.7500 |
| traditional_knowledge | Lexical/morphology | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.7500 |
| traditional_knowledge | Corpus-derived | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## 11. Comparison-query analysis

| Query | Variant | Targets found @5 / total | Target jurisdictions found @5 | Target ranks |
|---|---|---:|---|---|
| eval_029 | Original | 1 / 2 | International | —, 2 |
| eval_029 | Lexical/morphology | 1 / 2 | International | —, 2 |
| eval_029 | Corpus-derived | 1 / 2 | International | —, 1 |
| eval_030 | Original | 1 / 3 | International | —, 2, — |
| eval_030 | Lexical/morphology | 1 / 3 | International | —, 3, — |
| eval_030 | Corpus-derived | 1 / 3 | International | —, 2, — |
| eval_031 | Original | 1 / 2 | International | —, 2 |
| eval_031 | Lexical/morphology | 1 / 2 | International | —, 3 |
| eval_031 | Corpus-derived | 1 / 2 | International | —, 3 |
| eval_032 | Original | 1 / 2 | International | —, 1 |
| eval_032 | Lexical/morphology | 1 / 2 | International | 10, 1 |
| eval_032 | Corpus-derived | 1 / 2 | International | —, 2 |

## 12. Regression analysis

A regression is an expected target that was in original Top-5 and falls outside Top-5 under an expanded variant. Improvements are the reverse transition. These are target-level retrieval transitions, not relevance judgments.

| Variant | Improved targets into Top-5 | Regressed targets out of Top-5 |
|---|---:|---:|
| Lexical/morphology | 2 | 0 |
| Corpus-derived | 2 | 4 |

## 13. Examples of improved queries

### Lexical/morphology
- eval_010 Patent Act 2024 section 43 (7→1)
- eval_028 Madrid Protocol article 4 (9→4)

### Corpus-derived
- eval_010 Patent Act 2024 section 43 (7→1)
- eval_028 Madrid Protocol article 4 (9→4)

## 14. Examples where expansion hurts

### Lexical/morphology
- No expected target moved out of Top-5.

### Corpus-derived
- eval_001 Patent Act 2024 section 2 (1→9)
- eval_004 Gi Act section 2 (2→6)
- eval_013 Trademarks Act section 19 (5→6)
- eval_017 Designs Act section 11 (5→7)

## 15. Root-cause assessment

The candidate and rank evidence can distinguish candidate absence, source-pool depth, and fusion displacement. It cannot prove a semantic gap. Exact-token overlap is only a lexical indicator, and corpus co-occurrence does not establish synonymy. Where candidate absence coincides with low overlap, the report calls that mixed evidence rather than assigning semantic causation.

## 16. Recommendation

The simple corpus-attested singular/plural variant is promising enough for a separately controlled future ablation: it improved every aggregate metric here and moved two missed targets into Top-5 without moving a Top-5 target out. It also reduced trademarks R@1 and MRR, reduced patentability MRR, and lowered comparison MRR, so the evidence does not justify production deployment. The corpus co-occurrence variant should not be advanced: it reduced R@5, produced four Top-5 regressions, and lowered MRR versus the original. Validate any morphology-only candidate on independent queries and investigate the category regressions before considering implementation. No semantic relevance was verified.

## Validation and unchanged-state checks

- Chunks read: 1349; answerable queries: 35; expected target instances: 40.
- Production retrieval source is imported and called read-only; the script makes no Chroma add/update/delete calls.
- Integrity check: PASS; hashes match before/after; Chroma count remains **1349**.
  - `corpus (recursive manifest)`: `1e37b22815e50793bf606fc5ce9cd7ee7e5575af3b5aec2dc28851df553e5dbe`
  - `rag-service\app\retriever.py`: `3beb69805338d0901ce45f257bf98181cdb62f0426f2a1f895389ca43374f679`
  - `rag-service\data\chunks.json`: `521d427fabfbec7ba22e34aaf200f62e0a437a9e719a6832ea31329218444e8c`
  - `rag-service\data\extracted_documents.json`: `d48f09a7e79a559974c624af318f27e0f8a2dce21463d312852b7a4307488f32`
  - `rag-service\tests\eval_set.json`: `a8bb0dc4deeb9bbc03a483c1fee4af123db79d2133192b70c9b1d341b4e8b664`
- Chroma was accessed through collection reads only; no index mutation calls were made.

### Per-query expansion terms (auditable; generated from query + corpus only)

| Query ID | Intent | Morphology | Corpus-derived |
|---|---|---|---|
| eval_001 | definition | inventions, term | efficiently, hindered, accredited |
| eval_002 | definition | resource | adaptation, aspirations, chennai |
| eval_003 | definition | indians, term, drugs, advertisement | influence, bill, brackets |
| eval_004 | general | — | aimed, abbreviation, applica |
| eval_005 | prohibition | kind, matters, invention, indians, patents | advancement, bottom, consecutive |
| eval_006 | general | inventions | back, fields, accidentally |
| eval_007 | general | matters, member, makes, patents, protections | protectable, defendants, disciplines |
| eval_008 | general | patents, assignees | acquiescence, circumstance, devolution |
| eval_009 | general | belong, patents, specifications | illustrated, commence, commercially |
| eval_010 | general | effects, follow, controllers, grant, patents | disciplines, aesthetic, circumstance |
| eval_011 | general | ground, registrations, names, trademarks | initials, recently, repute |
| eval_012 | general | trademarks, mark, registrations | recently, repute, allowable |
| eval_013 | general | trademarks, registrations | repute, accessory, accredited |
| eval_014 | general | make, products, names, protections, indications | applica, registrability, abbreviation |
| eval_015 | general | right, registrations, gives, user, indications | dealings, impaired, abbreviation |
| eval_016 | definition | feature, definitions, designs | configuration, dimensional, applica |
| eval_017 | general | registrations | configuration, mandatory, prod |
| eval_018 | general | obtains, approvals, resource | chennai, cultivators, foreigner |
| eval_019 | general | approvals, rights, resource | orld, transparent, arbitrary |
| eval_020 | general | benefit, resource | aesthetic, appreciate, commitment |
| eval_021 | general | protocols, resource | appreciate, continental, diminishing |
| eval_022 | general | community | aesthetic, consistency, dramatic |
| eval_023 | general | requires, product | accredited, aimed, arya |
| eval_024 | purpose | makes, diseases, treatments, claim, products | aesthetic, complexes, dramatic |
| eval_025 | purpose | objectives, protocols, benefits | appreciate, economies, ended |
| eval_026 | general | makes, deposit, microorganism, country | italian, recognize, allegation |
| eval_027 | definition | effects, patents | aesthetic, ammunition, annexures |
| eval_028 | general | effects, trademarks, registrations, protocols | anticipations, authorizes, belong |
| eval_029 | comparison | exclusion, matters | generis, enjoyable, fields |
| eval_030 | general | indians, approvals, resource, relates, protocols | globally, orld, strong |
| eval_031 | comparison | indians, protections, indication | barriers, commitments, gatt |
| eval_032 | comparison | designs, protections, agreements, registrations, effect | appli, cant, abbreviated |
| eval_033 | explicit_provision | patent, need | accidentally, expected, aesthetic |
| eval_034 | explicit_provision | purposes, protocols, resource | adaptation, appreciate, continental |
| eval_035 | explicit_provision | trades | circles, protecting, repute |
