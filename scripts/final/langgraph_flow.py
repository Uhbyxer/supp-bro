"""Final project: route-aware SuppBro LangGraph workflow.

This module keeps the HW7 graph shape, but improves one weak point:
explicit GitHub issue metadata questions go directly to the GitHub tool
instead of running local issue RAG first. Community workaround search is modeled
as an optional augmentation after known issue investigation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is installed through requirements.txt
    load_dotenv = None
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT / "scripts/hw6"))
sys.path.insert(0, str(ROOT / "scripts/hw5"))

from agentic_workflow import (  # noqa: E402
    DEFAULT_GITHUB_REPO,
    RAG_FALLBACK,
    build_plan,
    map_hw5_route,
    run_hw4_rag,
    source_for_route,
    tool_observation_to_dict,
)
from external_tool_router import build_tool_request, classify_support_intent, execute_tool_request, extract_issue_number  # noqa: E402

WorkflowRoute = Literal["docs_answer", "issue_investigation", "community_lookup", "clarification"]

DEFAULT_DEMO_CASES = [
    {
        "name": "documentation answer",
        "question": "Can I get exactly once delivery with Debezium?",
        "allow_external_community_search": False,
        "issue_number": None,
    },
    {
        "name": "known issue explanation from local context",
        "question": "Explain the known Debezium MongoDB buffer lock problem from the local context.",
        "allow_external_community_search": False,
        "issue_number": None,
    },
    {
        "name": "explicit GitHub issue metadata",
        "question": "Is Debezium issue #3 still open and who worked on it?",
        "allow_external_community_search": False,
        "issue_number": 3,
    },
    {
        "name": "known issue with community workarounds",
        "question": "How to fix Debezium MongoDB buffer lock? Include possible community workarounds.",
        "allow_external_community_search": True,
        "issue_number": None,
    },
    {
        "name": "clarification",
        "question": "Help with Debezium",
        "allow_external_community_search": False,
        "issue_number": None,
    },
]


class AgentState(TypedDict, total=False):
    user_goal: str
    repo: str
    issue_number: int | None
    allow_external_community_search: bool
    github_token: str | None
    min_vector_score: float
    enable_rag: bool
    skip_issue_rag: bool
    search_community_after_issue: bool
    selected_route: WorkflowRoute
    route_reason: str
    plan: list[dict[str, Any]]
    current_step: str
    completed_steps: list[str]
    executed_nodes: list[str]
    tool_calls: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    rag_calls: list[dict[str, Any]]
    retrieved_context: dict[str, Any]
    external_tool_results: list[dict[str, Any]]
    requires_clarification: bool
    fallback_used: bool
    final_answer: str


def append_node(state: AgentState, node: str) -> None:
    state.setdefault("executed_nodes", []).append(node)
    state["current_step"] = node


def complete_step(state: AgentState, name: str, detail: str = "", failed: bool = False) -> None:
    state["current_step"] = name
    for step in state.get("plan", []):
        if step["name"] == name:
            step["status"] = "failed" if failed else "completed"
            step["detail"] = detail
            break
    if not failed:
        state.setdefault("completed_steps", []).append(name)


def classify_request(state: AgentState) -> AgentState:
    append_node(state, "classify_request")
    hw5_route, route_reason = classify_support_intent(state["user_goal"])
    selected_route = map_hw5_route(hw5_route)
    if selected_route == "community_lookup" and is_known_issue_context_request(state["user_goal"]):
        selected_route = "issue_investigation"
        route_reason = f"{route_reason} The question also describes a known issue, so local issue context is checked first."
    skip_issue_rag = should_skip_issue_rag(state, selected_route)
    search_community_after_issue = should_search_community_after_issue(state, selected_route, skip_issue_rag)
    state["selected_route"] = selected_route
    state["skip_issue_rag"] = skip_issue_rag
    state["search_community_after_issue"] = search_community_after_issue
    state["route_reason"] = route_reason
    state["plan"] = [asdict(step) for step in build_plan(selected_route)]
    if skip_issue_rag:
        state["plan"] = [step for step in state["plan"] if step["name"] != "retrieve_issues"]
        state["route_reason"] = f"{route_reason} Explicit issue metadata can be answered from GitHub directly."
    if search_community_after_issue:
        state["plan"].insert(
            -1,
            {
                "name": "search_community",
                "purpose": "Augment local issue context with Stack Overflow/community workaround signals.",
                "status": "pending",
                "detail": "",
            },
        )
    state.setdefault("observations", []).append(
        {
            "kind": "route",
            "hw5_route": hw5_route,
            "selected_route": selected_route,
            "reason": state["route_reason"],
            "skip_issue_rag": skip_issue_rag,
            "search_community_after_issue": search_community_after_issue,
        }
    )
    complete_step(state, "classify_intent", f"HW5 route: {hw5_route}")
    return state


def is_known_issue_context_request(question: str) -> bool:
    text = question.lower()
    return any(
        token in text
        for token in [
            "buffer lock",
            "queue is full",
            "backpressure",
            "error",
            "exception",
            "unable to",
            "known issue",
            "problem",
        ]
    )


def should_skip_issue_rag(state: AgentState, selected_route: WorkflowRoute) -> bool:
    if selected_route != "issue_investigation":
        return False
    question = state["user_goal"]
    text = question.lower()
    has_issue_number = state.get("issue_number") is not None or extract_issue_number(question) is not None
    asks_for_live_metadata = any(
        token in text
        for token in [
            "still open",
            "open",
            "closed",
            "state",
            "status",
            "who worked",
            "worked on",
            "assignee",
            "assignees",
            "labels",
            "participants",
            "comments",
            "updated",
        ]
    )
    return has_issue_number and asks_for_live_metadata


def should_search_community_after_issue(state: AgentState, selected_route: WorkflowRoute, skip_issue_rag: bool) -> bool:
    if selected_route != "issue_investigation" or skip_issue_rag:
        return False
    if not state.get("allow_external_community_search", False):
        return False
    text = state["user_goal"].lower()
    return any(token in text for token in ["workaround", "community", "stack overflow", "stackoverflow", "anyone seen"])


def route_after_classification(state: AgentState) -> str:
    if state["selected_route"] == "issue_investigation" and state.get("skip_issue_rag"):
        return "github_issue_metadata"
    return state["selected_route"]


def route_after_github_issue(state: AgentState) -> str:
    if state.get("search_community_after_issue"):
        return "search_community"
    return "build_answer"


def run_docs_rag(state: AgentState) -> AgentState:
    append_node(state, "run_docs_rag")
    return run_rag_step(state, "retrieve_docs")


def run_issue_rag(state: AgentState) -> AgentState:
    append_node(state, "run_issue_rag")
    return run_rag_step(state, "retrieve_issues")


def run_community_rag(state: AgentState) -> AgentState:
    append_node(state, "run_community_rag")
    return run_rag_step(state, "retrieve_issues")


def run_rag_step(state: AgentState, step_name: str) -> AgentState:
    rag = run_hw4_rag(
        question=state["user_goal"],
        source=source_for_route(state["selected_route"]),
        min_vector_score=state.get("min_vector_score", 0.30),
        enabled=state.get("enable_rag", True),
    )
    rag_payload = asdict(rag)
    state.setdefault("rag_calls", []).append(rag_payload)
    state.setdefault("retrieved_context", {}).update(rag.retrieved_context_by_id)
    state.setdefault("observations", []).append({"kind": "rag", **rag_payload})
    complete_step(state, step_name, rag.status, failed=not rag.success)
    return state


def read_github_issue(state: AgentState) -> AgentState:
    append_node(state, "read_github_issue")
    return run_tool_step(state, "read_github_issue")


def search_community(state: AgentState) -> AgentState:
    append_node(state, "search_community")
    return run_tool_step(state, "search_community")


def ask_clarification(state: AgentState) -> AgentState:
    append_node(state, "ask_clarification")
    return run_tool_step(state, "ask_clarifying_question")


def run_tool_step(state: AgentState, step_name: str) -> AgentState:
    hw5_route, _ = classify_support_intent(state["user_goal"])
    if step_name == "read_github_issue":
        hw5_route = "known_issue_question"
    elif step_name == "search_community":
        hw5_route = "community_troubleshooting"
    elif step_name == "ask_clarifying_question":
        hw5_route = "clarification"
    request = build_tool_request(
        route=hw5_route,
        question=state["user_goal"],
        repo=state.get("repo", DEFAULT_GITHUB_REPO),
        issue_number=state.get("issue_number"),
        allow_external_community_search=state.get("allow_external_community_search", False),
    )
    request_payload = asdict(request)
    observation = execute_tool_request(request, github_token=state.get("github_token") or os.getenv("GITHUB_TOKEN"))
    observation_payload = tool_observation_to_dict(observation)
    state.setdefault("tool_calls", []).append(request_payload)
    state.setdefault("external_tool_results", []).append(observation_payload)
    state.setdefault("observations", []).append({"kind": "tool", **observation_payload})
    state["requires_clarification"] = observation.tool_name == "ask_clarifying_question"
    complete_step(state, step_name, observation.error or observation.tool_name, failed=not observation.success)
    return state


def build_answer(state: AgentState) -> AgentState:
    append_node(state, "build_answer")
    state["final_answer"] = answer_from_state(state)
    complete_step(state, "compose_answer", "Final answer created from LangGraph state.")
    return state


def answer_from_state(state: AgentState) -> str:
    route = state["selected_route"]
    rag = state.get("rag_calls", [])[-1] if state.get("rag_calls") else None
    tool_results = state.get("external_tool_results", [])
    tool = tool_results[-1] if tool_results else None
    github_tool = next((item for item in tool_results if item["tool_name"] == "get_github_issue_context"), None)
    community_tool = next((item for item in tool_results if item["tool_name"] == "search_stackoverflow_questions"), None)

    if route == "docs_answer":
        if rag and rag.get("success"):
            citations = f" Citations: {', '.join(rag.get('citations') or [])}." if rag.get("citations") else ""
            return f"{rag.get('answer', '')}{citations}"
        state["fallback_used"] = True
        return "I could not produce a grounded docs answer from HW4 retrieval in this run. Check the RAG observation for the exact reason."

    if route == "issue_investigation":
        parts: list[str] = []
        if rag and rag.get("success") and rag.get("answer") != RAG_FALLBACK:
            parts.append(f"Local RAG context: {rag.get('answer')}")
        elif rag:
            state["fallback_used"] = True
            parts.append(f"Local RAG did not produce a grounded answer ({rag.get('status')}: {rag.get('fallback_reason') or 'no reason'}).")
        if github_tool:
            if github_tool["success"]:
                data = github_tool["data"]
                labels = ", ".join(data.get("labels") or []) or "no labels"
                assignees = ", ".join(data.get("assignees") or []) or "no assignees"
                parts.append(
                    f"Live GitHub issue {data['repo']}#{data['issue_number']} is {data['state']}: "
                    f"{data['title']}. Labels: {labels}; assignees: {assignees}; "
                    f"comments: {data['comment_count']}; updated: {data['updated_at']}. URL: {data['url']}"
                )
            else:
                state["fallback_used"] = True
                parts.append(f"GitHub issue tool failed: {github_tool.get('error')}")
        if community_tool:
            if community_tool["success"]:
                data = community_tool["data"]
                if data.get("count", 0) == 0:
                    parts.append("No matching Stack Overflow questions were found for the community workaround check.")
                else:
                    top = data["results"][0]
                    parts.append(
                        f"Community workaround check found {data['count']} Stack Overflow questions tagged {data['tag']}. "
                        f"Top result: {top['title']} (score: {top['score']}, answers: {top['answer_count']}). URL: {top['url']}"
                    )
            else:
                parts.append(f"Community workaround search failed: {community_tool.get('error')}")
        return " ".join(parts) if parts else "I need a concrete issue number or error signature to investigate this."

    if route == "community_lookup":
        if tool and tool["success"] and tool["tool_name"] == "search_stackoverflow_questions":
            data = tool["data"]
            if data.get("count", 0) == 0:
                return "I did not find matching Stack Overflow questions. Local RAG observation is available in the trace."
            top = data["results"][0]
            return (
                f"Found {data['count']} Stack Overflow questions tagged {data['tag']}. "
                f"Top result: {top['title']} (score: {top['score']}, answers: {top['answer_count']}). "
                f"Community results are useful for similar symptoms, but should be checked against docs or GitHub issues. URL: {top['url']}"
            )
        state["fallback_used"] = True
        return "External community search was not completed. The agent should ask for confirmation before using Stack Overflow."

    state["requires_clarification"] = True
    if tool and tool["success"] and tool["tool_name"] == "ask_clarifying_question":
        questions = " ".join(tool["data"].get("clarifying_questions", []))
        return f"I need more detail before choosing a reliable route. {questions}"
    return "I need a more specific Debezium question before choosing retrieval or an external tool."


def create_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("classify_request", classify_request)
    workflow.add_node("run_docs_rag", run_docs_rag)
    workflow.add_node("run_issue_rag", run_issue_rag)
    workflow.add_node("run_community_rag", run_community_rag)
    workflow.add_node("read_github_issue", read_github_issue)
    workflow.add_node("search_community", search_community)
    workflow.add_node("ask_clarification", ask_clarification)
    workflow.add_node("build_answer", build_answer)

    workflow.set_entry_point("classify_request")
    workflow.add_conditional_edges(
        "classify_request",
        route_after_classification,
        {
            "docs_answer": "run_docs_rag",
            "issue_investigation": "run_issue_rag",
            "github_issue_metadata": "read_github_issue",
            "community_lookup": "run_community_rag",
            "clarification": "ask_clarification",
        },
    )
    workflow.add_edge("run_docs_rag", "build_answer")
    workflow.add_edge("run_issue_rag", "read_github_issue")
    workflow.add_edge("run_community_rag", "search_community")
    workflow.add_conditional_edges(
        "read_github_issue",
        route_after_github_issue,
        {
            "search_community": "search_community",
            "build_answer": "build_answer",
        },
    )
    workflow.add_edge("search_community", "build_answer")
    workflow.add_edge("ask_clarification", "build_answer")
    workflow.add_edge("build_answer", END)
    return workflow.compile()


def initial_state(
    question: str,
    repo: str = DEFAULT_GITHUB_REPO,
    issue_number: int | None = None,
    allow_external_community_search: bool = False,
    github_token: str | None = None,
    min_vector_score: float = 0.30,
    enable_rag: bool = True,
) -> AgentState:
    return {
        "user_goal": question,
        "repo": repo,
        "issue_number": issue_number,
        "allow_external_community_search": allow_external_community_search,
        "github_token": github_token,
        "min_vector_score": min_vector_score,
        "enable_rag": enable_rag,
        "skip_issue_rag": False,
        "search_community_after_issue": False,
        "plan": [],
        "current_step": "",
        "completed_steps": [],
        "executed_nodes": [],
        "tool_calls": [],
        "observations": [],
        "rag_calls": [],
        "retrieved_context": {},
        "external_tool_results": [],
        "requires_clarification": False,
        "fallback_used": False,
        "final_answer": "",
    }


def run_langgraph_workflow(
    question: str,
    repo: str = DEFAULT_GITHUB_REPO,
    issue_number: int | None = None,
    allow_external_community_search: bool = False,
    github_token: str | None = None,
    min_vector_score: float = 0.30,
    enable_rag: bool = True,
) -> AgentState:
    app = create_graph()
    result = app.invoke(
        initial_state(
            question=question,
            repo=repo,
            issue_number=issue_number,
            allow_external_community_search=allow_external_community_search,
            github_token=github_token,
            min_vector_score=min_vector_score,
            enable_rag=enable_rag,
        )
    )
    return result


def render_markdown(state: AgentState) -> str:
    rag_status = state["rag_calls"][-1]["status"] if state.get("rag_calls") else "not_called"
    tool_names = ", ".join(call["tool_name"] for call in state.get("tool_calls", [])) or "none"
    return "\n".join(
        [
            "# Final LangGraph workflow result",
            "",
            f"User goal: `{state['user_goal']}`",
            "",
            f"Selected route: `{state['selected_route']}`",
            "",
            f"Executed nodes: `{' -> '.join(state['executed_nodes'])}`",
            "",
            f"RAG status: `{rag_status}`",
            "",
            f"Tool calls: `{tool_names}`",
            "",
            "Final answer:",
            "",
            state["final_answer"],
            "",
            "Final state:",
            "",
            "```json",
            json.dumps(state, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )


def render_demo_markdown(states: list[AgentState]) -> str:
    lines = [
        "# Final LangGraph workflow demo",
        "",
        "Demo проганяє 5 питань через фінальний route-aware SuppBro workflow.",
        "",
        "| # | Question | Route | Executed nodes | RAG status | Tool | Needs clarification |",
        "|---:|---|---|---|---|---|---|",
    ]
    for index, state in enumerate(states, start=1):
        rag_status = state["rag_calls"][-1]["status"] if state.get("rag_calls") else "not_called"
        tool = state["tool_calls"][-1]["tool_name"] if state.get("tool_calls") else "none"
        question = state["user_goal"].replace("|", "\\|")
        nodes = " -> ".join(state["executed_nodes"])
        lines.append(
            f"| {index} | `{question}` | `{state['selected_route']}` | `{nodes}` | `{rag_status}` | `{tool}` | `{state['requires_clarification']}` |"
        )

    lines.append("")
    for index, state in enumerate(states, start=1):
        lines.extend(
            [
                f"## Case {index}: {state['selected_route']}",
                "",
                f"Input question: `{state['user_goal']}`",
                "",
                f"Executed nodes: `{' -> '.join(state['executed_nodes'])}`",
                "",
                "Final answer:",
                "",
                state["final_answer"],
                "",
                "Final state:",
                "",
                "```json",
                json.dumps(state, indent=2, ensure_ascii=False),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run final route-aware LangGraph workflow.")
    parser.add_argument("question", nargs="?", default="", help="User question for single mode.")
    parser.add_argument("--mode", choices=["single", "demo"], default="single")
    parser.add_argument("--repo", default=DEFAULT_GITHUB_REPO)
    parser.add_argument("--issue-number", type=int, default=None)
    parser.add_argument("--allow-external-community-search", action="store_true")
    parser.add_argument("--disable-rag", action="store_true", help="Skip HW4 RAG call and record rag_disabled observation.")
    parser.add_argument("--min-vector-score", type=float, default=0.30)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "demo":
        states = [
            run_langgraph_workflow(
                question=case["question"],
                repo=args.repo,
                issue_number=case["issue_number"],
                allow_external_community_search=case["allow_external_community_search"],
                min_vector_score=args.min_vector_score,
                enable_rag=not args.disable_rag,
            )
            for case in DEFAULT_DEMO_CASES
        ]
        payload: dict[str, Any] = {"mode": "demo", "states": states}
        markdown = render_demo_markdown(states)
    else:
        if not args.question:
            raise SystemExit("question is required in single mode")
        state = run_langgraph_workflow(
            question=args.question,
            repo=args.repo,
            issue_number=args.issue_number,
            allow_external_community_search=args.allow_external_community_search,
            min_vector_score=args.min_vector_score,
            enable_rag=not args.disable_rag,
        )
        payload = {"mode": "single", "state": state}
        markdown = render_markdown(state)

    if args.output_json:
        Path(args.output_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        Path(args.output_md).write_text(markdown, encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
