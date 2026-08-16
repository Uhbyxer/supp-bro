from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentic_workflow import (
    DEFAULT_DEMO_CASES,
    build_plan,
    classify_support_intent,
    map_hw5_route,
    run_hw4_rag,
    run_workflow,
)


class AgenticWorkflowTest(unittest.TestCase):
    def test_maps_hw5_routes_to_hw6_routes(self) -> None:
        self.assertEqual(map_hw5_route("docs_question"), "docs_answer")
        self.assertEqual(map_hw5_route("known_issue_question"), "issue_investigation")
        self.assertEqual(map_hw5_route("community_troubleshooting"), "community_lookup")
        self.assertEqual(map_hw5_route("clarification"), "clarification")

    def test_each_route_has_controlled_steps(self) -> None:
        for route in ("docs_answer", "issue_investigation", "community_lookup", "clarification"):
            with self.subTest(route=route):
                plan = build_plan(route)
                self.assertGreaterEqual(len(plan), 3)
                self.assertEqual(plan[0].name, "classify_intent")
                self.assertEqual(plan[-1].name, "compose_answer")

    def test_missing_rag_credentials_are_recorded_without_crashing(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "PINECONE_API_KEY": ""}, clear=False):
            observation = run_hw4_rag("Can I get exactly once delivery?", "pages")
        self.assertFalse(observation.success)
        self.assertEqual(observation.status, "rag_unavailable")
        self.assertIn("missing", observation.fallback_reason or "")

    def test_docs_question_uses_rag_path_without_external_tool(self) -> None:
        state = run_workflow("Can I get exactly once delivery?", enable_rag=False)
        self.assertEqual(state.selected_route, "docs_answer")
        self.assertEqual(state.tool_calls, [])
        self.assertEqual(state.rag_calls[0].status, "rag_disabled")

    def test_clarification_route_sets_requires_clarification(self) -> None:
        state = run_workflow("Help", enable_rag=False)
        self.assertEqual(state.selected_route, "clarification")
        self.assertTrue(state.requires_clarification)
        self.assertEqual(state.tool_calls[0]["tool_name"], "ask_clarifying_question")

    def test_demo_cases_cover_expected_routes(self) -> None:
        routes = {
            map_hw5_route(classify_support_intent(case["question"])[0])
            for case in DEFAULT_DEMO_CASES
        }
        self.assertIn("docs_answer", routes)
        self.assertIn("issue_investigation", routes)
        self.assertIn("community_lookup", routes)
        self.assertIn("clarification", routes)


if __name__ == "__main__":
    unittest.main()
