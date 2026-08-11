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

from rag_answer import (FALLBACK, RetrievedChunk, build_prompt, generate,
                        validate_payload, weak_context_reason)


def chunk(score=0.8, chunk_id="pages:test:one"):
    return RetrievedChunk(chunk_id, "Supported fact.", "data/test.md", 0.03, score)


class FakeClient:
    def __init__(self, payload):
        self.responses = self
        self.payload = payload

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=json.dumps(self.payload))


class GroundingTests(unittest.TestCase):
    def test_prompt(self):
        prompt = build_prompt("Question?", [chunk()])
        self.assertIn("pages:test:one", prompt)
        self.assertIn("Question?", prompt)

    def test_retrieval_reasons(self):
        self.assertEqual("empty_retrieval", weak_context_reason([], .3))
        self.assertEqual("weak_retrieval", weak_context_reason([chunk(.2)], .3))
        self.assertIsNone(weak_context_reason([chunk()], .3))

    def test_valid_structured_answer(self):
        result = validate_payload({"has_enough_context": True, "answer": "Fact.", "citations": ["pages:test:one"]}, [chunk()])
        self.assertEqual("grounded_answer", result.status)
        self.assertEqual(["pages:test:one"], result.citations)

    def test_invalid_and_missing_citations(self):
        for citations in ([], ["fake:id"]):
            result = validate_payload({"has_enough_context": True, "answer": "Fact.", "citations": citations}, [chunk()])
            self.assertEqual("invalid_or_missing_citation", result.fallback_reason)

    def test_llm_fallback(self):
        result = validate_payload({"has_enough_context": False, "answer": FALLBACK, "citations": []}, [chunk()])
        self.assertEqual("llm_reports_insufficient_context", result.fallback_reason)

    def test_exactly_once_scenario(self):
        exact_id = "pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector"
        client = FakeClient({"has_enough_context": True, "answer": "Debezium uses Kafka Connect exactly-once support.", "citations": [exact_id]})
        result = generate("How does exactly-once work?", [chunk(.78, exact_id)], client, "gpt-4o-mini", .3)
        self.assertEqual("grounded_answer", result.status)
        self.assertEqual([exact_id], result.citations)
        self.assertEqual("json_schema", client.kwargs["text"]["format"]["type"])


if __name__ == "__main__":
    unittest.main()
