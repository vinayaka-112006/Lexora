"""Small dependency-free morphology helpers for retrieval queries."""
from __future__ import annotations

import re
from collections.abc import Iterable

_STOPWORDS = set("""a about above after again against all am an and any are as at be because been
before being below between both but by can could did do does doing down during each few for from
further had has have having he her here hers herself him himself his how i if in into is it its
itself just me more most my myself no nor not of off on once only or other our ours ourselves out
over own same she should so some such than that the their theirs them themselves then there these
they this those through to too under until up very was we were what when where which while who whom
why will with would you your yours act acts section sections article articles chapter part schedule
rule rules regulation regulations hereby aforesaid thereof therein thereto said provided pursuant
thereunder under this act""".split())
_LEGAL_NOISE = {
    "shall", "may", "means", "include", "includes", "including", "person", "government",
    "central", "authority", "court", "application", "provision", "provisions",
}
_TOKEN_PATTERN = re.compile(r"[a-z]{4,}")


def morphology_tokens(text: str) -> list[str]:
    """Use Stage 6H's substantive token filtering, excluding numerals and boilerplate."""
    return [word for word in _TOKEN_PATTERN.findall(text.casefold())
            if word not in _STOPWORDS and word not in _LEGAL_NOISE
            and not re.fullmatch(r"[mdclxvi]+", word)]


def morphology_vocabulary(chunks: Iterable[dict[str, object]]) -> set[str]:
    """Build the query-expansion vocabulary from all corpus chunks, without targets."""
    vocabulary: set[str] = set()
    for chunk in chunks:
        text = " ".join(str(chunk.get(field) or "") for field in
                        ("text", "provision_title", "document_name"))
        vocabulary.update(morphology_tokens(text))
    return vocabulary


def morphology_terms(query: str, vocabulary: set[str]) -> list[str]:
    """Apply Stage 6H's corpus-attested singular/plural rules and five-term cap."""
    original_terms = list(dict.fromkeys(morphology_tokens(query)))
    added: list[str] = []
    for term in original_terms:
        candidates: list[str] = []
        if len(term) > 4 and term.endswith("ies"):
            candidates.append(term[:-3] + "y")
        if len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
            candidates.append(term[:-1])
        elif len(term) > 3:
            candidates.append(term + "s")
        for candidate in candidates:
            if candidate in vocabulary and candidate not in original_terms and candidate not in added:
                added.append(candidate)
    return added[:5]


def expand_query_morphology(query: str, vocabulary: set[str]) -> str:
    """Append up to five deterministic, corpus-attested forms while preserving query text."""
    added = morphology_terms(query, vocabulary)
    return " ".join([query, *added]) if added else query


def conditionally_expand_query(
    query: str,
    intent: str,
    explicit_provision: dict[str, str] | None,
    vocabulary: set[str],
    enabled: bool,
) -> tuple[str, bool]:
    """Skip disabled, explicit, comparison, and fewer-than-four-token queries."""
    relation_query = bool(re.search(r"\b(relate|relationship|relation)\b", query.casefold()))
    if not enabled or explicit_provision is not None or intent == "comparison" or relation_query:
        return query, False
    if len(morphology_tokens(query)) < 4:
        return query, False
    expanded = expand_query_morphology(query, vocabulary)
    return expanded, expanded != query


# 10. Important limitations
# - It handles only simple s and ies transformations.
# - It does not perform full stemming or lemmatization.
# - It does not understand synonyms. For example, approval and permission are not treated as equivalent by this file.
# - The five-term limit prevents excessive query expansion.
# - Corpus vocabulary filtering reduces irrelevant expansions, but cannot guarantee that an added word improves retrieval.
# Remember this in one sentence:

# query_morphology.py expands a legal query with simple alternative word forms found in the actual corpus, helping the retriever improve lexical matching without changing the original question.