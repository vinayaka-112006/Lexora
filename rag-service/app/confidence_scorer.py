"""Transparent deterministic confidence scoring from retrieval and citation signals."""
from __future__ import annotations

import math
import re
from typing import Any

from app.retriever import analyze_legal_query, explicit_provision_matches_chunk

# Component weights total 100 points. Rank points decay as 20 / sqrt(rank).
WEIGHTS = {
    "usable_evidence": 20.0,
    "retrieval_rank": 20.0,
    "explicit_provision": 20.0,
    "retrieval_intent": 15.0,
    "jurisdiction": 10.0,
    "citation_coverage": 15.0,
}
HIGH_THRESHOLD = 0.75
MEDIUM_THRESHOLD = 0.45
EXPLICIT_MISSING_SCORE_CAP = 0.44
NO_CITATION_PENALTY = 15.0
INVALID_CITATION_PENALTY = 5.0
JURISDICTION_MISMATCH_PENALTY = 15.0
COMPARISON_MISSING_JURISDICTION_PENALTY = 10.0
ABSTENTION_MESSAGE = "I don't have sufficient evidence in the retrieved legal sources to answer this reliably."
CAUTION_MESSAGE = "Caution: the available retrieved evidence may be incomplete."


def _has_usable_text(chunk: dict[str, Any]) -> bool:
    """Treat non-empty retrieved source text as usable evidence for this stage."""
    return isinstance(chunk.get("text"), str) and bool(chunk["text"].strip())


def _matches_explicit_provision(chunk: dict[str, Any], requested: dict[str, str]) -> bool:
    """Check the requested provision type and number without fuzzy matching."""
    return explicit_provision_matches_chunk(chunk, requested)


def _matches_intent(chunk: dict[str, Any], intent: str) -> bool:
    """Use surface wording as a retrieval-intent signal, not claim verification."""
    title = str(chunk.get("provision_title") or "").casefold()
    text = str(chunk.get("text") or "").casefold()
    searchable = f"{title} {text}"
    patterns = {
        "definition": r"\b(definition|defined|meaning|means)\b",
        "purpose": r"\b(purpose|objective|objectives|aim|aims)\b",
        "prohibition": r"\b(prohibited|shall not|not an invention|not inventions|excluded|patentability|cannot be patented)\b",
    }
    if intent == "explicit_provision":
        return False
    if intent == "comparison":
        return bool(text.strip())
    if intent == "general":
        return bool(text.strip())
    pattern = patterns.get(intent)
    return bool(pattern and re.search(pattern, searchable))


def _citation_signals(validation: dict[str, Any] | None) -> tuple[int, int, float, int]:
    """Read counts and bounded coverage from the citation validator result."""
    if not validation:
        return 0, 0, 0.0, 0
    total = int(validation.get("total_citations", validation.get("citation_count", 0)) or 0)
    valid = int(validation.get("valid_citations", 0) or 0)
    invalid = int(validation.get("invalid_citations", max(0, total - valid)) or 0)
    if "citation_coverage" in validation:
        coverage = float(validation.get("citation_coverage") or 0.0)
    else:
        coverage = valid / total if total else 0.0
    return max(0, total), max(0, valid), min(1.0, max(0.0, coverage)), max(0, invalid)


def score_confidence(
    query: str,
    retrieved_chunks: list[dict[str, Any]],
    citation_validation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Score evidence sufficiency with an explainable weighted rule set.

    The score measures retrieval/citation integrity signals only. It does not establish
    legal correctness or whether the retrieved text semantically supports each claim.
    """
    analysis = analyze_legal_query(query)
    usable = [(rank, chunk) for rank, chunk in enumerate(retrieved_chunks, start=1)
              if _has_usable_text(chunk)]
    components = {name: 0.0 for name in WEIGHTS}
    adjustments: dict[str, float] = {}
    reasons: list[str] = []

    if not usable:
        return {
            "score": 0.0,
            "level": "low",
            "decision": "abstain",
            "reasons": ["No usable retrieved evidence is available."],
            "score_components": components,
            "adjustments": adjustments,
            "thresholds": {"high": HIGH_THRESHOLD, "medium": MEDIUM_THRESHOLD},
            "query_intent": analysis["intent"],
        }

    components["usable_evidence"] = WEIGHTS["usable_evidence"]
    reasons.append(f"Usable retrieved evidence is available ({len(usable)} chunk(s)).")

    best_rank, best_chunk = usable[0]
    components["retrieval_rank"] = WEIGHTS["retrieval_rank"] / math.sqrt(best_rank)
    reasons.append(f"Best usable evidence is ranked {best_rank}.")

    explicit = analysis["explicit_provision"]
    explicit_match = False
    if explicit:
        matching = [(rank, chunk) for rank, chunk in usable
                    if _matches_explicit_provision(chunk, explicit)]
        if matching:
            components["explicit_provision"] = WEIGHTS["explicit_provision"]
            explicit_match = True
            reasons.append(
                f"Requested {explicit['type']} {explicit['number']} appears in retrieved evidence."
            )
        else:
            reasons.append(
                f"Requested {explicit['type']} {explicit['number']} was not retrieved; "
                f"confidence is capped at {EXPLICIT_MISSING_SCORE_CAP:.0%}."
            )
    else:
        # Neutral partial credit: there was no exact provision request to verify.
        components["explicit_provision"] = WEIGHTS["explicit_provision"] / 2
        reasons.append("No explicit section/article number was requested.")

    intent = analysis["intent"]
    intent_match = any(_matches_intent(chunk, intent) for _, chunk in usable)
    if intent_match:
        components["retrieval_intent"] = WEIGHTS["retrieval_intent"]
        reasons.append(f"Retrieved text has wording associated with {intent} intent.")
    elif intent == "explicit_provision" and explicit_match:
        components["retrieval_intent"] = WEIGHTS["retrieval_intent"]
        reasons.append("Retrieved evidence matches the explicit provision reference.")
    else:
        reasons.append(f"Retrieved text did not show a clear {intent} signal.")

    requested_jurisdictions = analysis["jurisdictions_requested"]
    found_jurisdictions = {
        str(chunk.get("jurisdiction") or "") for _, chunk in usable
    }
    if not requested_jurisdictions:
        components["jurisdiction"] = WEIGHTS["jurisdiction"]
        reasons.append("No jurisdiction was specified; evidence from either jurisdiction is eligible.")
    else:
        matched_jurisdictions = set(requested_jurisdictions) & found_jurisdictions
        if len(requested_jurisdictions) > 1:
            fraction = len(matched_jurisdictions) / len(requested_jurisdictions)
            components["jurisdiction"] = WEIGHTS["jurisdiction"] * fraction
            if fraction == 1.0:
                reasons.append("Retrieved evidence covers both requested jurisdictions.")
            else:
                adjustments["missing_comparison_jurisdiction"] = -COMPARISON_MISSING_JURISDICTION_PENALTY
                reasons.append("Retrieved evidence is missing one or more requested comparison jurisdictions.")
        elif matched_jurisdictions:
            components["jurisdiction"] = WEIGHTS["jurisdiction"]
            reasons.append(f"Retrieved evidence includes requested jurisdiction {requested_jurisdictions[0]}.")
        else:
            adjustments["jurisdiction_mismatch"] = -JURISDICTION_MISMATCH_PENALTY
            reasons.append(f"No retrieved evidence matches requested jurisdiction {requested_jurisdictions[0]}.")

    total_citations, valid_citations, coverage, invalid_citations = _citation_signals(citation_validation)
    if total_citations:
        components["citation_coverage"] = WEIGHTS["citation_coverage"] * coverage
        reasons.append(f"Citation coverage is {coverage:.0%} ({valid_citations}/{total_citations} valid).")
        if invalid_citations:
            penalty = min(10.0, INVALID_CITATION_PENALTY * invalid_citations)
            adjustments["invalid_citations"] = -penalty
            reasons.append(f"{invalid_citations} citation(s) failed metadata validation.")
    else:
        adjustments["no_citations"] = -NO_CITATION_PENALTY
        reasons.append("No citations were validated; confidence is reduced.")

    points = sum(components.values()) + sum(adjustments.values())
    if explicit and not explicit_match:
        points = min(points, EXPLICIT_MISSING_SCORE_CAP * 100)
    points = min(100.0, max(0.0, points))
    score = round(points / 100.0, 4)
    if score >= HIGH_THRESHOLD:
        level, decision = "high", "answer"
    elif score >= MEDIUM_THRESHOLD:
        level, decision = "medium", "answer_with_caution"
    else:
        level, decision = "low", "abstain"
    return {
        "score": score,
        "level": level,
        "decision": decision,
        "reasons": reasons,
        "score_components": components,
        "adjustments": adjustments,
        "thresholds": {"high": HIGH_THRESHOLD, "medium": MEDIUM_THRESHOLD},
        "query_intent": intent,
    }


def apply_confidence_decision(answer: str, confidence: dict[str, Any]) -> str:
    """Choose the displayed response while preserving the source answer elsewhere."""
    decision = confidence.get("decision")
    if decision == "abstain":
        return ABSTENTION_MESSAGE
    if decision == "answer_with_caution":
        return f"{CAUTION_MESSAGE}\n\n{answer}"
    return answer



# . Important observations about this implementation
# There are a few things worth understanding before presenting this architecture.
# 1. It is a deterministic weighted scoring system. The same query, chunks, and citation-validation result produce the same score.
# 2. It is not an LLM evaluator. It doesn't ask the language model whether its generated answer is legally correct.
# 3. High confidence does not mean legal correctness. Even a score of 1.0 only means all the implemented retrieval and citation signals received full marks.
# 4. The explicit provision cap is useful. It prevents a high score when a specifically requested section or article is missing.
# 5. Jurisdiction penalties matter. They help reduce confidence when the retrieved evidence doesn't cover the requested legal jurisdiction.
# 6. The score is a heuristic, not a statistically calibrated probability. A score of 0.80 does not mean there is an 80% chance the answer is correct.
# One subtle point: in comparison queries, missing jurisdiction evidence reduces the jurisdiction component and also applies a separate penalty. This is intentional in the current code, but it makes the penalty stronger than the component reduction alone.

# 9. How to explain this to judges
# You can describe it like this:
# "We use a transparent, deterministic confidence-scoring mechanism based on six signals: usable evidence, retrieval ranking, explicit provision matching, query intent, jurisdiction coverage, and citation coverage. Each signal contributes to a weighted score. Based on predefined thresholds, the system either returns the answer, adds a caution message, or abstains when evidence is insufficient. This score evaluates evidence sufficiency and citation integrity, not legal correctness."

# That's the main purpose of confidence_scorer.py.

# It acts as the decision layer between answer generation and the final displayed response.