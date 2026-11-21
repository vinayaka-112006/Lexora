"""Hybrid LLM-based intent router for IP-SAKTI Sahayak.

Classifies incoming messages into:
- 'general': greetings, small talk, botanical/herbal explanations, ordinary chat
- 'legal': patentability, BDA/NBA/SBB compliance, IP law, regulatory statutory questions
- 'clarification': ambiguous queries needing further user clarification

Uses deterministic shortcuts for lightweight unambiguous cases (empty, exact standalone greetings/gratitude),
and the LLM classifier as the primary decision-maker for all other messages.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

ChatMode = Literal["general", "legal", "clarification"]


@dataclass(frozen=True)
class RouteDecision:
    mode: ChatMode
    reason: str
    is_greeting: bool = False
    is_small_talk: bool = False
    is_follow_up: bool = False
    clarification_question: str | None = None


# Exact standalone greetings and pleasantries (no attached questions)
_STANDALONE_GREETINGS = re.compile(
    r"^\s*(?:"
    r"hello(?:[!\s]+there)?"
    r"|hi(?:[!\s]+there)?"
    r"|hey(?:[!\s]+there)?"
    r"|hiya"
    r"|greetings"
    r"|good\s+(?:morning|afternoon|evening|day|night)"
    r"|howdy"
    r"|namaste"
    r"|what'?s\s+up"
    r"|sup"
    r"|how\s+are\s+you(?:\s+doing)?"
    r"|how\s+is\s+it\s+going"
    r"|how\s+do\s+you\s+do"
    r"|nice\s+to\s+meet\s+you"
    r"|pleased\s+to\s+meet\s+you"
    r")[!.,?\s]*$",
    re.IGNORECASE,
)

# Exact standalone gratitude and social acknowledgments
_STANDALONE_GRATITUDE = re.compile(
    r"^\s*(?:"
    r"thank\s+you(?:\s+(?:very\s+much|so\s+much|a\s+lot))?"
    r"|thanks(?:\s+(?:a\s+lot|so\s+much|very\s+much|a\s+ton))?"
    r"|thx"
    r"|many\s+thanks"
    r"|much\s+appreciated"
    r"|appreciate\s+it"
    r"|cheers"
    r"|ok(?:ay)?(?:\s+thanks|\s+thank\s+you)?"
    r"|got\s+it(?:\s*,?\s*thanks|\s*,?\s*thank\s+you)?"
    r"|understood(?:\s*,?\s*thanks|\s*,?\s*thank\s+you)?"
    r"|bye(?:[!\s]+bye)?"
    r"|goodbye"
    r"|see\s+you(?:\s+later)?"
    r"|have\s+a\s+(?:good|great|nice)\s+day"
    r")[!.,?\s]*$",
    re.IGNORECASE,
)

# Exact assistant identity questions
_ASSISTANT_IDENTITY = re.compile(
    r"^\s*(?:"
    r"who\s+are\s+you"
    r"|what\s+is\s+your\s+name"
    r"|what\s+can\s+you\s+do"
    r"|what\s+are\s+you"
    r"|tell\s+me\s+about\s+yourself"
    r"|help(?:\s+me)?"
    r")[!.,?\s]*$",
    re.IGNORECASE,
)

# Creative writing and general chitchat completely unrelated to law / regulations
_GENERAL_CREATIVE = re.compile(
    r"\b(?:"
    r"birthday\s+(?:message|wish|wishes|greeting|card)|"
    r"tell\s+me\s+a\s+joke|"
    r"write\s+(?:a\s+)?(?:poem|story|song|essay|haiku)|"
    r"recipe|dinner\s+plan|weather\s+today|"
    r"translate\s+this|capital\s+of\s+[A-Za-z]+"
    r")\b",
    re.IGNORECASE,
)

# Strong statutory terms used solely for fallback if LLM classification fails
# Note: words like 'Ashwagandha', 'Ayurveda', 'herbal', 'medicinal plants' are deliberately excluded.
_STRONG_LEGAL_MARKERS = re.compile(
    r"\b(?:"
    r"patent|patents|patented|patenting|patentable|patentability|prior\s+art|novelty|inventive\s+step|"
    r"specification|patent\s+claims?|infringement|compulsory\s+licen[sc]e|revocation|"
    r"trademark|trade\s+mark|copyright|geographical\s+indication|gi\s+tag|design\s+act|ipr|"
    r"biological\s+diversity|biodiversity\s+act|\bbda\b|\bnba\b|\bsbb\b|\bbmc\b|"
    r"biological\s+resources?|legal\s+provisions?|"
    r"national\s+biodiversity\s+authority|state\s+biodiversity\s+board|biodiversity\s+management\s+committee|"
    r"commercial\s+utili[sz]ation|commercial\s+sale|benefit\s+sharing|access\s+and\s+benefit\s+sharing|\babs\b|"
    r"certificate\s+of\s+origin|prior\s+intimation|prior\s+approval|"
    r"cultivat(?:ed|ion)\s+(?:roots?|plants?|medicinal)|private\s+agricultural\s+land|"
    r"forest\s+act|karnataka\s+forest|wild\s+collection|transit\s+pass|"
    r"section\s+\d+|article\s+\d+|rule\s+\d+|regulation\s+\d+|act,?\s+\d{4}|"
    r"statute|statutory|jurisdiction|infringe|litigation|gazette\s+notification|"
    r"drugs?\s+and\s+cosmetics?|schedule\s+t|gmp\s+compliance|gmp\s+requirements?|fssai|cdsco|"
    r"nagoya\s+protocol|\bcbd\b|\btkdl\b|export\s+regulations?|export\s+license"
    r")\b",
    re.IGNORECASE,
)

# Ambiguous permission or approval queries that warrant clarification when lacking context
_AMBIGUOUS_LEGAL_INQUIRY = re.compile(
    r"^\s*(?:"
    r"what\s+approval\s+do\s+i\s+need"
    r"|can\s+i\s+use\s+this"
    r"|can\s+i\s+sell\s+this"
    r"|can\s+i\s+sell\s+it"
    r"|what\s+about\s+registration"
    r"|what\s+about\s+(?:its\s+)?approval"
    r"|what\s+permissions?\s+(?:are\s+)?required"
    r"|how\s+do\s+i\s+register"
    r"|is\s+approval\s+needed"
    r")[?.!\s]*$",
    re.IGNORECASE,
)

_CLASSIFIER_SYSTEM_PROMPT = """You are the intent classifier for IP-SAKTI Sahayak, an AI research assistant for Indian intellectual property, biodiversity regulation, and traditional knowledge.

Your job is to classify the user's current message into exactly one of three routing modes:
1. "general":
   - Greetings, introductions, pleasantries, goodbyes, social chat.
   - General questions about plant biology, botany, botany science, agriculture, history, or culture.
   - General questions about herbs or Ayurvedic plants (e.g. "Tell me about Ashwagandha", "What are some popular medicinal plants in India?", "What are traditional uses of herbs?").
   - Ordinary conversation about the user's project, general science (e.g. "Explain photosynthesis simply"), or creative requests.
   - Any question that does NOT require evidence from statutory laws, legal acts, or regulatory frameworks.

2. "legal":
   - Intellectual property: patents, patentability requirements, patent exclusions (e.g. Section 3(p), Section 3(e)), novelty, inventive step, prior art, claims, infringement, trademarks, GI tags, designs.
   - Biodiversity law: Biological Diversity Act (BDA), National Biodiversity Authority (NBA), State Biodiversity Board (SBB), Biodiversity Management Committee (BMC), access and benefit-sharing (ABS), certificate of origin, prior intimation, commercial utilisation of biological resources.
   - Legal & regulatory compliance: Drugs & Cosmetics Act, Schedule T, GMP compliance, Ayush regulations, FSSAI Ayurveda Aahara regulations, clinical trials, export licensing and requirements.
   - Statutory provisions, sections, rules, legal obligations, or questions requiring evidence from legal documents.

3. "clarification":
   - Genuinely ambiguous messages where legal vs general intent cannot be safely determined from the message and conversation context (e.g. "What approval do I need?", "Can I use this?", "What about registration?").
   - When context is insufficient to know what product, activity, or law the user is asking about, ask a short, polite clarification.

Key Rules:
- The presence of words like "Ayurveda", "Ayurvedic", "herbal", "medicinal plants", "Ashwagandha", or "traditional knowledge" alone does NOT make a query legal. If the user asks about the plant, its properties, or general info, it is "general".
- Only classify as "legal" if the user is asking about legal rights, patentability, statutory permissions, regulatory compliance, commercial legality, or statutory provisions.
- When conversation history exists, use it to understand follow-ups:
  - If the previous topic was legal (e.g. patenting a formula) and the user asks "What about international protection?" or "What permissions are needed?", classify as "legal" with is_follow_up=true.
  - If the previous topic was general and the user asks "What are its traditional uses?", classify as "general" with is_follow_up=true.
  - If the user asks an unrelated new question (e.g. "Explain photosynthesis simply"), classify as "general" with is_follow_up=false.

Return ONLY a valid JSON object with this exact structure:
{
  "mode": "general" | "legal" | "clarification",
  "reason": "Short explanation of the decision",
  "is_greeting": false,
  "is_small_talk": false,
  "is_follow_up": false,
  "clarification_question": "Short question if mode is clarification, else null"
}"""


def _parse_classification_json(raw_text: str) -> dict[str, Any] | None:
    """Extract and parse JSON object from LLM response."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return None


def _validate_decision_dict(data: dict[str, Any]) -> RouteDecision | None:
    """Validate parsed JSON keys and types against supported routing modes."""
    mode_raw = str(data.get("mode", "")).strip().lower()
    if mode_raw not in {"general", "legal", "clarification"}:
        return None
    mode: ChatMode = mode_raw  # type: ignore[assignment]
    reason = str(data.get("reason", "")).strip() or f"llm_classified_{mode}"
    is_greeting = bool(data.get("is_greeting", False))
    is_small_talk = bool(data.get("is_small_talk", False))
    is_follow_up = bool(data.get("is_follow_up", False))
    clarification_question = data.get("clarification_question")
    if clarification_question is not None:
        clarification_question = str(clarification_question).strip() or None
    return RouteDecision(
        mode=mode,
        reason=reason,
        is_greeting=is_greeting,
        is_small_talk=is_small_talk,
        is_follow_up=is_follow_up,
        clarification_question=clarification_question,
    )


def _fallback_routing(query: str, history: list[dict[str, str]] | None = None) -> RouteDecision:
    """Safe fallback when LLM classification is unavailable or unparseable."""
    # Check for legacy embedded context markers
    if re.search(r"\b(?:context\s*:|follow-up\s+request\s*:)", query, re.I):
        if _STRONG_LEGAL_MARKERS.search(query):
            return RouteDecision(mode="legal", reason="fallback_contextual_follow_up", is_follow_up=True)

    # 1. Strong legal markers in current query
    if _STRONG_LEGAL_MARKERS.search(query):
        return RouteDecision(
            mode="legal",
            reason="fallback_strong_legal_detected",
        )

    # 2. Check if previous conversation was about a legal topic
    if history:
        for msg in reversed(history[-4:]):
            content = msg.get("content", "")
            if _STRONG_LEGAL_MARKERS.search(content):
                # If current message is anaphoric / follow-up
                if re.search(r"\b(?:this|that|these|those|it|they|allowed|permitted|permission|apply|exempt|protection|approval|patent)\b", query, re.I):
                    return RouteDecision(
                        mode="legal",
                        reason="fallback_history_legal_continuation",
                        is_follow_up=True,
                    )

    # 3. Ambiguous inquiry without context -> prefer clarification
    if _AMBIGUOUS_LEGAL_INQUIRY.search(query):
        return RouteDecision(
            mode="clarification",
            reason="fallback_ambiguous_inquiry",
            clarification_question=(
                "Could you please clarify whether you are asking about intellectual property / patentability, "
                "regulatory permissions (such as the Biological Diversity Act or Ayush/FSSAI rules), or general information?"
            ),
        )

    # 4. Default safe general route
    return RouteDecision(
        mode="general",
        reason="fallback_default_general",
        is_small_talk=True,
    )


def classify_intent_with_llm(
    query: str,
    history: list[dict[str, str]] | None = None,
    llm_client: Any | None = None,
) -> RouteDecision:
    """Classify user intent using OllamaClient with fallback on failure."""
    history_text = ""
    if history:
        formatted_history = []
        for msg in history[-6:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "").strip()
            if content:
                if len(content) > 300:
                    content = content[:300] + "..."
                formatted_history.append(f"{role}: {content}")
        if formatted_history:
            history_text = "Recent conversation context:\n" + "\n".join(formatted_history) + "\n\n"

    prompt_content = (
        f"{history_text}"
        f"User's current message:\n{query.strip()}\n\n"
        f"Classify the intent of the current message into JSON."
    )

    messages = [
        {"role": "system", "content": _CLASSIFIER_SYSTEM_PROMPT},
        {"role": "user", "content": prompt_content},
    ]

    try:
        if llm_client is None:
            from app.llm_client import OllamaClient
            client = OllamaClient(temperature=0.0, timeout=15.0)
        else:
            client = llm_client

        raw_response = client.generate(messages)
        parsed = _parse_classification_json(raw_response)
        if parsed:
            decision = _validate_decision_dict(parsed)
            if decision:
                return decision
        logger.warning("LLM router returned unparseable response: %r", raw_response[:200] if raw_response else "")
    except Exception as error:
        logger.warning("LLM classification failed (%s), using safe fallback", type(error).__name__)

    return _fallback_routing(query, history)


def route_query(
    query: str,
    history: list[dict[str, str]] | None = None,
    original_question: str = "",
    llm_client: Any | None = None,
) -> RouteDecision:
    """Classify incoming user query using deterministic shortcuts first, then LLM classification."""
    stripped = query.strip()
    if not stripped:
        return RouteDecision(mode="general", reason="empty_query", is_small_talk=True)

    # 1. Deterministic check: standalone gratitude or goodbye
    if _STANDALONE_GRATITUDE.match(stripped):
        return RouteDecision(mode="general", reason="standalone_gratitude", is_small_talk=True)

    # 2. Deterministic check: standalone greetings
    if _STANDALONE_GREETINGS.match(stripped):
        return RouteDecision(mode="general", reason="standalone_greeting", is_greeting=True)

    # 3. Deterministic check: assistant identity questions
    if _ASSISTANT_IDENTITY.match(stripped):
        return RouteDecision(mode="general", reason="assistant_identity", is_small_talk=True)

    # 4. Deterministic check: creative writing / jokes with no legal terms
    if _GENERAL_CREATIVE.search(stripped) and not _STRONG_LEGAL_MARKERS.search(stripped):
        return RouteDecision(mode="general", reason="creative_or_general_chitchat", is_small_talk=True)

    # Build history context from original_question if history was not explicitly provided
    effective_history = history
    if not effective_history and original_question:
        effective_history = [{"role": "user", "content": original_question}]

    # 5. Hybrid LLM classification for all other queries
    return classify_intent_with_llm(stripped, history=effective_history, llm_client=llm_client)
