"""Conservative, deterministic pre-generation abstention checks."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AbstentionGuardResult:
    should_abstain: bool
    category: str | None = None
    explanation: str = ""


_FRESHNESS_TERMS = re.compile(r"\b(today|current|currently|latest|recent)\b", re.IGNORECASE)
_AS_OF_YEAR = re.compile(r"\bas\s+of\s+(19\d{2}|20\d{2})\b", re.IGNORECASE)
_HISTORICAL_CUTOFF = re.compile(
    r"\b(?:before|prior\s+to|until|through|in|during|as\s+of)\s+(19\d{2}|20\d{2})\b",
    re.IGNORECASE,
)
_CASE_SPECIFIC = re.compile(
    r"\bmy\s+(?:company['’]s\s+)?(?:trademark|trade\s+mark|patent)\s+application\b"
    r"|\bstatus\s+of\s+my\s+(?:company['’]s\s+)?(?:trademark|trade\s+mark|patent)?\s*application\b"
    r"|\bhas\s+my\s+(?:company['’]s\s+)?(?:trademark|trade\s+mark|patent)?\s*application\b.{0,45}\b(?:accepted|approved|registered|rejected)\b"
    r"|\b(?:exact|which)\s+(?:patent\s+)?claims?\b.{0,70}\b(?:unpublished|my\s+(?:chemical\s+)?formula|my\s+invention|specific\s+application)\b"
    r"|\bunpublished\s+(?:chemical\s+)?(?:formula|invention)\b"
    r"|\bwhat\s+will\s+be\s+granted\b.{0,60}\b(?:my|specific)\s+application\b",
    re.IGNORECASE,
)
_UNSUPPORTED_JURISDICTION = re.compile(
    r"\b(?:u\.?\s*s\.?\s*a?\.?|united\s+states|american)\b"
    r"|\bcanad(?:a|ian)\b",
    re.IGNORECASE,
)
_OUT_OF_SCOPE = re.compile(
    r"\b(?:weekend\s+meal\s+plan|meal\s+plan|recipes?\s+using\s+ingredients|"
    r"suggest\s+(?:a\s+)?(?:weekend\s+)?meal)\b",
    re.IGNORECASE,
)


def _requires_freshness(query: str) -> bool:
    year = date.today().year
    as_of = _AS_OF_YEAR.search(query)
    if as_of and int(as_of.group(1)) >= year:
        return True

    terms = list(_FRESHNESS_TERMS.finditer(query))
    if not terms:
        return False
    # A past-year boundary makes “latest/recent” a historical question.
    cutoff = _HISTORICAL_CUTOFF.search(query)
    if cutoff and int(cutoff.group(1)) < year:
        non_historical_terms = [
            match for match in terms
            if match.group(1).casefold() in {"today", "current", "currently"}
        ]
        return bool(non_historical_terms)
    return True


def evaluate_abstention_guard(query: str) -> AbstentionGuardResult:
    """Flag only clear freshness, personal-case, unsupported-jurisdiction, or scope cases.

    This intentionally does not use the mere presence of retrieved text as evidence that a
    request is answerable. Corpus freshness is not tracked as live metadata by this system.
    """
    if _CASE_SPECIFIC.search(query):
        return AbstentionGuardResult(
            True,
            "case_specific",
            "The available corpus does not contain the application, registry, or unpublished case material needed to answer this request reliably.",
        )

    jurisdiction = _UNSUPPORTED_JURISDICTION.search(query)
    if jurisdiction:
        requested = jurisdiction.group(0)
        return AbstentionGuardResult(
            True,
            "unsupported_jurisdiction",
            f"The requested jurisdiction ({requested}) is not covered by the current corpus, which covers India and selected international treaties/frameworks.",
        )

    if _requires_freshness(query):
        return AbstentionGuardResult(
            True,
            "freshness",
            "The available legal corpus cannot establish current or latest information reliably; please consult an up-to-date official source.",
        )

    if _OUT_OF_SCOPE.search(query):
        return AbstentionGuardResult(
            True,
            "out_of_scope",
            "This system supports intellectual-property, legal, and regulatory questions, not meal planning or other unrelated requests.",
        )

    return AbstentionGuardResult(False)



# 7. Where does this file fit in your RAG architecture?
# The general execution flow is:
# User asks a question


# Router

# Determines general, legal, or clarification intent


# abstention.py

# Checks whether the query should be rejected before generation


# Retriever

# Dense + BM25 + RRF retrieval


# LLM generation

# Generates an answer using retrieved legal evidence


# Citation validation + claim verification


# The exact position of the guard relative to retrieval should be confirmed in your api.py because this diagram shows its conceptual role, not a guarantee of every call in your implementation.
# 8. My technical observations
# There are some important limitations worth understanding:
# 1. Regex-based detection is narrow. A user might ask about US laws without using any of the words currently covered by the regex.
# 2. Freshness detection is not corpus freshness verification. It cannot determine whether a particular document has been amended.
# 3. Historical questions can be tricky. The cutoff logic is a heuristic and may misclassify unusual wording.
# 4. Out-of-scope detection is very limited. It only identifies a few meal-related phrases, not every unrelated question.
# 5. No retrieval-quality check happens here. A query can pass this guard and still have insufficient legal evidence. That is a separate responsibility for retrieval and the rest of the RAG pipeline.
# One especially important design choice is that this guard does not say, "I found no relevant document, so I will abstain." It only checks clear categories before generation. That avoids confusing query classification with evidence quality.

# In one sentence: abstention.py is a deterministic safety gate that blocks clearly unsupported, case-specific, freshness-dependent, or unrelated queries before the LLM generates an answer.

# The next useful file to study is the API section that calls evaluate_abstention_guard()—that will show exactly how its result changes the response returned to the frontend.