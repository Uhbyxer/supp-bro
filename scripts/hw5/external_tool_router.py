"""HW5: Intent-based external tool orchestration for SuppBro.

Run examples:
    python scripts/hw5/external_tool_router.py \
        "Is Debezium issue #3 still active?"

    python scripts/hw5/external_tool_router.py \
        "Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?" \
        --allow-external-community-search
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Route = Literal[
    "docs_question",
    "known_issue_question",
    "report_new_issue",
    "community_troubleshooting",
    "clarification",
]
ToolType = Literal["read"]
ToolName = Literal[
    "get_github_issue_context",
    "search_stackoverflow_questions",
    "ask_clarifying_question",
    "none",
]

DEFAULT_GITHUB_REPO = "debezium/dbz"
DEFAULT_STACKOVERFLOW_TAG = "debezium"
USER_AGENT = "supp-bro-hw5-external-tool-demo"


@dataclass
class ToolRequest:
    tool_name: ToolName
    tool_type: ToolType
    payload: dict[str, Any]
    confirmed: bool = False


@dataclass
class ToolObservation:
    tool_name: ToolName
    success: bool
    data: dict[str, Any]
    error: str | None = None


@dataclass
class AgentState:
    user_query: str
    route: Route
    route_reason: str
    enabled_tools: list[ToolName] = field(default_factory=list)
    tool_request: ToolRequest | None = None
    observation: ToolObservation | None = None
    requires_clarification: bool = False
    final_answer: str = ""


def http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> dict[str, Any]:
    request_headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def classify_support_intent(question: str) -> tuple[Route, str]:
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
    match = re.search(r"(?:issue|bug)\s*#?\s*(\d+)", question, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


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


def get_github_issue_context(repo: str, issue_number: int, github_token: str | None = None) -> ToolObservation:
    headers: dict[str, str] = {}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    issue_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    comments_url = f"{issue_url}/comments?per_page=30"

    issue = http_get_json(issue_url, headers=headers)
    comments_payload = http_get_json(comments_url, headers=headers)
    comments = comments_payload if isinstance(comments_payload, list) else []

    participants = sorted(
        {
            *(comment.get("user", {}).get("login") for comment in comments if comment.get("user")),
            issue.get("user", {}).get("login"),
            *(assignee.get("login") for assignee in issue.get("assignees", [])),
        }
        - {None}
    )
    recent_comment_authors = [
        comment.get("user", {}).get("login")
        for comment in comments[-5:]
        if comment.get("user", {}).get("login")
    ]

    return ToolObservation(
        tool_name="get_github_issue_context",
        success=True,
        data={
            "repo": repo,
            "issue_number": issue_number,
            "title": issue.get("title"),
            "state": issue.get("state"),
            "labels": [label.get("name") for label in issue.get("labels", [])],
            "assignees": [assignee.get("login") for assignee in issue.get("assignees", [])],
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


def search_stackoverflow_questions(query: str, tag: str, max_results: int = 5) -> ToolObservation:
    normalized_query = normalize_stackoverflow_query(query)
    params = urllib.parse.urlencode(
        {
            "order": "desc",
            "sort": "relevance",
            "tagged": tag,
            "q": normalized_query,
            "site": "stackoverflow",
            "pagesize": max_results,
            "filter": "!nNPvSNdWme",
        }
    )
    url = f"https://api.stackexchange.com/2.3/search/advanced?{params}"
    payload = http_get_json(url)
    items = payload.get("items", [])
    results = [
        {
            "title": html.unescape(item.get("title") or ""),
            "score": item.get("score"),
            "answer_count": item.get("answer_count"),
            "is_answered": item.get("is_answered"),
            "last_activity_date": item.get("last_activity_date"),
            "url": item.get("link"),
        }
        for item in items
    ]
    return ToolObservation(
        tool_name="search_stackoverflow_questions",
        success=True,
        data={"query": query, "normalized_query": normalized_query, "tag": tag, "count": len(results), "results": results},
    )


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


def ask_clarifying_question(query: str) -> ToolObservation:
    return ToolObservation(
        tool_name="ask_clarifying_question",
        success=True,
        data={
            "original_query": query,
            "clarifying_questions": [
                "Which Debezium connector are you using?",
                "What is the exact error message?",
                "Do you want to search local docs/issues or external community sources?",
            ],
        },
    )


def execute_tool_request(request: ToolRequest, github_token: str | None = None) -> ToolObservation:
    validation_error = validate_tool_request(request)
    if validation_error:
        return ToolObservation(tool_name=request.tool_name, success=False, data={}, error=validation_error)

    try:
        if request.tool_name == "get_github_issue_context":
            return get_github_issue_context(
                repo=request.payload["repo"],
                issue_number=request.payload["issue_number"],
                github_token=github_token,
            )
        if request.tool_name == "search_stackoverflow_questions":
            if not request.confirmed:
                return ToolObservation(
                    tool_name=request.tool_name,
                    success=False,
                    data={},
                    error="External community search requires confirmation.",
                )
            return search_stackoverflow_questions(
                query=request.payload["query"],
                tag=request.payload["tag"],
                max_results=request.payload.get("max_results", 5),
            )
        if request.tool_name == "ask_clarifying_question":
            return ask_clarifying_question(query=request.payload["query"])
        return ToolObservation(tool_name="none", success=True, data={})
    except Exception as exc:  # pragma: no cover - network errors depend on external services
        return ToolObservation(tool_name=request.tool_name, success=False, data={}, error=str(exc))


def build_tool_request(
    route: Route,
    question: str,
    repo: str,
    issue_number: int | None,
    allow_external_community_search: bool,
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


def build_final_answer(state: AgentState) -> str:
    observation = state.observation
    if observation is None:
        return "No tool was called."
    if not observation.success:
        return f"Tool call failed: {observation.error}"
    if observation.tool_name == "get_github_issue_context":
        data = observation.data
        labels = ", ".join(data["labels"]) if data["labels"] else "no labels"
        assignees = ", ".join(data["assignees"]) if data["assignees"] else "no assignees"
        return (
            f"GitHub issue {data['repo']}#{data['issue_number']} is {data['state']}: "
            f"{data['title']}. It has {labels}, {assignees}, "
            f"{data['comment_count']} comments, and was last updated at {data['updated_at']}. "
            f"URL: {data['url']}"
        )
    if observation.tool_name == "search_stackoverflow_questions":
        data = observation.data
        if data["count"] == 0:
            return "I did not find matching Stack Overflow questions for this Debezium query."
        top = data["results"][0]
        return (
            f"Found {data['count']} Stack Overflow questions tagged {data['tag']}. "
            f"Top result: {top['title']} (score: {top['score']}, answers: {top['answer_count']}). "
            f"URL: {top['url']}"
        )
    if observation.tool_name == "ask_clarifying_question":
        state.requires_clarification = True
        questions = " ".join(observation.data["clarifying_questions"])
        return f"I need more detail before choosing a tool. {questions}"
    return "This looks like a documentation question. Use the local Debezium docs RAG path; no external tool is needed."


def run_agent(
    question: str,
    repo: str = DEFAULT_GITHUB_REPO,
    issue_number: int | None = None,
    allow_external_community_search: bool = False,
    github_token: str | None = None,
) -> AgentState:
    route, route_reason = classify_support_intent(question)
    tool_request = build_tool_request(
        route=route,
        question=question,
        repo=repo,
        issue_number=issue_number,
        allow_external_community_search=allow_external_community_search,
    )
    state = AgentState(
        user_query=question,
        route=route,
        route_reason=route_reason,
        enabled_tools=[tool_request.tool_name] if tool_request.tool_name != "none" else [],
        tool_request=tool_request,
    )
    state.observation = execute_tool_request(tool_request, github_token=github_token)
    state.final_answer = build_final_answer(state)
    return state


def render_markdown(state: AgentState) -> str:
    payload = asdict(state)
    return "\n".join(
        [
            "# HW5 external tool result",
            "",
            f"User question: `{state.user_query}`",
            "",
            f"Route: `{state.route}`",
            "",
            f"Route reason: {state.route_reason}",
            "",
            f"Tool called: `{state.tool_request.tool_name if state.tool_request else 'none'}`",
            "",
            "Final answer:",
            "",
            state.final_answer,
            "",
            "Normalized state:",
            "",
            "```json",
            json.dumps(payload, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HW5 external tool router.")
    parser.add_argument("question", help="User question to route.")
    parser.add_argument("--repo", default=DEFAULT_GITHUB_REPO, help="GitHub repo in owner/name format.")
    parser.add_argument("--issue-number", type=int, default=None, help="GitHub issue number override.")
    parser.add_argument(
        "--allow-external-community-search",
        action="store_true",
        help="Confirm that Stack Overflow/community search is allowed.",
    )
    parser.add_argument("--output-json", default="", help="Optional JSON output path.")
    parser.add_argument("--output-md", default="", help="Optional Markdown output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = run_agent(
        question=args.question,
        repo=args.repo,
        issue_number=args.issue_number,
        allow_external_community_search=args.allow_external_community_search,
        github_token=os.getenv("GITHUB_TOKEN"),
    )
    state_json = json.dumps(asdict(state), indent=2, ensure_ascii=False)
    print(state_json)

    if args.output_json:
        Path(args.output_json).write_text(state_json + "\n", encoding="utf-8")
    if args.output_md:
        Path(args.output_md).write_text(render_markdown(state), encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
