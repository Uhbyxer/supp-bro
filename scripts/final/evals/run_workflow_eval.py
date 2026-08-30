"""Run full-flow evaluation for the final SuppBro workflow."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
import sys

sys.path.insert(0, str(PROJECT_ROOT))

from scripts.final.langgraph_flow import run_langgraph_workflow  # noqa: E402

DEFAULT_CASES_PATH = PROJECT_ROOT / "scripts/final/evals/eval_cases.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "scripts/final/outputs"


def load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def tool_names(state: dict[str, Any]) -> list[str]:
    names = []
    for result in state.get("external_tool_results", []):
        name = result.get("tool_name")
        if name:
            names.append(name)
    return names


def retrieved_chunks(state: dict[str, Any]) -> str:
    chunk_ids: list[str] = []
    for rag_call in state.get("rag_calls", []):
        chunk_ids.extend((rag_call.get("retrieved_context_by_id") or {}).keys())
    return "; ".join(dict.fromkeys(chunk_ids)) or "none"


def route_or_mode(state: dict[str, Any]) -> str:
    route = state.get("selected_route", "unknown")
    if state.get("requires_clarification"):
        return "clarification"
    if state.get("fallback_used"):
        return f"{route}/fallback"
    if tool_names(state) and state.get("rag_calls"):
        return f"{route}/rag+tool"
    if tool_names(state):
        return f"{route}/tool"
    if state.get("rag_calls"):
        return f"{route}/rag"
    return route


def error_types(case: dict[str, Any], state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if state.get("selected_route") != case.get("expected_route"):
        errors.append("wrong_route")
    expected_tools = set(case.get("expected_tools") or [])
    actual_tools = set(tool_names(state))
    missing_tools = expected_tools - actual_tools
    unexpected_clarification = state.get("requires_clarification") and case.get("expected_route") != "clarification"
    if missing_tools:
        errors.append("missing_tool")
    if unexpected_clarification:
        errors.append("unexpected_clarification")
    for rag_call in state.get("rag_calls", []):
        status = rag_call.get("status")
        fallback_reason = rag_call.get("fallback_reason")
        if status in {"filter_fallback", "model_fallback"}:
            errors.append(fallback_reason or status)
    if state.get("fallback_used") and not errors:
        errors.append("fallback_used")
    return errors or ["none"]


def task_success(errors: list[str], state: dict[str, Any], case: dict[str, Any]) -> str:
    blocking = {"wrong_route", "missing_tool", "unexpected_clarification"}
    if any(error in blocking for error in errors):
        return "no"
    if state.get("selected_route") == case.get("expected_route") and not state.get("final_answer"):
        return "no"
    non_blocking = [error for error in errors if error != "none"]
    return "partial" if non_blocking else "yes"


def run_case(case: dict[str, Any], min_vector_score: float) -> dict[str, Any]:
    start = time.perf_counter()
    state = run_langgraph_workflow(
        question=case["question"],
        allow_external_community_search=case.get("allow_external_community_search", False),
        issue_number=case.get("issue_number"),
        min_vector_score=min_vector_score,
        enable_rag=True,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    errors = error_types(case, state)
    success = task_success(errors, state, case)
    return {
        "id": case["id"],
        "question": case["question"],
        "expected_behavior": case["expected_behavior"],
        "expected_route": case.get("expected_route", ""),
        "expected_tools": "; ".join(case.get("expected_tools") or []) or "none",
        "answer": state.get("final_answer", ""),
        "retrieved_chunks": retrieved_chunks(state),
        "actual_route": state.get("selected_route", "unknown"),
        "route_or_mode": route_or_mode(state),
        "tools_used": "; ".join(tool_names(state)) or "none",
        "task_success": success,
        "latency_ms": latency_ms,
        "errors": "; ".join(errors),
        "notes": f"Expected route: {case.get('expected_route')}; actual route: {state.get('selected_route')}",
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "id", "question", "expected_behavior", "expected_route", "expected_tools",
        "answer", "retrieved_chunks", "actual_route", "route_or_mode", "tools_used",
        "task_success", "latency_ms", "errors", "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def short_answer(answer: str, limit: int = 220) -> str:
    answer = " ".join(answer.split())
    return answer if len(answer) <= limit else answer[: limit - 1] + "…"


def write_summary(rows: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "## Deterministic workflow test cases",
        "",
        "| # | Question | Expected | Actual | Success | Latency | Errors |",
        "|---:|---|---|---|---|---:|---|",
    ]
    for row in rows:
        expected = f"{row['expected_behavior']}<br>route=`{row['expected_route']}`<br>tools=`{row['expected_tools']}`"
        actual = (
            f"route=`{row['actual_route']}`<br>mode=`{row['route_or_mode']}`<br>"
            f"tools=`{row['tools_used']}`<br>answer: {short_answer(row['answer'])}"
        )
        lines.append(
            f"| {row['id']} | {md(row['question'])} | {md(expected)} | {md(actual)} | "
            f"{row['task_success']} | {row['latency_ms']} ms | {md(row['errors'])} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run final SuppBro deterministic workflow evals.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-vector-score", type=float, default=0.30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [run_case(case, args.min_vector_score) for case in load_cases(args.cases)]
    write_csv(rows, args.output_dir / "eval_workflow_results.csv")
    write_summary(rows, args.output_dir / "eval_summary.md")
    print((args.output_dir / "eval_summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
