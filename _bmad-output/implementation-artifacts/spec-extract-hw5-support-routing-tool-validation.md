---
title: 'Extract HW5 support routing and tool validation'
type: 'refactor'
created: '2026-08-26'
status: 'done'
baseline_commit: 'afef64bc8a00eee1d6f3416a97ed69a083bfe63e'
review_loop_iteration: 0
context:
  - _bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** HW5 owns deterministic support-intent routing, issue-number extraction, Stack Overflow query normalization, and tool request validation inside a homework script, so the product package cannot reuse those behaviors without importing `scripts/hw5`. That risks duplicated route heuristics and validator drift as the new `src/supp_bro` package grows.

**Approach:** Move the provider-free HW5 routing and request-validation behavior into `src/supp_bro` domain/tools modules, then keep HW5 as a compatibility surface that delegates to the package while preserving its public function names, dataclass behavior, CLI output shape, and tests.

## Boundaries & Constraints

**Always:** Preserve exact HW5 route strings, tool names, validation messages, default repo/tag values, issue fallback behavior for buffer-lock/queue-full questions, and the unconfirmed Stack Overflow guard. Follow architecture AD-1/AD-2: domain owns route language and shared contracts; tools own request validation and tool-specific request helpers. Tests must not require live GitHub, Stack Overflow, MongoDB, OpenAI, Pinecone, or other provider credentials.

**Ask First:** Halt before changing live HTTP execution behavior, CLI arguments/output semantics, demo case meanings, `requirements.txt`, Makefile setup, or any HW4/HW6/HW7 behavior outside compatibility verification.

**Never:** Do not import from `scripts/hw5` inside product package modules. Do not introduce new runtime dependencies, external API calls in unit tests, `.env` loading, or secret handling. Do not print or persist `MONGODB_URI`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Intent classification | Documentation, issue, community, vague, and report-new-issue questions | Product classifier returns the same HW5 route and reason strings as current `classify_support_intent` | Unknown or sparse queries still fall back to `clarification` using existing heuristics |
| Issue request build | `known_issue_question` with explicit issue number, extracted issue number, or buffer-lock/queue-full text | Product helper returns `get_github_issue_context` with `repo` and selected `issue_number`; buffer-lock/queue-full still maps to issue `3` | Missing issue context returns an `ask_clarifying_question` request |
| Community request build | `community_troubleshooting` with confirmation flag true or false | Request payload keeps `query`, `tag: debezium`, `max_results: 5`, and `confirmed` mirrors the flag | Execution guard still returns `External community search requires confirmation.` before live lookup when unconfirmed |
| Validation | Invalid repo, issue number, query, tag, unknown tool, and `none` tool requests | Product validators return the exact current error strings or `None` | HW5 compatibility wrapper exposes the same validation results |

</frozen-after-approval>

## Code Map

- `scripts/hw5/external_tool_router.py:26` -- Current HW5 route/tool literals, default repo/tag constants, local dataclasses, deterministic router, validators, request builder, live tool execution, final answer rendering, CLI, and demo flow. Only provider-free routing/validation/request-building logic should move; live HTTP functions stay behaviorally unchanged.
- `scripts/hw5/external_tool_router.py:114` -- `classify_support_intent` is deterministic keyword/regex routing with exact reason strings that package tests must pin.
- `scripts/hw5/external_tool_router.py:132` -- `extract_issue_number` recognizes `issue #123`, `issue 123`, `bug #123`, and `bug 123`.
- `scripts/hw5/external_tool_router.py:139` -- `validate_repo`, `validate_issue_number`, `validate_search_query`, `validate_tag`, and `validate_tool_request` define the current error-message contract.
- `scripts/hw5/external_tool_router.py:271` -- `normalize_stackoverflow_query` strips community/Stack Overflow phrases and punctuation but returns the original query if normalization empties it.
- `scripts/hw5/external_tool_router.py:302` -- `execute_tool_request` performs validation and keeps the external community search confirmation guard before live Stack Exchange lookup.
- `scripts/hw5/external_tool_router.py:334` -- `build_tool_request` maps HW5 routes to tool requests, including buffer-lock/queue-full fallback to issue `3`.
- `scripts/hw5/test_external_tool_router.py:7` -- Existing HW5 tests import public names directly from the script directory; these tests are the compatibility baseline and should keep passing.
- `src/supp_bro/domain/routes.py:7` -- Existing package route literals and HW5-to-product route mapping; add or reuse HW5 route constants here so classifier output does not drift.
- `src/supp_bro/domain/contracts.py:8` -- Existing provider-neutral `ToolType`, `ToolName`, `ToolRequest`, and `ToolObservation` dataclasses; use these for package request validation rather than duplicating shapes.
- `src/supp_bro/domain/__init__.py:3` -- Domain export surface; update only for stable domain symbols used by later slices.
- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md` -- AD-1/AD-2/AD-7 require domain-owned routes/contracts and tool adapters returning domain contracts.

## Tasks & Acceptance

**Execution:**
- [x] `src/supp_bro/domain/routes.py` -- Add product-owned HW5 support-intent classification and issue-number extraction helpers, or a tightly scoped sibling domain module if cleaner -- centralizes route decisions under the domain boundary.
- [x] `src/supp_bro/tools/__init__.py` and focused tools modules such as `src/supp_bro/tools/requests.py` / `validation.py` -- Add default tool constants, Stack Overflow query normalization, tool request builder, and validators using `supp_bro.domain.contracts.ToolRequest` -- establishes provider-free tool request contracts without live API calls.
- [x] `scripts/hw5/external_tool_router.py` -- Replace duplicated pure routing/request-validation logic with imports/delegation to `supp_bro` package helpers while preserving public names, dataclass compatibility where needed, CLI behavior, demo behavior, and live HTTP execution behavior.
- [x] `tests/unit/test_support_intent_routing.py` and `tests/unit/test_tool_request_validation.py` -- Add focused package tests for classifier reasons, issue extraction, request building, normalization, exact validation errors, and no-tool behavior -- verifies the new package contract without external services.
- [x] Existing HW5 tests -- Keep `scripts/hw5/test_external_tool_router.py` passing unchanged or with import-path-only adjustments if the script wrapper requires them -- proves behavior preservation.

**Acceptance Criteria:**
- Given the current HW5 demo cases, when package routing helpers classify each question, then they return the same route strings as HW5 currently returns.
- Given representative HW5 tool requests, when package validators run, then they return the exact existing error strings and `None` success cases.
- Given HW5 imports `classify_support_intent`, `extract_issue_number`, `normalize_stackoverflow_query`, `validate_tool_request`, and `build_tool_request`, when existing HW5 tests run, then their assertions still pass.
- Given package unit tests run with only `PYTHONPATH=src`, when they exercise routing and validation, then no external network or credential access occurs.
- Given a docs-style route, when `build_tool_request` runs, then it returns the `none` read tool request exactly as HW5 does today.

## Spec Change Log

## Design Notes

Prefer small pure functions over classes. Keep the compatibility wrapper explicit: HW5 can import package functions and re-export them under the same names, while live functions such as `get_github_issue_context`, `search_stackoverflow_questions`, `execute_tool_request`, `run_agent`, and CLI rendering keep their current behavior and output shape.

The product validator should accept the domain `ToolRequest` dataclass. If HW5 keeps its local dataclass for output compatibility, either make it structurally compatible by sharing the imported class directly or convert only at the wrapper boundary without changing serialized field names.

## Verification

**Commands:**
- `PYTHONPATH=src python3.11 -m unittest discover tests/unit -q` -- expected: package unit tests pass without live credentials.
- `PYTHONPATH=src python3.11 -m unittest scripts.hw5.test_external_tool_router -q` -- expected: HW5 compatibility tests pass and the unconfirmed community-search guard remains local.
- `git diff -- scripts/hw4 scripts/hw6 scripts/hw7` -- expected: no diff outside HW5 compatibility wiring.

## Suggested Review Order

**Routing Boundary**

- Start with product-owned HW5 classification and preserved route precedence.
  [`support_intent.py:10`](../../src/supp_bro/domain/support_intent.py#L10)

- Check issue-number extraction moved without broadening behavior.
  [`support_intent.py:29`](../../src/supp_bro/domain/support_intent.py#L29)

- Confirm domain exports expose stable helpers for later slices.
  [`__init__.py:18`](../../src/supp_bro/domain/__init__.py#L18)

**Tool Request Boundary**

- Review exact validation errors before request dispatch.
  [`requests.py:16`](../../src/supp_bro/tools/requests.py#L16)

- Check Stack Overflow normalization keeps HW5 query semantics.
  [`requests.py:66`](../../src/supp_bro/tools/requests.py#L66)

- Review request builder route-to-tool behavior and fallback issue mapping.
  [`requests.py:82`](../../src/supp_bro/tools/requests.py#L82)

- Confirm public tool exports are deliberate and small.
  [`__init__.py:3`](../../src/supp_bro/tools/__init__.py#L3)

**HW5 Compatibility**

- Verify direct script imports find product package before re-exports.
  [`external_tool_router.py:25`](../../scripts/hw5/external_tool_router.py#L25)

- Confirm HW5 public names remain importable from the old module.
  [`external_tool_router.py:44`](../../scripts/hw5/external_tool_router.py#L44)

**Tests**

- Review route behavior, whitespace, and overlapping-intent coverage.
  [`test_support_intent_routing.py:8`](../../tests/unit/test_support_intent_routing.py#L8)

- Review request-building and exact validation-error coverage.
  [`test_tool_request_validation.py:15`](../../tests/unit/test_tool_request_validation.py#L15)

- Confirm HW5 wrapper re-exports product helpers under old names.
  [`test_hw5_compatibility_wrapper.py:18`](../../tests/unit/test_hw5_compatibility_wrapper.py#L18)
