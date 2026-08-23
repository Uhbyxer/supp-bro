<!-- bmad:context -->
<!-- Verified 2026-08-23 against 126e0837fe022ca837c89555f1ceafae11a0a592. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## SuppBro

SuppBro is a Python support assistant for Debezium documentation questions and technical issue investigation. The repo currently contains homework POCs in `scripts/hw*`; the product direction is to refactor useful behavior into a cleaner package-oriented codebase. Use BMAD in lightweight brownfield quick-dev mode: preserve working homework behavior, write only durable docs needed for context, then implement the next small slice.

## Policy

- Prefer the connected GitHub app or GitHub API for GitHub operations; do not require or use `gh` unless the user explicitly asks.
- Never store or print `MONGODB_URI`; local development uses `.env` and CI uses secrets.

## Where things are

- Current POCs live in `scripts/hw4` through `scripts/hw7`: RAG answering, external tools, custom workflow, and LangGraph workflow.
- New product code should go under `src/supp_bro/` when the package structure is introduced, not by growing homework scripts.
- Durable BMAD decisions belong in `docs/bmad/project-brief.md` and `docs/bmad/architecture.md`; implementation artifacts belong in `_bmad-output/implementation-artifacts/`.

## Running and verifying

- Use `make setup` before running project commands; Makefile targets use `.venv/bin/python`.
- In the Codex sandbox, run BMAD `uv` commands with `UV_CACHE_DIR=/private/tmp/uv-cache` because the default `~/.cache/uv` path is not writable.
- Prefer focused unit tests for the touched homework or package area; broad RAG, external API, or integration tests are not the default quick-dev loop.

## Conventions that differ from defaults

- Treat `scripts/hw*` folders as proof-of-concept learning history; copy useful logic into package boundaries instead of importing across homework folders.
- Keep the first production structure simple: retrieval, tools, workflow, domain state, config, and UI should stay as separate modules.
- For BMAD build work, start from existing repo behavior and preserve working HW behavior unless the change intentionally replaces it.

## Known pitfalls

- `bmad-build` halts without a concrete intent or spec path; invoke it with the specific small slice to build.
- The repo can be opened in detached `HEAD`; create or switch to a task branch before implementation work that should be committed.

<!-- /bmad:context -->
