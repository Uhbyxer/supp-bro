from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hw5"))

try:
    import langgraph_flow
    from external_tool_router import ToolObservation
except ModuleNotFoundError as exc:  # pragma: no cover - local env without requirements installed
    langgraph_flow = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


@unittest.skipIf(langgraph_flow is None, f"LangGraph dependencies are not installed: {IMPORT_ERROR}")
class LangGraphWorkflowTest(unittest.TestCase):
    def fake_tool(self, request, github_token=None):  # noqa: ANN001
        if request.tool_name == "get_github_issue_context":
            return ToolObservation(
                tool_name="get_github_issue_context",
                success=True,
                data={
                    "repo": request.payload["repo"],
                    "issue_number": request.payload["issue_number"],
                    "title": "mongodb : Unable to acquire buffer lock, buffer queue is likely full",
                    "state": "open",
                    "labels": ["component/mongodb-connector", "type/bug"],
                    "assignees": [],
                    "comment_count": 1,
                    "updated_at": "2025-12-03T08:47:35Z",
                    "url": "https://github.com/debezium/dbz/issues/3",
                },
            )
        if request.tool_name == "search_stackoverflow_questions":
            return ToolObservation(
                tool_name="search_stackoverflow_questions",
                success=True,
                data={"query": request.payload["query"], "tag": "debezium", "count": 0, "results": []},
            )
        return ToolObservation(
            tool_name="ask_clarifying_question",
            success=True,
            data={
                "clarifying_questions": [
                    "Which Debezium connector are you using?",
                    "What is the exact error message?",
                    "Do you want to search local docs/issues or external community sources?",
                ]
            },
        )

    def run_case(self, question: str, **kwargs):
        with (
            patch("langgraph_flow.execute_tool_request", side_effect=self.fake_tool),
            patch("langgraph_flow.should_use_model_synthesis", return_value=False),
        ):
            return langgraph_flow.run_langgraph_workflow(question, enable_rag=False, **kwargs)

    def test_docs_question_routes_through_docs_rag_node(self) -> None:
        state = self.run_case("Can I get exactly once delivery?")
        self.assertEqual(state["selected_route"], "docs_answer")
        self.assertEqual(state["executed_nodes"], ["classify_request", "run_docs_rag", "synthesize_answer"])
        self.assertEqual(state["rag_calls"][0]["status"], "rag_disabled")

    def test_known_error_with_mapping_uses_rag_github_and_community(self) -> None:
        state = self.run_case(
            "What should I do if Debezium MongoDB says unable to acquire buffer lock?",
            allow_external_community_search=True,
        )
        self.assertEqual(state["selected_route"], "issue_investigation")
        self.assertEqual(
            state["executed_nodes"],
            ["classify_request", "run_issue_rag", "read_github_issue", "search_community", "synthesize_answer"],
        )
        self.assertFalse(state["skip_issue_rag"])
        self.assertEqual(state["tool_calls"][0]["tool_name"], "get_github_issue_context")
        self.assertEqual(state["tool_calls"][1]["tool_name"], "search_stackoverflow_questions")

    def test_known_error_still_uses_rag_then_github_tool(self) -> None:
        state = self.run_case("Backpressure error says unable to acquire buffer lock and queue is full")
        self.assertEqual(state["selected_route"], "issue_investigation")
        self.assertFalse(state["skip_issue_rag"])
        self.assertFalse(state["search_community_after_issue"])
        self.assertIn("run_issue_rag", state["executed_nodes"])
        self.assertIn("read_github_issue", state["executed_nodes"])
        self.assertEqual(state["rag_calls"][0]["status"], "rag_disabled")
        self.assertEqual(state["tool_calls"][0]["tool_name"], "get_github_issue_context")

    def test_troubleshooting_question_adds_community_with_clean_query(self) -> None:
        state = self.run_case(
            "Debezium Mysql Connector Failed with IllegalStateException for history topic",
            allow_external_community_search=True,
        )
        self.assertEqual(state["selected_route"], "issue_investigation")
        self.assertFalse(state["skip_issue_rag"])
        self.assertTrue(state["search_community_after_issue"])
        self.assertEqual(
            state["executed_nodes"],
            ["classify_request", "run_issue_rag", "search_community", "synthesize_answer"],
        )
        self.assertEqual(
            [call["tool_name"] for call in state["tool_calls"]],
            ["search_stackoverflow_questions"],
        )
        self.assertEqual(
            state["tool_calls"][0]["payload"]["query"],
            "Debezium Mysql Connector Failed with IllegalStateException for history topic",
        )
        self.assertNotIn("read_github_issue", [step["name"] for step in state["plan"]])

    def test_stackoverflow_query_drops_routing_words(self) -> None:
        query = langgraph_flow.build_stackoverflow_query(
            "How to fix Debezium MongoDB buffer lock? Include possible community workarounds."
        )
        self.assertEqual(query, "Debezium MongoDB buffer lock")

    def test_synthesis_prompt_includes_all_evidence(self) -> None:
        state = self.run_case(
            "What should I do if Debezium MongoDB says unable to acquire buffer lock?",
            allow_external_community_search=True,
        )
        prompt = langgraph_flow.build_synthesis_prompt(state)
        self.assertIn("rag_calls", prompt)
        self.assertIn("tool_results", prompt)
        self.assertIn("get_github_issue_context", prompt)
        self.assertIn("search_stackoverflow_questions", prompt)

    def test_all_five_demo_cases_have_routes_and_nodes(self) -> None:
        with patch("langgraph_flow.execute_tool_request", side_effect=self.fake_tool):
            states = [
                langgraph_flow.run_langgraph_workflow(
                    question=case["question"],
                    issue_number=case["issue_number"],
                    allow_external_community_search=case["allow_external_community_search"],
                    enable_rag=False,
                )
                for case in langgraph_flow.DEFAULT_DEMO_CASES
            ]
        self.assertEqual(len(states), 5)
        self.assertEqual(
            {state["selected_route"] for state in states},
            {"docs_answer", "issue_investigation", "clarification"},
        )
        self.assertEqual(
            states[3]["executed_nodes"],
            ["classify_request", "run_issue_rag", "search_community", "synthesize_answer"],
        )
        for state in states:
            self.assertEqual(state["executed_nodes"][0], "classify_request")
            self.assertEqual(state["executed_nodes"][-1], "synthesize_answer")


if __name__ == "__main__":
    unittest.main()
