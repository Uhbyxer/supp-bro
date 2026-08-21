# HW7: LangGraph workflow для SuppBro

У HW7 я переніс custom agentic workflow з HW6 на LangGraph. Логіка бота залишилась та сама: користувач питає про Debezium, агент визначає route, запускає потрібний retrieval або external tool, записує observations у state і формує фінальну відповідь.

LangGraph обраний тому, що він природно описує те, що в HW6 було зроблено вручну: `State`, `Nodes`, `Edges` і conditional routing. Для маленького workflow це трохи більше boilerplate, але структура стає видимою як граф.

## Як запускати

Single question:

```bash
python scripts/hw7/langgraph_flow.py \
  "Is Debezium issue #3 still open and who worked on it?" \
  --issue-number 3 \
  --output-json hw7-langgraph-result.json \
  --output-md hw7-langgraph-summary.md
```

Demo на 5 питаннях:

```bash
python scripts/hw7/langgraph_flow.py \
  --mode demo \
  --output-json hw7-langgraph-result.json \
  --output-md outputs/langgraph_examples.md
```

Якщо треба прогнати без HW4 credentials:

```bash
python scripts/hw7/langgraph_flow.py \
  --mode demo \
  --disable-rag \
  --output-md outputs/langgraph_examples.md
```

Streamlit demo:

```bash
make hw7-streamlit
```

## State

State визначений як `TypedDict` у `scripts/hw7/langgraph_flow.py`.

| Field | Для чого |
|---|---|
| `user_goal` | Початкове питання користувача. |
| `selected_route` | Route після classification: docs, issue, community або clarification. |
| `route_reason` | Чому classifier вибрав цей route. |
| `plan` | Людинозрозумілий plan зі статусами кроків. |
| `executed_nodes` | Реальна послідовність LangGraph nodes. |
| `rag_calls` | HW4 retrieval observations. |
| `tool_calls` | HW5 tool requests. |
| `external_tool_results` | HW5 tool observations. |
| `observations` | Загальна timeline-стрічка route/RAG/tool events. |
| `final_answer` | Відповідь, зібрана з фінального state. |

## Nodes

| Node | Що робить |
|---|---|
| `classify_request` | Викликає HW5 classifier, вибирає route і будує plan. |
| `run_docs_rag` | Запускає HW4 RAG по documentation chunks. |
| `run_issue_rag` | Запускає HW4 RAG по issue chunks. |
| `run_community_rag` | Спочатку перевіряє local issue context перед community lookup. |
| `read_github_issue` | Викликає HW5 GitHub tool для live issue metadata. |
| `search_community` | Викликає HW5 Stack Overflow tool, якщо community search дозволений. |
| `ask_clarification` | Повертає уточнюючі питання замість випадкового retrieval. |
| `build_answer` | Формує фінальну відповідь із LangGraph state. |

## Edges

Після `classify_request` використовується conditional edge:

| Route | Наступний node |
|---|---|
| `docs_answer` | `run_docs_rag` |
| `issue_investigation` | `run_issue_rag` |
| `community_lookup` | `run_community_rag` |
| `clarification` | `ask_clarification` |

Далі workflow завершується через `build_answer`.

```text
classify_request
  -> run_docs_rag -> build_answer
  -> run_issue_rag -> read_github_issue -> build_answer
  -> run_community_rag -> search_community -> build_answer
  -> ask_clarification -> build_answer
```

## Приклади

Файл з результатами demo: `outputs/langgraph_examples.md`.

Demo запускає ті самі 5 питань, які використовувались у HW6:

| # | Тип | Query | Очікуваний route |
|---:|---|---|---|
| 1 | Документаційне питання | `Can I get exactly once delivery?` | `docs_answer` |
| 2 | Known error | `Backpressure error says unable to acquire buffer lock and queue is full` | `issue_investigation` |
| 3 | Точний GitHub issue | `Is Debezium issue #3 still open and who worked on it?` | `issue_investigation` |
| 4 | Community search | `Has anyone seen Debezium unable to acquire buffer lock on Stack Overflow?` | `community_lookup` |
| 5 | Нечітке питання | `Help with Debezium` | `clarification` |

## Streamlit

Streamlit перенесений на HW7 і тепер показує не тільки plan/RAG/tools/state, а й фактичний список `executed_nodes`. Це зручно для демонстрації framework workflow: видно, якими LangGraph nodes пройшло конкретне питання.

Запуск:

```bash
python -m streamlit run scripts/hw7/streamlit_app.py
```

## Custom HW6 vs LangGraph HW7

| Аспект | Custom HW6 | LangGraph HW7 |
|---|---|---|
| Структура workflow | Послідовність кроків описана вручну через `if/else`. | Nodes і edges явно описані в graph definition. |
| State | Dataclass, який ми самі передаємо і змінюємо. | `TypedDict`, який проходить через LangGraph nodes. |
| Conditional routing | Звичайна умова в Python-коді. | Explicit conditional edge після `classify_request`. |
| Debug/demo | Треба читати custom trace fields. | Окремо видно `executed_nodes`, тобто реальний шлях у графі. |
| Складність | Менше boilerplate для малого workflow. | Більше коду, але краще масштабується для нових routes/nodes. |

Висновок: для HW6 custom implementation був достатній, бо workflow невеликий. Для HW7 LangGraph корисний тим, що робить route branching явним і краще підходить для наступного розвитку SuppBro: додавання нових tools, окремого review node, retry/fallback paths або людського clarification step.
