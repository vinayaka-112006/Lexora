"""Focused preflight tests for Stage 6L configuration and checkpoint safety."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.llm_client import OllamaClient  # noqa: E402
from evaluate_end_to_end import (  # noqa: E402
    STAGE_6D_BASELINE,
    _classifier_record,
    _abstention_metrics,
    _llm_configuration_lines,
    _load_project_env,
    _reusable_checkpoint_records,
)
from app.retriever import analyze_legal_query  # noqa: E402


class Stage6LPreflightTests(unittest.TestCase):
    @staticmethod
    def _abstention_case(should_abstain: bool, decision: str, actual_abstained: bool | None,
                         generated_answer: str | None, *, generation_error: str | None = None) -> tuple[dict, dict]:
        item = {"id": "q1", "should_abstain": should_abstain}
        record = {
            "id": "q1", "decision": decision, "actual_abstained": actual_abstained,
            "generated_answer": generated_answer,
        }
        if generation_error:
            record["generation_error"] = generation_error
        return item, record

    def test_successful_expected_abstention_is_correct(self) -> None:
        item, record = self._abstention_case(True, "abstain", True, "I cannot answer.")
        metrics = _abstention_metrics([item], [record])
        self.assertEqual(metrics["evaluated_expected_abstention_cases"], 1)
        self.assertEqual(metrics["unevaluated_expected_abstention_cases"], 0)
        self.assertEqual(metrics["actual_abstentions"], 1)
        self.assertEqual(metrics["correct_abstentions"], 1)
        self.assertEqual(metrics["incorrect_answers_on_abstention_cases"], 0)

    def test_successful_non_abstention_on_expected_case_is_incorrect(self) -> None:
        item, record = self._abstention_case(True, "answer", False, "Here is an answer.")
        metrics = _abstention_metrics([item], [record])
        self.assertEqual(metrics["evaluated_expected_abstention_cases"], 1)
        self.assertEqual(metrics["actual_abstentions"], 0)
        self.assertEqual(metrics["correct_abstentions"], 0)
        self.assertEqual(metrics["incorrect_answers_on_abstention_cases"], 1)

    def test_generation_error_on_expected_case_is_unevaluated(self) -> None:
        item, record = self._abstention_case(
            True, "generation_error", None, None, generation_error="provider failed",
        )
        metrics = _abstention_metrics([item], [record])
        self.assertEqual(metrics["unevaluated_expected_abstention_cases"], 1)
        self.assertEqual(metrics["unevaluated_expected_abstention_ids"], ["q1"])
        self.assertEqual(metrics["actual_abstentions"], 0)
        self.assertEqual(metrics["correct_abstentions"], 0)
        self.assertEqual(metrics["incorrect_answers_on_abstention_cases"], 0)

    def test_generation_error_on_answerable_query_is_not_false_abstention(self) -> None:
        item, record = self._abstention_case(
            False, "generation_error", None, None, generation_error="provider failed",
        )
        metrics = _abstention_metrics([item], [record])
        self.assertEqual(metrics["generation_error_queries"], 1)
        self.assertEqual(metrics["false_abstentions_on_answerable_queries"], 0)
        self.assertEqual(metrics["incorrect_answers_on_abstention_cases"], 0)
        self.assertEqual(metrics["actual_abstentions"], 0)

    def test_generation_error_totals_and_ids_are_separate(self) -> None:
        items = [
            {"id": "q1", "should_abstain": True},
            {"id": "q2", "should_abstain": False},
            {"id": "q3", "should_abstain": False},
        ]
        records = [
            {"id": "q1", "decision": "generation_error", "actual_abstained": None,
             "generated_answer": None, "generation_error": "provider failed"},
            {"id": "q2", "decision": "generation_error", "actual_abstained": None,
             "generated_answer": None},
            {"id": "q3", "decision": "answer", "actual_abstained": False,
             "generated_answer": "answer"},
        ]
        metrics = _abstention_metrics(items, records)
        self.assertEqual(metrics["total_queries"], 3)
        self.assertEqual(metrics["successful_generation_queries"], 1)
        self.assertEqual(metrics["generation_error_queries"], 2)
        self.assertEqual(metrics["generation_error_ids"], ["q1", "q2"])
        self.assertEqual(metrics["expected_abstention_cases"], 1)
        self.assertEqual(metrics["expected_abstention_ids"], ["q1"])
        self.assertEqual(metrics["evaluated_expected_abstention_cases"], 0)
        self.assertEqual(metrics["unevaluated_expected_abstention_cases"], 1)

    def test_project_dotenv_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "LLM_PROVIDER=gemini\nGEMINI_API_KEY=unit-test-key\nGEMINI_MODEL=gemini-3.5-flash\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                self.assertTrue(_load_project_env(env_path))
                self.assertEqual(os.environ["LLM_PROVIDER"], "gemini")
                self.assertEqual(os.environ["GEMINI_API_KEY"], "unit-test-key")
                self.assertEqual(os.environ["GEMINI_MODEL"], "gemini-3.5-flash")

    def test_gemini_provider_and_model_are_detected_without_api_call(self) -> None:
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "unit-test-key",
            "GEMINI_MODEL": "gemini-3.5-flash",
        }, clear=True):
            client = OllamaClient()
        self.assertEqual(client.provider, "gemini")
        self.assertEqual(client.model, "gemini-3.5-flash")

    def test_checkpoint_without_provider_model_is_stale(self) -> None:
        dataset = "rag-service/tests/eval_set.json"
        stale = {
            "dataset": dataset,
            "morphology_enabled": False,
            "llm_provider": "gemini",
            "llm_model": "gemini-3.5-flash",
            "items": [{"id": "q1", "generated_answer": "old answer"}],
        }
        self.assertEqual(
            _reusable_checkpoint_records(stale, dataset, False, "gemini", "gemini-3.5-flash"),
            {},
        )

    def test_matching_checkpoint_record_can_resume(self) -> None:
        dataset = "rag-service/tests/eval_set.json"
        record = {
            "id": "q1", "dataset": dataset, "morphology_enabled": False,
            "llm_provider": "gemini", "llm_model": "gemini-3.5-flash",
            "generated_answer": "answer",
        }
        checkpoint = {
            "dataset": dataset, "morphology_enabled": False,
            "llm_provider": "gemini", "llm_model": "gemini-3.5-flash",
            "items": [record],
        }
        self.assertEqual(
            _reusable_checkpoint_records(checkpoint, dataset, False, "gemini", "gemini-3.5-flash"),
            {"q1": record},
        )

    def test_report_uses_runtime_provider_and_model(self) -> None:
        lines = _llm_configuration_lines("gemini", "gemini-3.5-flash")
        self.assertEqual(lines, ["- LLM provider: `gemini`; model: `gemini-3.5-flash`; temperature 0.1."])

    def test_intent_analysis_is_reported_as_deterministic_classifier(self) -> None:
        analysis = analyze_legal_query("What is a trademark?")
        self.assertEqual(_classifier_record(analysis), {
            "available": True,
            "type": "deterministic_query_intent",
            "is_ml_classifier": False,
            "intent": "definition",
        })

    def test_stage_6d_retrieval_baseline_is_unchanged(self) -> None:
        self.assertEqual(STAGE_6D_BASELINE, {
            "recall@1": 0.3857,
            "recall@3": 0.5952,
            "recall@5": 0.7381,
            "recall@10": 0.8810,
            "mrr": 0.5711,
        })


if __name__ == "__main__":
    unittest.main()
