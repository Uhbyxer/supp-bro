from __future__ import annotations

import unittest

from supp_bro.domain.contracts import RagObservation, ToolObservation, ToolRequest
from supp_bro.domain.state import WorkflowState, WorkflowStep


class DomainStateTest(unittest.TestCase):
    def test_default_workflow_state_collections_are_isolated(self) -> None:
        first = WorkflowState(user_goal="Can I get exactly once delivery?")
        second = WorkflowState(user_goal="Help")

        first.completed_steps.append("classify_intent")
        first.executed_nodes.append("classify_request")
        first.observations.append({"kind": "route"})
        first.retrieved_context["chunk-1"] = {"text": "context"}

        self.assertEqual(second.completed_steps, [])
        self.assertEqual(second.executed_nodes, [])
        self.assertEqual(second.observations, [])
        self.assertEqual(second.retrieved_context, {})
        self.assertEqual(second.final_answer, "")

    def test_state_to_trace_projection_contains_canonical_fields(self) -> None:
        state = WorkflowState(
            user_goal="Is Debezium issue #3 still open?",
            selected_route="issue_investigation",
            route_reason="The user asks about current GitHub issue metadata.",
            plan=[WorkflowStep("classify_intent", "Route the request.")],
        )
        state.append_node("classify_request")
        state.mark_step("classify_intent", "completed", "HW5 route: known_issue_question")
        state.tool_calls.append(
            ToolRequest(
                tool_name="get_github_issue_context",
                tool_type="read",
                payload={"repo": "debezium/dbz", "issue_number": 3},
            )
        )
        state.rag_calls.append(RagObservation(source="issues", success=False, status="rag_unavailable"))
        state.final_answer = "Check the trace for unavailable providers."

        trace = state.to_trace_view()

        self.assertEqual(trace.selected_route, "issue_investigation")
        self.assertEqual(trace.plan[0]["status"], "completed")
        self.assertEqual(trace.completed_steps, ["classify_intent"])
        self.assertEqual(trace.executed_nodes, ["classify_request"])
        self.assertEqual(trace.tool_calls[0]["tool_name"], "get_github_issue_context")
        self.assertEqual(trace.rag_calls[0]["status"], "rag_unavailable")
        self.assertEqual(trace.final_answer, "Check the trace for unavailable providers.")

    def test_mark_step_rejects_unknown_step(self) -> None:
        state = WorkflowState(user_goal="Help", plan=[WorkflowStep("classify_intent", "Route the request.")])

        with self.assertRaises(KeyError):
            state.mark_step("compose_answer", "completed")

    def test_trace_projection_deep_copies_mapping_items(self) -> None:
        state = WorkflowState(user_goal="Help")
        state.observations.append({"kind": "route", "data": {"route": "clarification"}})
        state.retrieved_context["chunk-1"] = {"text": "context"}

        trace = state.to_trace_view()
        state.observations[0]["data"]["route"] = "docs_answer"
        state.retrieved_context["chunk-1"]["text"] = "changed"

        self.assertEqual(trace.observations[0]["data"]["route"], "clarification")
        self.assertEqual(trace.retrieved_context["chunk-1"]["text"], "context")

    def test_trace_projection_rejects_invalid_items(self) -> None:
        state = WorkflowState(user_goal="Help")
        state.observations.append("bad item")  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            state.to_trace_view()

    def test_unavailable_provider_observation_is_domain_data_only(self) -> None:
        observation = ToolObservation(
            tool_name="get_github_issue_context",
            success=False,
            status="unavailable",
            error="missing GITHUB_TOKEN",
            source="github",
        )

        self.assertFalse(observation.success)
        self.assertEqual(observation.status, "unavailable")
        self.assertEqual(observation.data, {})
        self.assertIsNone(observation.raw_reference)
        self.assertNotIn("secret", (observation.error or "").lower())
