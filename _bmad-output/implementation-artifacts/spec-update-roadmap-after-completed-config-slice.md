---
title: 'Update roadmap after completed config slice'
type: 'chore'
created: '2026-08-26'
status: 'done'
route: 'one-shot'
---

# Update roadmap after completed config slice

## Intent

**Problem:** The implementation roadmap still listed product config as not started after the completed config/settings slice was pushed.

**Approach:** Refresh the roadmap to mark config as started and usable, document the concrete config API and supported capability/env boundaries, and make the next recommended slice start with HW5 live tool adapters consuming `LocalSettings`.

## Suggested Review Order

**Config Completion**

- Start here: roadmap now points at the completed config spec.
  [`roadmap.md:3`](roadmap.md#L3)

- Done section captures config API, capabilities, env vars, and secret-safe behavior.
  [`roadmap.md:38`](roadmap.md#L38)

- Current state marks config as started and usable.
  [`roadmap.md:68`](roadmap.md#L68)

**Next Slice**

- Tool adapters are now the first remaining recommended slice.
  [`roadmap.md:70`](roadmap.md#L70)

- Adapter guidance now requires `LocalSettings` and typed degraded observations.
  [`roadmap.md:72`](roadmap.md#L72)

- Retrieval and workflow slices carry the same config ownership rule forward.
  [`roadmap.md:81`](roadmap.md#L81)

**Guardrails**

- Deferred work names end-to-end provider degraded mode as still incomplete.
  [`roadmap.md:111`](roadmap.md#L111)

- Conventions preserve environment reads inside config only.
  [`roadmap.md:119`](roadmap.md#L119)

- Verification evidence records the refreshed roadmap checks.
  [`roadmap.md:127`](roadmap.md#L127)
