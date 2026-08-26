"""Provider-free tool request construction and validation."""

from __future__ import annotations

import re
from typing import Any

from supp_bro.domain.contracts import ToolRequest
from supp_bro.domain.routes import Hw5Route
from supp_bro.domain.support_intent import extract_issue_number

DEFAULT_GITHUB_REPO = "debezium/dbz"
DEFAULT_STACKOVERFLOW_TAG = "debezium"


def validate_repo(repo: Any) -> str | None:
    if not isinstance(repo, str) or not repo.strip():
        return "repo is required and must be a non-empty string."
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        return "repo must use owner/name format."
    return None


def validate_issue_number(issue_number: Any) -> str | None:
    if not isinstance(issue_number, int):
        return "issue_number must be an integer."
    if issue_number < 1:
        return "issue_number must be positive."
    return None


def validate_search_query(query: Any) -> str | None:
    if not isinstance(query, str) or not query.strip():
        return "query is required and must be a non-empty string."
    if len(query) > 300:
        return "query must be 300 characters or shorter."
    return None


def validate_tag(tag: Any) -> str | None:
    if not isinstance(tag, str) or not tag.strip():
        return "tag is required and must be a non-empty string."
    if not re.fullmatch(r"[A-Za-z0-9_.#+-]+", tag):
        return "tag contains unsupported characters."
    return None


def validate_tool_request(request: ToolRequest) -> str | None:
    if request.tool_name == "get_github_issue_context":
        repo_error = validate_repo(request.payload.get("repo"))
        if repo_error:
            return repo_error
        return validate_issue_number(request.payload.get("issue_number"))
    if request.tool_name == "search_stackoverflow_questions":
        query_error = validate_search_query(request.payload.get("query"))
        if query_error:
            return query_error
        return validate_tag(request.payload.get("tag"))
    if request.tool_name == "ask_clarifying_question":
        return validate_search_query(request.payload.get("query"))
    if request.tool_name == "none":
        return None
    return "Unknown tool."


def normalize_stackoverflow_query(query: str) -> str:
    normalized = query.lower()
    for phrase in [
        "has anyone seen",
        "on stack overflow",
        "stackoverflow",
        "stack overflow",
        "community",
        "workaround",
    ]:
        normalized = normalized.replace(phrase, " ")
    normalized = re.sub(r"[?!.:,;]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or query


def build_tool_request(
    route: Hw5Route,
    question: str,
    repo: str = DEFAULT_GITHUB_REPO,
    issue_number: int | None = None,
    allow_external_community_search: bool = False,
) -> ToolRequest:
    if route == "known_issue_question":
        selected_issue = issue_number or extract_issue_number(question)
        if selected_issue is None:
            if "buffer lock" in question.lower() or "queue is full" in question.lower():
                selected_issue = 3
            else:
                return ToolRequest(
                    tool_name="ask_clarifying_question",
                    tool_type="read",
                    payload={"query": question},
                )
        return ToolRequest(
            tool_name="get_github_issue_context",
            tool_type="read",
            payload={"repo": repo, "issue_number": selected_issue},
        )
    if route == "community_troubleshooting":
        return ToolRequest(
            tool_name="search_stackoverflow_questions",
            tool_type="read",
            payload={"query": question, "tag": DEFAULT_STACKOVERFLOW_TAG, "max_results": 5},
            confirmed=allow_external_community_search,
        )
    if route == "clarification" or route == "report_new_issue":
        return ToolRequest(
            tool_name="ask_clarifying_question",
            tool_type="read",
            payload={"query": question},
        )
    return ToolRequest(tool_name="none", tool_type="read", payload={})
