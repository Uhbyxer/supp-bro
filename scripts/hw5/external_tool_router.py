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
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from supp_bro.domain.contracts import ToolName, ToolRequest, ToolType
from supp_bro.domain.routes import Hw5Route as Route
from supp_bro.domain.support_intent import classify_support_intent, extract_issue_number
from supp_bro.tools import (
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

__all__ = [
    "AgentState",
    "DEFAULT_GITHUB_REPO",
    "DEFAULT_STACKOVERFLOW_TAG",
    "DEMO_CASES",
    "Route",
    "ToolName",
    "ToolObservation",
    "ToolRequest",
    "ToolType",
    "ask_clarifying_question",
    "build_final_answer",
    "build_tool_request",
    "classify_support_intent",
    "execute_tool_request",
    "extract_issue_number",
    "get_github_issue_context",
    "http_get_json",
    "normalize_stackoverflow_query",
    "render_demo_markdown",
    "render_markdown",
    "run_agent",
    "search_stackoverflow_questions",
    "validate_issue_number",
    "validate_repo",
    "validate_search_query",
    "validate_tag",
    "validate_tool_request",
]

USER_AGENT = "supp-bro-hw5-external-tool-demo"
DEMO_CASES = [
    {
        "name": "docs question",
        "question": "Can I get exactly once delivery?",
        "allow_external_community_search": False,
        "issue_number": None,
    },
    {
        "name": "explicit GitHub issue",
        "question": "Is Debezium issue #3 still open?",
        "allow_external_community_search": False,
        "issue_number": 3,
    },
    {
        "name": "known error mapped to issue",
        "question": "MongoDB connector backpressure error says unable to acquire buffer lock and queue is full",
        "allow_external_community_search": False,
        "issue_number": None,
    },
    {
        "name": "confirmed Stack Overflow lookup",
        "question": "Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?",
        "allow_external_community_search": True,
        "issue_number": None,
    },
    {
        "name": "clarification",
        "question": "Help",
        "allow_external_community_search": False,
        "issue_number": None,
    },
]


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


def render_demo_markdown(states: list[AgentState]) -> str:
    lines = [
        "# HW5 external tool demo",
        "",
        "This demo runs multiple deterministic support-assistant cases in one execution.",
        "",
        "| # | Question | Route | Tool | Success |",
        "|---:|---|---|---|---|",
    ]
    for index, state in enumerate(states, start=1):
        tool_name = state.tool_request.tool_name if state.tool_request else "none"
        success = state.observation.success if state.observation else False
        question = state.user_query.replace("|", "\\|")
        lines.append(f"| {index} | `{question}` | `{state.route}` | `{tool_name}` | `{success}` |")

    lines.append("")
    for index, state in enumerate(states, start=1):
        payload = asdict(state)
        lines.extend(
            [
                f"## Case {index}: {state.route}",
                "",
                f"User question: `{state.user_query}`",
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
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HW5 external tool router.")
    parser.add_argument("question", nargs="?", default="", help="User question to route.")
    parser.add_argument(
        "--mode",
        choices=["single", "demo"],
        default="single",
        help="Run one question or the built-in demo matrix.",
    )
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
    if args.mode == "single" and not args.question:
        raise SystemExit("question is required in single mode")

    if args.mode == "demo":
        states = [
            run_agent(
                question=case["question"],
                repo=args.repo,
                issue_number=case["issue_number"],
                allow_external_community_search=case["allow_external_community_search"],
                github_token=os.getenv("GITHUB_TOKEN"),
            )
            for case in DEMO_CASES
        ]
        payload = {"mode": "demo", "cases": [asdict(state) for state in states]}
        state_json = json.dumps(payload, indent=2, ensure_ascii=False)
        print(state_json)

        if args.output_json:
            Path(args.output_json).write_text(state_json + "\n", encoding="utf-8")
        if args.output_md:
            Path(args.output_md).write_text(render_demo_markdown(states), encoding="utf-8")
        return 0

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
