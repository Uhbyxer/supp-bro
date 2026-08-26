from __future__ import annotations

import unittest

from supp_bro.domain import classify_support_intent, extract_issue_number


class SupportIntentRoutingTest(unittest.TestCase):
    def test_classifies_docs_question_with_preserved_reason(self) -> None:
        self.assertEqual(
            classify_support_intent("Can I get exactly once delivery with Debezium?"),
            ("docs_question", "The user asks a documentation-style question."),
        )

    def test_classifies_known_issue_question_with_preserved_reason(self) -> None:
        self.assertEqual(
            classify_support_intent("Is Debezium issue #3 still open?"),
            ("known_issue_question", "The user asks about current GitHub issue metadata."),
        )

    def test_classifies_concrete_error_as_known_issue(self) -> None:
        self.assertEqual(
            classify_support_intent("MongoDB connector backpressure error says queue is full"),
            (
                "known_issue_question",
                "The user asks about a concrete error that may map to a known issue.",
            ),
        )

    def test_classifies_community_troubleshooting_with_preserved_reason(self) -> None:
        self.assertEqual(
            classify_support_intent("Has anyone seen this Debezium error on Stack Overflow?"),
            ("community_troubleshooting", "The user asks for external community troubleshooting."),
        )

    def test_classifies_vague_question_as_clarification(self) -> None:
        self.assertEqual(
            classify_support_intent("Help"),
            ("clarification", "The query is too vague to choose a reliable tool."),
        )

    def test_classifies_whitespace_only_question_as_clarification(self) -> None:
        self.assertEqual(
            classify_support_intent("   "),
            ("clarification", "The query is too vague to choose a reliable tool."),
        )

    def test_classifies_report_issue_request(self) -> None:
        self.assertEqual(
            classify_support_intent("I want to file issue for Debezium"),
            ("report_new_issue", "The user wants to report a new issue or bug."),
        )

    def test_preserves_hw5_route_precedence_for_overlapping_intents(self) -> None:
        self.assertEqual(
            classify_support_intent("Is Stack Overflow issue #123 related to Debezium?")[0],
            "community_troubleshooting",
        )
        self.assertEqual(
            classify_support_intent("Help with Debezium issue #123 please")[0],
            "known_issue_question",
        )

    def test_extracts_issue_number_from_issue_and_bug_phrases(self) -> None:
        self.assertEqual(extract_issue_number("Check issue #123 please"), 123)
        self.assertEqual(extract_issue_number("issue 124 is relevant"), 124)
        self.assertEqual(extract_issue_number("bug #42 is relevant"), 42)
        self.assertEqual(extract_issue_number("bug 43 is relevant"), 43)
        self.assertIsNone(extract_issue_number("no issue number here"))


if __name__ == "__main__":
    unittest.main()
