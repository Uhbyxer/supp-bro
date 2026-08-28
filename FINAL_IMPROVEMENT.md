# Final Improvement: Route-Aware GitHub Issue Metadata Lookup

## Weak Point Before

The HW7 workflow correctly routed explicit GitHub issue questions to `issue_investigation`, but it always ran local issue RAG before calling the GitHub tool.

For example:

```text
Question: Is Debezium issue #3 still open and who worked on it?
Before:   classify_request -> run_issue_rag -> read_github_issue -> build_answer
RAG:      model_fallback
Tool:     get_github_issue_context success
```

This was functional, but not ideal. The question asks for live issue metadata: state, assignees, labels, participants, comments, updated date, and URL. Local RAG is not the best source for that data because it can be stale or incomplete. Running it first added an expected fallback to the trace and made the workflow look noisier than necessary.

## Improvement After

The final workflow detects explicit GitHub issue metadata questions and skips local issue RAG for that branch.

```text
Question: Is Debezium issue #3 still open and who worked on it?
After:    classify_request -> read_github_issue -> build_answer
RAG:      not_called
Tool:     get_github_issue_context success
```

The workflow still uses RAG for issue-like error questions that need local context before checking a related GitHub issue.

```text
Question: Backpressure error says unable to acquire buffer lock and queue is full
After:    classify_request -> run_issue_rag -> read_github_issue -> build_answer
RAG:      called
Tool:     get_github_issue_context success
```

## Detection Rule

The workflow skips issue RAG only when both are true:

- the user provides an explicit issue number, either in the question or through `--issue-number`;
- the question asks for live metadata such as status, open/closed state, assignees, labels, participants, comments, updates, or who worked on the issue.

This keeps the improvement narrow: exact issue metadata goes directly to the live tool, while broader issue investigation can still combine local RAG context with GitHub metadata.

## Files

| File | Purpose |
|---|---|
| `scripts/final/langgraph_flow.py` | Final route-aware LangGraph workflow. |
| `scripts/final/streamlit_app.py` | Streamlit dashboard for the final workflow. |
| `scripts/final/test_langgraph_flow.py` | Unit tests for final routing behavior. |
| `scripts/final/README.md` | Final workflow run instructions. |

## Verification

Run the focused tests:

```bash
python -m unittest scripts/final/test_langgraph_flow.py
```

Run the final demo without external RAG credentials:

```bash
python scripts/final/langgraph_flow.py --mode demo --disable-rag
```

The explicit issue metadata case should show:

```text
classify_request -> read_github_issue -> build_answer
RAG status: not_called
```