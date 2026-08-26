import json
import unittest
from types import SimpleNamespace

from supp_bro.domain.contracts import RagObservation
from supp_bro.retrieval.rag import (
    FALLBACK,
    GenerationResult,
    RetrievedChunk,
    accept_payload_without_post_validation,
    build_output,
    build_prompt,
    generate,
    markdown_table,
    prompt_template,
    run_experiments,
    to_rag_observation,
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
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return SimpleNamespace(output_text=text)


class RetrievalRagTests(unittest.TestCase):
    def test_prompt_flavors_preserve_hw4_text(self):
        with open("scripts/hw4/prompt_template.txt", encoding="utf-8") as file:
            expected_strong = file.read()
        with open("scripts/hw4/prompt_template_weak.txt", encoding="utf-8") as file:
            expected_weak = file.read()
        self.assertEqual(expected_strong, prompt_template("strong"))
        self.assertEqual(expected_weak, prompt_template("weak"))
        strong = build_prompt("Question?", [chunk()], "strong")
        weak = build_prompt("Question?", [chunk()], "weak")
        self.assertIn("ONLY the context", strong)
        self.assertIn("Answer the user's question directly and helpfully.", weak)
        self.assertIn("Add citations from the retrieved CHUNK_ID values when possible.", weak)
        self.assertNotIn("partially relevant", weak)

    def test_empty_and_weak_retrieval_skip_client_call(self):
        client = FakeClient({"answer": "unused"})
        empty = generate("Question?", [], client, "gpt-4o-mini", 0.3, "strong", "on")
        weak = generate("Question?", [chunk(0.2)], client, "gpt-4o-mini", 0.3, "strong", "on")
        missing_scores = generate("Question?", [chunk(None)], client, "gpt-4o-mini", 0.3, "strong", "on")
        self.assertEqual("retrieval_filter_fallback", empty.status)
        self.assertEqual("empty_retrieval", empty.fallback_reason)
        self.assertEqual("retrieval_filter_fallback", weak.status)
        self.assertEqual("weak_retrieval", weak.fallback_reason)
        self.assertEqual("weak_retrieval", missing_scores.fallback_reason)
        self.assertEqual([], client.calls)

    def test_zero_threshold_disables_vector_score_gate(self):
        payload = {"has_enough_context": True, "answer": "Fact.", "citations": ["pages:test:one"]}
        client = FakeClient(payload)
        result = generate("Question?", [chunk(0.1)], client, "gpt-4o-mini", 0.0, "strong", "on")
        self.assertEqual("grounded_answer", result.status)
        self.assertEqual(1, len(client.calls))
        self.assertIsNone(weak_context_reason([chunk(0.1)], 0.0))

    def test_valid_structured_answer_deduplicates_citations(self):
        result = validate_payload(
            {"has_enough_context": True, "answer": "Fact.", "citations": ["pages:test:one", "pages:test:one"]},
            [chunk()],
        )
        self.assertEqual("grounded_answer", result.status)
        self.assertEqual("Fact.", result.answer)
        self.assertEqual(["pages:test:one"], result.citations)

    def test_invalid_payloads_fall_back(self):
        cases = [
            ("llm_reports_insufficient_context", {"has_enough_context": False, "answer": FALLBACK, "citations": []}),
            ("invalid_or_missing_citation", {"has_enough_context": True, "answer": "Fact.", "citations": []}),
            ("invalid_or_missing_citation", {"has_enough_context": True, "answer": "Fact.", "citations": ["fake:id"]}),
            ("invalid_llm_response", {"has_enough_context": True, "answer": "", "citations": ["pages:test:one"]}),
            ("invalid_llm_response", {"has_enough_context": True, "answer": FALLBACK, "citations": ["pages:test:one"]}),
        ]
        for reason, payload in cases:
            with self.subTest(reason=reason, payload=payload):
                result = validate_payload(payload, [chunk()])
                self.assertEqual("model_fallback", result.status)
                self.assertEqual(reason, result.fallback_reason)

    def test_bad_json_missing_keys_and_malformed_types_do_not_escape(self):
        bad_json = generate("Question?", [chunk()], FakeClient("{bad json"), "gpt-4o-mini", 0.0, "strong", "on")
        missing_keys = generate("Question?", [chunk()], FakeClient({"answer": "Fact."}), "gpt-4o-mini", 0.0, "strong", "on")
        string_citations = generate("Question?", [chunk()], FakeClient({"has_enough_context": True, "answer": "Fact.", "citations": "pages:test:one"}), "gpt-4o-mini", 0.0, "strong", "on")
        numeric_answer = generate("Question?", [chunk()], FakeClient({"has_enough_context": True, "answer": 123, "citations": ["pages:test:one"]}), "gpt-4o-mini", 0.0, "strong", "on")
        string_context_flag = generate("Question?", [chunk()], FakeClient({"has_enough_context": "yes", "answer": "Fact.", "citations": ["pages:test:one"]}), "gpt-4o-mini", 0.0, "strong", "on")
        self.assertEqual("invalid_llm_response", bad_json.fallback_reason)
        self.assertEqual("invalid_llm_response", missing_keys.fallback_reason)
        self.assertEqual("invalid_llm_response", string_citations.fallback_reason)
        self.assertEqual("invalid_llm_response", numeric_answer.fallback_reason)
        self.assertEqual("invalid_llm_response", string_context_flag.fallback_reason)

    def test_invalid_generation_configuration_raises(self):
        payload = {"has_enough_context": True, "answer": "Fact.", "citations": ["pages:test:one"]}
        with self.assertRaises(ValueError):
            generate("Question?", [chunk()], FakeClient(payload), "gpt-4o-mini", 0.0, "missing", "on")
        with self.assertRaises(ValueError):
            generate("Question?", [chunk()], FakeClient(payload), "gpt-4o-mini", 0.0, "strong", "bad")

    def test_post_validator_can_be_disabled(self):
        payload = {"has_enough_context": True, "answer": "Free answer.", "citations": []}
        strict = validate_payload(payload, [chunk()])
        relaxed = accept_payload_without_post_validation(payload)
        self.assertEqual("model_fallback", strict.status)
        self.assertEqual("invalid_or_missing_citation", strict.fallback_reason)
        self.assertEqual("unvalidated_answer", relaxed.status)
        self.assertEqual("Free answer.", relaxed.answer)
        self.assertEqual([], relaxed.citations)

    def test_post_validator_off_rejects_malformed_citations(self):
        result = generate(
            "Question?",
            [chunk()],
            FakeClient({"has_enough_context": True, "answer": "Free answer.", "citations": "pages:test:one"}),
            "gpt-4o-mini",
            0.0,
            "weak",
            "off",
        )
        self.assertEqual("model_fallback", result.status)
        self.assertEqual("invalid_llm_response", result.fallback_reason)

    def test_output_shape_has_context_map_and_no_legacy_duplicates(self):
        result = GenerationResult("grounded_answer", "Fact.", ["pages:test:one"])
        output = build_output("Question?", [chunk()], result, 0.3, "strong", "on")
        self.assertEqual("Question?", output["question"])
        self.assertEqual(0.3, output["min_vector_score"])
        self.assertEqual(0.8, output["best_vector_score"])
        self.assertEqual("Supported fact.", output["retrieved_context_by_id"]["pages:test:one"]["text"])
        self.assertNotIn("sources", output)
        self.assertNotIn("retrieved_chunks", output)

    def test_experiment_matrix_and_markdown_contract(self):
        exact_id = "pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector"
        payload = {"has_enough_context": True, "answer": "Debezium uses Kafka Connect exactly-once support.", "citations": [exact_id]}
        output = run_experiments("How does exactly-once work?", [chunk(0.78, exact_id)], FakeClient([payload] * 8), "gpt-4o-mini")
        self.assertEqual(
            [
                "weak_no_filter_no_validator",
                "weak_no_filter_with_validator",
                "strong_no_filter_no_validator",
                "strong_no_filter_with_validator",
                "weak_filter_no_validator",
                "weak_filter_with_validator",
                "strong_filter_no_validator",
                "strong_filter_with_validator",
            ],
            [item["experiment"] for item in output["experiments"]],
        )
        self.assertIn("| Experiment | Prompt | Post validator |", output["summary_markdown"])
        self.assertIn("Answered with validated citations.", output["summary_markdown"])

    def test_markdown_table_marks_filter_vs_model_fallback(self):
        table = markdown_table(
            [
                {
                    "experiment": "weak_prompt_with_filter",
                    "prompt_flavor": "weak",
                    "post_validator": "on",
                    "min_vector_score": 0.3,
                    "best_vector_score": 0.1,
                    "status": "retrieval_filter_fallback",
                    "fallback_reason": "weak_retrieval",
                    "citations": [],
                },
                {
                    "experiment": "strong_prompt_no_filter",
                    "prompt_flavor": "strong",
                    "post_validator": "on",
                    "min_vector_score": 0.0,
                    "best_vector_score": 0.1,
                    "status": "model_fallback",
                    "fallback_reason": "llm_reports_insufficient_context",
                    "citations": [],
                },
            ]
        )
        self.assertIn("Blocked before LLM", table)
        self.assertIn("LLM or citation validator", table)
        self.assertIn("Post validator", table)

    def test_markdown_table_escapes_cells(self):
        table = markdown_table(
            [
                {
                    "experiment": "weak|prompt",
                    "prompt_flavor": "weak",
                    "post_validator": "on",
                    "min_vector_score": 0.0,
                    "best_vector_score": None,
                    "status": "model\nfallback",
                    "fallback_reason": "bad|payload",
                    "citations": ["pages:test|one"],
                }
            ]
        )
        self.assertIn("weak\\|prompt", table)
        self.assertIn("model<br>fallback", table)
        self.assertIn("bad\\|payload", table)

    def test_can_convert_to_domain_rag_observation(self):
        result = GenerationResult("grounded_answer", "Fact.", ["pages:test:one"])
        observation = to_rag_observation("Question?", [chunk()], result)
        self.assertIsInstance(observation, RagObservation)
        self.assertTrue(observation.success)
        self.assertEqual("grounded_answer", observation.status)
        self.assertEqual(["pages:test:one"], observation.citations)


if __name__ == "__main__":
    unittest.main()
