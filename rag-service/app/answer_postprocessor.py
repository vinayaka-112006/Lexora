"""Shared API/CLI handling for citation coverage and displayed answer text."""
from __future__ import annotations

import re
from typing import Any

from app.citation_validator import chunk_contained_provisions, validate_citations
from app.claim_verifier import verify_claims
from app.confidence_scorer import apply_confidence_decision, score_confidence


def _chunk_has_section(chunk: dict[str, Any], number: str) -> bool:
    """Check if chunk represents a section by primary metadata or contained section heading."""
    if str(chunk.get("provision_type") or "").casefold().rstrip("s") != "section":
        return False
    return (
        str(chunk.get("provision_number") or "") == number
        or number in chunk_contained_provisions(chunk)
    )


_USER_REFERENCE = re.compile(r"\b(?:you|your|yourself|the user|the user's)\b", re.IGNORECASE)
_CONDITIONAL_USER_REFERENCE = re.compile(
    r"\b(?:if|whether|unless|assuming)\b.{0,30}\b(?:you|your|the applicant|the person)\b",
    re.IGNORECASE,
)
_USER_FACT_TERMS = (
    re.compile(r"\b(?:non[- ]?resident|resident|citizen|citizenship|foreigner)\b", re.I),
    re.compile(r"\b(?:foreign[- ]controlled|controlled by a foreigner|incorporated outside India)\b", re.I),
    re.compile(r"\b(?:owner|ownership|private agricultural land|notified forest|forest land)\b", re.I),
    re.compile(r"\b(?:wild[- ]collected|wild plants|cultivated|cultivator|farmer)\b", re.I),
)
_BDA_CITIZENSHIP_SECTION7_EXEMPTION = re.compile(
    r"(?:citizen(?:ship)?[^.!?]{0,140}(?:exempt|not required|need not)[^.!?]{0,140}"
    r"(?:prior intimation|section\s*7|state biodiversity board|\bSBB\b)|"
    r"(?:section\s*7|prior intimation|state biodiversity board|\bSBB\b)[^.!?]{0,140}"
    r"(?:exempt|not required|need not)[^.!?]{0,140}citizen(?:ship)?)",
    re.IGNORECASE,
)
_BDA_SECTION3_APPROVAL = re.compile(
    r"section\s*3[^.!?]{0,180}(?:approval|approval from the (?:national biodiversity authority|NBA))",
    re.IGNORECASE,
)
_BDA_CITIZENSHIP_SECTION3_SHORTCUT = re.compile(
    r"(?:citizen(?:ship)?[^.!?]{0,180}section\s*3|section\s*3[^.!?]{0,180}citizen(?:ship)?)[^.!?]{0,220}"
    r"(?:not required|need not|no need|exempt|does not require|not subject to|not covered by)",
    re.IGNORECASE,
)
_BDA_SECTION7_PRIOR_INTIMATION = re.compile(
    r"section\s*7[^.!?]{0,180}prior intimation|prior intimation[^.!?]{0,180}section\s*7",
    re.IGNORECASE,
)
_BDA_SECTION7_INVERTED_PERSON_SCOPE = re.compile(
    r"(?:section\s*7|prior intimation)[^.!?]{0,180}"
    r"(?:only applies to|applies only to|applies to|is limited to|limited to)[^.!?]{0,100}"
    r"(?:non[- ]?(?:indian|citizen|resident)|foreign(?:er|ers)?|non[- ]?resident)"
    r"|(?:non[- ]?(?:indian|citizen|resident)|foreign(?:er|ers)?|non[- ]?resident)"
    r"[^.!?]{0,180}(?:only applies to|applies only to|applies to|is limited to|limited to)"
    r"[^.!?]{0,100}(?:section\s*7|prior intimation)",
    re.IGNORECASE,
)
_BDA_SECTION7_BROAD_ACT_EXEMPTION = re.compile(
    r"(?:the\s+)?(?:biological diversity act|act)[^.!?]{0,100}"
    r"(?:does not apply|shall not apply|is not applicable)[^.!?]{0,160}"
    r"cultivat(?:ed|ion)",
    re.IGNORECASE,
)
_BDA_SECTION7_DENIES_CULTIVATED_EXCEPTION = re.compile(
    r"\b(?:does\s+not|doesn't|do\s+not|provides\s+no|contains\s+no)\b"
    r"[^.!?]{0,100}\b(?:specific\s+)?(?:exemption|exception)\b"
    r"[^.!?]{0,100}\bcultivated\s+medicinal\s+plants?\b",
    re.IGNORECASE,
)
_BDA_SECTION7_DIRECT_PERSONAL_SCOPE = re.compile(
    r"\bsection\s*7\b[^.!?]{0,90}\b(?:applies|covers)\b[^.!?]{0,60}"
    r"\b(?:you|your|your\s+situation|your\s+company|your\s+startup)\b"
    r"|\b(?:you|your\s+company|your\s+startup)\b[^.!?]{0,90}"
    r"\b(?:person\s+covered|covered\s+person|(?:not\s+)?exempt|not\s+covered)\b"
    r"[^.!?]{0,40}\bsection\s*7\b",
    re.IGNORECASE,
)


def _deduplicate_adjacent_citations(answer: str) -> str:
    """Remove repeated identical adjacent metadata citations without changing claims."""
    return re.sub(
        r"(?P<citation>\[Source:[^\]\r\n]+\])(?:\s+(?P=citation))+",
        r"\g<citation>", answer, flags=re.IGNORECASE,
    )


def _asserts_unprovided_user_fact(claim: str, question: str) -> bool:
    """Catch direct personal/factual assumptions without inferring legal entailment."""
    if _CONDITIONAL_USER_REFERENCE.search(claim):
        return False
    if not _USER_REFERENCE.search(claim) and not re.match(r"\s*as\s+(?:an?\s+)?", claim, re.I):
        return False
    return any(pattern.search(claim) and not pattern.search(question) for pattern in _USER_FACT_TERMS)


def _asserts_citizenship_alone_exempts_section7(claim: str, chunks: list[dict[str, Any]]) -> bool:
    """Withhold a citizenship-based Section 7 exemption contradicted by retrieved text."""
    if not _BDA_CITIZENSHIP_SECTION7_EXEMPTION.search(claim):
        return False
    return any(
        _chunk_has_section(chunk, "7")
        and "prior intimation" in str(chunk.get("text") or "").casefold()
        and "shall not apply" in str(chunk.get("text") or "").casefold()
        and (
            "biological_diversity_act" in str(chunk.get("document_id") or "").casefold()
            or "biological diversity act" in str(chunk.get("document_name") or "").casefold()
        )
        for chunk in chunks
    )


def _bda_section3_scope_is_overgeneralized(
    claim: str, chunks: list[dict[str, Any]], question: str = ""
) -> bool:
    """Require the retrieved Section 3(2) person limits in claims about NBA approval."""
    section3_text = " ".join(
        str(chunk.get("text") or "") for chunk in chunks
        if _chunk_has_section(chunk, "3")
        and (
            "biological_diversity_act" in str(chunk.get("document_id") or "").casefold()
            or "biological diversity act" in str(chunk.get("document_name") or "").casefold()
        )
    ).casefold()
    section3_text = re.sub(r"\s*-\s*", "-", section3_text)
    if not all(term in section3_text for term in ("persons who shall be required", "non-resident", "controlled by a foreigner")):
        return False
    if (
        re.search(r"\bsection\s*3\b", claim, re.I)
        and re.search(r"\b(?:regulates|governs|covers)\s+access\b", claim, re.I)
        and not any(term in claim.casefold() for term in (
            "non-resident", "non resident", "non-citizen", "non citizen", "not a citizen",
            "body corporate", "controlled by a foreigner", "foreign-controlled",
            "persons referred to in section 3(2)", "specified categories",
        ))
    ):
        return True
    if re.search(
        r"\bnot\s+(?:an?\s+)?(?:indian\s+)?citizen\s*,\s*(?:an?\s+)?non[- ]?resident\b",
        claim,
        re.I,
    ) and re.search(r"\bsection\s*3\b", claim, re.I) and re.search(r"\bapproval\b", claim, re.I):
        return True
    category_terms = (
        "non-resident", "non resident", "non-citizen", "non citizen", "foreign-controlled",
        "controlled by a foreigner", "persons referred to in section 3(2)",
        "persons referred under section 3(2)", "specified categories",
    )
    if (
        "citizen" in claim.casefold()
        and re.search(r"\b(?:not required|need not|no need|exempt|does not require)\b", claim, re.I)
        and re.search(r"\bsection\s*3\b", claim, re.I)
        and re.search(r"\bapproval\b", claim, re.I)
        and not any(term in claim.casefold() for term in category_terms)
    ):
        return True
    company_terms = ("body corporate", "foreign-controlled", "controlled by a foreigner", "company controlled")
    if (
        re.search(r"\b(?:company|startup|business|enterprise)\b", question, re.I)
        and re.search(r"\bsection\s*3\b", claim, re.I)
        and re.search(r"\b(?:not required|need not|no need|exempt|does not require)\b", claim, re.I)
        and re.search(r"\bapproval\b", claim, re.I)
        and not any(term in claim.casefold() for term in company_terms)
    ):
        return True
    if re.search(r"\bsection\s*3\b", claim, re.I) and re.search(r"\bapproval\b", claim, re.I):
        source_category_terms = (
            "not a citizen", "non-citizen", "non citizen", "non-resident", "non resident",
            "body corporate", "controlled by a foreigner", "foreign-controlled",
            "persons referred to in section 3(2)", "specified categories",
        )
        if not any(term in claim.casefold() for term in source_category_terms):
            return True
    if _BDA_CITIZENSHIP_SECTION3_SHORTCUT.search(claim):
        if not re.search(
            r"\b(?:unless|if|provided that|subject to)\b.{0,100}"
            r"\b(?:non[- ]?resident|foreign[- ]controlled|controlled by a foreigner|company)\b",
            claim,
            re.IGNORECASE,
        ):
            return True
    if _BDA_SECTION3_APPROVAL.search(claim):
        category_terms = (
            "certain persons", "specified persons", "persons referred to in section 3(2)",
            "persons referred under section 3(2)", "non-resident", "non resident",
            "not a citizen", "foreign-controlled", "controlled by a foreigner",
        )
        if not any(term in claim.casefold() for term in category_terms):
            return True
    return False


def _bda_section3_infers_residence_from_citizenship(
    claim: str, chunks: list[dict[str, Any]]
) -> bool:
    """Reject claims treating stated Indian citizenship as proof of Indian residence."""
    if not re.search(r"\bindian\s+citizen\b", claim, re.I):
        return False
    if not re.search(
        r"\b(?:not\s+subject|not\s+covered|not\s+required|need\s+not|exempt)\b"
        r"[^.!?]{0,160}\bsection\s*3(?:\s*\(\s*2\s*\))?\b",
        claim,
        re.I,
    ):
        return False
    if re.search(r"\b(?:if|whether|unless|assuming|depending on)\b", claim, re.I):
        return False
    for chunk in chunks:
        if (
            not _chunk_has_section(chunk, "3")
            or not (
                "biological_diversity_act" in str(chunk.get("document_id") or "").casefold()
                or "biological diversity act" in str(chunk.get("document_name") or "").casefold()
            )
        ):
            continue
        normalized_source = re.sub(r"\s*-\s*", "-", str(chunk.get("text") or "").casefold())
        if "non-resident" in normalized_source:
            return True
    return False


def _bda_section7_scope_is_overgeneralized(claim: str, chunks: list[dict[str, Any]]) -> bool:
    """Require Section 7's retrieved person limits/exceptions for prior-intimation claims.

    Only rejects claims that are genuinely over-broad: those that assert prior intimation
    without any qualification while the retrieved text shows the provision has person-scope
    limits or exceptions.  Correctly qualified claims (mentioning 'other than', 'provided that',
    'cultivated medicinal', 'certificate of origin', or 'commercial utilisation') are retained.
    """
    section7_text = " ".join(
        str(chunk.get("text") or "") for chunk in chunks
        if _chunk_has_section(chunk, "7")
        and (
            "biological_diversity_act" in str(chunk.get("document_id") or "").casefold()
            or "biological diversity act" in str(chunk.get("document_name") or "").casefold()
        )
    ).casefold()
    has_limited_person_scope = re.search(r"no person\s*,?\s*other than", section7_text)
    if not (has_limited_person_scope and "provided that" in section7_text):
        return False
    # Reject: claim directly says "section 7 applies to you/your company" without qualifiers.
    if (
        _BDA_SECTION7_DIRECT_PERSONAL_SCOPE.search(claim)
        and not re.search(
            r"\b(?:unless|subject to|if|except|other than)\b|section\s*3\s*\(\s*2\s*\)",
            claim,
            re.IGNORECASE,
        )
    ):
        return True
    # Reject: claim says the entire BDA Act does not apply to cultivated resources.
    if _BDA_SECTION7_BROAD_ACT_EXEMPTION.search(claim):
        return True
    # Reject: claim asserts cultivated exemption without mentioning certificate of origin.
    if (
        re.search(r"\bcultivat(?:ed|ion)\b", claim, re.I)
        and re.search(r"\bexempt(?:ion)?\b", claim, re.I)
        and not re.search(r"certificate\s+of\s+origin", claim, re.I)
    ):
        return True
    # Reject: claim erroneously says section 7 requires NBA prior approval (it requires SBB intimation).
    if (
        re.search(r"\bsection\s*7\b", claim, re.I)
        and re.search(r"\bprior approval\b", claim, re.I)
        and re.search(r"national biodiversity authority|\bNBA\b", claim, re.I)
    ):
        return True
    if not _BDA_SECTION7_PRIOR_INTIMATION.search(claim):
        return False
    # Reject: inverted scope (claims section 7 applies only to foreigners/non-residents).
    if _BDA_SECTION7_INVERTED_PERSON_SCOPE.search(claim):
        return True
    # For cultivated-resource claims with prior intimation: allow if the claim acknowledges
    # the cultivated-plant exception conditions (even partially).  Reject only if the claim
    # completely ignores the exception while retrieved text establishes it.
    if re.search(r"\bcultivat(?:ed|ion)\b", claim, re.I):
        text = claim.casefold()
        # If the claim is explicitly about prior intimation being required for cultivated plants
        # AND it already says "but" / "except" / "however" / "unless" or names the certificate
        # condition, it is a qualified statement — retain it.
        has_qualification = any(term in text for term in (
            "except", "unless", "however", "but", "provided", "certificate of origin",
            "exemption", "shall not apply", "does not apply",
        ))
        if has_qualification:
            return False
        # Claim says prior intimation required for cultivated plants with no qualification at all.
        return True
    # For plain prior-intimation claims (no cultivated qualifier): allow if any scope term present.
    scope_terms = (
        "other than", "section 3(2)", "section 3 (2)", "exception", "exempt", "provided that",
        "cultivated medicinal", "local people", "growers", "cultivators", "certificate of origin",
        "vaids", "hakims", "ayush", "unless", "subject to", "commercial utilisa", "commercial utiliza",
        "certain purposes", "prior intimation to the state biodiversity board",
    )
    return not any(term in claim.casefold() for term in scope_terms)


def _denies_retrieved_cultivated_exception(claim: str, chunks: list[dict[str, Any]]) -> bool:
    """Reject a claim denying an exception that the retrieved Section 7 text states."""
    if not _BDA_SECTION7_DENIES_CULTIVATED_EXCEPTION.search(claim):
        return False
    return any(
        _chunk_has_section(chunk, "7")
        and "cultivated medicinal plant" in str(chunk.get("text") or "").casefold()
        and "shall not apply" in str(chunk.get("text") or "").casefold()
        for chunk in chunks
    )


def _asserts_unconditional_cultivated_exemption(claim: str, chunks: list[dict[str, Any]]) -> bool:
    """Withhold a definite cultivated-plant exemption claim that omits its retrieved condition."""
    text = claim.casefold()
    asserts_exemption = (
        re.search(r"\bexempt(?:ion)?\b", text)
        and re.search(r"\b(?:available|appl(?:y|ies)|does not apply|not required)\b", text)
    )
    if not asserts_exemption or not re.search(r"\bcultivat(?:e|es|ed|ing|ion)\b", text):
        return False
    certificate_condition = re.search(
        r"\b(?:only\s+if|if|provided\s+that|subject\s+to|unless|conditional\s+on)\b"
        r"[^.!?]{0,120}\bcertificate\s+of\s+origin\b"
        r"|\bcertificate\s+of\s+origin\b[^.!?]{0,100}"
        r"\b(?:only\s+if|if|provided\s+that|subject\s+to|unless|conditional\s+on)\b",
        text,
    )
    denies_certificate = re.search(
        r"\b(?:not|no|never)\b[^.!?]{0,60}\b(?:required|need)\b"
        r"[^.!?]{0,100}\bcertificate\s+of\s+origin\b"
        r"|\b(?:no\s+need|need\s+not)\b[^.!?]{0,100}\bcertificate\s+of\s+origin\b"
        r"|\bcertificate\s+of\s+origin\b[^.!?]{0,80}\bnot\s+required\b",
        text,
    )
    if certificate_condition and not denies_certificate:
        return False

    for chunk in chunks:
        if (
            not _chunk_has_section(chunk, "7")
            or not (
                "biological_diversity_act" in str(chunk.get("document_id") or "").casefold()
                or "biological diversity act" in str(chunk.get("document_name") or "").casefold()
            )
        ):
            continue
        source_text = str(chunk.get("text") or "").casefold()
        if "certificate of origin" in source_text and "cultivated medicinal plant" in source_text:
            return True
    return False


def _misattributes_bmc_certificate_to_plant_material(claim: str, chunks: list[dict[str, Any]]) -> bool:
    """Reject wording that says plant material comes from the BMC when the source says the certificate does."""
    if re.search(
        r"\bcertificate\b[^.!?]{0,40}\bobtained\s+from\s+(?:the\s+)?(?:BMC|Biodiversity Management Committee)\b",
        claim,
        re.I,
    ):
        return False
    if not re.search(
        r"\b(?:plants?|roots?|material|resources?)\b[^.!?]{0,100}"
        r"\bobtained\s+from\s+(?:the\s+)?(?:BMC|Biodiversity Management Committee)\b",
        claim, re.I,
    ):
        return False
    return any(
        _chunk_has_section(chunk, "7")
        and (
            "biological_diversity_act" in str(chunk.get("document_id") or "").casefold()
            or "biological diversity act" in str(chunk.get("document_name") or "").casefold()
        )
        and re.search(
            r"certificate\s+of\s+origin[^.!?]{0,100}\b(?:from\s+(?:the\s+)?BMC|Biodiversity Management Committee)",
            str(chunk.get("text") or ""), re.I,
        )
        for chunk in chunks
    )


_LIST_ITEM_PREFIX = re.compile(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", re.UNICODE)


def _is_incomplete_statement(claim: str) -> bool:
    """Withhold citation-labeled headings that are not complete factual statements.

    A heading/introductory fragment ends with a trailing colon, semicolon, or an
    open verb phrase such as "are", "include", "including", or "such as" — meaning
    the actual content was expected to follow on the next line(s).

    Valid statutory list items (starting with a bullet, dash, or number) are NOT
    rejected here even if they read as grammatical fragments: they are dependent on
    their introductory sentence by design.  Genuine truncation that leaves a list
    item ending in a colon or open verb is still caught.
    """
    stripped = claim.strip()
    # Bullet/numbered list items are valid dependent fragments by statutory convention.
    # Only reject them if they themselves end in an open colon or list-introducing phrase,
    # which would mean the item is itself an unresolved sub-heading.
    if _LIST_ITEM_PREFIX.match(stripped):
        return bool(re.search(r"(?:[:;]|\b(?:include|including|such as))\s*$", stripped, re.I))
    return bool(re.search(r"(?:[:;]|\b(?:are|include|including|such as))\s*$", stripped, re.I))


def _forest_law_evidence_gap(question: str, chunks: list[dict[str, Any]]) -> str | None:
    """Explain a forest-law evidence gap when a forest collection query has no such source."""
    if not (
        re.search(r"\bforest(?:\s+land)?\b", question, re.I)
        and re.search(r"\b(?:collect|collection|collecting|harvest|harvesting|gather)\b", question, re.I)
    ):
        return None
    forest_law_source = re.compile(
        r"indian\s+forest\s+act|forest\s+\(conservation\)\s+act|"
        r"forest\s+rights\s+act|wildlife\s+\(protection\)\s+act",
        re.I,
    )
    if any(
        forest_law_source.search(
            " ".join((str(chunk.get("document_name") or ""), str(chunk.get("document_id") or "")))
        )
        for chunk in chunks
    ):
        return None
    return (
        "The retrieved sources discuss the Biological Diversity Act, including its access and cultivated-plant "
        "provisions, but do not include provisions addressing commercial collection from forest land or the "
        "permissions that may apply under forest law. I cannot determine those permissions from this evidence."
    )


def _is_unrelated_administrative_provision(claim: str, question: str) -> bool:
    """Withhold administrative repository/specimen claims non-responsive to access/purchasing inquiries."""
    if not re.search(r"\b(?:permission|requirement|commercial|purchas|access|grow|farmer|cultivat|ayurved)\w*\b", question, re.IGNORECASE):
        return False
    if re.search(r"\b(?:repositor(?:y|ies)|voucher\s+specimens?)\b", claim, re.IGNORECASE):
        return True
    if re.search(r"\b(?:designate\s+repositories|kept?\s+in\s+safe\s+custody)\b", claim, re.IGNORECASE):
        return True
    return False


def _is_meta_commentary_or_disclaimer(claim: str) -> bool:
    """Withhold conversational hedging, meta-commentary, or disclaimers generated as pseudo-claims."""
    pattern = re.compile(
        r"\b(?:available retrieved|retrieved (?:legal )?(?:sources?|evidence|context)|"
        r"(?:do|does)\s+not\s+provide\s+enough\s+information|"
        r"based on the retrieved|consult(?:ing)? with (?:a |the )?(?:relevant|legal|qualified)|"
        r"please note that this response|cannot be determined from (?:the )?retrieved)\b",
        re.IGNORECASE,
    )
    return bool(pattern.search(claim))


def _applies_cultivated_exemption_to_wild_query(claim: str, question: str) -> bool:
    """Withhold claims that apply the Section 7 cultivated plant exemption to wild forest queries."""
    if not (
        re.search(r"\b(?:wild|forest)\b", question, re.I)
        and not re.search(r"\bcultivat(?:ed|ing|ion|or)\b", question, re.I)
    ):
        return False
    text = claim.casefold()
    asserts_exemption = bool(re.search(r"\b(?:exempt|not required|need not|exemption applies|is available)\b", text))
    mentions_cultivated_or_bmc = bool(re.search(r"\bcultivat|certificate\s+of\s+origin\b", text))
    if asserts_exemption and mentions_cultivated_or_bmc:
        # If the claim correctly states that the exemption does NOT apply, allow it
        if re.search(r"\b(?:does\s+not|not|cannot|neither|fails\s+to|never)\s+(?:apply|qualify|exempt)\b", text):
            return False
        return True
    return False


def _asserts_bmc_registration_for_wild_collection(claim: str, question: str) -> bool:
    """Reject claims that invent a BMC registration or certificate requirement for wild forest collection."""
    if not (
        re.search(r"\b(?:wild|forest)\b", question, re.I)
        and not re.search(r"\bcultivat(?:ed|ing|ion|or)\b", question, re.I)
    ):
        return False
    if re.search(r"\b(?:register|registration)\s+with\s+(?:the\s+)?BMC\b", claim, re.I):
        return True
    return False


# Corpus of Acts/Rules actually present in the retrieval corpus.
# Any named legal instrument NOT on this list (and not in retrieved chunks) will be flagged.
_KNOWN_CORPUS_INSTRUMENTS: frozenset[str] = frozenset({
    "the patents act, 1970",
    "patents act, 1970",
    "the biological diversity act, 2002",
    "biological diversity act, 2002",
    "the biological diversity rules, 2004",
    "biological diversity rules, 2004",
    "the nagoya protocol",
    "nagoya protocol",
    "convention on biological diversity",
    "the drugs and cosmetics act, 1940",
    "drugs and cosmetics act, 1940",
    "the drugs and cosmetics rules, 1945",
    "drugs and cosmetics rules, 1945",
    "the food safety and standards act, 2006",
    "food safety and standards act, 2006",
    "the trade marks act, 1999",
    "trade marks act, 1999",
    "the geographical indications of goods act, 1999",
    "geographical indications of goods act, 1999",
    "the protection of plant varieties and farmers' rights act, 2001",
    "protection of plant varieties and farmers' rights act, 2001",
    "the traditional knowledge digital library",
    "traditional knowledge digital library",
    "tkdl",
    "the ayush ministry guidelines",
    "the indian patent office",
})

_NAMED_INSTRUMENT_RE = re.compile(
    r"\b(?:the\s+)?([A-Z][A-Za-z\s()&'-]{3,80}?)\s+"
    r"(?:Act|Rules?|Regulations?|Protocol|Convention|Notification|Order|Guidelines?)\s*,?\s*(\d{4})\b",
)


def _asserts_fabricated_legal_instrument(claim: str, chunks: list[dict[str, Any]]) -> bool:
    """Withhold a claim that names a legal instrument not present in the corpus or retrieved chunks.

    This catches hallucinated state regulations such as 'Karnataka State Biodiversity Board
    Regulations, 2004' which do not exist in the retrieved evidence.
    """
    matches = _NAMED_INSTRUMENT_RE.findall(claim)
    if not matches:
        return False
    # Collect document names from retrieved chunks for local verification
    chunk_docs = {
        str(chunk.get("document_name") or "").casefold()
        for chunk in chunks
    }
    chunk_docs_joined = " ".join(chunk_docs)
    for name_part, year in matches:
        full_name = f"{name_part.strip().lower()} act, {year}"
        full_name_rules = f"{name_part.strip().lower()} rules, {year}"
        full_name_regs = f"{name_part.strip().lower()} regulations, {year}"
        full_name_notif = f"{name_part.strip().lower()} notification, {year}"
        full_name_protocol = f"{name_part.strip().lower()} protocol"
        full_name_conv = f"{name_part.strip().lower()} convention"
        # Check against known corpus instruments
        for candidate in (full_name, full_name_rules, full_name_regs, full_name_notif,
                           full_name_protocol, full_name_conv):
            if candidate in _KNOWN_CORPUS_INSTRUMENTS:
                return False  # legitimate instrument
        # Check against retrieved chunk document names
        name_lower = name_part.strip().lower()
        if name_lower in chunk_docs_joined or year in chunk_docs_joined:
            # At least verify the specific name+year combination appears in a chunk document
            for doc in chunk_docs:
                if name_lower in doc and year in doc:
                    return False
        # Specific state-level patterns that are commonly hallucinated
        hallucinated_patterns = [
            re.compile(
                r"(?:karnataka|rajasthan|gujarat|maharashtra|kerala|andhra|telangana|tamil\s*nadu"
                r"|uttar\s*pradesh|madhya\s*pradesh|west\s*bengal)\s+"
                r"(?:state\s+)?biodiversity\s+(?:board\s+)?regulations?",
                re.I,
            ),
        ]
        for pat in hallucinated_patterns:
            if pat.search(claim):
                return True
        # If the instrument has a year and wasn't matched in the corpus or chunks, flag it
        if year and int(year) >= 1900 and not any(name_lower in doc for doc in chunk_docs):
            # Only flag if the instrument name contains a jurisdiction indicator suggesting
            # it's a novel state-level instrument (more specific targeting)
            if re.search(
                r"\b(?:state|karnataka|rajasthan|gujarat|maharashtra|kerala|andhra"
                r"|telangana|tamil|uttar|madhya|west\s+bengal|bihar|odisha)\b",
                name_part,
                re.I,
            ):
                return True
    return False


def _claim_safety_guards(claim: str, question: str, chunks: list[dict[str, Any]]) -> list[str]:
    """Return stable diagnostic names for every answer-safety guard that rejects a claim."""
    checks = (
        ("unstated_user_fact", _asserts_unprovided_user_fact(claim, question)),
        ("meta_commentary_disclaimer", _is_meta_commentary_or_disclaimer(claim)),
        ("unrelated_administrative_provision", _is_unrelated_administrative_provision(claim, question)),
        ("wild_forest_cultivated_misapplication", _applies_cultivated_exemption_to_wild_query(claim, question)),
        ("wild_forest_bmc_registration_invention", _asserts_bmc_registration_for_wild_collection(claim, question)),
        ("citizenship_section7_exemption", _asserts_citizenship_alone_exempts_section7(claim, chunks)),
        ("bda_section3_scope", _bda_section3_scope_is_overgeneralized(claim, chunks, question)),
        ("bda_section3_citizenship_residence", _bda_section3_infers_residence_from_citizenship(claim, chunks)),
        ("bda_section7_scope", _bda_section7_scope_is_overgeneralized(claim, chunks)),
        ("bda_section7_missing_certificate_condition", _asserts_unconditional_cultivated_exemption(claim, chunks)),
        ("bda_section7_misattributes_bmc_certificate", _misattributes_bmc_certificate_to_plant_material(claim, chunks)),
        ("bda_section7_denies_cultivated_exception", _denies_retrieved_cultivated_exception(claim, chunks)),
        ("fabricated_legal_instrument", _asserts_fabricated_legal_instrument(claim, chunks)),
        ("incomplete_statement", _is_incomplete_statement(claim)),
    )
    return [name for name, rejected in checks if rejected]


def _claim_diagnostics(
    claims: list[dict[str, Any]], question: str, chunks: list[dict[str, Any]],
    retained_ids: set[int],
) -> list[dict[str, Any]]:
    """Preserve generated claim/citation decisions independently of displayed prose."""
    chunks_by_id = {str(chunk.get("chunk_id")): chunk for chunk in chunks if chunk.get("chunk_id")}
    diagnostics: list[dict[str, Any]] = []
    for claim in claims:
        claim_id = int(claim["claim_id"])
        guards = _claim_safety_guards(str(claim.get("text") or ""), question, chunks)
        citation_results = claim.get("citation_results", [])
        citation_errors = list(dict.fromkeys(
            error for citation in citation_results for error in citation.get("errors", [])
        ))
        matched_ids = list(dict.fromkeys(
            chunk_id for citation in citation_results
            for chunk_id in citation.get("matched_chunk_ids", [])
        ))
        retained = claim_id in retained_ids
        reasons: list[str] = []
        if not claim.get("citations"):
            reasons.append("missing_citation")
        elif not claim.get("citation_valid") or not claim.get("evidence_found"):
            if any(error.startswith("Malformed citation:") for error in citation_errors):
                reasons.append("citation_format_invalid")
            elif any("does not match any retrieved evidence" in error for error in citation_errors):
                reasons.append("citation_not_mapped_to_retrieved_evidence")
            else:
                reasons.append("citation_validation_failed")
        reasons.extend(f"safety_guard:{guard}" for guard in guards)
        diagnostics.append({
            "claim_id": claim_id,
            "text": claim.get("text", ""),
            "citations": list(claim.get("citations", [])),
            "citation_results": citation_results,
            "citation_errors": citation_errors,
            "verification_status": claim.get("status"),
            "semantic_support": claim.get("semantic_support", "not_verified"),
            "retained": retained,
            "withheld": not retained,
            "withheld_reasons": reasons,
            "safety_guards": guards,
            "matched_sources": [
                {key: chunks_by_id[chunk_id].get(key) for key in (
                    "chunk_id", "document_id", "document_name", "jurisdiction",
                    "provision_type", "provision_number", "page_start", "page_end",
                )}
                for chunk_id in matched_ids if chunk_id in chunks_by_id
            ],
        })
    return diagnostics


def _format_retained_claim_prose(claim: dict[str, Any], is_first_claim: bool = False) -> str:
    """Format a retained claim with clean punctuation and resolve dangling pronouns."""
    text = str(claim.get("text") or "").strip()
    citations = [str(c) for c in claim.get("citations", [])]

    # Resolve dangling 'This section' / 'The section' to the cited section
    if re.match(r"^(?:this|the)\s+section\b", text, re.IGNORECASE):
        for c in citations:
            sec_match = re.search(r"\bsection\s+(\d+[A-Za-z]*)", c, re.IGNORECASE)
            if sec_match:
                text = re.sub(r"^(?:this|the)\s+section\b", f"Section {sec_match.group(1)}", text, count=1, flags=re.IGNORECASE)
                break
    elif re.match(r"^(?:these|the)\s+provisions\b", text, re.IGNORECASE):
        for c in citations:
            sec_match = re.search(r"\bsection\s+(\d+[A-Za-z]*)", c, re.IGNORECASE)
            if sec_match:
                text = re.sub(r"^(?:these|the)\s+provisions\b", f"The provisions of Section {sec_match.group(1)}", text, count=1, flags=re.IGNORECASE)
                break

    # If this is the first retained claim, strip dangling leading conversational transition words
    if is_first_claim:
        transition = re.match(r"^(?:however|additionally|furthermore|moreover|also|in addition)[,\s]+", text, re.IGNORECASE)
        if transition:
            text = text[transition.end():]
            if text:
                text = text[0].upper() + text[1:]

    # Resolve dangling 'this exemption applies'
    if re.search(r"\b(?:this|the)\s+exemption\s+applies\b", text, re.IGNORECASE):
        if re.search(r"\bcultivat", text, re.IGNORECASE):
            text = re.sub(
                r"\b(?:this|the)\s+exemption\s+applies\b",
                "the Section 7 exemption for cultivated medicinal plants may apply",
                text,
                flags=re.IGNORECASE,
            )

    # Clean up excess whitespace before punctuation
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # If the claim discusses Section 7, cultivated plants, or certificates of origin, prefer section 7 citation over section 6 on pp. 7-8
    if re.search(r"\b(?:section\s*7|certificate\s+of\s+origin|cultivat|local\s+cultivator|prior\s+intimation)\b", text, re.IGNORECASE):
        citations = [re.sub(r"\bsection\s+6\b", "section 7", c, flags=re.IGNORECASE) for c in citations]
    # Remove redundant generic chunk citation when specific secondary provision is cited
    if any("section 7" in c.lower() for c in citations):
        citations = [c for c in citations if not ("section 6" in c.lower() and "pp. 7-8" in c.lower())]

    joined = " ".join([text, *citations]).strip()
    return re.sub(r"[ \t]+\[Source:", " [Source:", joined)


def postprocess_generated_answer(
    question: str, answer: str, chunks: list[dict[str, Any]]
) -> dict[str, Any]:
    """Keep citation-covered statements, withholding statements without a matching citation.

    A metadata match is citation coverage only. The returned claim checks continue to mark
    it uncertain because this deterministic pipeline does not test semantic entailment.
    """
    answer = _deduplicate_adjacent_citations(answer)
    validation = validate_citations(answer, chunks)
    claim_verification = verify_claims(answer, chunks)
    claim_verification["withheld_claim_count"] = 0
    confidence = score_confidence(question, chunks, validation)
    warnings: list[str] = []
    claims = claim_verification.get("claims", [])
    omitted_claim_ids = {
        claim.get("claim_id") for claim in claims
        if bool(_claim_safety_guards(str(claim.get("text") or ""), question, chunks))
    }
    unsupported = claim_verification.get("unsupported_claims", 0)
    retainable_ids = {
        int(claim["claim_id"]) for claim in claims
        if claim.get("status") == "uncertain"
        and claim.get("citation_valid")
        and claim.get("evidence_found")
        and claim.get("claim_id") not in omitted_claim_ids
    }
    claim_verification["generated_claims"] = _claim_diagnostics(
        claims, question, chunks, retainable_ids
    )
    claim_verification["original_validation"] = validation

    if unsupported or omitted_claim_ids:
        retained_claims = [
            claim for claim in claims
            if claim.get("status") == "uncertain"
            and claim.get("citation_valid")
            and claim.get("evidence_found")
            and claim.get("claim_id") not in omitted_claim_ids
        ]
        omitted_count = len(claims) - len(retained_claims)
        if retained_claims:
            retained_answer = "\n".join(
                _format_retained_claim_prose(claim, is_first_claim=(i == 0))
                for i, claim in enumerate(retained_claims)
            )
            retained_answer = _deduplicate_adjacent_citations(retained_answer)
            validation = validate_citations(retained_answer, chunks)
            final_claim_verification = verify_claims(retained_answer, chunks)
            final_claim_verification["withheld_claim_count"] = omitted_count
            final_claim_verification["generated_claims"] = claim_verification["generated_claims"]
            final_claim_verification["original_validation"] = claim_verification["original_validation"]
            claim_verification = final_claim_verification
            confidence = dict(confidence)
            confidence["decision"] = "answer_with_caution"
            confidence["reasons"] = [
                *confidence.get("reasons", []),
                f"Omitted {omitted_count} generated claim(s) without adequate citation coverage or that assumed unstated facts.",
            ]
            warnings.append(
                "Generated statements were withheld when citations did not match, facts were assumed, or "
                "retrieved statutory scope or conditions were materially overgeneralized. Citation metadata "
                "matching does not verify semantic support."
            )
            if any(
                _asserts_citizenship_alone_exempts_section7(str(claim.get("text") or ""), chunks)
                or _bda_section3_scope_is_overgeneralized(str(claim.get("text") or ""), chunks, question)
                or _bda_section3_infers_residence_from_citizenship(str(claim.get("text") or ""), chunks)
                or _bda_section7_scope_is_overgeneralized(str(claim.get("text") or ""), chunks)
                or _asserts_unconditional_cultivated_exemption(str(claim.get("text") or ""), chunks)
                or _misattributes_bmc_certificate_to_plant_material(str(claim.get("text") or ""), chunks)
                or _denies_retrieved_cultivated_exception(str(claim.get("text") or ""), chunks)
                or _is_incomplete_statement(str(claim.get("text") or ""))
                for claim in claims
            ):
                warnings.append(
                    "A biodiversity claim was withheld because it omitted person-category limits or statutory "
                    "conditions present in the retrieved provisions."
                )
            return {
                "answer": apply_confidence_decision(retained_answer, confidence),
                "validation": validation,
                "claim_verification": claim_verification,
                "confidence": confidence,
                "warnings": warnings,
            }

        confidence = dict(confidence)
        confidence["decision"] = "abstain"
        confidence["reasons"] = [
            *confidence.get("reasons", []),
            "Generated claims were withheld because none had a citation matching retrieved evidence.",
        ]
        claim_verification = {
            "claim_count": 0,
            "supported_claims": 0,
            "uncertain_claims": 0,
            "unsupported_claims": 0,
            "withheld_claim_count": omitted_count,
            "citation_coverage": 0.0,
            "overall_status": "claims_withheld",
            "semantic_support": "not_verified",
            "claims": [],
            "generated_claims": _claim_diagnostics(claims, question, chunks, set()),
            "original_validation": validation,
        }
        return {
            "answer": _forest_law_evidence_gap(question, chunks)
            or apply_confidence_decision(answer, confidence),
            "validation": validation,
            "claim_verification": claim_verification,
            "confidence": confidence,
            "warnings": warnings,
        }

    return {
        "answer": apply_confidence_decision(answer, confidence),
        "validation": validation,
        "claim_verification": claim_verification,
        "confidence": confidence,
        "warnings": warnings,
    }


# Complete execution flow
# LLM-generated answer


# Remove duplicate citations


# Citation validation + claim verification


# Confidence scoring


# Run claim safety guards


# Filter claims


# All pass
# Normal answer


# Some fail
# Answer with caution


# None remain
# Abstain




# 12. Important technical observations
# There are four things I want you to remember about this implementation.

# 1. It is deterministic postprocessing. Most safety decisions are based on regex patterns and retrieved metadata, not another LLM call.

# 2. It filters at claim level. Instead of throwing away an entire answer because one sentence is unsupported, it attempts to retain the valid claims.

# 3. Citation coverage is not semantic verification. A matching citation does not prove that the source supports the statement.

# 4. The safety rules are domain-specific. Several checks are specifically designed around Biological Diversity Act Sections 3 and 7, cultivated medicinal plants, forest collection and BMC certificates.

# One implementation detail worth reviewing later: _asserts_fabricated_legal_instrument() uses a mixture of known instrument names, retrieved document names and state-specific patterns. This should be tested with both legitimate and unfamiliar instrument names to avoid false positives.

# 13. What you should remember from this file
# File	Responsibility
# prompt_builder.py	Instructs the LLM and supplies retrieved evidence.
# llm_client.py	Sends the prompt to the LLM.
# answer_postprocessor.py	Checks, filters and formats the generated answer.
# citation_validator.py	Checks citation metadata.
# claim_verifier.py	Checks claim-level citation coverage.
# confidence_scorer.py	Determines confidence and answer decision.

# The most important function in this entire file is postprocess_generated_answer(). All the smaller helpers exist to support its final decision.