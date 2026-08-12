# HW4: grounded answer generation

This task evaluates a grounded RAG answer-generation pipeline for Debezium support questions. The goal is not only to produce an answer, but to show when the system should refuse to answer because retrieval is weak or the model cannot ground its response in the returned chunks.

Pipeline:

```text
question → source filter → Pinecone + BM25 → RRF → Top-5 → prompt flavor → LLM → citation validation
```

Використано найкращий pipeline HW3: hybrid retrieval із правильним `source` дав Top-1 90%, Hit@5 100%, MRR 0.95 і Precision@5 64%.

## Prompt і grounding

LLM повертає строгий JSON із `has_enough_context`, `answer` і окремим списком `citations`. Код перевіряє кожну citation проти retrieved `chunk_id`; тому форматування тексту відповіді більше не може випадково спричинити fallback.

Є два prompt flavors:

| Flavor | Поведінка |
|---|---|
| `strong` | Строгий grounded prompt. Відповідає лише коли context прямо підтримує відповідь. |
| `weak` | М'якший prompt. Дозволяє відповідати, коли context частково релевантний, але citations усе одно мають бути валідні. |

Статуси розділяють, де саме зупинився pipeline:

| Status | Значення |
|---|---|
| `grounded_answer` | Модель дала відповідь із валідними citations. |
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

Параметри: `--source pages|issues`, `--top-k`, `--model`, `--min-vector-score`, `--prompt-flavor strong|weak`, `--experiment`.

Поріг доступний також як input `min_vector_score` у workflow; default залишається `0.30`. Якщо встановити `0.0`, pre-LLM retrieval filter фактично вимикається і рішення переходить до prompt + model validation. JSON має лише канонічне поле `citations` — дубльоване поле `sources` видалено.

Workflow `Run HW4 Grounded RAG Answer` має два режими:

| Mode | Що робить |
|---|---|
| `single` | Один запуск із вибраним `prompt_flavor` і `min_vector_score`. |
| `experiment` | Для одного query запускає 4 варіанти: weak/no filter, strong/no filter, weak/filter, strong/filter. |

Experiment mode додає в artifact поле `summary_markdown` із таблицею:

| Experiment | Prompt | Min vector score | Best vector score | Status | Fallback reason | Citations | Conclusion |
|---|---|---:|---:|---|---|---|---|
| `weak_prompt_no_filter` | `weak` | 0.00 | query-dependent | model/result | reason | IDs | Перевіряє, чи м'який prompt відповідає без retrieval filter. |
| `strong_prompt_no_filter` | `strong` | 0.00 | query-dependent | model/result | reason | IDs | Перевіряє, чи строгий prompt сам відмовиться без retrieval filter. |
| `weak_prompt_with_filter` | `weak` | 0.30 | query-dependent | model/filter | reason | IDs | Перевіряє ефект retrieval filter із м'яким prompt. |
| `strong_prompt_with_filter` | `strong` | 0.30 | query-dependent | model/filter | reason | IDs | Основний production-like варіант. |

## Prompt improvements

1. Відповідь обмежена retrieved context і має явний fallback.
2. Citation повертається структурованим списком та перевіряється проти дозволених IDs.
3. Слабкий retrieval відсікається до LLM, а кожен fallback має діагностичну причину.
4. Prompt flavor дозволяє порівняти строгий grounded prompt із м'якшим prompt.
5. Experiment mode показує різницю між model fallback і retrieval filter fallback в одній таблиці.

## Test questions

Підготовлено 5-10 test questions у `outputs/rag_answers_examples.md`. Для кожного query можна запускати `experiment` mode і робити висновок за `summary_markdown`:

| Категорія | Очікувана поведінка |
|---|---|
| Просте питання, де відповідь точно є в context | `grounded_answer` у strong/filter режимі. |
| Переформульоване питання | `grounded_answer`, якщо hybrid retrieval знайшов правильний issue/page. |
| Недостатній context | `model_fallback` без filter або `retrieval_filter_fallback`, якщо score слабкий. |
| Слабкий chunk | `retrieval_filter_fallback` у filter режимах, але no-filter режими показують, що зробила б модель. |

## Тестування

```bash
.venv/bin/python -m unittest scripts/hw4/test_rag_answer.py
```

Тести охоплюють слабкий/порожній retrieval, валідну citation, відсутню або вигадану citation, model fallback, retrieval filter fallback, prompt flavors, experiment matrix і markdown-таблицю.
