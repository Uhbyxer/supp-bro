"""Deterministic support-intent routing shared with the HW5 compatibility script."""

from __future__ import annotations

import re

from supp_bro.domain.routes import Hw5Route


def classify_support_intent(question: str) -> tuple[Hw5Route, str]:
    """Classify a support question using the preserved HW5 keyword heuristics."""
    text = question.lower()

    if any(token in text for token in ["report issue", "create issue", "file issue", "submit bug"]):
        return "report_new_issue", "The user wants to report a new issue or bug."
    if any(token in text for token in ["stackoverflow", "stack overflow", "anyone seen", "workaround", "community"]):
        return "community_troubleshooting", "The user asks for external community troubleshooting."
    if re.search(r"(issue|bug)\s*#?\d+", text) or any(
        token in text for token in ["still open", "closed", "assignee", "labels", "contributors"]
    ):
        return "known_issue_question", "The user asks about current GitHub issue metadata."
    if any(token in text for token in ["error", "exception", "unable to", "buffer lock", "queue is full", "backpressure"]):
        return "known_issue_question", "The user asks about a concrete error that may map to a known issue."
    if len(text.split()) < 5 or any(token in text for token in ["something wrong", "help", "problem"]):
        return "clarification", "The query is too vague to choose a reliable tool."
    return "docs_question", "The user asks a documentation-style question."


def extract_issue_number(question: str) -> int | None:
    """Extract a GitHub issue number from an issue/bug phrase."""
    match = re.search(r"(?:issue|bug)\s*#?\s*(\d+)", question, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None
