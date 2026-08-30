"""Run HW8-style evaluation for the final SuppBro workflow."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from collections import Counter
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
        if status in {"filter_fallback", "model_fallback", "rag_disabled"}:
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


def groundedness(state: dict[str, Any], success: str) -> str:
    if state.get("requires_clarification"):
        return "not_applicable"
    has_evidence = bool(state.get("retrieved_context")) or bool(state.get("external_tool_results"))
    if success == "yes" and has_evidence:
        return "good"
    if has_evidence:
        return "partial"
    return "bad"


def answer_quality(state: dict[str, Any], success: str) -> str:
    if not state.get("final_answer"):
        return "bad"
    if success == "yes":
        return "good"
    if success == "partial":
        return "partial"
    return "bad"


def run_case(case: dict[str, Any], disable_rag: bool, min_vector_score: float) -> dict[str, Any]:
    start = time.perf_counter()
    state = run_langgraph_workflow(
        question=case["question"],
        allow_external_community_search=case.get("allow_external_community_search", False),
        issue_number=case.get("issue_number"),
        min_vector_score=min_vector_score,
        enable_rag=not disable_rag,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    errors = error_types(case, state)
    success = task_success(errors, state, case)
    return {
        "id": case["id"],
        "question": case["question"],
        "expected_behavior": case["expected_behavior"],
        "answer": state.get("final_answer", ""),
        "retrieved_chunks": retrieved_chunks(state),
        "route_or_mode": route_or_mode(state),
        "tools_used": "; ".join(tool_names(state)) or "none",
        "task_success": success,
        "groundedness": groundedness(state, success),
        "answer_quality": answer_quality(state, success),
        "latency_ms": latency_ms,
        "errors": "; ".join(errors),
        "notes": f"Expected route: {case.get('expected_route')}; actual route: {state.get('selected_route')}",
        "state": state,
        "ground_truth": case.get("ground_truth", ""),
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "id", "question", "expected_behavior", "answer", "retrieved_chunks",
        "route_or_mode", "tools_used", "task_success", "groundedness",
        "answer_quality", "latency_ms", "errors", "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fieldnames})


def write_summary(rows: list[dict[str, Any]], path: Path) -> None:
    total = len(rows)
    successes = sum(row["task_success"] == "yes" for row in rows)
    grounded_good = sum(row["groundedness"] == "good" for row in rows)
    avg_latency = int(statistics.mean(row["latency_ms"] for row in rows)) if rows else 0
    errors = Counter(error for row in rows for error in row["errors"].split("; "))
    error_summary = ", ".join(f"{error}: {count}" for error, count in errors.most_common()) or "none"
    success_rate = f"{successes}/{total} ({successes / total:.0%})" if total else "n/a"
    grounded_rate = f"{grounded_good}/{total} ({grounded_good / total:.0%})" if total else "n/a"
    lines = [
        "## Deterministic workflow metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total cases | {total} |",
        f"| Success rate | {success_rate} |",
        f"| Groundedness good rate | {grounded_rate} |",
        f"| Average latency | {avg_latency} ms |",
        f"| Error types | {error_summary} |",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ragas_input(rows: list[dict[str, Any]], path: Path) -> None:
    payload = []
    for row in rows:
        state = row["state"]
        contexts: list[str] = []
        for rag_call in state.get("rag_calls", []):
            contexts.extend((rag_call.get("retrieved_context_by_id") or {}).values())
        for tool_result in state.get("external_tool_results", []):
            contexts.append(json.dumps(tool_result, ensure_ascii=False))
        payload.append({
            "id": row["id"], "question": row["question"], "answer": row["answer"],
            "contexts": contexts[:5], "ground_truth": row["ground_truth"],
        })
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run final SuppBro workflow evals.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--disable-rag", action="store_true")
    parser.add_argument("--min-vector-score", type=float, default=0.30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [run_case(case, args.disable_rag, args.min_vector_score) for case in load_cases(args.cases)]
    write_csv(rows, args.output_dir / "eval_workflow_results.csv")
    write_summary(rows, args.output_dir / "eval_summary.md")
    write_ragas_input(rows, args.output_dir / "ragas_input.json")
    print((args.output_dir / "eval_summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
