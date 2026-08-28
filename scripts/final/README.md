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

See [`FINAL_IMPROVEMENT.md`](../../FINAL_IMPROVEMENT.md) for the before/after explanation and verification plan.