# HW6 agentic workflow examples

Цей файл показує 5 прикладів трасування для контрольованого workflow. Повний JSON state генерується командою:

```bash
python scripts/hw6/agentic_workflow.py --mode demo --output-json hw6-agentic-workflow-result.json
```

## Summary

| # | Query | Route | RAG | Tool | Чому це корисно |
|---:|---|---|---|---|---|
| 1 | `Can I get exactly once delivery?` | `docs_answer` | `pages` | `none` | Документаційне питання не потребує external API. |
| 2 | `Backpressure error says unable to acquire buffer lock and queue is full` | `issue_investigation` | `issues` | `get_github_issue_context` | RAG шукає локальний context, а GitHub tool додає live статус issue. |
| 3 | `Is Debezium issue #3 still open and who worked on it?` | `issue_investigation` | `issues` | `get_github_issue_context` | Retrieval може бути snapshot-ом, тому current metadata краще брати з GitHub. |
| 4 | `Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?` | `community_lookup` | `issues` | `search_stackoverflow_questions` | Community search має сенс тільки коли користувач явно просить зовнішні джерела. |
| 5 | `Help with Debezium` | `clarification` | `not_called` | `ask_clarifying_question` | Нечіткий запит краще уточнити, ніж випадково викликати RAG або tool. |

## Case 1: docs answer

Trace:

```json
{
  "user_goal": "Can I get exactly once delivery?",
  "selected_route": "docs_answer",
  "steps": ["classify_intent", "retrieve_docs", "compose_answer"],
  "rag_source": "pages",
  "tool_calls": [],
  "expected_behavior": "Return a grounded docs answer with citations when HW4 credentials are configured."
}
```

Перевага над external tool: це authoritative documentation question, тому GitHub або Stack Overflow тільки додали б шум.

## Case 2: known error

Trace:

```json
{
  "user_goal": "Backpressure error says unable to acquire buffer lock and queue is full",
  "selected_route": "issue_investigation",
  "steps": ["classify_intent", "retrieve_issues", "read_github_issue", "compose_answer"],
  "rag_source": "issues",
  "tool_calls": [
    {
      "tool_name": "get_github_issue_context",
      "payload": {"repo": "debezium/dbz", "issue_number": 3}
    }
  ],
  "expected_behavior": "Combine local issue context with live GitHub issue status."
}
```

Перевага над retrieval: local issue chunk може пояснити симптом, але не гарантує актуальний `state`, labels, assignees або last update.

## Case 3: exact issue metadata

Trace:

```json
{
  "user_goal": "Is Debezium issue #3 still open and who worked on it?",
  "selected_route": "issue_investigation",
  "steps": ["classify_intent", "retrieve_issues", "read_github_issue", "compose_answer"],
  "rag_source": "issues",
  "tool_calls": [
    {
      "tool_name": "get_github_issue_context",
      "payload": {"repo": "debezium/dbz", "issue_number": 3}
    }
  ],
  "expected_behavior": "Use GitHub as source of truth for current issue metadata."
}
```

Перевага над retrieval: питання прямо просить current state і людей навколо issue, а це live API data.

## Case 4: community lookup

Trace:

```json
{
  "user_goal": "Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?",
  "selected_route": "community_lookup",
  "steps": ["classify_intent", "retrieve_issues", "search_community", "compose_answer"],
  "rag_source": "issues",
  "tool_calls": [
    {
      "tool_name": "search_stackoverflow_questions",
      "payload": {"query": "Debezium unable to acquire buffer lock", "tag": "debezium"}
    }
  ],
  "expected_behavior": "Search external community reports only after confirmation."
}
```

Перевага над retrieval: локальна база не містить Stack Overflow discussions, але результат треба позначати як community source, не як офіційну документацію.

## Case 5: clarification

Trace:

```json
{
  "user_goal": "Help with Debezium",
  "selected_route": "clarification",
  "steps": ["classify_intent", "ask_clarifying_question", "compose_answer"],
  "rag_source": "not_called",
  "tool_calls": [
    {
      "tool_name": "ask_clarifying_question",
      "payload": {"query": "Help with Debezium"}
    }
  ],
  "expected_behavior": "Ask which connector, exact error, and preferred source before searching."
}
```

Перевага над retrieval: нечіткий запит легко веде до випадкового context, тому agentic workflow має право зупинитись і перепитати.
