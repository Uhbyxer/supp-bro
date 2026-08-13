# HW5: external support tools

У цьому завданні я додав intent-based orchestration для support assistant. Ідея така: перед викликом retrieval або external tool агент спочатку визначає, що саме хоче користувач: знайти відповідь у документації, перевірити known issue, зарепортати новий issue, пошукати community workaround або уточнити нечіткий запит.

Pipeline:

```text
user question → support intent router → tool request → validation → external source → normalized observation → final answer
```

## Routes

| Route | Коли використовується | Поведінка |
|---|---|---|
| `docs_question` | Питання схоже на документаційне | External tool не викликається; відповідь має йти через local docs RAG. |
| `known_issue_question` | Питання про issue, bug, error або current status | Викликається GitHub issue context tool. |
| `report_new_issue` | Користувач хоче створити або зарепортати bug | Агент просить уточнення, щоб підготувати issue report. |
| `community_troubleshooting` | Користувач просить external/community workaround | Stack Overflow search викликається тільки після confirmation flag. |
| `clarification` | Запит занадто нечіткий | Агент повертає уточнюючі питання. |

## Tools

### `get_github_issue_context`

Read-only tool, який читає GitHub REST API і повертає актуальний structured context по issue.

Коли викликати:
- RAG або router знайшов конкретний Debezium issue.
- Користувач питає, чи issue still open/closed.
- Користувач питає про labels, assignees, participants або activity.

Коли не викликати:
- Загальне документаційне питання.
- Нерелевантний або занадто нечіткий запит без issue number.

Input:

```json
{
  "repo": "debezium/dbz",
  "issue_number": 3
}
```

Output:

```json
{
  "repo": "debezium/dbz",
  "issue_number": 3,
  "title": "...",
  "state": "open",
  "labels": ["..."],
  "assignees": ["..."],
  "created_by": "...",
  "updated_at": "...",
  "comment_count": 5,
  "participants": ["..."],
  "recent_comment_authors": ["..."],
  "url": "https://github.com/debezium/dbz/issues/3"
}
```

### `search_stackoverflow_questions`

Read-only tool, який читає Stack Exchange API і шукає Stack Overflow questions по query і tag.

Коли викликати:
- Користувач явно просить community/Stack Overflow/workaround.
- Local retrieval слабкий і користувач погодився на external community search.

Коли не викликати:
- Без confirmation.
- Для authoritative docs answer, де достатньо local RAG.

Input:

```json
{
  "query": "Debezium unable to acquire buffer lock",
  "tag": "debezium",
  "max_results": 5
}
```

Output:

```json
{
  "query": "Debezium unable to acquire buffer lock",
  "normalized_query": "debezium unable to acquire buffer lock",
  "tag": "debezium",
  "count": 2,
  "results": [
    {
      "title": "...",
      "score": 3,
      "answer_count": 1,
      "is_answered": true,
      "last_activity_date": 1760000000,
      "url": "https://stackoverflow.com/questions/..."
    }
  ]
}
```

## Validation

Перед виконанням tool layer перевіряє:

| Field | Validation |
|---|---|
| `repo` | Обов'язковий формат `owner/name`. |
| `issue_number` | Додатне integer value. |
| `query` | Non-empty string, максимум 300 characters. |
| `tag` | Safe Stack Overflow tag string. |
| community search | Потрібен explicit confirmation flag `--allow-external-community-search`. |

Tool layer не приймає raw SQL або довільні небезпечні запити від моделі. Усі tool calls проходять через typed `ToolRequest` і повертають normalized `ToolObservation`.

## Чому tool корисніший за retrieval

HW5 не замінює retrieval повністю. Router вирішує, коли local RAG достатній, а коли треба external tool. Це важливо, бо не кожне питання виграє від зовнішнього API.

| Case | Чому retrieval недостатній | Чому tool кращий |
|---|---|---|
| GitHub issue status | Retrieved issue chunk є snapshot-ом і може бути застарілим. | GitHub API повертає live `state`, `updated_at`, `closed_at`, labels і URL. |
| Issue ownership/activity | Chunk може містити текст issue, але не показує актуальних assignees або recent commenters. | `get_github_issue_context` читає assignees, participants і recent comment authors. |
| Known error mapped to issue | RAG пояснює зміст помилки, але не знає, чи issue досі активний. | Tool додає current metadata до знайденого known issue. |
| Stack Overflow/community lookup | Local knowledge base не містить зовнішні community discussions і може не мати recent workarounds. | Stack Exchange API шукає external reports по tag `debezium`; результат явно позначений як community source. |
| Clarification | Для дуже нечіткого запиту weak retrieval може знайти випадковий context. | Clarification path зупиняє неправильний tool/RAG call і просить connector, exact error message та бажаний source. |
| Documentation question | Тут retrieval якраз достатній. | External tool не викликається; router повертає `docs_question`, щоб не змішувати authoritative docs із community/API data. |

## Покриття критеріїв оцінювання

| Критерій | Де покрито |
|---|---|
| Tool описаний: назва, тип, мета, коли викликати | Секція `Tools`: `get_github_issue_context` і `search_stackoverflow_questions` описані як read-only tools із правилами when to call / when not to call. |
| Input / output contract визначено | У секції `Tools` є JSON input/output examples для обох tools. |
| Validation реалізовано | `scripts/hw5/external_tool_router.py`: `validate_repo`, `validate_issue_number`, `validate_search_query`, `validate_tag`, `validate_tool_request`. |
| Tool реалізовано і запускається | `get_github_issue_context` читає GitHub REST API, `search_stackoverflow_questions` читає Stack Exchange API. Локальний CLI і GitHub Actions запускають ті самі tools. |
| 3-5 прикладів з поясненням переваги перед retrieval | `outputs/hw5_tool_examples.md` містить 5 examples, а секція `Чому tool корисніший за retrieval` узагальнює аргументацію. |
| Виклик через orchestration layer або модель показано | `classify_support_intent` → `build_tool_request` → `validate_tool_request` → `execute_tool_request` → `ToolObservation` → `final_answer`. |

## Запуск локально

Single mode:

```bash
python scripts/hw5/external_tool_router.py \
  "Is Debezium issue #3 still open?" \
  --output-json hw5-external-tool-result.json \
  --output-md hw5-external-tool-summary.md
```

Community search вимагає confirmation flag:

```bash
python scripts/hw5/external_tool_router.py \
  "Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?" \
  --allow-external-community-search
```

Demo mode проганяє 5 predefined cases одним запуском: docs question, explicit GitHub issue, known error, confirmed Stack Overflow lookup і clarification.

```bash
python scripts/hw5/external_tool_router.py \
  --mode demo \
  --output-json hw5-external-tool-result.json \
  --output-md hw5-external-tool-summary.md
```

## GitHub Actions

Workflow `Run HW5 External Tool Demo` дозволяє запустити той самий tool router через `workflow_dispatch`.

Inputs:

| Input | Meaning |
|---|---|
| `mode` | `single` для одного question або `demo` для predefined matrix. |
| `question` | User question для routing. Потрібний тільки в `single` mode. |
| `repo` | GitHub repo, default `debezium/dbz`. |
| `issue_number` | Optional issue number override. |
| `allow_external_community_search` | Confirmation flag для Stack Overflow search. |

Workflow зберігає artifacts:

```text
hw5-external-tool-result.json
hw5-external-tool-summary.md
```

## Multi-step clarification

Скрипт не зберігає server-side chat state. Multi-step сценарій показується як два deterministic CLI/Actions runs:

1. Нечіткий запит повертає `requires_clarification=true` і список уточнюючих питань.
2. Другий запуск із уточненим питанням або `issue_number` викликає відповідний external tool.

Це дозволяє показати agentic pattern без деплою повноцінного chatbot server.
