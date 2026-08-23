# Repository instructions

## GitHub workflow

- Prefer the connected GitHub app or GitHub API for all GitHub operations.
- Do not require or use the `gh` CLI unless the user explicitly requests it.
- Use the GitHub app or API to create branches, commits, pull requests, comments, and to read pull request metadata.
- If the GitHub app or API is unavailable, explain the blocker instead of automatically falling back to `gh`.

## Development direction

- Treat `scripts/hw*` folders as proof-of-concept work and learning history.
- Do not keep growing homework scripts into the final product unless the user explicitly asks to change a specific homework.
- New product code should move into a package-oriented structure, with reusable modules under `src/supp_bro/` when the project structure is introduced.
- It is fine to copy useful logic from HW4-HW7, but refactor it into clear package boundaries instead of importing across homework folders.
- Keep the first production structure simple: retrieval, tools, workflow, domain state, config, and UI should be separate modules.

## BMAD / quick-dev mode

- Use BMAD as a lightweight brownfield planning aid, not as a heavy ceremony requirement.
- Prefer quick-dev style: clarify the goal, write only the docs needed for durable context, then implement the next small slice.
- Store lasting project decisions in docs such as `docs/bmad/project-brief.md` and `docs/bmad/architecture.md`.
- Use `AGENTS.md` for repo-wide coding rules and agent behavior, not for long product specs.
- For each BMAD/dev story, start from the existing repo behavior and preserve working HW behavior unless a change is intentional.

## Testing expectations

- Default to fast unit tests for critical behavior.
- Prioritize tests for routing decisions, tool input/output validation, workflow state transitions, and fallback behavior.
- Avoid broad integration, RAG, or external API tests in the normal quick-dev loop unless the current task changes that contract.
- Prefer commands like `pytest tests/unit -q` once unit tests are split out.
