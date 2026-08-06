"""Utilities for comparing an evaluation report with the previous workflow run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EPSILON = 1e-12


def compare_with_previous(
    current_metrics: dict[str, float],
    previous_path: Path,
    pipeline_key: str,
) -> dict[str, Any]:
    """Compare current aggregate metrics with the same pipeline in an older report."""
    if not previous_path.exists():
        return {
            "available": False,
            "previous_report": str(previous_path),
            "verdict": "No previous successful run was found; this run becomes the comparison baseline.",
        }

    try:
        previous_report = json.loads(previous_path.read_text(encoding="utf-8"))
        previous_metrics = previous_report["aggregate"][pipeline_key]
        missing = sorted(set(current_metrics) - set(previous_metrics))
        if missing:
            raise KeyError(f"missing metrics: {', '.join(missing)}")
        previous_metrics = {name: float(previous_metrics[name]) for name in current_metrics}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return {
            "available": False,
            "previous_report": str(previous_path),
            "verdict": f"Previous report could not be compared: {exc}.",
        }

    delta = {name: current_metrics[name] - previous_metrics[name] for name in current_metrics}
    improved = [name for name, value in delta.items() if value > EPSILON]
    regressed = [name for name, value in delta.items() if value < -EPSILON]
    if improved and not regressed:
        verdict = "Improved versus the previous successful run with no measured regression."
    elif improved and regressed:
        verdict = "Mixed result versus the previous successful run: some metrics improved and others regressed."
    elif regressed:
        verdict = "Regressed versus the previous successful run."
    else:
        verdict = "No metric changed versus the previous successful run."
    return {
        "available": True,
        "previous_report": str(previous_path),
        "previous": previous_metrics,
        "current": current_metrics,
        "delta": delta,
        "improved_metrics": improved,
        "regressed_metrics": regressed,
        "verdict": verdict,
    }


def previous_comparison_markdown(comparison: dict[str, Any], pipeline_label: str) -> list[str]:
    lines = ["## Current run vs previous successful run", ""]
    if not comparison["available"]:
        return lines + [comparison["verdict"], ""]

    previous = comparison["previous"]
    current = comparison["current"]
    delta = comparison["delta"]
    lines.extend(
        [
            f"Pipeline compared: **{pipeline_label}**.",
            "",
            "| Metric | Previous | Current | Delta |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for name in current:
        lines.append(f"| {name} | {previous[name]:.3f} | {current[name]:.3f} | {delta[name]:+.3f} |")
    lines.extend(["", f"**Previous-run verdict:** {comparison['verdict']}", ""])
    return lines
