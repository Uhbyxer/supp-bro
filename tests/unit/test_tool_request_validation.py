from __future__ import annotations

import unittest

from supp_bro.domain.contracts import ToolRequest
from supp_bro.tools import (
    DEFAULT_GITHUB_REPO,
    DEFAULT_STACKOVERFLOW_TAG,
    build_tool_request,
    normalize_stackoverflow_query,
    validate_tool_request,
)


class ToolRequestValidationTest(unittest.TestCase):
    def test_builds_github_request_from_explicit_issue_number(self) -> None:
        request = build_tool_request(
            route="known_issue_question",
            question="Is Debezium issue #3 still open?",
            repo=DEFAULT_GITHUB_REPO,
            issue_number=None,
            allow_external_community_search=False,
        )

        self.assertEqual(request.tool_name, "get_github_issue_context")
        self.assertEqual(request.tool_type, "read")
        self.assertEqual(request.payload, {"repo": "debezium/dbz", "issue_number": 3})

    def test_builds_github_request_from_buffer_lock_fallback(self) -> None:
        request = build_tool_request(
            route="known_issue_question",
            question="Unable to acquire buffer lock and queue is full",
        )

        self.assertEqual(request.tool_name, "get_github_issue_context")
        self.assertEqual(request.payload["issue_number"], 3)

    def test_missing_issue_context_builds_clarifying_request(self) -> None:
        request = build_tool_request(
            route="known_issue_question",
            question="Is there a known issue for this connector?",
        )

        self.assertEqual(request.tool_name, "ask_clarifying_question")
        self.assertEqual(request.payload, {"query": "Is there a known issue for this connector?"})

    def test_builds_community_request_with_confirmation_flag(self) -> None:
        request = build_tool_request(
            route="community_troubleshooting",
            question="Has anyone seen Debezium buffer lock on Stack Overflow?",
            allow_external_community_search=True,
        )

        self.assertEqual(request.tool_name, "search_stackoverflow_questions")
        self.assertEqual(
            request.payload,
            {
                "query": "Has anyone seen Debezium buffer lock on Stack Overflow?",
                "tag": DEFAULT_STACKOVERFLOW_TAG,
                "max_results": 5,
            },
        )
        self.assertTrue(request.confirmed)

    def test_builds_clarification_request_for_report_issue(self) -> None:
        request = build_tool_request(route="report_new_issue", question="I want to report issue")

        self.assertEqual(request.tool_name, "ask_clarifying_question")
        self.assertEqual(request.payload, {"query": "I want to report issue"})

    def test_builds_none_request_for_docs_question(self) -> None:
        request = build_tool_request(route="docs_question", question="Can I get exactly once delivery?")

        self.assertEqual(request.tool_name, "none")
        self.assertEqual(request.tool_type, "read")
        self.assertEqual(request.payload, {})

    def test_validates_github_request_and_exact_errors(self) -> None:
        self.assertIsNone(
            validate_tool_request(
                ToolRequest(
                    tool_name="get_github_issue_context",
                    tool_type="read",
                    payload={"repo": "debezium/dbz", "issue_number": 3},
                )
            )
        )
        self.assertEqual(
            validate_tool_request(
                ToolRequest(
                    tool_name="get_github_issue_context",
                    tool_type="read",
                    payload={"repo": "bad repo", "issue_number": 3},
                )
            ),
            "repo must use owner/name format.",
        )
        self.assertEqual(
            validate_tool_request(
                ToolRequest(
                    tool_name="get_github_issue_context",
                    tool_type="read",
                    payload={"repo": "debezium/dbz", "issue_number": 0},
                )
            ),
            "issue_number must be positive.",
        )

    def test_validates_stackoverflow_request_and_exact_errors(self) -> None:
        self.assertIsNone(
            validate_tool_request(
                ToolRequest(
                    tool_name="search_stackoverflow_questions",
                    tool_type="read",
                    payload={"query": "debezium backpressure", "tag": "debezium"},
                )
            )
        )
        self.assertEqual(
            validate_tool_request(
                ToolRequest(
                    tool_name="search_stackoverflow_questions",
                    tool_type="read",
                    payload={"query": "", "tag": "debezium"},
                )
            ),
            "query is required and must be a non-empty string.",
        )
        self.assertEqual(
            validate_tool_request(
                ToolRequest(
                    tool_name="search_stackoverflow_questions",
                    tool_type="read",
                    payload={"query": "debezium", "tag": "bad tag"},
                )
            ),
            "tag contains unsupported characters.",
        )

    def test_normalizes_stackoverflow_query(self) -> None:
        self.assertEqual(
            normalize_stackoverflow_query("Has anyone seen Debezium buffer lock on Stack Overflow?"),
            "debezium buffer lock",
        )
        self.assertEqual(normalize_stackoverflow_query("Stack Overflow?!"), "Stack Overflow?!")

    def test_unknown_and_none_tool_validation(self) -> None:
        self.assertIsNone(validate_tool_request(ToolRequest(tool_name="none", tool_type="read", payload={})))

        request = ToolRequest(tool_name="none", tool_type="read", payload={})
        request.tool_name = "unexpected_tool"  # type: ignore[assignment]
        self.assertEqual(validate_tool_request(request), "Unknown tool.")


if __name__ == "__main__":
    unittest.main()
