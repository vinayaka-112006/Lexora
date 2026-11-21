"""Integration and contract tests for query_endpoint with hybrid routing and history."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.api import QueryRequest, QueryResponse, query_endpoint
from app.router import RouteDecision


class ApiRoutingDirectTests(unittest.TestCase):
    def test_general_greeting_returns_general_mode_without_retrieval(self) -> None:
        req = QueryRequest(query="Hello there!")
        res = query_endpoint(req)
        self.assertIsInstance(res, QueryResponse)
        self.assertEqual(res.mode, "general")
        self.assertEqual(res.decision, "general")
        self.assertEqual(res.retrieved_evidence, [])
        self.assertEqual(res.sources, [])
        self.assertEqual(res.confidence, 1.0)
        self.assertTrue(len(res.answer) > 0)

    @patch("app.api.route_query")
    def test_clarification_mode_returns_question_without_retrieval(self, mock_route: MagicMock) -> None:
        mock_route.return_value = RouteDecision(
            mode="clarification",
            reason="Ambiguous approval query",
            clarification_question="Are you asking about patent grant or biodiversity permission?",
        )
        req = QueryRequest(query="What approval do I need?")
        res = query_endpoint(req)
        self.assertEqual(res.mode, "clarification")
        self.assertEqual(res.decision, "clarification")
        self.assertEqual(res.answer, "Are you asking about patent grant or biodiversity permission?")
        self.assertEqual(res.retrieved_evidence, [])
        self.assertEqual(res.sources, [])
        self.assertEqual(res.confidence, 1.0)

    @patch("app.api.route_query")
    def test_query_with_history_passes_history_to_router(self, mock_route: MagicMock) -> None:
        mock_route.return_value = RouteDecision(
            mode="general",
            reason="small_talk",
            is_small_talk=True,
        )
        history = [
            {"role": "user", "content": "Can I patent an Ashwagandha formulation?"},
            {"role": "assistant", "content": "Under Section 3(p), traditional knowledge formulations are excluded."},
        ]
        req = QueryRequest(
            query="Thank you so much!",
            history=history,
        )
        res = query_endpoint(req)
        self.assertEqual(res.mode, "general")
        mock_route.assert_called_once()
        call_kwargs = mock_route.call_args.kwargs
        call_history = call_kwargs.get("history")
        self.assertIsNotNone(call_history)
        self.assertEqual(len(call_history), 2)
        self.assertEqual(call_history[0]["content"], "Can I patent an Ashwagandha formulation?")

    def test_empty_query_rejected_by_pydantic_validator(self) -> None:
        with self.assertRaises(ValueError):
            QueryRequest(query="   ")

    def test_history_with_content_or_text_keys_parsed_correctly(self) -> None:
        req = QueryRequest(
            query="Who are you?",
            history=[
                {"role": "user", "text": "Hello there", "extra": "ignored"},
                {"role": "assistant", "content": "I am IP-SAKTI Sahayak."},
            ],
        )
        res = query_endpoint(req)
        self.assertEqual(res.mode, "general")
        self.assertIn("IP-SAKTI Sahayak", res.answer)

    @patch("app.api.route_query")
    def test_contextual_follow_up_enriches_retrieval_query(self, mock_route: MagicMock) -> None:
        mock_route.return_value = RouteDecision(
            mode="legal",
            reason="contextual_follow_up",
            is_follow_up=True,
        )
        with patch("app.api._get_shared_retriever") as mock_get_retriever:
            mock_retriever = MagicMock()
            mock_retriever.retrieve.return_value = []
            mock_get_retriever.return_value = mock_retriever

            req = QueryRequest(
                query="What about international protection?",
                history=[
                    {"role": "user", "content": "Can I patent an Ashwagandha formulation?"},
                    {"role": "assistant", "content": "Under Section 3(p), traditional knowledge formulations are excluded."},
                ],
            )
            res = query_endpoint(req)
            self.assertEqual(res.mode, "legal")
            # Verify retriever was called with enriched context
            mock_retriever.retrieve.assert_called_once()
            retrieved_q = mock_retriever.retrieve.call_args.args[0]
            self.assertIn("Context: original question: Can I patent an Ashwagandha formulation?", retrieved_q)


if __name__ == "__main__":
    unittest.main()
