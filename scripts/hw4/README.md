# HW4: grounded answer generation

This task evaluates a grounded RAG answer-generation pipeline for Debezium support questions. The goal is not only to produce an answer, but to show when the system should refuse to answer because retrieval is weak or the model cannot ground its response in the returned chunks.

Pipeline:

```text
question → source filter → Pinecone + BM25 → RRF → Top-5 → prompt flavor → LLM → optional post-validator
```

Використано найкращий pipeline HW3: hybrid retrieval із правильним `source` дав Top-1 90%, Hit@5 100%, MRR 0.95 і Precision@5 64%.

## Prompt і grounding

LLM повертає строгий JSON із `has_enough_context`, `answer` і окремим списком `citations`. Код перевіряє кожну citation проти retrieved `chunk_id`; тому форматування тексту відповіді більше не може випадково спричинити fallback.

Є два prompt flavors:

| Flavor | Поведінка |
|---|---|
| `strong` | Строгий grounded prompt. Відповідає лише коли context прямо підтримує відповідь. |
| `weak` | Слабкий prompt. Просто просить відповісти на питання і додати citations, якщо це можливо. |

Post-validator можна вмикати окремо:

| Post-validator | Поведінка |
|---|---|
| `on` | Перевіряє, що citations не порожні та точно збігаються з retrieved `chunk_id`. |
| `off` | Приймає відповідь моделі без citation validation і маркує її як `unvalidated_answer`. |

Статуси розділяють, де саме зупинився pipeline:

| Status | Значення |
|---|---|
| `grounded_answer` | Модель дала відповідь із валідними citations. |
| `unvalidated_answer` | Модель дала відповідь, а post-validator був вимкнений. |
| `retrieval_filter_fallback` | Відповідь заблокована до LLM через `empty_retrieval` або `weak_retrieval`. |
| `model_fallback` | LLM або citation validator повернули fallback після виклику моделі. |

Порожній або слабкий context може завершуватися fallback до виклику LLM. Інші причини доступні у полі `fallback_reason`: `empty_retrieval`, `weak_retrieval`, `llm_reports_insufficient_context`, `invalid_or_missing_citation`, `invalid_llm_response`.

Діагностичні логи містять кількість chunks, IDs, максимальний vector score, prompt flavor, citations і причину fallback. JSON artifact окремо містить мапу `retrieved_context_by_id`: для кожного `chunk_id` доступні повний текст, source file, RRF score і vector score, щоб retrieval можна було перевірити. API keys не логуються.

## Запуск

```bash
make setup
PINECONE_API_KEY="..." OPENAI_API_KEY="..." \
  make rag-answer QUESTION="How does Debezium achieve exactly-once delivery?" SOURCE=pages
```

Параметри: `--source pages|issues`, `--top-k`, `--model`, `--min-vector-score`, `--prompt-flavor strong|weak`, `--post-validator on|off`, `--experiment`.

Поріг доступний також як input `min_vector_score` у workflow; default залишається `0.30`. Якщо встановити `0.0`, pre-LLM retrieval filter фактично вимикається і рішення переходить до prompt + model validation. JSON має лише канонічне поле `citations` — дубльоване поле `sources` видалено.

Workflow `Run HW4 Grounded RAG Answer` має два режими:

| Mode | Що робить |
|---|---|
| `single` | Один запуск із вибраними `prompt_flavor`, `post_validator` і `min_vector_score`. |
| `experiment` | Для одного query запускає 8 варіантів: prompt `weak/strong` × retrieval filter `off/on` × post-validator `off/on`. |

Experiment mode додає в artifact поле `summary_markdown` із таблицею:

| Experiment | Prompt | Post validator | Min vector score | Best vector score | Status | Fallback reason | Citations | Conclusion |
|---|---|---|---:|---:|---|---|---|---|
| `weak_no_filter_no_validator` | `weak` | `off` | 0.00 | query-dependent | model/result | reason | IDs | Перевіряє, що слабкий prompt відповідає без guardrails. |
| `weak_no_filter_with_validator` | `weak` | `on` | 0.00 | query-dependent | model/result | reason | IDs | Показує, чи саме validator перетворює weak answer на fallback. |
| `strong_no_filter_no_validator` | `strong` | `off` | 0.00 | query-dependent | model/result | reason | IDs | Перевіряє strict prompt без post-validation. |
| `strong_no_filter_with_validator` | `strong` | `on` | 0.00 | query-dependent | model/result | reason | IDs | Перевіряє, чи strict prompt сам дає валідні citations. |
| `weak_filter_no_validator` | `weak` | `off` | 0.30 | query-dependent | model/filter | reason | IDs | Ізолює ефект retrieval filter для weak prompt. |
| `weak_filter_with_validator` | `weak` | `on` | 0.30 | query-dependent | model/filter | reason | IDs | Показує combined effect filter + validator для weak prompt. |
| `strong_filter_no_validator` | `strong` | `off` | 0.30 | query-dependent | model/filter | reason | IDs | Ізолює retrieval filter для strict prompt. |
| `strong_filter_with_validator` | `strong` | `on` | 0.30 | query-dependent | model/filter | reason | IDs | Основний production-like варіант. |

## Experiment plan and observations

Загалом проганяємо 5 test queries через однакову 8-way matrix. Набір включає:

| # | Query type | Purpose |
|---:|---|---|
| 1 | Completely unrelated question | Перевірити, що слабкий retrieval і guardrails поводяться очікувано для питання поза Debezium context. |
| 2 | Ambiguous / unclear Debezium question | Перевірити, чи no-filter режими покажуть поведінку моделі, а filter режими заблокують слабкий retrieval. |
| 3 | Ambiguous paraphrased Debezium question | Перевірити, чи hybrid retrieval зможе знайти частково релевантний issue/page. |
| 4 | Direct in-context question | Перевірити grounded answer із валідними citations. |
| 5 | Another direct in-context question | Перевірити стабільність grounded answer на іншому known-answer query. |

### Query 1: unrelated question

Run: [31600084357](https://github.com/Uhbyxer/supp-bro/actions/runs/31600084357)

Question:

```text
What is the weather today?
```

Best retrieved vector score was only `0.103`, so retrieval found unrelated Debezium chunks. The weakest configuration still produced an answer because both the retrieval filter and post-validator were disabled.

| Experiment | Prompt | Post validator | Min vector score | Best vector score | Status | Fallback reason | Citations | Comment | Expected? |
|---|---|---|---:|---:|---|---|---|---|---|
| `weak_no_filter_no_validator` | `weak` | `off` | 0.00 | 0.103 | `unvalidated_answer` | - | - | Model answered freely and said it cannot provide current weather; this is model behavior without guardrails. | Yes |
| `weak_no_filter_with_validator` | `weak` | `on` | 0.00 | 0.103 | `model_fallback` | `llm_reports_insufficient_context` | - | Weak prompt reached the model, but post-validation/model context check did not allow a grounded answer. | Yes |
| `strong_no_filter_no_validator` | `strong` | `off` | 0.00 | 0.103 | `model_fallback` | `invalid_llm_response` | - | Strong prompt refused or produced fallback-like output; without validator, empty/fallback answer is still rejected as invalid. | Yes |
| `strong_no_filter_with_validator` | `strong` | `on` | 0.00 | 0.103 | `model_fallback` | `llm_reports_insufficient_context` | - | Strong prompt correctly reported insufficient context. | Yes |
| `weak_filter_no_validator` | `weak` | `off` | 0.30 | 0.103 | `retrieval_filter_fallback` | `weak_retrieval` | - | Retrieval filter blocked before LLM because score was below threshold. | Yes |
| `weak_filter_with_validator` | `weak` | `on` | 0.30 | 0.103 | `retrieval_filter_fallback` | `weak_retrieval` | - | Same retrieval-filter block; post-validator never ran. | Yes |
| `strong_filter_no_validator` | `strong` | `off` | 0.30 | 0.103 | `retrieval_filter_fallback` | `weak_retrieval` | - | Same retrieval-filter block for strong prompt. | Yes |
| `strong_filter_with_validator` | `strong` | `on` | 0.30 | 0.103 | `retrieval_filter_fallback` | `weak_retrieval` | - | Production-like mode correctly refused unrelated question before LLM. | Yes |

Conclusion: the unrelated weather query demonstrates all guardrail layers. With both guardrails disabled, the model gives an unvalidated general answer. With post-validation enabled, it falls back after the model. With retrieval filter enabled, it falls back before the model because retrieval is weak.

## Prompt improvements

1. Відповідь обмежена retrieved context і має явний fallback.
2. Citation повертається структурованим списком та перевіряється проти дозволених IDs.
3. Слабкий retrieval відсікається до LLM, а кожен fallback має діагностичну причину.
4. Prompt flavor дозволяє порівняти строгий grounded prompt зі слабким prompt.
5. Post-validator можна вимкнути, щоб відділити поведінку моделі від citation validation.
6. Experiment mode показує різницю між model fallback, retrieval filter fallback і validator effect в одній таблиці.

## Test questions

Підготовлено 5-10 test questions у `outputs/rag_answers_examples.md`. Для кожного query можна запускати `experiment` mode і робити висновок за `summary_markdown`:

| Категорія | Очікувана поведінка |
|---|---|
| Просте питання, де відповідь точно є в context | `grounded_answer` у strong/filter режимі. |
| Переформульоване питання | `grounded_answer`, якщо hybrid retrieval знайшов правильний issue/page. |
| Недостатній context | `unvalidated_answer` у weak/no-filter/no-validator може показати відповідь моделі; `model_fallback` або `retrieval_filter_fallback` показують guardrail behavior. |
| Слабкий chunk | `retrieval_filter_fallback` у filter режимах, а no-filter режими показують різницю між model answer і validator fallback. |

## Тестування

```bash
.venv/bin/python -m unittest scripts/hw4/test_rag_answer.py
```

Тести охоплюють слабкий/порожній retrieval, валідну citation, відсутню або вигадану citation, model fallback, retrieval filter fallback, вимкнений post-validator, prompt flavors, experiment matrix і markdown-таблицю.
