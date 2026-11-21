"""Unit and integration tests for Hybrid LLM-Based Intent Routing in IP-SAKTI Sahayak."""
from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from app.router import (
    RouteDecision,
    _fallback_routing,
    _parse_classification_json,
    _validate_decision_dict,
    classify_intent_with_llm,
    route_query,
)


class MockLLMClient:
    """Mock LLM client returning configurable text responses or raising errors."""

    def __init__(self, response_text: str = "", exception_to_raise: Exception | None = None) -> None:
        self.response_text = response_text
        self.exception_to_raise = exception_to_raise
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if self.exception_to_raise is not None:
            raise self.exception_to_raise
        return self.response_text


class TestGroupAGeneralConversation(unittest.TestCase):
    """Test group A: General conversation must route to 'general' mode."""

    def test_exact_standalone_greetings(self) -> None:
        greetings = [
            "hello", "Hello", "HELLO", "hello!", "hello there",
            "hi", "Hi!", "hi there", "hey", "Hey!",
            "good morning", "Good afternoon", "Good evening",
            "how are you?", "how are you doing?", "how is it going",
            "namaste", "what's up",
        ]
        for greeting in greetings:
            decision = route_query(greeting)
            self.assertEqual(
                decision.mode, "general",
                f"Expected '{greeting}' to route to general mode, got {decision.mode}",
            )
            self.assertTrue(decision.is_greeting or decision.is_small_talk)

    def test_standalone_gratitude_and_goodbye(self) -> None:
        gratitude_queries = [
            "thank you", "Thanks!", "thank you very much", "thanks a lot",
            "thx", "cheers", "ok thanks", "got it, thank you",
            "bye", "goodbye", "see you later", "have a nice day",
        ]
        for query in gratitude_queries:
            decision = route_query(query)
            self.assertEqual(
                decision.mode, "general",
                f"Expected '{query}' to route to general mode, got {decision.mode}",
            )
            self.assertTrue(decision.is_small_talk)

    def test_user_motivating_query_vinayak(self) -> None:
        """The user's key problem query MUST route to general mode, NOT legal RAG."""
        query = "Hello, I am Vinayak. I want some information about Ayurvedic plants and herbs. Can I ask you?"
        # 1. With mock LLM classifier returning general intent
        mock_client = MockLLMClient(response_text=json.dumps({
            "mode": "general",
            "reason": "User is introducing themselves and asking for general information about herbs.",
            "is_greeting": True,
            "is_small_talk": True,
            "is_follow_up": False,
        }))
        decision = route_query(query, llm_client=mock_client)
        self.assertEqual(decision.mode, "general")
        self.assertTrue(decision.is_greeting)

        # 2. With fallback routing (when LLM is offline)
        fallback_decision = route_query(query, llm_client=MockLLMClient(exception_to_raise=RuntimeError("timeout")))
        self.assertEqual(fallback_decision.mode, "general")

    def test_conversational_and_botanical_queries(self) -> None:
        general_queries = [
            ("Hi, I am Vinayak", True),
            ("Can I ask you something?", False),
            ("Tell me about Ashwagandha", False),
            ("What are some popular medicinal plants in India?", False),
            ("Explain photosynthesis simply", False),
            ("Tell me about yourself", True),
            ("Who are you", True),
            ("write a short poem about nature", False),
            ("tell me a joke", False),
        ]
        for query, is_intro in general_queries:
            mock_client = MockLLMClient(response_text=json.dumps({
                "mode": "general",
                "reason": f"General inquiry: {query}",
                "is_greeting": is_intro,
                "is_small_talk": True,
                "is_follow_up": False,
            }))
            decision = route_query(query, llm_client=mock_client)
            self.assertEqual(
                decision.mode, "general",
                f"Expected general query '{query}' to route to general mode, got {decision.mode}",
            )


class TestGroupBLegalQuestions(unittest.TestCase):
    """Test group B: Specific legal, IP, BDA, and regulatory questions must route to 'legal'."""

    def test_explicit_legal_queries(self) -> None:
        legal_queries = [
            "Can I patent an Ashwagandha formulation?",
            "What permissions are required under the Biological Diversity Act?",
            "Explain patentability requirements in India",
            "Can I export an Ayurvedic medicine to Germany?",
            "What are the applicable GMP requirements?",
            "Which legal provisions govern access to biological resources?",
            "What is Section 3(p) of the Patents Act, 1970?",
            "Do I need a certificate of origin from the BMC?",
            "How does prior intimation to the State Biodiversity Board work?",
            "What permissions are needed from the National Biodiversity Authority?",
        ]
        for query in legal_queries:
            mock_client = MockLLMClient(response_text=json.dumps({
                "mode": "legal",
                "reason": f"Legal question regarding IP or regulation: {query}",
                "is_greeting": False,
                "is_small_talk": False,
                "is_follow_up": False,
            }))
            decision = route_query(query, llm_client=mock_client)
            self.assertEqual(
                decision.mode, "legal",
                f"Expected legal query '{query}' to route to legal mode, got {decision.mode}",
            )

    def test_legal_queries_fallback_behavior(self) -> None:
        """When LLM is unavailable, strong legal statutory markers must reliably route to legal."""
        offline_client = MockLLMClient(exception_to_raise=RuntimeError("connection refused"))
        statutory_queries = [
            "Can I patent an Ashwagandha formulation?",
            "What permissions are required under the Biological Diversity Act?",
            "Explain patentability requirements in India",
            "What are the applicable GMP requirements?",
            "Which legal provisions govern access to biological resources?",
            "Do I need a certificate of origin from the BMC?",
        ]
        for query in statutory_queries:
            decision = route_query(query, llm_client=offline_client)
            self.assertEqual(
                decision.mode, "legal",
                f"Expected offline fallback for '{query}' to route to legal mode, got {decision.mode}",
            )


class TestGroupCContextualFollowUps(unittest.TestCase):
    """Test group C: Contextual follow-up questions with conversation history."""

    def test_legal_follow_up_international_protection(self) -> None:
        history = [
            {"role": "user", "content": "Can I patent an Ashwagandha formulation?"},
            {"role": "assistant", "content": "Under Section 3(p) of the Patents Act, traditional knowledge formulations are not patentable..."},
        ]
        query = "What about international protection?"
        mock_client = MockLLMClient(response_text=json.dumps({
            "mode": "legal",
            "reason": "Follow-up question regarding international patent protection for the previously mentioned formulation.",
            "is_greeting": False,
            "is_small_talk": False,
            "is_follow_up": True,
        }))
        decision = route_query(query, history=history, llm_client=mock_client)
        self.assertEqual(decision.mode, "legal")
        self.assertTrue(decision.is_follow_up)

        # Verify history was forwarded into classifier prompt
        self.assertTrue(any("Can I patent an Ashwagandha formulation?" in str(call) for call in mock_client.calls))

    def test_general_follow_up_traditional_uses(self) -> None:
        history = [
            {"role": "user", "content": "Tell me about Ashwagandha"},
            {"role": "assistant", "content": "Ashwagandha (Withania somnifera) is an ancient medicinal herb commonly used in Ayurveda..."},
        ]
        query = "What are its traditional uses?"
        mock_client = MockLLMClient(response_text=json.dumps({
            "mode": "general",
            "reason": "General botanical and traditional knowledge question continuing general conversation.",
            "is_greeting": False,
            "is_small_talk": True,
            "is_follow_up": True,
        }))
        decision = route_query(query, history=history, llm_client=mock_client)
        self.assertEqual(decision.mode, "general")
        self.assertTrue(decision.is_follow_up)

    def test_unrelated_new_question_after_legal_discussion(self) -> None:
        """A new unrelated question must NOT be contaminated by earlier legal context."""
        history = [
            {"role": "user", "content": "Can I patent an Ashwagandha formulation?"},
            {"role": "assistant", "content": "Patents Act Section 3(p) excludes traditional knowledge..."},
        ]
        query = "Explain photosynthesis simply"
        mock_client = MockLLMClient(response_text=json.dumps({
            "mode": "general",
            "reason": "User asked an unrelated general biology question.",
            "is_greeting": False,
            "is_small_talk": False,
            "is_follow_up": False,
        }))
        decision = route_query(query, history=history, llm_client=mock_client)
        self.assertEqual(decision.mode, "general")
        self.assertFalse(decision.is_follow_up)

    def test_gratitude_after_legal_discussion_routes_to_general(self) -> None:
        history = [
            {"role": "user", "content": "Can I patent an Ashwagandha formulation?"},
            {"role": "assistant", "content": "Patents Act Section 3(p) excludes traditional knowledge..."},
        ]
        query = "thank you so much!"
        decision = route_query(query, history=history)
        self.assertEqual(decision.mode, "general")
        self.assertTrue(decision.is_small_talk)

    def test_fallback_follow_up_preserves_legal_context(self) -> None:
        history = [
            {"role": "user", "content": "Can I patent an Ashwagandha formulation?"},
            {"role": "assistant", "content": "Patents Act Section 3 excludes traditional knowledge..."},
        ]
        offline_client = MockLLMClient(exception_to_raise=RuntimeError("offline"))
        decision = route_query("is that allowed?", history=history, llm_client=offline_client)
        self.assertEqual(decision.mode, "legal")
        self.assertTrue(decision.is_follow_up)


class TestGroupDAmbiguousMessages(unittest.TestCase):
    """Test group D: Genuinely ambiguous messages where clarification is needed."""

    def test_ambiguous_inquiries_without_context(self) -> None:
        ambiguous_queries = [
            "What approval do I need?",
            "Can I use this?",
            "What about registration?",
        ]
        for query in ambiguous_queries:
            mock_client = MockLLMClient(response_text=json.dumps({
                "mode": "clarification",
                "reason": "The user did not specify what type of approval or activity they are asking about.",
                "is_greeting": False,
                "is_small_talk": False,
                "is_follow_up": False,
                "clarification_question": "Are you asking about patent grant, biodiversity access, or product marketing approval?",
            }))
            decision = route_query(query, llm_client=mock_client)
            self.assertEqual(decision.mode, "clarification")
            self.assertIsNotNone(decision.clarification_question)

    def test_ambiguous_inquiries_offline_fallback_routes_to_clarification(self) -> None:
        offline_client = MockLLMClient(exception_to_raise=RuntimeError("offline"))
        decision = route_query("What approval do I need?", llm_client=offline_client)
        self.assertEqual(decision.mode, "clarification")
        self.assertIsNotNone(decision.clarification_question)


class TestGroupEFailureHandling(unittest.TestCase):
    """Test group E: Malformed classifier outputs, unexpected responses, and errors."""

    def test_invalid_json_falls_back_safely(self) -> None:
        # 1. Invalid JSON for query with legal terms -> falls back to legal
        garbage_client = MockLLMClient(response_text="Not valid JSON at all! Just raw text.")
        decision = route_query("Can I patent an Ashwagandha formulation?", llm_client=garbage_client)
        self.assertEqual(decision.mode, "legal")

        # 2. Invalid JSON for non-legal query -> falls back to general
        decision_gen = route_query("Explain photosynthesis simply", llm_client=garbage_client)
        self.assertEqual(decision_gen.mode, "general")

    def test_unexpected_routing_mode_falls_back_safely(self) -> None:
        weird_client = MockLLMClient(response_text=json.dumps({
            "mode": "unknown_hyper_quantum_mode",
            "reason": "Invalid mode string",
        }))
        decision = route_query("What are the rules under the Patents Act?", llm_client=weird_client)
        self.assertEqual(decision.mode, "legal")

    def test_empty_classifier_response_handled_safely(self) -> None:
        empty_client = MockLLMClient(response_text="")
        decision = route_query("Explain Section 3 of Patents Act", llm_client=empty_client)
        self.assertEqual(decision.mode, "legal")

    def test_empty_user_query_handled_deterministically(self) -> None:
        decision = route_query("   ")
        self.assertEqual(decision.mode, "general")
        self.assertEqual(decision.reason, "empty_query")

    def test_markdown_code_fenced_json_parsed_correctly(self) -> None:
        fenced_client = MockLLMClient(response_text="""```json
{
  "mode": "legal",
  "reason": "User asks about patent exclusions.",
  "is_greeting": false,
  "is_small_talk": false,
  "is_follow_up": false
}
```""")
        decision = route_query("Can I patent this herbal product?", llm_client=fenced_client)
        self.assertEqual(decision.mode, "legal")
        self.assertEqual(decision.reason, "User asks about patent exclusions.")

    def test_malformed_conversation_history_does_not_crash(self) -> None:
        # History items missing keys or with None values
        bad_history: list[dict[str, Any]] = [
            {"not_role": 123},
            {"role": "user"},
            {"content": None},
        ]
        decision = route_query("hello", history=bad_history)
        self.assertEqual(decision.mode, "general")


if __name__ == "__main__":
    unittest.main()
