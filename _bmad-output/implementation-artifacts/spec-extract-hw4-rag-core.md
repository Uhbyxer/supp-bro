---
title: 'Extract HW4 RAG core'
type: 'refactor'
created: '2026-08-26'
status: 'done'
baseline_commit: '268fe839bba4645500c88efce83fb9934e84ee56'
review_loop_iteration: 1
context:
  - _bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** HW4 owns useful RAG answer behavior inside `scripts/hw4/rag_answer.py`, including retrieval weak-context gating, prompt construction, structured response validation, fallback reasons, output shaping, and experiment summaries. Product workflows cannot reuse that behavior without importing a homework script that also loads `.env`, mutates `sys.path`, and wires live OpenAI/Pinecone/SentenceTransformer clients.

**Approach:** Extract the provider-free HW4 RAG core into `src/supp_bro/retrieval/` with domain-compatible contracts and network-free tests. Keep live provider bootstrapping in the HW4 script for now, but make the script delegate pure chunk/result/prompt/validation/output behavior to the product package while preserving CLI output shape and existing HW4 tests.

## Boundaries & Constraints

**Always:** Preserve HW4 fallback text, result statuses, fallback reasons, prompt flavors, post-validator modes, experiment names/order, best-vector-score behavior, context-map shape, markdown table columns, and weak-context rule: empty retrieval falls back; threshold greater than zero falls back when no vector scores exist or max score is below threshold; threshold zero disables that vector-score gate. Product modules must not import `scripts/hw*`, read `.env`, read environment variables, create provider clients, or call networks. Unit tests must use fake chunks/clients only.

**Ask First:** Halt before changing retrieval backend choice, moving live Pinecone/OpenAI/SentenceTransformer setup into the package, adding dependencies, changing prompt wording, changing CLI args/output semantics, or touching HW5/HW6/HW7 behavior.

**Never:** Do not store or print `MONGODB_URI`. Do not require live OpenAI, Pinecone, Mongo, FAISS, sentence-transformers, or `.env` for package import/tests. Do not add a long-term retrieval adapter abstraction unless the extraction cannot stay simple without it.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Empty retrieval | `generate` receives no chunks | Returns fallback `GenerationResult` with status `retrieval_filter_fallback` and reason `empty_retrieval` | No LLM call |
| Weak vector retrieval | Chunks have vector scores below positive threshold, or no vector scores with positive threshold | Returns fallback with reason `weak_retrieval` | No LLM call |
| Filter disabled | Chunks have low vector scores but threshold is `0.0` | Calls injected client and can return answer based on payload validation | Invalid payload still falls back |
| Valid structured answer | Payload has `has_enough_context=True`, non-empty answer, citations from retrieved chunk IDs | Returns status `grounded_answer`, deduplicated citations, original answer | Unknown citations fall back |
| Validator disabled | Payload has answer but missing citations and post-validator is off | Returns status `unvalidated_answer` with deduplicated citations | Empty/fallback answer still falls back |
| Invalid model payload | Bad JSON, missing keys, wrong mode, empty answer, fallback answer, or invalid citations | Returns status `model_fallback` with appropriate fallback reason | No exception escapes |
| Output/experiment summary | Build output or run experiments over the fixed matrix | Preserves HW4 JSON keys and markdown table columns/conclusions | No duplicate `sources` or `retrieved_chunks` keys |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md:48` -- AD-1 places retrieval under `src/supp_bro/retrieval` and keeps adapters returning domain contracts.
- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md:72` -- AD-5 keeps environment and secrets out of retrieval core.
- `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md:90` -- AD-8 requires degraded/missing provider behavior to be typed rather than startup failure; this slice handles provider-free fallback semantics only.
- `_bmad-output/implementation-artifacts/roadmap.md:81` -- Current retrieval slice should add `src/supp_bro/retrieval/rag.py`, use HW4 as behavior reference, and avoid choosing a long-term backend prematurely.
- `src/supp_bro/retrieval/rag.py:13` -- Package-owned fallback sentence, thresholds, prompt/mode tuples, experiment matrix, and response schema.
- `src/supp_bro/retrieval/rag.py:74` -- `RetrievedChunk` and `GenerationResult` dataclasses preserve the HW4 pure RAG contract.
- `src/supp_bro/retrieval/rag.py:91` -- `weak_context_reason` preserves the pre-LLM empty/weak retrieval gate.
- `src/supp_bro/retrieval/rag.py:104` -- Prompt flavor selection reads existing HW4 prompt files when present, with package constants as fallback text.
- `src/supp_bro/retrieval/rag.py:119` -- Payload shape, citation validation, validator-off behavior, and answer fallback checks.
- `src/supp_bro/retrieval/rag.py:152` -- `generate` performs config validation, retrieval gate, injected client call, JSON parsing, validation, and provider/client failure fallback.
- `src/supp_bro/retrieval/rag.py:201` -- Output helpers preserve best score, context map, markdown table, conclusions, and experiment matrix.
- `scripts/hw4/rag_answer.py:19` -- HW4 adds `src` to `sys.path` before importing product retrieval so the existing workflow can run without editable install.
- `scripts/hw4/rag_answer.py:26` -- HW4 re-exports provider-free product retrieval names for old tests/callers.
- `scripts/hw4/rag_answer.py:55` -- `retrieve` remains the live HW3/Pinecone/BM25/RRF orchestration boundary for this slice.
- `scripts/hw4/test_rag_answer.py:9` -- Existing tests stub live HW3 dependencies before importing HW4; package tests should not need those stubs.
- `scripts/hw4/test_rag_answer.py:56` -- Existing guardrail tests pin prompt flavors, retrieval reasons, validation, validator-off behavior, output shape, and experiment markdown.
- `src/supp_bro/domain/contracts.py:49` -- `RagObservation` exists for workflow-facing RAG results; product retrieval core may provide conversion without forcing live workflow integration.
- `src/supp_bro/config.py:14` -- Config already defines OpenAI/Pinecone/Mongo capability tokens; retrieval core should not consume them yet except through future adapters.

## Tasks & Acceptance

**Execution:**
- [x] `src/supp_bro/retrieval/__init__.py` and `src/supp_bro/retrieval/rag.py` -- Add provider-free HW4 RAG core dataclasses/constants/functions, prompt templates as package-owned constants or resources, and optional conversion to `RagObservation` -- establishes package retrieval contracts without live dependencies.
- [x] `scripts/hw4/rag_answer.py` -- Delegate provider-free chunk/result/prompt/validation/output behavior to `supp_bro.retrieval.rag` while keeping live retrieve/client setup, `.env` loading, CLI args, output JSON shape, and public names compatible -- preserves HW4 as runnable POC history.
- [x] `tests/unit/test_retrieval_rag.py` -- Add network-free package tests mirroring HW4 guardrails for weak-context gating, prompt flavors, payload validation, validator-off mode, invalid payloads, output shape, and experiment table -- proves product behavior without HW3 stubs.
- [x] Existing HW4 tests -- Keep `scripts/hw4/test_rag_answer.py` passing -- proves compatibility with old import path and behavior.

**Acceptance Criteria:**
- Given no provider packages or credentials, when package retrieval tests import `supp_bro.retrieval.rag`, then import succeeds without `.env`, `sys.path`, OpenAI, Pinecone, or sentence-transformers setup.
- Given empty or weak retrieved chunks, when `generate` runs, then it returns the HW4 fallback before calling the injected client.
- Given threshold `0.0`, when low-scored chunks are passed to `generate`, then the injected client can be called and payload validation determines the result.
- Given valid and invalid structured payloads, when validation functions run, then statuses, citations, answer text, and fallback reasons match HW4 behavior.
- Given output and experiment helpers run, when their results are inspected, then JSON keys, experiment order, markdown columns, and conclusions match HW4 tests.
- Given existing HW4 tests, when they run, then compatibility imports, prompt text assertions, output shape, and experiment assertions still pass.

## Spec Change Log

## Design Notes

Prefer a single `rag.py` module for this slice. Keep live retrieval orchestration (`retrieve`, OpenAI/Pinecone/SentenceTransformer construction, `.env` loading, and HW3 imports) in `scripts/hw4/rag_answer.py`; the product module should own pure behavior only. If prompt templates move into constants, preserve exact current text including the strong prompt's "ONLY the context" and the weak prompt's direct helpful wording.

## Verification

**Commands:**
- `PYTHONPATH=src python3.11 -m unittest tests.unit.test_retrieval_rag -q` -- passed: 14 tests.
- `PYTHONPATH=src python3.11 -m unittest discover tests/unit -q` -- passed: 66 tests.
- `python3.11 -m unittest scripts.hw4.test_rag_answer -q` -- passed: 9 tests without `PYTHONPATH=src`.
- `git diff -- scripts/hw5 scripts/hw6 scripts/hw7` -- passed: no diff outside HW4 compatibility wiring.

## Suggested Review Order

**Extracted Contract**

- Start with the provider-free RAG surface and preserved constants.
  [`rag.py:13`](../../src/supp_bro/retrieval/rag.py#L13)

- Check the weak-context gate before any injected client call.
  [`rag.py:91`](../../src/supp_bro/retrieval/rag.py#L91)

- Verify prompt loading preserves HW4 file text with package fallbacks.
  [`rag.py:104`](../../src/supp_bro/retrieval/rag.py#L104)

**Validation And Output**

- Review strict payload shape checks before citation and answer handling.
  [`rag.py:119`](../../src/supp_bro/retrieval/rag.py#L119)

- Confirm generation separates config errors from model/client fallback.
  [`rag.py:152`](../../src/supp_bro/retrieval/rag.py#L152)

- Confirm output helpers preserve JSON and markdown experiment contracts.
  [`rag.py:201`](../../src/supp_bro/retrieval/rag.py#L201)

**Compatibility**

- Check HW4 bootstraps `src` before product imports.
  [`rag_answer.py:19`](../../scripts/hw4/rag_answer.py#L19)

- Verify live provider retrieval remains inside the HW4 script.
  [`rag_answer.py:55`](../../scripts/hw4/rag_answer.py#L55)

**Tests And Exports**

- Review network-free tests covering the extraction matrix.
  [`test_retrieval_rag.py:40`](../../tests/unit/test_retrieval_rag.py#L40)

- Verify package exports stay intentionally narrow.
  [`__init__.py:1`](../../src/supp_bro/retrieval/__init__.py#L1)
