"""Provider-neutral contracts shared by workflow, retrieval, tool, and UI layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ToolType = Literal["read"]
ToolName = Literal[
    "get_github_issue_context",
    "search_stackoverflow_questions",
    "ask_clarifying_question",
    "none",
]
ObservationStatus = Literal["success", "unavailable", "failed", "skipped", "timeout"]
RunOutcome = Literal["success", "degraded", "needs_clarification", "failed"]


@dataclass
class ToolRequest:
    tool_name: ToolName
    tool_type: ToolType
    payload: dict[str, Any] = field(default_factory=dict)
    confirmed: bool = False


@dataclass
class ToolObservation:
    tool_name: ToolName
    success: bool
    status: ObservationStatus
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    source: str = ""
    raw_reference: str | None = None


@dataclass
class EvidenceObservation:
    source: str
    status: ObservationStatus
    snippet: str = ""
    citation_target: str = ""
    confidence: float | None = None
    raw_reference: str | None = None
    error: str | None = None


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
class TraceView:
    selected_route: str
    route_reason: str
    plan: list[dict[str, Any]]
    completed_steps: list[str]
    executed_nodes: list[str]
    observations: list[dict[str, Any]]
    rag_calls: list[dict[str, Any]]
    retrieved_context: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    external_tool_results: list[dict[str, Any]]
    outcome: RunOutcome
    requires_clarification: bool
    fallback_used: bool
    final_answer: str
