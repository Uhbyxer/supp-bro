"""Tool request helpers and validation for SuppBro adapters."""

from supp_bro.tools.requests import (
    DEFAULT_GITHUB_REPO,
    DEFAULT_STACKOVERFLOW_TAG,
    build_tool_request,
    normalize_stackoverflow_query,
    validate_issue_number,
    validate_repo,
    validate_search_query,
    validate_tag,
    validate_tool_request,
)
from supp_bro.tools.github_issues import fetch_github_issue_context
from supp_bro.tools.stackoverflow import (
    UNCONFIRMED_SEARCH_ERROR,
    search_stackoverflow_questions,
)

__all__ = [
    "DEFAULT_GITHUB_REPO",
    "DEFAULT_STACKOVERFLOW_TAG",
    "UNCONFIRMED_SEARCH_ERROR",
    "build_tool_request",
    "fetch_github_issue_context",
    "normalize_stackoverflow_query",
    "search_stackoverflow_questions",
    "validate_issue_number",
    "validate_repo",
    "validate_search_query",
    "validate_tag",
    "validate_tool_request",
]
