# Adversarial Divergence Review — SuppBro Architecture Spine

Source: `ARCHITECTURE-SPINE.md`  
Lens: adversarial divergence  
Verdict: Not ready for reviewer gate. The spine establishes useful layer ownership, but several ADs are still too broad to prevent compliant one-level-down units from building incompatible contracts, state transitions, and operational assumptions.

## Findings

### AD-2 allows incompatible workflow state schemas

- **Location:** `AD-2 — Domain owns routes, state, and shared contracts`; `Consistency Conventions / State mutation`
- **Divergence pair:** `domain/state.py` defines `WorkflowState` as a `TypedDict` with `rag_calls: list[RagObservation]`, `tool_calls: list[ToolObservation]`, and `final_answer: AnswerEnvelope`; `workflows/nodes.py` defines node functions that mutate a Pydantic `WorkflowState` with `observations: list[Observation]`, `intermediate_results: dict[str, Any]`, and `answer: str`. Both can claim domain owns state and workflows mutate one shared object, but their serialized shape is incompatible.
- **Trigger condition:** AD-2 says domain owns workflow state fields, but does not name the canonical state type, mutability model, serialization boundary, or whether typed dicts, dataclasses, or Pydantic models are allowed.
- **Guard snippet:** Add an AD that names the canonical state contract, for example: "`domain.state.WorkflowState` is the only workflow state type; all nodes accept and return that type; trace collections are named exactly as defined in `domain.state`; adapters and UI may only read serialized projections produced by `domain.contracts`."
- **Potential consequence:** LangGraph nodes, Streamlit trace rendering, and tests can all be locally compliant while failing at runtime due to missing keys or incompatible model methods.

### AD-4 allows two trace models for the same run

- **Location:** `AD-4 — Traceability is part of the state contract`; `Consistency Conventions / Fallbacks`
- **Divergence pair:** `workflows/nodes.py` records traceability as an append-only event log with generic events such as `{kind, node, payload}`; `ui/streamlit_app.py` expects separate state fields like `executed_nodes`, `rag_calls`, `retrieved_context`, `tool_calls`, `fallback_flag`, and `clarification_flag`. Both obey AD-4's list of required facts, but they disagree on whether trace data is normalized fields or an event stream.
- **Trigger condition:** AD-4 enumerates facts that must be recorded but does not require a single trace representation or projection API.
- **Guard snippet:** Tighten AD-4: "Traceability is stored in one canonical `WorkflowTrace` shape in `domain.state`; UI reads trace through a `TraceView` projection; generic event logs may exist only as internal implementation detail if they produce the canonical fields before crossing module boundaries."
- **Potential consequence:** The demo can answer correctly but show empty, duplicated, or misleading trace sections because producers and consumers encode the trace differently.

### AD-3 and AD-4 leave completed-step ownership ambiguous

- **Location:** `AD-3 — Workflows are the only orchestration layer`; `AD-4 — Traceability is part of the state contract`
- **Divergence pair:** The planner node appends `completed_steps` after each workflow node finishes; individual retrieval/tool execution nodes also append `completed_steps` when they return observations. Both are workflow nodes mutating shared state and both record completed steps, but they can double-count, reorder, or mark a failed step as completed.
- **Trigger condition:** AD-3 says workflow nodes append observations and compose final answers, while AD-4 requires completed steps, but no AD assigns exclusive mutation ownership for each state field.
- **Guard snippet:** Add a state-mutation ownership table: `route` mutated only by classification; `plan` only by planning; `completed_steps` only by the graph executor after successful node outcome; `observations` only by execution nodes; `final_answer` only by answer composition.
- **Potential consequence:** Route tests can pass while user-visible trace and fallback behavior drift between workflow implementations.

### AD-3 permits conflicting final-answer composition paths

- **Location:** `AD-3 — Workflows are the only orchestration layer`; `Capability -> Architecture Map`
- **Divergence pair:** `retrieval/rag.py` returns a fully formatted answer envelope for documentation questions; `workflows/nodes.py` composes the final answer from retrieved chunks and tool observations. Both can comply if retrieval returns a domain contract and workflows compose final answers, but the boundary between evidence and answer is unclear.
- **Trigger condition:** AD-3 prevents retrieval from composing final answers independently, yet AD-2 also lists answer envelopes as domain contracts and the capability map places documentation answers in both retrieval and workflows.
- **Guard snippet:** Tighten AD-3: "Retrieval and tools return evidence-only observations; only `workflows.nodes.compose_answer` writes `final_answer`. If an adapter receives provider-generated prose, it must store it as evidence metadata, not as the product answer."
- **Potential consequence:** Different routes can produce answers with inconsistent citation, fallback, and trace semantics.

### AD-2 allows duplicated route semantics behind shared route literals

- **Location:** `AD-2 — Domain owns routes, state, and shared contracts`; `Consistency Conventions / Routes`
- **Divergence pair:** `domain/routes.py` defines four route literals; `workflows/nodes.py` maps `issue_investigation` to RAG plus GitHub; `tools/github_issues.py` treats issue investigation as GitHub-only and returns "no issue found" without RAG. Both use the approved route name and domain contracts, but the route behavior diverges.
- **Trigger condition:** The spine standardizes route names but not route capabilities, required steps, or minimum observations per route.
- **Guard snippet:** Add an AD or route contract table that defines each route's required plan shape, allowed optional steps, and required observation types, for example `issue_investigation = docs retrieval + GitHub issue lookup + final synthesis`.
- **Potential consequence:** Tests may agree on route selection but disagree on what executing that route must do.

### AD-1 permits adapter-specific request shapes at the workflow boundary

- **Location:** `AD-1 — Package boundaries use ports-and-adapters`; `AD-2 — Domain owns routes, state, and shared contracts`
- **Divergence pair:** `tools/stackoverflow.py` exposes `lookup(query: str, tags: list[str])`; `tools/github_issues.py` exposes `search(request: IssueSearchRequest)`; workflow nodes call each adapter directly with different request shapes. Both tools return domain observations and avoid provider JSON leakage, but workflow code becomes adapter-specific.
- **Trigger condition:** AD-1 constrains returned values but does not require input ports to use domain request contracts consistently.
- **Guard snippet:** Tighten AD-1/AD-2: "Workflow-to-adapter inputs must also be domain contracts; every retrieval/tool adapter exposes a port method accepting a domain request type and returning a domain observation type."
- **Potential consequence:** Adding or swapping tools requires orchestration changes and can fork query normalization across nodes.

### AD-5 omits runtime dependency lifecycle and optional provider policy

- **Location:** `AD-5 — Configuration owns environment access and secrets`; `Deferred / Retrieval backend consolidation`
- **Divergence pair:** `config.py` requires OpenAI, Pinecone, and GitHub tokens at startup; adapters treat missing tokens as explicit fallback observations. Both avoid direct environment reads and do not print secrets, but one prevents local demo startup while the other supports degraded operation.
- **Trigger condition:** AD-5 controls where environment variables are read but not which settings are required per capability, when validation happens, or how unavailable providers are represented.
- **Guard snippet:** Add an operational AD: "Settings validation is capability-scoped; local quick-dev starts without live provider credentials; missing credentials produce typed unavailable-provider observations unless the invoked capability is explicitly configured as required."
- **Potential consequence:** A compliant package can be impossible to run locally in the intended quick-dev/demo mode.

### AD-5 does not define client ownership, timeout, retry, or rate-limit behavior

- **Location:** `AD-5 — Configuration owns environment access and secrets`; `Capability -> Architecture Map`
- **Divergence pair:** Each adapter creates its own HTTP/API client from typed settings; `workflows/langgraph_app.py` constructs shared clients and injects them into nodes. Both receive settings or explicit tokens through typed inputs, but timeout, retry, and rate-limit behavior diverge by route.
- **Trigger condition:** The config AD covers secrets but not operational client policy.
- **Guard snippet:** Add an AD: "Config defines settings only; adapter factories own provider clients through explicit port constructors; all provider calls use shared timeout, retry, and rate-limit policies represented in typed settings and tested without live credentials."
- **Potential consequence:** Failure behavior varies between RAG, GitHub, and Stack Overflow even when the user sees one assistant workflow.

### AD-4 and AD-5 leave error taxonomy underspecified

- **Location:** `AD-4 — Traceability is part of the state contract`; `Consistency Conventions / Fallbacks`
- **Divergence pair:** Retrieval failure sets `fallback_flag=True` and writes a final fallback answer; tool failure appends an external tool result with `status="error"` but leaves `fallback_flag=False`; clarification sets `clarification_flag=True` but no fallback. Each path is explicit and visible, but no shared taxonomy tells the UI or tests what kind of non-happy-path occurred.
- **Trigger condition:** The spine lists fallback, tool failure, and clarification as explicit state outcomes but does not define their relationship or enum values.
- **Guard snippet:** Add a domain outcome contract: `RunOutcome = answered | needs_clarification | degraded_answer | provider_unavailable | no_context | failed`, with field-level rules for when each flag/result can be set.
- **Potential consequence:** UI badges, tests, and final-answer wording can contradict each other across routes.

### Structural seed leaves ownership of domain/contracts.py too broad

- **Location:** `Structural Seed`; `AD-2 — Domain owns routes, state, and shared contracts`
- **Divergence pair:** Retrieval owns `RagObservation` in `domain/contracts.py`; tools own `ToolObservation` in the same file; answer composition owns `AnswerEnvelope` in the same file. All are in domain, but no one owns cross-contract compatibility or versioning, so fields can be optimized for one adapter and break another consumer.
- **Trigger condition:** AD-2 centralizes contracts in a module but does not assign entity ownership inside the domain layer or compatibility rules between contracts.
- **Guard snippet:** Split or specify domain contract ownership: `state.py` owns workflow state; `routes.py` owns route enum and route plans; `contracts.py` owns stable adapter port DTOs and must preserve backward-compatible fields consumed by workflows and UI.
- **Potential consequence:** "Domain owns it" becomes a dumping ground rather than a stable shared language.

### Deferred packaging can invalidate every structural import rule

- **Location:** `Deferred / Persistent package format`; `Structural Seed`
- **Divergence pair:** One slice imports via `src/supp_bro/...` and assumes editable install; another keeps Makefile/requirements script execution and imports by path manipulation. Both can obey the structural seed in source layout, but they are incompatible under tests and Streamlit startup.
- **Trigger condition:** The spine defers package format while simultaneously binding all product code under `src/supp_bro/`.
- **Guard snippet:** Tighten the deferred item or add an AD: "The first `src/supp_bro` slice must establish one import/install contract for local tests and Streamlit startup; no product module may rely on script-directory path mutation."
- **Potential consequence:** Early slices pass only from their own working directory and fail in CI or app launch.

### Provider normalization lacks source/citation identity requirements

- **Location:** `Consistency Conventions / Provider data`; `AD-4 — Traceability is part of the state contract`
- **Divergence pair:** RAG chunks normalize to `{text, score, metadata}`; GitHub issues normalize to `{title, url, state}`; Stack Overflow answers normalize to `{question_title, link, score}`. All provider payloads are normalized before entering workflow state, but final synthesis cannot uniformly cite or sort evidence.
- **Trigger condition:** Normalization is required, but canonical evidence identity, source type, confidence score, and citation fields are not.
- **Guard snippet:** Add an evidence contract: every observation item has `source_type`, `source_id`, `title`, `url_or_path`, `snippet`, `confidence`, and `raw_ref` redaction rules where applicable.
- **Potential consequence:** Final answers can mix evidence without reliable provenance, weakening traceability and user trust.

### Tests convention does not specify contract-level compatibility checks

- **Location:** `Consistency Conventions / Tests`
- **Divergence pair:** Domain tests validate `WorkflowState` construction; workflow tests assert route transitions using mocks; UI tests snapshot trace fields. Each satisfies the listed test categories, but none catches adapter request/response compatibility across package boundaries.
- **Trigger condition:** Test requirements name behavior areas but not consumer-driven or contract compatibility checks between one-level-down units.
- **Guard snippet:** Add a testing AD: "Every port contract has producer and consumer tests using shared fixtures from `tests/fixtures/domain_contracts.py`; workflow tests must execute mocked adapters through the same port methods used in production."
- **Potential consequence:** Interface drift reaches integration time despite passing focused unit tests.

## Gate Recommendation

Close the gate only after tightening the AD set around:

1. Canonical workflow state and trace shapes.
2. Field-level mutation ownership.
3. Route execution contracts.
4. Adapter input and output port contracts.
5. Operational policy for missing credentials, provider clients, timeouts, retries, and degraded outcomes.

