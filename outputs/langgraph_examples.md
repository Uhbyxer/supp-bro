# HW7 LangGraph workflow demo

Demo проганяє 5 питань через LangGraph implementation того самого SuppBro workflow з HW6.

| # | Question | Route | Executed nodes | RAG status | Tool | Needs clarification |
|---:|---|---|---|---|---|---|
| 1 | `Can I get exactly once delivery?` | `docs_answer` | `classify_request -> run_docs_rag -> build_answer` | `rag_disabled` | `none` | `False` |
| 2 | `Backpressure error says unable to acquire buffer lock and queue is full` | `issue_investigation` | `classify_request -> run_issue_rag -> read_github_issue -> build_answer` | `rag_disabled` | `get_github_issue_context` | `False` |
| 3 | `Is Debezium issue #3 still open and who worked on it?` | `issue_investigation` | `classify_request -> run_issue_rag -> read_github_issue -> build_answer` | `rag_disabled` | `get_github_issue_context` | `False` |
| 4 | `Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?` | `community_lookup` | `classify_request -> run_community_rag -> search_community -> build_answer` | `rag_disabled` | `search_stackoverflow_questions` | `False` |
| 5 | `Help with Debezium` | `clarification` | `classify_request -> ask_clarification -> build_answer` | `not_called` | `ask_clarifying_question` | `True` |

## Case 1: docs_answer

Input question: `Can I get exactly once delivery?`

Executed nodes: `classify_request -> run_docs_rag -> build_answer`

Final answer:

I could not produce a grounded docs answer from HW4 retrieval in this run. Check the RAG observation for the exact reason.

Final state:

```json
{
  "user_goal": "Can I get exactly once delivery?",
  "repo": "debezium/dbz",
  "issue_number": null,
  "allow_external_community_search": false,
  "github_token": null,
  "min_vector_score": 0.3,
  "enable_rag": false,
  "selected_route": "docs_answer",
  "route_reason": "The user asks a documentation-style question.",
  "plan": [
    {
      "name": "classify_intent",
      "purpose": "Determine whether the user needs docs, issue metadata, community search, or clarification.",
      "status": "completed",
      "detail": "HW5 route: docs_question"
    },
    {
      "name": "retrieve_docs",
      "purpose": "Ask HW4 RAG to answer from documentation chunks.",
      "status": "failed",
      "detail": "rag_disabled"
    },
    {
      "name": "compose_answer",
      "purpose": "Return the grounded documentation answer with citations when available.",
      "status": "completed",
      "detail": "Final answer created from LangGraph state."
    }
  ],
  "current_step": "compose_answer",
  "completed_steps": [
    "classify_intent",
    "compose_answer"
  ],
  "executed_nodes": [
    "classify_request",
    "run_docs_rag",
    "build_answer"
  ],
  "tool_calls": [],
  "observations": [
    {
      "kind": "route",
      "hw5_route": "docs_question",
      "selected_route": "docs_answer",
      "reason": "The user asks a documentation-style question."
    },
    {
      "kind": "rag",
      "source": "pages",
      "success": false,
      "status": "rag_disabled",
      "answer": "",
      "citations": [],
      "retrieved_context_by_id": {},
      "fallback_reason": "disabled_by_user",
      "error": null
    }
  ],
  "rag_calls": [
    {
      "source": "pages",
      "success": false,
      "status": "rag_disabled",
      "answer": "",
      "citations": [],
      "retrieved_context_by_id": {},
      "fallback_reason": "disabled_by_user",
      "error": null
    }
  ],
  "retrieved_context": {},
  "external_tool_results": [],
  "requires_clarification": false,
  "fallback_used": true,
  "final_answer": "I could not produce a grounded docs answer from HW4 retrieval in this run. Check the RAG observation for the exact reason."
}
```

## Case 2: issue_investigation

Input question: `Backpressure error says unable to acquire buffer lock and queue is full`

Executed nodes: `classify_request -> run_issue_rag -> read_github_issue -> build_answer`

Final answer:

Local RAG did not produce a grounded answer (rag_disabled: disabled_by_user). Live GitHub issue debezium/dbz#3 is open: mongodb :  Unable to acquire buffer lock, buffer queue is likely full. Labels: component/mongodb-connector, type/bug; assignees: no assignees; comments: 1; updated: 2025-12-03T08:47:35Z. URL: https://github.com/debezium/dbz/issues/3

Final state:

```json
{
  "user_goal": "Backpressure error says unable to acquire buffer lock and queue is full",
  "repo": "debezium/dbz",
  "issue_number": null,
  "allow_external_community_search": false,
  "github_token": null,
  "min_vector_score": 0.3,
  "enable_rag": false,
  "selected_route": "issue_investigation",
  "route_reason": "The user asks about a concrete error that may map to a known issue.",
  "plan": [
    {
      "name": "classify_intent",
      "purpose": "Determine whether the user needs docs, issue metadata, community search, or clarification.",
      "status": "completed",
      "detail": "HW5 route: known_issue_question"
    },
    {
      "name": "retrieve_issues",
      "purpose": "Ask HW4 RAG for local issue/document context.",
      "status": "failed",
      "detail": "rag_disabled"
    },
    {
      "name": "read_github_issue",
      "purpose": "Use the HW5 GitHub tool for live issue metadata.",
      "status": "completed",
      "detail": "get_github_issue_context"
    },
    {
      "name": "compose_answer",
      "purpose": "Combine retrieved context with live issue state.",
      "status": "completed",
      "detail": "Final answer created from LangGraph state."
    }
  ],
  "current_step": "compose_answer",
  "completed_steps": [
    "classify_intent",
    "read_github_issue",
    "compose_answer"
  ],
  "executed_nodes": [
    "classify_request",
    "run_issue_rag",
    "read_github_issue",
    "build_answer"
  ],
  "tool_calls": [
    {
      "tool_name": "get_github_issue_context",
      "tool_type": "read",
      "payload": {
        "repo": "debezium/dbz",
        "issue_number": 3
      },
      "confirmed": false
    }
  ],
  "observations": [
    {
      "kind": "route",
      "hw5_route": "known_issue_question",
      "selected_route": "issue_investigation",
      "reason": "The user asks about a concrete error that may map to a known issue."
    },
    {
      "kind": "rag",
      "source": "issues",
      "success": false,
      "status": "rag_disabled",
      "answer": "",
      "citations": [],
      "retrieved_context_by_id": {},
      "fallback_reason": "disabled_by_user",
      "error": null
    },
    {
      "kind": "tool",
      "tool_name": "get_github_issue_context",
      "success": true,
      "data": {
        "repo": "debezium/dbz",
        "issue_number": 3,
        "title": "mongodb :  Unable to acquire buffer lock, buffer queue is likely full",
        "state": "open",
        "labels": [
          "component/mongodb-connector",
          "type/bug"
        ],
        "assignees": [],
        "created_by": "bain2018",
        "created_at": "2025-11-27T08:20:34Z",
        "updated_at": "2025-12-03T08:47:35Z",
        "closed_at": null,
        "comment_count": 1,
        "participants": [
          "bain2018",
          "jpechane"
        ],
        "recent_comment_authors": [
          "jpechane"
        ],
        "url": "https://github.com/debezium/dbz/issues/3"
      },
      "error": null
    }
  ],
  "rag_calls": [
    {
      "source": "issues",
      "success": false,
      "status": "rag_disabled",
      "answer": "",
      "citations": [],
      "retrieved_context_by_id": {},
      "fallback_reason": "disabled_by_user",
      "error": null
    }
  ],
  "retrieved_context": {},
  "external_tool_results": [
    {
      "tool_name": "get_github_issue_context",
      "success": true,
      "data": {
        "repo": "debezium/dbz",
        "issue_number": 3,
        "title": "mongodb :  Unable to acquire buffer lock, buffer queue is likely full",
        "state": "open",
        "labels": [
          "component/mongodb-connector",
          "type/bug"
        ],
        "assignees": [],
        "created_by": "bain2018",
        "created_at": "2025-11-27T08:20:34Z",
        "updated_at": "2025-12-03T08:47:35Z",
        "closed_at": null,
        "comment_count": 1,
        "participants": [
          "bain2018",
          "jpechane"
        ],
        "recent_comment_authors": [
          "jpechane"
        ],
        "url": "https://github.com/debezium/dbz/issues/3"
      },
      "error": null
    }
  ],
  "requires_clarification": false,
  "fallback_used": true,
  "final_answer": "Local RAG did not produce a grounded answer (rag_disabled: disabled_by_user). Live GitHub issue debezium/dbz#3 is open: mongodb :  Unable to acquire buffer lock, buffer queue is likely full. Labels: component/mongodb-connector, type/bug; assignees: no assignees; comments: 1; updated: 2025-12-03T08:47:35Z. URL: https://github.com/debezium/dbz/issues/3"
}
```

## Case 3: issue_investigation

Input question: `Is Debezium issue #3 still open and who worked on it?`

Executed nodes: `classify_request -> run_issue_rag -> read_github_issue -> build_answer`

Final answer:

Local RAG did not produce a grounded answer (rag_disabled: disabled_by_user). Live GitHub issue debezium/dbz#3 is open: mongodb :  Unable to acquire buffer lock, buffer queue is likely full. Labels: component/mongodb-connector, type/bug; assignees: no assignees; comments: 1; updated: 2025-12-03T08:47:35Z. URL: https://github.com/debezium/dbz/issues/3

Final state:

```json
{
  "user_goal": "Is Debezium issue #3 still open and who worked on it?",
  "repo": "debezium/dbz",
  "issue_number": 3,
  "allow_external_community_search": false,
  "github_token": null,
  "min_vector_score": 0.3,
  "enable_rag": false,
  "selected_route": "issue_investigation",
  "route_reason": "The user asks about current GitHub issue metadata.",
  "plan": [
    {
      "name": "classify_intent",
      "purpose": "Determine whether the user needs docs, issue metadata, community search, or clarification.",
      "status": "completed",
      "detail": "HW5 route: known_issue_question"
    },
    {
      "name": "retrieve_issues",
      "purpose": "Ask HW4 RAG for local issue/document context.",
      "status": "failed",
      "detail": "rag_disabled"
    },
    {
      "name": "read_github_issue",
      "purpose": "Use the HW5 GitHub tool for live issue metadata.",
      "status": "completed",
      "detail": "get_github_issue_context"
    },
    {
      "name": "compose_answer",
      "purpose": "Combine retrieved context with live issue state.",
      "status": "completed",
      "detail": "Final answer created from LangGraph state."
    }
  ],
  "current_step": "compose_answer",
  "completed_steps": [
    "classify_intent",
    "read_github_issue",
    "compose_answer"
  ],
  "executed_nodes": [
    "classify_request",
    "run_issue_rag",
    "read_github_issue",
    "build_answer"
  ],
  "tool_calls": [
    {
      "tool_name": "get_github_issue_context",
      "tool_type": "read",
      "payload": {
        "repo": "debezium/dbz",
        "issue_number": 3
      },
      "confirmed": false
    }
  ],
  "observations": [
    {
      "kind": "route",
      "hw5_route": "known_issue_question",
      "selected_route": "issue_investigation",
      "reason": "The user asks about current GitHub issue metadata."
    },
    {
      "kind": "rag",
      "source": "issues",
      "success": false,
      "status": "rag_disabled",
      "answer": "",
      "citations": [],
      "retrieved_context_by_id": {},
      "fallback_reason": "disabled_by_user",
      "error": null
    },
    {
      "kind": "tool",
      "tool_name": "get_github_issue_context",
      "success": true,
      "data": {
        "repo": "debezium/dbz",
        "issue_number": 3,
        "title": "mongodb :  Unable to acquire buffer lock, buffer queue is likely full",
        "state": "open",
        "labels": [
          "component/mongodb-connector",
          "type/bug"
        ],
        "assignees": [],
        "created_by": "bain2018",
        "created_at": "2025-11-27T08:20:34Z",
        "updated_at": "2025-12-03T08:47:35Z",
        "closed_at": null,
        "comment_count": 1,
        "participants": [
          "bain2018",
          "jpechane"
        ],
        "recent_comment_authors": [
          "jpechane"
        ],
        "url": "https://github.com/debezium/dbz/issues/3"
      },
      "error": null
    }
  ],
  "rag_calls": [
    {
      "source": "issues",
      "success": false,
      "status": "rag_disabled",
      "answer": "",
      "citations": [],
      "retrieved_context_by_id": {},
      "fallback_reason": "disabled_by_user",
      "error": null
    }
  ],
  "retrieved_context": {},
  "external_tool_results": [
    {
      "tool_name": "get_github_issue_context",
      "success": true,
      "data": {
        "repo": "debezium/dbz",
        "issue_number": 3,
        "title": "mongodb :  Unable to acquire buffer lock, buffer queue is likely full",
        "state": "open",
        "labels": [
          "component/mongodb-connector",
          "type/bug"
        ],
        "assignees": [],
        "created_by": "bain2018",
        "created_at": "2025-11-27T08:20:34Z",
        "updated_at": "2025-12-03T08:47:35Z",
        "closed_at": null,
        "comment_count": 1,
        "participants": [
          "bain2018",
          "jpechane"
        ],
        "recent_comment_authors": [
          "jpechane"
        ],
        "url": "https://github.com/debezium/dbz/issues/3"
      },
      "error": null
    }
  ],
  "requires_clarification": false,
  "fallback_used": true,
  "final_answer": "Local RAG did not produce a grounded answer (rag_disabled: disabled_by_user). Live GitHub issue debezium/dbz#3 is open: mongodb :  Unable to acquire buffer lock, buffer queue is likely full. Labels: component/mongodb-connector, type/bug; assignees: no assignees; comments: 1; updated: 2025-12-03T08:47:35Z. URL: https://github.com/debezium/dbz/issues/3"
}
```

## Case 4: community_lookup

Input question: `Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?`

Executed nodes: `classify_request -> run_community_rag -> search_community -> build_answer`

Final answer:

I did not find matching Stack Overflow questions. Local RAG observation is available in the trace.

Final state:

```json
{
  "user_goal": "Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?",
  "repo": "debezium/dbz",
  "issue_number": null,
  "allow_external_community_search": true,
  "github_token": null,
  "min_vector_score": 0.3,
  "enable_rag": false,
  "selected_route": "community_lookup",
  "route_reason": "The user asks for external community troubleshooting.",
  "plan": [
    {
      "name": "classify_intent",
      "purpose": "Determine whether the user needs docs, issue metadata, community search, or clarification.",
      "status": "completed",
      "detail": "HW5 route: community_troubleshooting"
    },
    {
      "name": "retrieve_issues",
      "purpose": "Check local context first, so external community results are not the only source.",
      "status": "failed",
      "detail": "rag_disabled"
    },
    {
      "name": "search_community",
      "purpose": "Use the HW5 Stack Overflow tool only when confirmation is enabled.",
      "status": "completed",
      "detail": "search_stackoverflow_questions"
    },
    {
      "name": "compose_answer",
      "purpose": "Explain community results and their limits.",
      "status": "completed",
      "detail": "Final answer created from LangGraph state."
    }
  ],
  "current_step": "compose_answer",
  "completed_steps": [
    "classify_intent",
    "search_community",
    "compose_answer"
  ],
  "executed_nodes": [
    "classify_request",
    "run_community_rag",
    "search_community",
    "build_answer"
  ],
  "tool_calls": [
    {
      "tool_name": "search_stackoverflow_questions",
      "tool_type": "read",
      "payload": {
        "query": "Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?",
        "tag": "debezium",
        "max_results": 5
      },
      "confirmed": true
    }
  ],
  "observations": [
    {
      "kind": "route",
      "hw5_route": "community_troubleshooting",
      "selected_route": "community_lookup",
      "reason": "The user asks for external community troubleshooting."
    },
    {
      "kind": "rag",
      "source": "issues",
      "success": false,
      "status": "rag_disabled",
      "answer": "",
      "citations": [],
      "retrieved_context_by_id": {},
      "fallback_reason": "disabled_by_user",
      "error": null
    },
    {
      "kind": "tool",
      "tool_name": "search_stackoverflow_questions",
      "success": true,
      "data": {
        "query": "Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?",
        "normalized_query": "debezium unable to acquire buffer lock",
        "tag": "debezium",
        "count": 0,
        "results": []
      },
      "error": null
    }
  ],
  "rag_calls": [
    {
      "source": "issues",
      "success": false,
      "status": "rag_disabled",
      "answer": "",
      "citations": [],
      "retrieved_context_by_id": {},
      "fallback_reason": "disabled_by_user",
      "error": null
    }
  ],
  "retrieved_context": {},
  "external_tool_results": [
    {
      "tool_name": "search_stackoverflow_questions",
      "success": true,
      "data": {
        "query": "Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?",
        "normalized_query": "debezium unable to acquire buffer lock",
        "tag": "debezium",
        "count": 0,
        "results": []
      },
      "error": null
    }
  ],
  "requires_clarification": false,
  "fallback_used": false,
  "final_answer": "I did not find matching Stack Overflow questions. Local RAG observation is available in the trace."
}
```

## Case 5: clarification

Input question: `Help with Debezium`

Executed nodes: `classify_request -> ask_clarification -> build_answer`

Final answer:

I need more detail before choosing a reliable route. Which Debezium connector are you using? What is the exact error message? Do you want to search local docs/issues or external community sources?

Final state:

```json
{
  "user_goal": "Help with Debezium",
  "repo": "debezium/dbz",
  "issue_number": null,
  "allow_external_community_search": false,
  "github_token": null,
  "min_vector_score": 0.3,
  "enable_rag": false,
  "selected_route": "clarification",
  "route_reason": "The query is too vague to choose a reliable tool.",
  "plan": [
    {
      "name": "classify_intent",
      "purpose": "Determine whether the user needs docs, issue metadata, community search, or clarification.",
      "status": "completed",
      "detail": "HW5 route: clarification"
    },
    {
      "name": "ask_clarifying_question",
      "purpose": "Use the HW5 clarification tool instead of guessing.",
      "status": "completed",
      "detail": "ask_clarifying_question"
    },
    {
      "name": "compose_answer",
      "purpose": "Return targeted follow-up questions.",
      "status": "completed",
      "detail": "Final answer created from LangGraph state."
    }
  ],
  "current_step": "compose_answer",
  "completed_steps": [
    "classify_intent",
    "ask_clarifying_question",
    "compose_answer"
  ],
  "executed_nodes": [
    "classify_request",
    "ask_clarification",
    "build_answer"
  ],
  "tool_calls": [
    {
      "tool_name": "ask_clarifying_question",
      "tool_type": "read",
      "payload": {
        "query": "Help with Debezium"
      },
      "confirmed": false
    }
  ],
  "observations": [
    {
      "kind": "route",
      "hw5_route": "clarification",
      "selected_route": "clarification",
      "reason": "The query is too vague to choose a reliable tool."
    },
    {
      "kind": "tool",
      "tool_name": "ask_clarifying_question",
      "success": true,
      "data": {
        "original_query": "Help with Debezium",
        "clarifying_questions": [
          "Which Debezium connector are you using?",
          "What is the exact error message?",
          "Do you want to search local docs/issues or external community sources?"
        ]
      },
      "error": null
    }
  ],
  "rag_calls": [],
  "retrieved_context": {},
  "external_tool_results": [
    {
      "tool_name": "ask_clarifying_question",
      "success": true,
      "data": {
        "original_query": "Help with Debezium",
        "clarifying_questions": [
          "Which Debezium connector are you using?",
          "What is the exact error message?",
          "Do you want to search local docs/issues or external community sources?"
        ]
      },
      "error": null
    }
  ],
  "requires_clarification": true,
  "fallback_used": false,
  "final_answer": "I need more detail before choosing a reliable route. Which Debezium connector are you using? What is the exact error message? Do you want to search local docs/issues or external community sources?"
}
```
