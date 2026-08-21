"""HW7: LangGraph implementation of the SuppBro agentic workflow.

This module keeps the HW6 behavior, but moves orchestration to LangGraph:
state is a TypedDict, steps are graph nodes, and route selection is a
conditional edge after classification.
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
    DEFAULT_DEMO_CASES,
    DEFAULT_GITHUB_REPO,
    RAG_FALLBACK,
    build_plan,
    map_hw5_route,
    run_hw4_rag,
    source_for_route,
    tool_observation_to_dict,
)
from external_tool_router import build_tool_request, classify_support_intent, execute_tool_request  # noqa: E402

WorkflowRoute = Literal["docs_answer", "issue_investigation", "community_lookup", "clarification"]


class AgentState(TypedDict, total=False):
    user_goal: str
    repo: str
    issue_number: int | None
    allow_external_community_search: bool
    github_token: str | None
    min_vector_score: float
    enable_rag: bool
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
    state["selected_route"] = selected_route
    state["route_reason"] = route_reason
    state["plan"] = [asdict(step) for step in build_plan(selected_route)]
    state.setdefault("observations", []).append(
        {"kind": "route", "hw5_route": hw5_route, "selected_route": selected_route, "reason": route_reason}
    )
    complete_step(state, "classify_intent", f"HW5 route: {hw5_route}")
    return state


def route_after_classification(state: AgentState) -> str:
    return state["selected_route"]


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
    tool = state.get("external_tool_results", [])[-1] if state.get("external_tool_results") else None

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
        if tool:
            if tool["success"] and tool["tool_name"] == "get_github_issue_context":
                data = tool["data"]
                labels = ", ".join(data.get("labels") or []) or "no labels"
                assignees = ", ".join(data.get("assignees") or []) or "no assignees"
                parts.append(
                    f"Live GitHub issue {data['repo']}#{data['issue_number']} is {data['state']}: "
                    f"{data['title']}. Labels: {labels}; assignees: {assignees}; "
                    f"comments: {data['comment_count']}; updated: {data['updated_at']}. URL: {data['url']}"
                )
            else:
                state["fallback_used"] = True
                parts.append(f"GitHub issue tool failed: {tool.get('error')}")
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
            "community_lookup": "run_community_rag",
            "clarification": "ask_clarification",
        },
    )
    workflow.add_edge("run_docs_rag", "build_answer")
    workflow.add_edge("run_issue_rag", "read_github_issue")
    workflow.add_edge("run_community_rag", "search_community")
    workflow.add_edge("read_github_issue", "build_answer")
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
            "# HW7 LangGraph workflow result",
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
        "# HW7 LangGraph workflow demo",
        "",
        "Demo проганяє 5 питань через LangGraph implementation того самого SuppBro workflow з HW6.",
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
    parser = argparse.ArgumentParser(description="Run HW7 LangGraph workflow.")
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
