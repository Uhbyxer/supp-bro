---
title: 'Capability-scoped local settings and provider tokens'
type: 'feature'
created: '2026-08-26'
status: 'done'
baseline_commit: '6ac597584391a09cb15486043e0d68483921143d'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** Product code has domain and tool request contracts, but no package-owned settings boundary for local defaults or optional provider tokens. Future adapters need a shared way to ask whether a capability is configured without making package import or application startup require live credentials.

**Approach:** Add a minimal `src/supp_bro/config.py` module using standard-library dataclasses and environment mapping inputs. Model provider tokens as optional per-capability values, expose safe availability checks, and keep missing credentials as normal local state rather than startup errors.

## Boundaries & Constraints

**Always:** Importing `supp_bro.config` must not read external files, call networks, or require any environment variable. Missing tokens must be represented as unavailable capabilities, not exceptions. Tests must avoid real credentials and must not print or persist token values.

**Ask First:** Halt before adding new runtime dependencies, introducing `.env` parsing, changing `scripts/hw*`, changing package top-level exports beyond import coverage, or choosing concrete provider client implementations.

**Never:** Do not store, log, or expose raw provider token values through repr-friendly structures or availability summaries. Do not require `MONGODB_URI`, GitHub, Stack Overflow, OpenAI, Pinecone, or Mongo credentials at import/startup. Do not add live provider validation.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Empty local environment | No relevant env vars | Settings object builds successfully; all token-backed capabilities report unavailable | No exception |
| Configured provider token | Mapping contains a token env var such as `GITHUB_TOKEN` | Matching provider token is stored for explicit adapter use; capability availability reports available without exposing the token | Token value never appears in summary/repr assertions |
| Disabled capability | Mapping disables a capability with false-like text | Capability reports unavailable even if a token exists | No live validation |
| Unknown provider key | Mapping contains unrelated env vars | Unknown keys are ignored | No exception |

</frozen-after-approval>

## Code Map

- `AGENTS.md` -- Repo-level rules: new product code belongs under `src/supp_bro`; preserve homework scripts; never store or print `MONGODB_URI`.
- `pyproject.toml` -- Current package is a minimal Python 3.11 `src` layout with no runtime dependencies beyond the standard library.
- `src/supp_bro/__init__.py` -- Top-level package currently exports only `domain`; avoid broad API churn unless tests require import coverage.
- `src/supp_bro/domain/contracts.py` -- Uses simple dataclasses, `Literal`, and default factories for provider-neutral product contracts.
- `src/supp_bro/domain/state.py` -- Existing dataclass style and mutation-safe defaults for canonical local state.
- `src/supp_bro/tools/requests.py` -- Defines current provider-free tool request defaults and validation without credential requirements.
- `tests/unit/test_package_imports.py` -- Existing import smoke-test style for package modules.
- `tests/unit/test_tool_request_validation.py` -- Existing focused unit-test style for tool-layer behavior without live services.

## Tasks & Acceptance

**Execution:**
- [x] `src/supp_bro/config.py` -- Add minimal settings dataclasses, provider token loading from an explicit mapping/default environment, capability enablement, and safe availability summaries -- gives future adapters a credential boundary that does not fail at startup.
- [x] `tests/unit/test_config.py` -- Add focused unit tests for empty environment, token-backed capability availability, disabled capabilities, ignored unknown keys, and non-exposure of token values -- locks the no-live-credentials contract.
- [x] `tests/unit/test_package_imports.py` -- Add a small import assertion for `supp_bro.config` if needed -- verifies the module is importable without credentials.

**Acceptance Criteria:**
- Given no relevant environment variables, when `supp_bro.config` is imported and settings are built, then no exception is raised and token-backed capabilities report unavailable.
- Given a provider token in an explicit mapping, when settings are built, then the relevant provider/capability reports available and the raw token is accessible only through explicit token fields intended for adapters.
- Given false-like capability enablement text in the mapping, when settings are built, then that capability reports unavailable even if a token value exists.
- Given settings or availability summaries are represented as strings, when tests inspect those strings, then raw token values do not appear.
- Given existing homework scripts and tests, when this slice is implemented, then no `scripts/hw*` files are changed.

## Spec Change Log

## Verification

**Commands:**
- `PYTHONPATH=src python3.11 -m unittest tests.unit.test_config tests.unit.test_package_imports -q` -- expected: config and import tests pass without live credentials.
- `PYTHONPATH=src python3.11 -m unittest discover tests/unit -q` -- expected: focused package unit suite passes.
- `git diff -- scripts/hw4 scripts/hw5 scripts/hw6 scripts/hw7` -- expected: no diff.

## Suggested Review Order

**Settings Boundary**

- Start here: package-owned local config, no live startup credentials.
  [`config.py:95`](../../src/supp_bro/config.py#L95)

- Token fields are adapter-only and hidden from repr.
  [`config.py:41`](../../src/supp_bro/config.py#L41)

- Capability status reports booleans, never raw secrets.
  [`config.py:81`](../../src/supp_bro/config.py#L81)

- Local settings snapshot caller mappings despite frozen dataclass limits.
  [`config.py:75`](../../src/supp_bro/config.py#L75)

**Capability Registry**

- Supported capability tokens stay centralized by env var.
  [`config.py:20`](../../src/supp_bro/config.py#L20)

- Enable flags default on and accept false-like local overrides.
  [`config.py:30`](../../src/supp_bro/config.py#L30)

**Verification**

- All provider token mappings are tested against explicit fields.
  [`test_config.py:24`](../../tests/unit/test_config.py#L24)

- Disabled capability behavior is pinned without live validation.
  [`test_config.py:46`](../../tests/unit/test_config.py#L46)

- Secret-safe representation and summary behavior are checked.
  [`test_config.py:75`](../../tests/unit/test_config.py#L75)

- Import smoke test proves startup has no credential requirement.
  [`test_package_imports.py:7`](../../tests/unit/test_package_imports.py#L7)
