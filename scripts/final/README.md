# Final project: route-aware SuppBro workflow

This folder contains the final project workflow. It is based on the HW7 LangGraph implementation, but lives separately from the homework folders and adds one focused improvement: explicit GitHub issue metadata questions skip local issue RAG and go directly to the GitHub issue tool.

## How to run

Single question:

```bash
python scripts/final/langgraph_flow.py \
  "Is Debezium issue #3 still open and who worked on it?" \
  --issue-number 3 \
  --output-json final-langgraph-result.json \
  --output-md final-langgraph-summary.md
```

Demo on five questions:

```bash
python scripts/final/langgraph_flow.py \
  --mode demo \
  --output-json final-langgraph-result.json \
  --output-md outputs/final_langgraph_examples.md
```

Run without HW4 credentials:

```bash
python scripts/final/langgraph_flow.py \
  --mode demo \
  --disable-rag \
  --output-md outputs/final_langgraph_examples.md
```

Streamlit demo:

```bash
make final-streamlit
```

## Routes

| Route | Purpose |
|---|---|
| `docs_answer` | Answer documentation-style questions using local RAG. |
| `issue_investigation` | Investigate known issues using local issue context and/or live GitHub metadata. |
| `community_lookup` | Search Stack Overflow/community sources for explicitly community-oriented questions. |
| `clarification` | Ask follow-up questions when the request is too vague. |

## Final improvement

### Weak point before

The HW7 workflow correctly routed explicit GitHub issue questions to `issue_investigation`, but it always ran local issue RAG before calling the GitHub tool.

For example:

```text
Question: Is Debezium issue #3 still open and who worked on it?
Before:   classify_request -> run_issue_rag -> read_github_issue -> build_answer
RAG:      model_fallback
Tool:     get_github_issue_context success
```

This was functional, but not ideal. The question asks for live issue metadata: state, assignees, labels, participants, comments, updated date, and URL. Local RAG is not the best source for that data because it can be stale or incomplete. Running it first added an expected fallback to the trace and made the workflow look noisier than necessary.

### Improvement after

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

### Detection rule

The workflow skips issue RAG only when both are true:

- the user provides an explicit issue number, either in the question or through `--issue-number`;
- the question asks for live metadata such as status, open/closed state, assignees, labels, participants, comments, updates, or who worked on the issue.

This keeps the improvement narrow: exact issue metadata goes directly to the live tool, while broader issue investigation can still combine local RAG context with GitHub metadata.

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