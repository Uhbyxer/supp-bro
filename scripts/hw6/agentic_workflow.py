"""HW6: controlled agentic workflow for SuppBro.

The workflow reuses HW4 retrieval and HW5 external tools, but keeps the
agentic control flow deterministic: route, plan, execute steps, record
observations, update state, and only then build the final answer.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is installed through requirements.txt
    load_dotenv = None
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "scripts/hw5"))

from external_tool_router import (  # noqa: E402
    DEFAULT_GITHUB_REPO,
    ToolObservation,
    build_tool_request,
    classify_support_intent,
    execute_tool_request,
)

WorkflowRoute = Literal["docs_answer", "issue_investigation", "community_lookup", "clarification"]
StepStatus = Literal["pending", "completed", "skipped", "failed"]

RAG_FALLBACK = "I do not have enough information in the retrieved context to answer this question."
DEFAULT_DEMO_CASES = [
    {
        "name": "docs retrieval",
        "question": "Can I get exactly once delivery?",
        "allow_external_community_search": False,
        "issue_number": None,
    },
    {
        "name": "known error with issue tool",
        "question": "Backpressure error says unable to acquire buffer lock and queue is full",
        "allow_external_community_search": False,
        "issue_number": None,
    },
    {
        "name": "explicit GitHub issue",
        "question": "Is Debezium issue #3 still open and who worked on it?",
        "allow_external_community_search": False,
        "issue_number": 3,
    },
    {
        "name": "confirmed community lookup",
        "question": "Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?",
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


@dataclass
class WorkflowStep:
    name: str
    purpose: str
    status: StepStatus = "pending"
    detail: str = ""


@dataclass
class RagObservation:
    source: str
    success: bool
    status: str
    answer: str = ""
    citations: list[str] = field(default_factory=list)
    retrieved_context_by_id: dict[str, Any] = field(default_factory=dict)
    fallback_reason: str | None = None
    error: str | None = None


@dataclass
class WorkflowState:
    user_goal: str
    selected_route: WorkflowRoute
    route_reason: str
    plan: list[WorkflowStep]
    current_step: str = ""
    completed_steps: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    rag_calls: list[RagObservation] = field(default_factory=list)
    retrieved_context: dict[str, Any] = field(default_factory=dict)
    external_tool_results: list[dict[str, Any]] = field(default_factory=list)
    requires_clarification: bool = False
    fallback_used: bool = False
    final_answer: str = ""


def map_hw5_route(route: str) -> WorkflowRoute:
    if route == "docs_question":
        return "docs_answer"
    if route in {"known_issue_question", "report_new_issue"}:
        return "issue_investigation" if route == "known_issue_question" else "clarification"
    if route == "community_troubleshooting":
        return "community_lookup"
    return "clarification"


def build_plan(route: WorkflowRoute) -> list[WorkflowStep]:
    common = [
        WorkflowStep("classify_intent", "Determine whether the user needs docs, issue metadata, community search, or clarification."),
    ]
    if route == "docs_answer":
        return common + [
            WorkflowStep("retrieve_docs", "Ask HW4 RAG to answer from documentation chunks."),
            WorkflowStep("compose_answer", "Return the grounded documentation answer with citations when available."),
        ]
    if route == "issue_investigation":
        return common + [
            WorkflowStep("retrieve_issues", "Ask HW4 RAG for local issue/document context."),
            WorkflowStep("read_github_issue", "Use the HW5 GitHub tool for live issue metadata."),
            WorkflowStep("compose_answer", "Combine retrieved context with live issue state."),
        ]
    if route == "community_lookup":
        return common + [
            WorkflowStep("retrieve_issues", "Check local context first, so external community results are not the only source."),
            WorkflowStep("search_community", "Use the HW5 Stack Overflow tool only when confirmation is enabled."),
            WorkflowStep("compose_answer", "Explain community results and their limits."),
        ]
    return common + [
        WorkflowStep("ask_clarifying_question", "Use the HW5 clarification tool instead of guessing."),
        WorkflowStep("compose_answer", "Return targeted follow-up questions."),
    ]


def mark_step(state: WorkflowState, name: str, status: StepStatus, detail: str = "") -> None:
    state.current_step = name
    for step in state.plan:
        if step.name == name:
            step.status = status
            step.detail = detail
            break
    if status == "completed" and name not in state.completed_steps:
        state.completed_steps.append(name)


def source_for_route(route: WorkflowRoute) -> str:
    return "pages" if route == "docs_answer" else "issues"


def run_hw4_rag(
    question: str,
    source: str,
    min_vector_score: float = 0.30,
    prompt_flavor: str = "strong",
    post_validator: str = "on",
    enabled: bool = True,
) -> RagObservation:
    if not enabled:
        return RagObservation(source=source, success=False, status="rag_disabled", fallback_reason="disabled_by_user")
    missing = [name for name in ("OPENAI_API_KEY", "PINECONE_API_KEY") if not os.getenv(name)]
    if missing:
        return RagObservation(
            source=source,
            success=False,
            status="rag_unavailable",
            fallback_reason=f"missing {'/'.join(missing)}",
            error="HW4 retrieval needs OpenAI and Pinecone credentials.",
        )

    command = [
        sys.executable,
        str(ROOT / "scripts/hw4/rag_answer.py"),
        question,
        "--source",
        source,
        "--prompt-flavor",
        prompt_flavor,
        "--post-validator",
        post_validator,
        "--min-vector-score",
        str(min_vector_score),
    ]
    try:
        completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return RagObservation(source=source, success=False, status="rag_timeout", fallback_reason="timeout", error="HW4 RAG timed out.")

    if completed.returncode != 0:
        return RagObservation(
            source=source,
            success=False,
            status="rag_failed",
            fallback_reason="subprocess_error",
            error=(completed.stderr or completed.stdout).strip(),
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return RagObservation(source=source, success=False, status="rag_failed", fallback_reason="invalid_json", error=str(exc))

    status = payload.get("status", "unknown")
    return RagObservation(
        source=source,
        success=status in {"grounded_answer", "unvalidated_answer"},
        status=status,
        answer=payload.get("answer", ""),
        citations=payload.get("citations") or [],
        retrieved_context_by_id=payload.get("retrieved_context_by_id") or {},
        fallback_reason=payload.get("fallback_reason"),
    )


def record_observation(state: WorkflowState, kind: str, payload: dict[str, Any]) -> None:
    state.observations.append({"kind": kind, **payload})


def tool_observation_to_dict(observation: ToolObservation) -> dict[str, Any]:
    return {
        "tool_name": observation.tool_name,
        "success": observation.success,
        "data": observation.data,
        "error": observation.error,
    }


def build_agent_answer(state: WorkflowState) -> str:
    rag = state.rag_calls[-1] if state.rag_calls else None
    tool = state.external_tool_results[-1] if state.external_tool_results else None

    if state.selected_route == "docs_answer":
        if rag and rag.success:
            citations = f" Citations: {', '.join(rag.citations)}." if rag.citations else ""
            return f"{rag.answer}{citations}"
        state.fallback_used = True
        return "I could not produce a grounded docs answer from HW4 retrieval in this run. Check the RAG observation for the exact reason."

    if state.selected_route == "issue_investigation":
        parts: list[str] = []
        if rag and rag.success and rag.answer != RAG_FALLBACK:
            parts.append(f"Local RAG context: {rag.answer}")
        elif rag:
            state.fallback_used = True
            parts.append(f"Local RAG did not produce a grounded answer ({rag.status}: {rag.fallback_reason or 'no reason'}).")
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
                state.fallback_used = True
                parts.append(f"GitHub issue tool failed: {tool.get('error')}")
        return " ".join(parts) if parts else "I need a concrete issue number or error signature to investigate this."

    if state.selected_route == "community_lookup":
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
        state.fallback_used = True
        return "External community search was not completed. The agent should ask for confirmation before using Stack Overflow."

    state.requires_clarification = True
    if tool and tool["success"] and tool["tool_name"] == "ask_clarifying_question":
        questions = " ".join(tool["data"].get("clarifying_questions", []))
        return f"I need more detail before choosing a reliable route. {questions}"
    return "I need a more specific Debezium question before choosing retrieval or an external tool."


def run_workflow(
    question: str,
    repo: str = DEFAULT_GITHUB_REPO,
    issue_number: int | None = None,
    allow_external_community_search: bool = False,
    github_token: str | None = None,
    min_vector_score: float = 0.30,
    enable_rag: bool = True,
) -> WorkflowState:
    hw5_route, route_reason = classify_support_intent(question)
    route = map_hw5_route(hw5_route)
    state = WorkflowState(user_goal=question, selected_route=route, route_reason=route_reason, plan=build_plan(route))

    mark_step(state, "classify_intent", "completed", f"HW5 route: {hw5_route}")
    record_observation(state, "route", {"hw5_route": hw5_route, "selected_route": route, "reason": route_reason})

    if route in {"docs_answer", "issue_investigation", "community_lookup"}:
        rag_step = "retrieve_docs" if route == "docs_answer" else "retrieve_issues"
        rag = run_hw4_rag(
            question=question,
            source=source_for_route(route),
            min_vector_score=min_vector_score,
            enabled=enable_rag,
        )
        state.rag_calls.append(rag)
        state.retrieved_context.update(rag.retrieved_context_by_id)
        mark_step(state, rag_step, "completed" if rag.success else "failed", rag.status)
        record_observation(state, "rag", asdict(rag))

    if route in {"issue_investigation", "community_lookup", "clarification"}:
        request = build_tool_request(
            route=hw5_route,
            question=question,
            repo=repo,
            issue_number=issue_number,
            allow_external_community_search=allow_external_community_search,
        )
        state.tool_calls.append(asdict(request))
        tool_step = {
            "issue_investigation": "read_github_issue",
            "community_lookup": "search_community",
            "clarification": "ask_clarifying_question",
        }[route]
        observation = execute_tool_request(request, github_token=github_token or os.getenv("GITHUB_TOKEN"))
        observation_dict = tool_observation_to_dict(observation)
        state.external_tool_results.append(observation_dict)
        state.requires_clarification = observation.tool_name == "ask_clarifying_question"
        mark_step(state, tool_step, "completed" if observation.success else "failed", observation.error or observation.tool_name)
        record_observation(state, "tool", observation_dict)

    state.final_answer = build_agent_answer(state)
    mark_step(state, "compose_answer", "completed", "Final answer created from normalized state.")
    return state


def render_markdown(state: WorkflowState) -> str:
    payload = asdict(state)
    tool_names = ", ".join(call["tool_name"] for call in state.tool_calls) or "none"
    rag_status = state.rag_calls[-1].status if state.rag_calls else "not_called"
    return "\n".join(
        [
            "# HW6 agentic workflow result",
            "",
            f"User goal: `{state.user_goal}`",
            "",
            f"Selected route: `{state.selected_route}`",
            "",
            f"Route reason: {state.route_reason}",
            "",
            f"RAG status: `{rag_status}`",
            "",
            f"Tool calls: `{tool_names}`",
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


def render_demo_markdown(states: list[WorkflowState]) -> str:
    lines = [
        "# HW6 agentic workflow demo",
        "",
        "Demo проганяє 5 різних питань через один контрольований workflow: route, plan, action, observation, state update і final answer.",
        "",
        "| # | Question | Route | RAG status | Tool | Needs clarification |",
        "|---:|---|---|---|---|---|",
    ]
    for index, state in enumerate(states, start=1):
        rag_status = state.rag_calls[-1].status if state.rag_calls else "not_called"
        tool = state.tool_calls[-1]["tool_name"] if state.tool_calls else "none"
        question = state.user_goal.replace("|", "\\|")
        lines.append(f"| {index} | `{question}` | `{state.selected_route}` | `{rag_status}` | `{tool}` | `{state.requires_clarification}` |")

    lines.append("")
    for index, state in enumerate(states, start=1):
        lines.extend(
            [
                f"## Case {index}: {state.selected_route}",
                "",
                f"User goal: `{state.user_goal}`",
                "",
                "Final answer:",
                "",
                state.final_answer,
                "",
                "State trace:",
                "",
                "```json",
                json.dumps(asdict(state), indent=2, ensure_ascii=False),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HW6 controlled agentic workflow.")
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
            run_workflow(
                question=case["question"],
                repo=args.repo,
                issue_number=case["issue_number"],
                allow_external_community_search=case["allow_external_community_search"],
                min_vector_score=args.min_vector_score,
                enable_rag=not args.disable_rag,
            )
            for case in DEFAULT_DEMO_CASES
        ]
        payload: dict[str, Any] = {"mode": "demo", "states": [asdict(state) for state in states]}
        markdown = render_demo_markdown(states)
    else:
        if not args.question:
            raise SystemExit("question is required in single mode")
        state = run_workflow(
            question=args.question,
            repo=args.repo,
            issue_number=args.issue_number,
            allow_external_community_search=args.allow_external_community_search,
            min_vector_score=args.min_vector_score,
            enable_rag=not args.disable_rag,
        )
        payload = {"mode": "single", "state": asdict(state)}
        markdown = render_markdown(state)

    if args.output_json:
        Path(args.output_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        Path(args.output_md).write_text(markdown, encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
