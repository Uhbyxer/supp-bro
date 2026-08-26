---
title: 'Create implementation roadmap status'
type: 'chore'
created: '2026-08-26'
status: 'done'
baseline_commit: 'ed5f981f84761a0e831452e1733de361e7f33594'
review_loop_iteration: 0
context:
  - _bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** SuppBro's BMAD progress is currently discoverable only by reading separate architecture and implementation spec files, so it is hard to answer what is already done, what is next, and what remains later. This slows quick-dev onboarding and makes the next slice choice depend on conversation memory.

**Approach:** Add one durable roadmap/status artifact under `_bmad-output/implementation-artifacts/` that summarizes completed BMAD slices, the current package state, recommended next slices, deferred work, and the source files used to derive the status.

## Boundaries & Constraints

**Always:** Derive status from committed BMAD artifacts, the architecture spine, and current `src/supp_bro` files. Keep the file concise, beginner-readable, and useful as the first place to check project progress. Separate confirmed `Done`, concrete `Next`, and broader `Later` work. Include enough source references that the roadmap can be refreshed without relying on chat history.

**Ask First:** Halt before inventing a full PRD, epics/story hierarchy, sprint process, dates, owners, estimates, or product commitments that are not present in the current BMAD artifacts.

**Never:** Do not change product code, homework scripts, tests, dependencies, Makefile targets, architecture decisions, or existing completed specs. Do not claim a task is done unless a completed spec or current code confirms it. Do not print or persist `MONGODB_URI`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Completed slice discovery | Existing implementation specs with `status: done` | Roadmap lists each completed slice with the main artifact/code outcomes | If a spec is not `done`, list it outside Done or omit it with a note |
| Architecture gap discovery | Architecture spine lists target `retrieval`, `tools`, `workflows`, `ui`, and `config` areas | Roadmap identifies missing or partial areas as Next/Later without overcommitting | If target area has no code yet, mark it as not started rather than inferred |
| Current code snapshot | `src/supp_bro` contains domain and partial tools modules only | Roadmap states package skeleton/domain/tools-request status accurately | Do not treat homework scripts as completed product package modules |
| Refreshability | A future agent opens the roadmap first | File points to the exact specs/architecture sources used for status | If sources move later, future refresh should update references rather than silently trusting stale text |

</frozen-after-approval>

## Code Map

- `_bmad-output/implementation-artifacts/spec-establish-src-supp-bro-package-skeleton.md:2` -- Completed first product slice; confirms package skeleton, domain route/contracts/state modules, import setup, and focused unit tests.
- `_bmad-output/implementation-artifacts/spec-extract-hw5-support-routing-tool-validation.md:2` -- Completed second product slice; confirms HW5 routing, issue extraction, request validation, request building, and HW5 compatibility wrapper extraction.
- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md:27` -- Architecture source of truth for layered ports-and-adapters, domain ownership, workflow orchestration, traceability, config ownership, and provider-degraded behavior.
- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md:133` -- Structural seed lists expected `config`, `retrieval`, `tools`, `workflows`, and `ui` package areas.
- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md:156` -- Capability map identifies Debezium docs answers, known issue investigation, community lookup, clarifying questions, Streamlit trace, and provider degraded mode.
- `src/supp_bro/domain/routes.py` -- Current product route names and HW5-to-product route mapping exist.
- `src/supp_bro/domain/contracts.py` -- Current provider-neutral tool/RAG/evidence/trace contracts exist.
- `src/supp_bro/domain/state.py` -- Current canonical workflow state and trace projection exist.
- `src/supp_bro/domain/support_intent.py` -- Current extracted HW5 intent classifier and issue-number extraction exist.
- `src/supp_bro/tools/requests.py` -- Current extracted provider-free tool request construction and validation exists; live adapters are not yet product modules.
- `src/supp_bro/retrieval/`, `src/supp_bro/workflows/`, `src/supp_bro/ui/`, `src/supp_bro/config.py` -- Expected by architecture but not present in the current package tree.

## Tasks & Acceptance

**Execution:**
- [x] `_bmad-output/implementation-artifacts/roadmap.md` -- Create a concise status board with sections for purpose, sources, Done, Current Package State, Recommended Next Slices, Later, and How To Refresh -- gives the project one durable progress entrypoint.
- [x] `_bmad-output/implementation-artifacts/roadmap.md` -- Mark completed work only when backed by `done` specs or current code; mark missing architecture areas as not started or partial -- avoids conversation-memory drift.
- [x] `_bmad-output/implementation-artifacts/roadmap.md` -- Include a short recommended next slice list that starts with HW5 live tool adapters, then HW4 RAG core, workflow nodes, LangGraph app, Streamlit UI, and cleanup -- preserves quick-dev sequencing without creating formal user stories.
- [x] Verification -- Inspect the roadmap against current specs, architecture, and `src/supp_bro` file list -- confirms the roadmap is source-grounded.

**Acceptance Criteria:**
- Given the current repo, when a developer opens `_bmad-output/implementation-artifacts/roadmap.md`, then they can see what is done, what exists in the package, and what to build next without reading chat history.
- Given only completed implementation specs, when the roadmap lists Done work, then every Done item names the backing spec or code source.
- Given architecture target modules that do not exist yet, when the roadmap mentions them, then it marks them as future/not started rather than completed.
- Given the project remains in quick-dev mode, when the roadmap lists upcoming work, then it uses small implementation slices instead of full epics, estimates, owners, or release dates.

## Spec Change Log

## Design Notes

This is a lightweight status artifact, not a planning framework. Use plain Markdown and avoid YAML-only status structures because the immediate user need is human orientation. Keep formal user stories out of scope for now; they can be added later if the project moves from quick-dev refactoring to product planning.

## Verification

**Commands:**
- `sed -n '1,260p' _bmad-output/implementation-artifacts/roadmap.md` -- expected: roadmap is readable and contains Done, Current Package State, Recommended Next Slices, Later, and How To Refresh sections.
- `rg -n "status: 'done'|src/supp_bro/retrieval|src/supp_bro/workflows|src/supp_bro/ui|src/supp_bro/config.py" _bmad-output/implementation-artifacts _bmad-output/planning-artifacts src/supp_bro` -- expected: roadmap claims match current done specs and package tree.

## Suggested Review Order

**Roadmap Entry**

- Start with the human-facing status board and source precedence rule.
  [`roadmap.md:1`](roadmap.md#L1)

- Review completed work against backed BMAD specs.
  [`roadmap.md:21`](roadmap.md#L21)

- Check package area statuses and next acceptance conditions.
  [`roadmap.md:51`](roadmap.md#L51)

**Next Work**

- Confirm next slices stay small and start with config/tool adapters.
  [`roadmap.md:61`](roadmap.md#L61)

- Check deferred items remain out of quick-dev scope.
  [`roadmap.md:103`](roadmap.md#L103)

- Confirm product/homework boundary conventions are explicit.
  [`roadmap.md:110`](roadmap.md#L110)

**Refresh**

- Review verification evidence preserved inside the artifact.
  [`roadmap.md:117`](roadmap.md#L117)

- Check refresh rules keep Done source-grounded.
  [`roadmap.md:123`](roadmap.md#L123)
