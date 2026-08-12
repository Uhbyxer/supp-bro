import json
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

# Unit tests cover HW4 guardrails without loading retrieval dependencies.
hybrid = ModuleType("pinecone_hybrid_evaluation")
hybrid.CANDIDATE_K = 15
hybrid.DEFAULT_INDEX = "test"
hybrid.DEFAULT_NAMESPACE = "test"
hybrid.bm25_search = lambda *args: []
hybrid.load_chunks = lambda: []
hybrid.reciprocal_rank_fusion = lambda *args: []
hybrid.select_chunks = lambda chunks, source: chunks
retrieval = ModuleType("pinecone_retrieval_evaluation")
retrieval.EMBEDDING_MODEL = "test"
retrieval.required_env = lambda name: "test"
retrieval.search = lambda *args: []
sys.modules[hybrid.__name__] = hybrid
sys.modules[retrieval.__name__] = retrieval

from rag_answer import (  # noqa: E402
    FALLBACK,
    GenerationResult,
    RetrievedChunk,
    build_output,
    build_prompt,
    generate,
    markdown_table,
    run_experiments,
    validate_payload,
    weak_context_reason,
)


def chunk(score=0.8, chunk_id="pages:test:one"):
    return RetrievedChunk(chunk_id, "Supported fact.", "data/test.md", 0.03, score)


class FakeClient:
    def __init__(self, payloads):
        self.responses = self
        self.payloads = payloads if isinstance(payloads, list) else [payloads]
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads.pop(0)
        return SimpleNamespace(output_text=json.dumps(payload))


class GroundingTests(unittest.TestCase):
    def test_prompt_flavors(self):
        strong = build_prompt("Question?", [chunk()], "strong")
        weak = build_prompt("Question?", [chunk()], "weak")
        self.assertIn("ONLY the context", strong)
        self.assertIn("Answer the user's question directly and helpfully.", weak)
        self.assertIn("Add citations from the retrieved CHUNK_ID values when possible.", weak)
        self.assertNotIn("partially relevant", weak)

    def test_retrieval_reasons(self):
        self.assertEqual("empty_retrieval", weak_context_reason([], .3))
        self.assertEqual("weak_retrieval", weak_context_reason([chunk(.2)], .3))
        self.assertIsNone(weak_context_reason([chunk(.2)], 0.0))
        self.assertIsNone(weak_context_reason([chunk()], .3))

    def test_valid_structured_answer(self):
        result = validate_payload({"has_enough_context": True, "answer": "Fact.", "citations": ["pages:test:one"]}, [chunk()])
        self.assertEqual("grounded_answer", result.status)
        self.assertEqual(["pages:test:one"], result.citations)

    def test_invalid_and_missing_citations_are_model_fallbacks(self):
        for citations in ([], ["fake:id"]):
            result = validate_payload({"has_enough_context": True, "answer": "Fact.", "citations": citations}, [chunk()])
            self.assertEqual("model_fallback", result.status)
            self.assertEqual("invalid_or_missing_citation", result.fallback_reason)

    def test_llm_fallback_is_distinct_from_filter_fallback(self):
        result = validate_payload({"has_enough_context": False, "answer": FALLBACK, "citations": []}, [chunk()])
        self.assertEqual("model_fallback", result.status)
        self.assertEqual("llm_reports_insufficient_context", result.fallback_reason)
        filtered = generate("Question?", [chunk(.2)], FakeClient({}), "gpt-4o-mini", .3, "strong")
        self.assertEqual("retrieval_filter_fallback", filtered.status)
        self.assertEqual("weak_retrieval", filtered.fallback_reason)

    def test_output_contains_context_text_without_duplicate_sources(self):
        chunks = [chunk(.8)]
        result = GenerationResult("grounded_answer", "Fact.", ["pages:test:one"])
        output = build_output("Question?", chunks, result, .3, "strong")
        self.assertEqual(.3, output["min_vector_score"])
        self.assertEqual("strong", output["prompt_flavor"])
        self.assertEqual(.8, output["best_vector_score"])
        self.assertEqual("Supported fact.", output["retrieved_context_by_id"]["pages:test:one"]["text"])
        self.assertEqual(["pages:test:one"], output["citations"])
        self.assertNotIn("sources", output)
        self.assertNotIn("retrieved_chunks", output)

    def test_experiment_matrix_and_markdown(self):
        exact_id = "pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector"
        payload = {"has_enough_context": True, "answer": "Debezium uses Kafka Connect exactly-once support.", "citations": [exact_id]}
        client = FakeClient([payload, payload, payload, payload])
        output = run_experiments("How does exactly-once work?", [chunk(.78, exact_id)], client, "gpt-4o-mini")
        self.assertEqual(4, len(output["experiments"]))
        self.assertIn("| Experiment | Prompt |", output["summary_markdown"])
        self.assertIn("weak_prompt_no_filter", output["summary_markdown"])

    def test_markdown_table_marks_filter_vs_model_fallback(self):
        table = markdown_table([
            {
                "experiment": "weak_prompt_with_filter",
                "prompt_flavor": "weak",
                "min_vector_score": .3,
                "best_vector_score": .1,
                "status": "retrieval_filter_fallback",
                "fallback_reason": "weak_retrieval",
                "citations": [],
            },
            {
                "experiment": "strong_prompt_no_filter",
                "prompt_flavor": "strong",
                "min_vector_score": 0.0,
                "best_vector_score": .1,
                "status": "model_fallback",
                "fallback_reason": "llm_reports_insufficient_context",
                "citations": [],
            },
        ])
        self.assertIn("Blocked before LLM", table)
        self.assertIn("LLM or citation validator", table)


if __name__ == "__main__":
    unittest.main()
