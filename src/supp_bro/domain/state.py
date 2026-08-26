"""Canonical workflow state and trace projection for product workflows."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal, Mapping

from supp_bro.domain.contracts import RagObservation, RunOutcome, ToolObservation, ToolRequest, TraceView
from supp_bro.domain.routes import ProductRoute

StepStatus = Literal["pending", "completed", "skipped", "failed"]


@dataclass
class WorkflowStep:
    name: str
    purpose: str
    status: StepStatus = "pending"
    detail: str = ""


@dataclass
class WorkflowState:
    user_goal: str
    selected_route: ProductRoute = "clarification"
    route_reason: str = ""
    plan: list[WorkflowStep] = field(default_factory=list)
    current_step: str = ""
    completed_steps: list[str] = field(default_factory=list)
    executed_nodes: list[str] = field(default_factory=list)
    tool_calls: list[ToolRequest | dict[str, Any]] = field(default_factory=list)
    observations: list[ToolObservation | dict[str, Any]] = field(default_factory=list)
    rag_calls: list[RagObservation] = field(default_factory=list)
    retrieved_context: dict[str, Any] = field(default_factory=dict)
    external_tool_results: list[ToolObservation | dict[str, Any]] = field(default_factory=list)
    outcome: RunOutcome = "success"
    requires_clarification: bool = False
    fallback_used: bool = False
    final_answer: str = ""

    def mark_step(self, name: str, status: StepStatus, detail: str = "") -> None:
        self.current_step = name
        for step in self.plan:
            if step.name == name:
                step.status = status
                step.detail = detail
                if status == "completed" and name not in self.completed_steps:
                    self.completed_steps.append(name)
                return
        raise KeyError(f"Unknown workflow step: {name}")

    def append_node(self, node: str) -> None:
        self.executed_nodes.append(node)
        self.current_step = node

    def to_trace_view(self) -> TraceView:
        return TraceView(
            selected_route=self.selected_route,
            route_reason=self.route_reason,
            plan=[asdict(step) for step in self.plan],
            completed_steps=list(self.completed_steps),
            executed_nodes=list(self.executed_nodes),
            observations=[_to_dict(item) for item in self.observations],
            rag_calls=[asdict(item) for item in self.rag_calls],
            retrieved_context=deepcopy(self.retrieved_context),
            tool_calls=[_to_dict(item) for item in self.tool_calls],
            external_tool_results=[_to_dict(item) for item in self.external_tool_results],
            outcome=self.outcome,
            requires_clarification=self.requires_clarification,
            fallback_used=self.fallback_used,
            final_answer=self.final_answer,
        )


def _to_dict(item: Any) -> dict[str, Any]:
    if is_dataclass(item):
        return asdict(item)
    if isinstance(item, Mapping):
        return deepcopy(dict(item))
    raise TypeError(f"Trace item must be a dataclass or mapping, got {type(item).__name__}")
