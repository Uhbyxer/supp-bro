"""Stack Overflow search adapter returning product domain observations."""

from __future__ import annotations

import html
import urllib.parse
from typing import Any, Callable

from supp_bro.config import STACKOVERFLOW_SEARCH_CAPABILITY, LocalSettings
from supp_bro.domain.contracts import ToolObservation, ToolRequest
from supp_bro.tools.requests import normalize_stackoverflow_query, validate_tool_request

HttpGetJson = Callable[[str, dict[str, str] | None, int], Any]

STACKOVERFLOW_SOURCE = "stackoverflow"
STACKEXCHANGE_SEARCH_URL = "https://api.stackexchange.com/2.3/search/advanced"
UNCONFIRMED_SEARCH_ERROR = "External community search requires confirmation."


def search_stackoverflow_questions(
    request: ToolRequest,
    settings: LocalSettings,
    http_get_json: HttpGetJson,
    timeout: int = 20,
) -> ToolObservation:
    """Search Stack Overflow after explicit user confirmation."""

    validation_error = validate_tool_request(request)
    if validation_error:
        return _failed_observation("failed", validation_error)

    if not request.confirmed:
        return _failed_observation("skipped", UNCONFIRMED_SEARCH_ERROR)

    if not settings.is_capability_available(STACKOVERFLOW_SEARCH_CAPABILITY):
        return _failed_observation("unavailable", "Stack Overflow search capability is unavailable.")

    token = settings.provider_tokens.stackoverflow_token
    query = request.payload["query"]
    tag = request.payload["tag"]
    max_results = request.payload.get("max_results", 5)
    normalized_query = normalize_stackoverflow_query(query)
    params = {
        "order": "desc",
        "sort": "relevance",
        "tagged": tag,
        "q": normalized_query,
        "site": "stackoverflow",
        "pagesize": max_results,
        "filter": "!nNPvSNdWme",
    }
    if token:
        params["key"] = token
    url = f"{STACKEXCHANGE_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    raw_reference = f"{STACKEXCHANGE_SEARCH_URL}?{urllib.parse.urlencode({k: v for k, v in params.items() if k != 'key'})}"

    try:
        payload = http_get_json(url, None, timeout)
    except TimeoutError as exc:
        return _failed_observation("timeout", _clean_error(exc, token))
    except Exception as exc:  # pragma: no cover - concrete provider exception types vary
        return _failed_observation("failed", _clean_error(exc, token))

    if not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
        return _failed_observation("failed", "Stack Overflow response was malformed.")

    results = [
        {
            "title": html.unescape(item.get("title") or ""),
            "score": item.get("score"),
            "answer_count": item.get("answer_count"),
            "is_answered": item.get("is_answered"),
            "last_activity_date": item.get("last_activity_date"),
            "url": item.get("link"),
        }
        for item in payload.get("items", [])
        if isinstance(item, dict)
    ]
    return ToolObservation(
        tool_name="search_stackoverflow_questions",
        success=True,
        status="success",
        source=STACKOVERFLOW_SOURCE,
        raw_reference=raw_reference,
        data={
            "query": query,
            "normalized_query": normalized_query,
            "tag": tag,
            "count": len(results),
            "results": results,
        },
    )


def _failed_observation(status: str, error: str) -> ToolObservation:
    return ToolObservation(
        tool_name="search_stackoverflow_questions",
        success=False,
        status=status,  # type: ignore[arg-type]
        source=STACKOVERFLOW_SOURCE,
        data={},
        error=error,
    )


def _clean_error(exc: Exception, token: str | None) -> str:
    message = str(exc) or exc.__class__.__name__
    if token:
        message = message.replace(token, "[redacted]")
    return message
