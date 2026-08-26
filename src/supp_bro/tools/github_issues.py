"""GitHub issue adapter returning product domain observations."""

from __future__ import annotations

from typing import Any, Callable

from supp_bro.config import GITHUB_ISSUES_CAPABILITY, LocalSettings
from supp_bro.domain.contracts import ToolObservation, ToolRequest
from supp_bro.tools.requests import validate_tool_request

HttpGetJson = Callable[[str, dict[str, str] | None, int], Any]

GITHUB_API_ROOT = "https://api.github.com"
GITHUB_SOURCE = "github"


def fetch_github_issue_context(
    request: ToolRequest,
    settings: LocalSettings,
    http_get_json: HttpGetJson,
    timeout: int = 20,
) -> ToolObservation:
    """Fetch and normalize a GitHub issue plus recent comments."""

    validation_error = validate_tool_request(request)
    if validation_error:
        return _failed_observation("failed", validation_error)

    if not settings.is_capability_available(GITHUB_ISSUES_CAPABILITY):
        return _failed_observation("unavailable", "GitHub issues capability is unavailable.")

    token = settings.provider_tokens.github_token
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    repo = request.payload["repo"]
    issue_number = request.payload["issue_number"]
    issue_url = f"{GITHUB_API_ROOT}/repos/{repo}/issues/{issue_number}"
    comments_url = f"{issue_url}/comments?per_page=30"

    try:
        issue = http_get_json(issue_url, headers, timeout)
        comments_payload = http_get_json(comments_url, headers, timeout)
    except TimeoutError as exc:
        return _failed_observation("timeout", _clean_error(exc, token))
    except Exception as exc:  # pragma: no cover - concrete provider exception types vary
        return _failed_observation("failed", _clean_error(exc, token))

    if not isinstance(issue, dict):
        return _failed_observation("failed", "GitHub issue response was malformed.")
    comments = comments_payload if isinstance(comments_payload, list) else []

    participants = sorted(
        {
            *(comment.get("user", {}).get("login") for comment in comments if isinstance(comment, dict) and comment.get("user")),
            issue.get("user", {}).get("login"),
            *(assignee.get("login") for assignee in issue.get("assignees", []) if isinstance(assignee, dict)),
        }
        - {None}
    )
    recent_comment_authors = [
        comment.get("user", {}).get("login")
        for comment in comments[-5:]
        if isinstance(comment, dict) and comment.get("user", {}).get("login")
    ]

    return ToolObservation(
        tool_name="get_github_issue_context",
        success=True,
        status="success",
        source=GITHUB_SOURCE,
        raw_reference=issue_url,
        data={
            "repo": repo,
            "issue_number": issue_number,
            "title": issue.get("title"),
            "state": issue.get("state"),
            "labels": [label.get("name") for label in issue.get("labels", []) if isinstance(label, dict)],
            "assignees": [
                assignee.get("login") for assignee in issue.get("assignees", []) if isinstance(assignee, dict)
            ],
            "created_by": issue.get("user", {}).get("login"),
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
            "closed_at": issue.get("closed_at"),
            "comment_count": issue.get("comments"),
            "participants": participants,
            "recent_comment_authors": recent_comment_authors,
            "url": issue.get("html_url"),
        },
    )


def _failed_observation(status: str, error: str) -> ToolObservation:
    return ToolObservation(
        tool_name="get_github_issue_context",
        success=False,
        status=status,  # type: ignore[arg-type]
        source=GITHUB_SOURCE,
        data={},
        error=error,
    )


def _clean_error(exc: Exception, token: str | None) -> str:
    message = str(exc) or exc.__class__.__name__
    if token:
        message = message.replace(token, "[redacted]")
    return message
