---
title: 'Establish src/supp_bro package skeleton'
type: 'feature'
created: '2026-08-25'
status: 'done'
baseline_commit: '4ff811d871d607a39a6285c89f3a9bc0800e160d'
review_loop_iteration: 0
context:
  - _bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** SuppBro still has only homework-style scripts and path-mutating tests, so new product code has no stable package import contract or shared domain language. This makes later BMAD build slices likely to duplicate route names, workflow state fields, and tool/RAG payload shapes.

**Approach:** Add the first `src/supp_bro` package slice with package metadata, domain route/state/contract modules, and focused unit tests. Preserve all `scripts/hw*` behavior by adding new product scaffolding only, without importing it from homework scripts yet.

## Boundaries & Constraints

**Always:** Follow the architecture spine AD-1 through AD-9. Route and status string values must match HW5/HW6/HW7 exactly. `domain.state.WorkflowState` is the canonical product workflow state for future slices. Tests must run without live OpenAI, Pinecone, GitHub, Stack Overflow, MongoDB, or other provider credentials.

**Ask First:** Halt before changing any `scripts/hw*` behavior, replacing `requirements.txt`/Makefile workflow, choosing a long-term retrieval backend, or adding runtime dependencies not already present.

**Never:** Do not migrate HW4-HW7 implementation logic in this slice. Do not add external API calls, `.env` loading, Streamlit UI, LangGraph graph construction, or provider clients. Do not print or persist `MONGODB_URI`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Package import | Fresh checkout with editable install or test path setup | `import supp_bro` and imports from `supp_bro.domain` succeed | Import failures fail focused unit tests |
| Route mapping | HW5 route `report_new_issue` | Product route mapping returns `clarification`, matching HW6 behavior | Unknown HW5 routes map to or raise through a tested explicit path |
| Empty state | Construct default `WorkflowState` for a user goal | Lists/dicts/flags default independently and final answer starts empty | Mutable defaults must not be shared between instances |
| Provider unavailable | Domain observation represents missing credentials or provider failure | Observation is a typed data object with status/outcome fields, no live call | No exception or secret output is required for domain tests |

</frozen-after-approval>

## Code Map

- `AGENTS.md` -- Repo-level BMAD quick-dev rules: new product code goes under `src/supp_bro`; do not grow homework scripts; preserve HW behavior unless intentionally replacing it.
- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md` -- Binding architecture: layered ports-and-adapters, canonical `domain.state.WorkflowState`, domain route/contracts ownership, capability-scoped provider availability, and first product slice import contract.
- `README.md` -- Current setup contract: Python 3.11, `make setup`, local `.venv`, `pip`, and Makefile-driven execution.
- `Makefile` -- Current commands use `.venv/bin/python`; no package/test command exists yet.
- `requirements.txt` -- Existing dependency source; do not add dependencies for this slice.
- `scripts/hw5/external_tool_router.py` -- Existing HW5 source for `Route`, `ToolName`, `ToolRequest`, `ToolObservation`, and intent classification strings.
- `scripts/hw6/agentic_workflow.py` -- Existing HW6 source for product workflow route names, `StepStatus`, `WorkflowStep`, `RagObservation`, `WorkflowState`, `map_hw5_route`, and `build_plan` behavior.
- `scripts/hw7/langgraph_flow.py` -- Existing HW7 `AgentState`/trace shape reference for future workflow migration; do not modify now.
- `scripts/hw5/test_external_tool_router.py`, `scripts/hw6/test_agentic_workflow.py`, `scripts/hw7/test_langgraph_flow.py` -- Existing unittest patterns and behavior coverage; use as baseline, not as files to edit.

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml` -- Add minimal package metadata for a `src` layout and pytest/unittest-compatible test discovery -- establishes AD-9 import contract without changing Makefile behavior.
- [x] `src/supp_bro/__init__.py` and `src/supp_bro/domain/__init__.py` -- Create product package namespace exports -- gives later slices stable import targets.
- [x] `src/supp_bro/domain/routes.py` -- Define canonical route literals/constants and HW5-to-product route mapping -- prevents route string drift from HW5/HW6/HW7.
- [x] `src/supp_bro/domain/contracts.py` -- Define dataclasses or typed contracts for tool requests, tool observations, evidence observations, RAG observations, trace view, and run outcomes -- creates adapter port language without provider dependencies.
- [x] `src/supp_bro/domain/state.py` -- Define canonical `WorkflowState`, workflow step/status structures, mutation-safe defaults, and state-to-trace projection -- establishes AD-4/AD-6 state and trace contract.
- [x] `tests/unit/test_domain_routes.py`, `tests/unit/test_domain_state.py`, `tests/unit/test_package_imports.py` -- Add focused tests for package imports, exact route values/mapping, default state isolation, trace projection, and unavailable-provider/domain observation behavior -- verifies the new contract without live services.

**Acceptance Criteria:**
- Given the repository after this slice, when unit tests import `supp_bro` and `supp_bro.domain`, then imports succeed without modifying `sys.path` inside tests.
- Given HW5 route names, when the product route mapper is called, then `docs_question`, `known_issue_question`, `community_troubleshooting`, and `clarification` map to the same product routes as HW6, and `report_new_issue` maps to `clarification`.
- Given two default `WorkflowState` instances, when one state's trace collections are mutated, then the other state's collections remain unchanged.
- Given missing provider credentials represented as a domain observation, when the observation is created, then no external call is made and no secret value is required or exposed.
- Given existing homework tests, when this slice is implemented, then no `scripts/hw*` files are changed.

## Spec Change Log

## Design Notes

The first implementation should prefer simple standard-library typing and dataclasses over Pydantic or new dependencies. Keep contracts intentionally small: enough to stabilize imports, route names, state shape, trace projection, and provider-unavailable semantics for future adapter/workflow slices.

Example route boundary:

```python
HW5_TO_WORKFLOW_ROUTE = {
    "docs_question": "docs_answer",
    "known_issue_question": "issue_investigation",
    "report_new_issue": "clarification",
    "community_troubleshooting": "community_lookup",
    "clarification": "clarification",
}
```

## Verification

**Commands:**
- `PYTHONPATH=src python3.11 -m unittest discover tests/unit -q` -- expected: new unit tests pass without live credentials.
- `python3.11 -m unittest scripts.hw5.test_external_tool_router scripts.hw6.test_agentic_workflow -q` -- expected: existing HW behavior still passes or skips only for missing optional dependencies already handled by tests.
- `git diff -- scripts/hw4 scripts/hw5 scripts/hw6 scripts/hw7` -- expected: no diff.

## Suggested Review Order

**Domain route contract**

- Start with route values: they preserve HW6 behavior for future workflows.
  [`routes.py:14`](../../src/supp_bro/domain/routes.py#L14)

- Review HW5 mapping: `report_new_issue` intentionally routes to clarification.
  [`routes.py:28`](../../src/supp_bro/domain/routes.py#L28)

- Check defensive mapping: unknown inputs fall back without type-ignore hacks.
  [`routes.py:37`](../../src/supp_bro/domain/routes.py#L37)

**Canonical state and trace**

- Review canonical state fields: this is the future workflow state boundary.
  [`state.py:23`](../../src/supp_bro/domain/state.py#L23)

- Check step mutation rules: unknown steps fail loudly.
  [`state.py:42`](../../src/supp_bro/domain/state.py#L42)

- Review trace projection: UI-facing trace is copied from state.
  [`state.py:57`](../../src/supp_bro/domain/state.py#L57)

- Check serialization guard: invalid trace items fail with explicit errors.
  [`state.py:76`](../../src/supp_bro/domain/state.py#L76)

**Provider-neutral contracts**

- Review observation statuses: provider unavailable remains domain data.
  [`contracts.py:15`](../../src/supp_bro/domain/contracts.py#L15)

- Check request and observation DTOs: adapters get stable port shapes.
  [`contracts.py:19`](../../src/supp_bro/domain/contracts.py#L19)

- Review TraceView shape: this is the UI projection contract.
  [`contracts.py:61`](../../src/supp_bro/domain/contracts.py#L61)

**Import and verification support**

- Confirm package layout: tests can import `supp_bro` from `src`.
  [`pyproject.toml:11`](../../pyproject.toml#L11)

- Review route tests first: they pin HW route compatibility.
  [`test_domain_routes.py:8`](../../tests/unit/test_domain_routes.py#L8)

- Review state edge tests: they cover mutable defaults and projection guards.
  [`test_domain_state.py:9`](../../tests/unit/test_domain_state.py#L9)

- Confirm top-level export behavior: `from supp_bro import *` exposes domain.
  [`test_package_imports.py:6`](../../tests/unit/test_package_imports.py#L6)
