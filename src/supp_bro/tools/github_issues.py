"""GitHub issue adapter returning product domain observations."""

from __future__ import annotations

import urllib.parse
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
    owner, name = repo.split("/", maxsplit=1)
    quoted_repo = f"{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(name, safe='')}"
    issue_url = f"{GITHUB_API_ROOT}/repos/{quoted_repo}/issues/{issue_number}"
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
    if not isinstance(comments_payload, list):
        return _failed_observation("failed", "GitHub comments response was malformed.")

    issue_user = issue.get("user") if isinstance(issue.get("user"), dict) else {}
    labels = issue.get("labels") if isinstance(issue.get("labels"), list) else []
    assignees = issue.get("assignees") if isinstance(issue.get("assignees"), list) else []
    comment_users = [
        comment.get("user")
        for comment in comments_payload
        if isinstance(comment, dict) and isinstance(comment.get("user"), dict)
    ]
    participants = sorted(
        {
            *(user.get("login") for user in comment_users),
            issue_user.get("login"),
            *(assignee.get("login") for assignee in assignees if isinstance(assignee, dict)),
        }
        - {None}
    )
    recent_comment_authors = [
        user.get("login")
        for user in comment_users[-5:]
        if user.get("login")
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
            "labels": [label.get("name") for label in labels if isinstance(label, dict)],
            "assignees": [
                assignee.get("login") for assignee in assignees if isinstance(assignee, dict)
            ],
            "created_by": issue_user.get("login"),
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
