---
title: 'Extract HW5 live tool adapters'
type: 'refactor'
created: '2026-08-26'
status: 'done'
baseline_commit: '4938cdd69e8d1186601fc37d9405cc8f2ca1be51'
review_loop_iteration: 0
context:
  - _bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** HW5 still owns live GitHub and Stack Overflow HTTP execution inside `scripts/hw5/external_tool_router.py`, so product workflows cannot call external tools without importing homework scripts or duplicating provider normalization. This keeps provider failures, missing credentials, and network behavior outside the package-owned ports-and-adapters boundary.

**Approach:** Add product tool adapter modules for GitHub issues and Stack Overflow search under `src/supp_bro/tools/`, returning domain `ToolObservation` objects and accepting `LocalSettings` or explicit HTTP callables for deterministic tests. Keep HW5 CLI/demo behavior compatible by delegating live execution through the package adapters while preserving the old public wrapper shape.

## Boundaries & Constraints

**Always:** Product adapters must return `supp_bro.domain.contracts.ToolObservation` with explicit `status`, `source`, `data`, `error`, and redacted `raw_reference` where useful. `src/supp_bro/config.py` remains the only product module that reads environment variables; adapters must receive `LocalSettings`, explicit tokens, or injected HTTP functions. Missing credentials, timeouts, rate limits, HTTP/provider errors, malformed provider payloads, and unconfirmed Stack Overflow search must be represented as typed observations, not uncaught startup failures. Unit tests must be network-free.

**Ask First:** Halt before adding runtime dependencies, changing CLI arguments/output shape, broadening HW5 routing heuristics, changing request validation messages, requiring live credentials, or touching HW4/HW6/HW7 behavior.

**Never:** Do not import from `scripts/hw5` inside `src/supp_bro`. Do not read `os.environ` from adapter modules. Do not print/store provider tokens or raw `MONGODB_URI`. Do not run live GitHub or Stack Exchange calls in unit tests.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| GitHub issue success | Valid repo/issue request, GitHub capability available, injected HTTP returns issue and comments JSON | Product adapter returns successful `ToolObservation` with normalized HW5-equivalent issue fields | No raw token in observation |
| GitHub unavailable | Valid request but settings have no GitHub token or capability disabled | Product adapter returns `success=False`, `status="unavailable"`, empty data, and a clear non-secret error | No live HTTP callable invoked |
| GitHub provider failure | Injected HTTP raises timeout or HTTP/provider exception | Product adapter returns `status="timeout"` for timeout, otherwise `status="failed"` | Error text is concise and token-free |
| Stack Overflow confirmed success | Confirmed request, Stack Overflow capability available, injected HTTP returns items | Product adapter returns successful `ToolObservation` with normalized query, tag, count, and result list matching HW5 fields | HTML titles are unescaped |
| Stack Overflow unconfirmed | Request has `confirmed=False` | Product adapter returns `success=False`, `status="skipped"`, and exact error `External community search requires confirmation.` | No live HTTP callable invoked |
| Stack Overflow unavailable or failed | Capability unavailable or injected HTTP fails | Product adapter returns typed unavailable/timeout/failed observation | No raw provider payload or token exposed |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md:48` -- AD-1 requires tools to be adapters under `src/supp_bro/tools` and return domain contracts to workflows.
- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md:72` -- AD-5 requires `config.py` to own environment reads and secrets; adapters receive settings or explicit tokens.
- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md:90` -- AD-8 requires missing credentials, timeouts, rate limits, and provider errors to become typed observations.
- `_bmad-output/implementation-artifacts/roadmap.md:72` -- Current next slice: add `github_issues.py` and `stackoverflow.py`, use `LocalSettings`, return `ToolObservation`, preserve HW5, and keep tests network-free.
- `_bmad-output/implementation-artifacts/spec-capability-scoped-local-settings-provider-tokens.md:38` -- Config slice defines `LocalSettings`, capability availability, token fields, and no-live-credential startup behavior.
- `src/supp_bro/config.py:12` -- Capability constants: `github_issues` and `stackoverflow_search`; adapters should use these instead of new strings.
- `src/supp_bro/config.py:41` -- `ProviderTokens` stores adapter-only `github_token` and `stackoverflow_token` with repr hidden.
- `src/supp_bro/config.py:70` -- `LocalSettings` exposes capability availability without adapter environment reads.
- `src/supp_bro/domain/contracts.py:27` -- Product `ToolObservation` includes `status`, `source`, and `raw_reference`, unlike the HW5 local compatibility dataclass.
- `src/supp_bro/tools/requests.py:12` -- Existing defaults and request validation belong to product tools and should be reused by adapters.
- `scripts/hw5/external_tool_router.py:129` -- Current HW5 `http_get_json` uses `urllib.request` and returns JSON; this behavior is the live-call reference.
- `scripts/hw5/external_tool_router.py:137` -- Current GitHub normalization fields: repo, issue number, title, state, labels, assignees, created/updated/closed, comments, participants, recent authors, URL.
- `scripts/hw5/external_tool_router.py:185` -- Current Stack Overflow query construction and result normalization fields.
- `scripts/hw5/external_tool_router.py:234` -- Current execution guard validates requests, skips unconfirmed community search, catches external exceptions, and returns HW5 local `ToolObservation`.
- `scripts/hw5/test_external_tool_router.py:56` -- Existing HW5 compatibility test pins exact unconfirmed community-search error.
- `tests/unit/test_tool_request_validation.py:47` -- Package tests already cover request building/confirmation flags without live network.

## Tasks & Acceptance

**Execution:**
- [x] `src/supp_bro/tools/github_issues.py` -- Add a GitHub issue adapter with injected HTTP callable support, `LocalSettings` capability checks, HW5-equivalent normalization, and typed failure observations -- moves live GitHub behavior into the product package boundary.
- [x] `src/supp_bro/tools/stackoverflow.py` -- Add a Stack Overflow search adapter with injected HTTP callable support, confirmation guard, `LocalSettings` capability checks, HW5-equivalent normalization, and typed failure observations -- moves live community lookup into the product package boundary.
- [x] `src/supp_bro/tools/__init__.py` -- Export the new adapter functions/classes deliberately -- gives workflows stable import targets.
- [x] `scripts/hw5/external_tool_router.py` -- Delegate live GitHub/Stack Overflow execution to product adapters while preserving existing HW5 public function names, local `ToolObservation` shape, CLI/demo output shape, and `http_get_json` monkeypatch surface where tests depend on it -- keeps homework compatibility while removing duplicated live logic.
- [x] `tests/unit/test_github_issues_adapter.py` and `tests/unit/test_stackoverflow_adapter.py` -- Add network-free tests for success, unavailable capability, unconfirmed search, timeout, provider failure, normalization, and no-token leakage -- covers the adapter edge-case matrix.
- [x] Existing package and HW5 tests -- Keep request-validation and HW5 compatibility tests passing -- verifies no regression in prior slices.

**Acceptance Criteria:**
- Given a valid GitHub issue request and injected successful HTTP responses, when the product GitHub adapter runs, then it returns a successful domain `ToolObservation` with HW5-equivalent normalized issue data.
- Given GitHub settings without an available capability, when the product GitHub adapter runs, then it returns `status="unavailable"` and does not invoke the HTTP callable.
- Given a confirmed Stack Overflow request and injected successful HTTP response, when the product Stack Overflow adapter runs, then it returns a successful domain `ToolObservation` with normalized query, tag, count, and unescaped result titles.
- Given an unconfirmed Stack Overflow request, when the product Stack Overflow adapter runs, then it returns `status="skipped"` with exact error `External community search requires confirmation.` and does not invoke the HTTP callable.
- Given injected timeout or provider errors, when either adapter runs, then it returns `status="timeout"` or `status="failed"` without leaking tokens.
- Given existing HW5 script tests, when they run, then public imports, CLI-facing dataclass fields, unconfirmed guard behavior, and final answer rendering remain compatible.

## Spec Change Log

## Design Notes

Keep HTTP as an injectable callable instead of creating a client class unless the implementation becomes awkward. A small function boundary is enough for this slice and avoids new dependencies:

```python
def fetch_github_issue_context(request: ToolRequest, settings: LocalSettings, http_get_json: HttpGetJson) -> ToolObservation:
    ...
```

The HW5 wrapper may convert product `ToolObservation(status=..., source=..., raw_reference=...)` back to its local four-field `ToolObservation` so `asdict(state)` and existing markdown/final-answer behavior remain stable.

## Verification

**Commands:**
- `PYTHONPATH=src python3.11 -m unittest tests.unit.test_github_issues_adapter tests.unit.test_stackoverflow_adapter tests.unit.test_tool_request_validation -q` -- expected: adapter and request tests pass without live network.
- `PYTHONPATH=src python3.11 -m unittest discover tests/unit -q` -- expected: full package unit suite passes.
- `PYTHONPATH=src python3.11 -m unittest scripts.hw5.test_external_tool_router -q` -- expected: HW5 compatibility tests pass.
- `git diff -- scripts/hw4 scripts/hw6 scripts/hw7` -- expected: no diff outside HW5 compatibility wiring.

## Suggested Review Order

**Adapter Boundary**

- Start with the GitHub product adapter boundary and capability gate.
  [`github_issues.py:17`](../../src/supp_bro/tools/github_issues.py#L17)

- Review GitHub provider calls, typed failures, and token redaction.
  [`github_issues.py:39`](../../src/supp_bro/tools/github_issues.py#L39)

- Check HW5-equivalent issue normalization before workflow crossing.
  [`github_issues.py:65`](../../src/supp_bro/tools/github_issues.py#L65)

- Review Stack Overflow confirmation, capability gate, and query shaping.
  [`stackoverflow.py:20`](../../src/supp_bro/tools/stackoverflow.py#L20)

- Check Stack Overflow raw-reference redaction and result normalization.
  [`stackoverflow.py:54`](../../src/supp_bro/tools/stackoverflow.py#L54)

**Compatibility Wiring**

- Confirm HW5 wrapper still exposes the old GitHub call shape.
  [`external_tool_router.py:137`](../../scripts/hw5/external_tool_router.py#L137)

- Confirm HW5 preserves the exact unconfirmed community guard.
  [`external_tool_router.py:196`](../../scripts/hw5/external_tool_router.py#L196)

- Check conversion from product observations to HW5 dataclass output.
  [`external_tool_router.py:213`](../../scripts/hw5/external_tool_router.py#L213)

- Verify stable product exports for workflow imports.
  [`__init__.py:14`](../../src/supp_bro/tools/__init__.py#L14)

**Tests**

- GitHub tests cover success, unavailable, provider failure, and malformed payload.
  [`test_github_issues_adapter.py:19`](../../tests/unit/test_github_issues_adapter.py#L19)

- Stack Overflow tests cover confirmation, normalization, redaction, and failures.
  [`test_stackoverflow_adapter.py:20`](../../tests/unit/test_stackoverflow_adapter.py#L20)
