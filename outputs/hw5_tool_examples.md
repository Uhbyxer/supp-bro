# HW5 tool examples

## Example 1: GitHub issue status

User question:

```text
Is Debezium issue #3 still open?
```

Tool called:

```text
get_github_issue_context
```

Input:

```json
{
  "repo": "debezium/dbz",
  "issue_number": 3
}
```

Result:

```text
The tool reads GitHub issue metadata: state, title, labels, assignees, participants, comments, updated_at and URL.
```

Final answer:

```text
The assistant answers with the current GitHub issue status and links to the issue.
```

Why tool is better than retrieval:

```text
RAG can retrieve an old issue chunk, but it cannot know the current GitHub state, labels, assignees or recent activity.
```

## Example 2: Known error with issue override

User question:

```text
MongoDB connector backpressure error says unable to acquire buffer lock and queue is full
```

Tool called:

```text
get_github_issue_context
```

Input:

```json
{
  "repo": "debezium/dbz",
  "issue_number": 3
}
```

Final answer:

```text
The assistant combines the known issue route with current GitHub metadata.
```

Why tool is better than retrieval:

```text
Retrieval explains what the issue is about. The external tool adds current status and ownership/activity signals.
```

## Example 3: Documentation question

User question:

```text
Can I get exactly once delivery?
```

Tool called:

```text
none
```

Final answer:

```text
This is a documentation-style question. Use local Debezium docs RAG; no external tool is needed.
```

Why tool is better than retrieval:

```text
It is not better here. This example shows that the router should avoid external tools when static docs retrieval is the right source.
```

## Example 4: Community troubleshooting

User question:

```text
Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?
```

Tool called:

```text
search_stackoverflow_questions
```

Input:

```json
{
  "query": "Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?",
  "tag": "debezium",
  "max_results": 5
}
```

Final answer:

```text
The assistant summarizes Stack Overflow search results only when external community search is explicitly allowed.
```

Why tool is better than retrieval:

```text
Local RAG may not include community discussions or recent workarounds. Stack Overflow search can find external reports, but it is less authoritative than docs/issues.
```

## Example 5: Clarification

User question:

```text
Help
```

Tool called:

```text
ask_clarifying_question
```

Final answer:

```text
The assistant asks which connector is used, what the exact error message is, and whether to search local or external sources.
```

Why tool is better than retrieval:

```text
The query is too vague. A clarification step prevents weak retrieval, wrong external tool calls, and hallucinated troubleshooting.
```
