# SuppBro Implementation Roadmap

Status: current as of `2026-08-26` after `_bmad-output/implementation-artifacts/spec-capability-scoped-local-settings-provider-tokens.md`.

## Purpose

This file is the first place to check what BMAD quick-dev has already built and what the next small implementation slices should be. It is a lightweight status board, not a PRD, sprint plan, or formal user-story backlog.

## Sources

- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md` -- target package structure, architecture rules, capability map, and deferred decisions.
- `_bmad-output/implementation-artifacts/spec-establish-src-supp-bro-package-skeleton.md` -- completed package skeleton slice.
- `_bmad-output/implementation-artifacts/spec-extract-hw5-support-routing-tool-validation.md` -- completed HW5 routing and request-validation extraction slice.
- `_bmad-output/implementation-artifacts/spec-capability-scoped-local-settings-provider-tokens.md` -- completed config/settings boundary slice.
- `src/supp_bro/` -- current product package tree.

If sources disagree, prefer current code for what exists, completed specs for what was intentionally finished, and the architecture spine for target direction.

## Done

- BMAD project context is installed in `AGENTS.md`.
- Architecture spine `architecture-SuppBro-2026-08-23` is complete for the product package direction:
  - layered ports-and-adapters;
  - domain-owned routes, state, and contracts;
  - workflows as the only orchestration layer;
  - traceability as part of workflow state;
  - capability-scoped provider availability.
- `src/supp_bro` package skeleton exists.
- `pyproject.toml` supports the `src` package layout for local unit tests.
- Domain package exists:
  - `src/supp_bro/domain/routes.py` defines product route names and HW5-to-product mapping;
  - `src/supp_bro/domain/contracts.py` defines provider-neutral tool, RAG, evidence, and trace contracts;
  - `src/supp_bro/domain/state.py` defines canonical workflow state and trace projection;
  - `src/supp_bro/domain/support_intent.py` contains extracted HW5 support-intent routing and issue-number extraction.
- Partial tools package exists:
  - `src/supp_bro/tools/requests.py` contains provider-free tool request construction, validation, and Stack Overflow query normalization;
  - `src/supp_bro/tools/__init__.py` exports the current tool request helpers.
- Minimal product config exists:
  - `src/supp_bro/config.py` exposes `LocalSettings`, `ProviderTokens`, `CapabilityAvailability`, `build_local_settings`, and capability availability checks;
  - supported token-backed capabilities are GitHub issues, Stack Overflow search, OpenAI embeddings, Pinecone retrieval, and Mongo retrieval;
  - recognized token env vars are `GITHUB_TOKEN`, `STACKOVERFLOW_TOKEN`, `OPENAI_API_KEY`, `PINECONE_API_KEY`, and `MONGODB_URI`;
  - recognized enablement env vars are `SUPP_BRO_ENABLE_GITHUB_ISSUES`, `SUPP_BRO_ENABLE_STACKOVERFLOW_SEARCH`, `SUPP_BRO_ENABLE_OPENAI_EMBEDDINGS`, `SUPP_BRO_ENABLE_PINECONE_RETRIEVAL`, and `SUPP_BRO_ENABLE_MONGO_RETRIEVAL`;
  - `build_local_settings(env=None)` reads `os.environ`, while explicit mappings keep tests and adapters deterministic;
  - settings build without live credentials at import/startup, false-like enablement values disable a capability, and unknown env keys are ignored;
  - token-backed availability summaries and repr output do not expose raw secret values; `ProviderTokens` fields are intended only for explicit adapter access.
- HW5 compatibility wrapper is preserved:
  - `scripts/hw5/external_tool_router.py` still exposes old public names;
  - live GitHub and Stack Overflow HTTP execution still lives in HW5;
  - old HW5 tests continue to pass.
- Focused unit tests exist for imports, domain routes/state/contracts, support-intent routing, tool request validation, and HW5 wrapper compatibility.
  - `tests/unit/test_package_imports.py`
  - `tests/unit/test_domain_routes.py`
  - `tests/unit/test_domain_state.py`
  - `tests/unit/test_support_intent_routing.py`
  - `tests/unit/test_tool_request_validation.py`
  - `tests/unit/test_hw5_compatibility_wrapper.py`
  - `tests/unit/test_config.py`

## Current Package State

| Area | Status | Evidence | Next acceptance condition |
| --- | --- | --- | --- |
| `domain` | Started and usable | `routes.py`, `contracts.py`, `state.py`, `support_intent.py` exist under `src/supp_bro/domain/`. | Workflow nodes can use domain state/contracts without importing homework scripts. |
| `tools` | Partial | Provider-free request helpers exist; live GitHub/Stack Overflow adapters are not product modules yet. | `github_issues.py` and `stackoverflow.py` wrap live calls and return domain observations. |
| `retrieval` | Not started | Architecture expects `src/supp_bro/retrieval/`, but no package module exists yet. | HW4 RAG behavior is available behind package retrieval functions/contracts. |
| `workflows` | Not started | Architecture expects `src/supp_bro/workflows/`, but no package module exists yet. | Nodes mutate `WorkflowState` and cover docs, issue, community, and clarification routes. |
| `ui` | Not started | Architecture expects `src/supp_bro/ui/`, but no package module exists yet. | Streamlit demo can run the product workflow and show trace/state JSON. |
| `config.py` | Started and usable | `src/supp_bro/config.py` reads optional provider tokens/settings in one package module and keeps missing credentials non-fatal. | Future provider adapters consume `LocalSettings` instead of reading environment directly. |

## Recommended Next Slices

1. Extract HW5 live tool adapters into product modules:
   - add `src/supp_bro/tools/github_issues.py`;
   - add `src/supp_bro/tools/stackoverflow.py`;
   - return domain `ToolObservation` objects;
   - use `LocalSettings` capability checks before live calls instead of reading environment directly;
   - map missing credentials, timeouts, rate limits, and provider errors into typed observations;
   - preserve HW5 CLI behavior through compatibility wiring;
   - keep tests network-free by mocking HTTP boundaries.

2. Extract HW4 RAG core behind retrieval contracts:
   - add `src/supp_bro/retrieval/rag.py`;
   - add `src/supp_bro/retrieval/adapters.py` only if needed;
   - respect existing OpenAI, Pinecone, and Mongo capability settings before provider-backed retrieval;
   - use `scripts/hw4/rag_answer.py` as the behavior reference for citation, fallback, filters, prompt variants, and post-validation behavior;
   - avoid choosing a long-term backend prematurely.

3. Add workflow nodes over domain state:
   - add `src/supp_bro/workflows/nodes.py`;
   - route docs, issue, community, and clarification requests;
   - receive settings or explicit tokens through typed inputs rather than reading environment directly;
   - append traceable observations to `WorkflowState`;
   - output updated `WorkflowState` for each route.

4. Add product LangGraph app:
   - add `src/supp_bro/workflows/langgraph_app.py`;
   - wire nodes without importing homework scripts;
   - preserve HW7's useful trace-dashboard behavior as reference, not final structure.

5. Add Streamlit product demo:
   - add `src/supp_bro/ui/streamlit_app.py`;
   - expose chat, selected route, plan, RAG state, tool calls, and state JSON;
   - show provider availability/degraded state without exposing credentials;
   - minimum complete demo: one query can run through the product workflow and show answer plus trace.

6. Cleanup and docs pass:
   - update README commands if package entrypoints change;
   - keep homework folders as POC history;
   - avoid broad integration tests unless the touched slice needs them.

## Blocked Or Deferred

- Long-term retrieval backend consolidation.
- Deployment, hosting, production persistence, and operational telemetry.
- End-to-end provider degraded mode across adapters, workflow fallback, and UI display; only the config boundary exists today.
- Formal epics and user stories, once the product workflow is less speculative.
- Richer product UX beyond the local Streamlit demo.

## Conventions To Preserve

- Product modules under `src/supp_bro/` must not import from `scripts/hw*`.
- Homework folders remain POC history and compatibility references.
- New slices should be small BMAD quick-dev specs until the workflow is stable enough for formal stories.
- Only `src/supp_bro/config.py` should read environment variables; downstream modules should receive settings or explicit values.
- Provider calls should have network-free unit tests at the package boundary.

## Verification Evidence

- `sed -n '1,260p' _bmad-output/implementation-artifacts/roadmap.md` was rerun after this update and confirms this file is readable with the refreshed config status.
- `sed -n '1,140p' _bmad-output/implementation-artifacts/spec-capability-scoped-local-settings-provider-tokens.md` was rerun after this update and confirms the config spec is `done`.
- `rg -n "spec-capability-scoped|config.py|Recommended Next Slices|Extract HW5|Started and usable|test_config" _bmad-output/implementation-artifacts/roadmap.md` was rerun after this update and confirms Done evidence, config status, and next slice ordering.
- `git diff -- scripts/hw4 scripts/hw5 scripts/hw6 scripts/hw7` was rerun after this update and confirms no homework-script changes.
- `find src/supp_bro -maxdepth 3 -type f -print | sort` confirms the current package tree when excluding ignored generated caches from review.

## How To Refresh

1. Check `_bmad-output/implementation-artifacts/` for specs with `status: 'done'`.
2. Check `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md` for target package areas and deferred decisions.
3. Check `src/supp_bro/` for modules that actually exist.
4. Move items from Recommended Next Slices to Done only after a completed spec or code evidence confirms them.
5. If a spec is `draft`, `ready-for-dev`, `in-progress`, or `in-review`, mention it separately from Done only if it affects the next action.
6. Roadmap updates are manual and should happen after meaningful BMAD slice completion.
7. Keep this file concise; detailed implementation contracts belong in their own `spec-*.md` files.
