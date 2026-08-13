import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from external_tool_router import (
    ToolRequest,
    DEMO_CASES,
    classify_support_intent,
    execute_tool_request,
    extract_issue_number,
    normalize_stackoverflow_query,
    validate_tool_request,
)


class ExternalToolRouterTest(unittest.TestCase):
    def test_routes_docs_question(self) -> None:
        route, _ = classify_support_intent("Can I get exactly once delivery with Debezium?")
        self.assertEqual(route, "docs_question")

    def test_routes_known_issue_question(self) -> None:
        route, _ = classify_support_intent("Is Debezium issue #3 still open?")
        self.assertEqual(route, "known_issue_question")

    def test_routes_community_troubleshooting(self) -> None:
        route, _ = classify_support_intent("Has anyone seen this Debezium error on Stack Overflow?")
        self.assertEqual(route, "community_troubleshooting")

    def test_routes_vague_question_to_clarification(self) -> None:
        route, _ = classify_support_intent("Help")
        self.assertEqual(route, "clarification")

    def test_extracts_issue_number(self) -> None:
        self.assertEqual(extract_issue_number("Check issue #123 please"), 123)
        self.assertEqual(extract_issue_number("bug 42 is relevant"), 42)
        self.assertIsNone(extract_issue_number("no issue number here"))

    def test_validates_github_request(self) -> None:
        request = ToolRequest(
            tool_name="get_github_issue_context",
            tool_type="read",
            payload={"repo": "debezium/dbz", "issue_number": 3},
        )
        self.assertIsNone(validate_tool_request(request))

    def test_rejects_invalid_repo(self) -> None:
        request = ToolRequest(
            tool_name="get_github_issue_context",
            tool_type="read",
            payload={"repo": "bad repo", "issue_number": 3},
        )
        self.assertEqual(validate_tool_request(request), "repo must use owner/name format.")

    def test_rejects_unconfirmed_community_search(self) -> None:
        request = ToolRequest(
            tool_name="search_stackoverflow_questions",
            tool_type="read",
            payload={"query": "debezium backpressure", "tag": "debezium"},
            confirmed=False,
        )
        observation = execute_tool_request(request)
        self.assertFalse(observation.success)
        self.assertEqual(observation.error, "External community search requires confirmation.")

    def test_normalizes_stackoverflow_query(self) -> None:
        self.assertEqual(
            normalize_stackoverflow_query("Has anyone seen Debezium buffer lock on Stack Overflow?"),
            "debezium buffer lock",
        )

    def test_demo_cases_cover_main_routes(self) -> None:
        routes = {classify_support_intent(case["question"])[0] for case in DEMO_CASES}
        self.assertIn("docs_question", routes)
        self.assertIn("known_issue_question", routes)
        self.assertIn("community_troubleshooting", routes)
        self.assertIn("clarification", routes)


if __name__ == "__main__":
    unittest.main()
