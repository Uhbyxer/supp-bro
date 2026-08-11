# HW4: grounded answer generation

Pipeline:

```text
question → source filter → Pinecone + BM25 → RRF → Top-5 → structured prompt → LLM → citation validation
```

Використано найкращий pipeline HW3: hybrid retrieval із правильним `source` дав Top-1 90%, Hit@5 100%, MRR 0.95 і Precision@5 64%.

## Prompt і grounding

LLM повертає строгий JSON із `has_enough_context`, `answer` і окремим списком `citations`. Код перевіряє кожну citation проти retrieved `chunk_id`; тому форматування тексту відповіді більше не може випадково спричинити fallback.

Порожній або слабкий context завершується fallback до виклику LLM. Інші причини доступні у полі `fallback_reason`: `empty_retrieval`, `weak_retrieval`, `llm_reports_insufficient_context`, `invalid_or_missing_citation`, `invalid_llm_response`.

Діагностичні логи містять кількість chunks, IDs, максимальний vector score, citations і причину fallback. JSON artifact окремо містить мапу `retrieved_context_by_id`: для кожного `chunk_id` доступні повний текст, source file, RRF score і vector score, щоб retrieval можна було перевірити. API keys не логуються.

## Запуск

```bash
make setup
PINECONE_API_KEY="..." OPENAI_API_KEY="..." \
  make rag-answer QUESTION="How does Debezium achieve exactly-once delivery?" SOURCE=pages
```

Параметри: `--source pages|issues`, `--top-k`, `--model`, `--min-vector-score`. Поріг доступний також як input `min_vector_score` у workflow; default залишається `0.30`. JSON має лише канонічне поле `citations` — дубльоване поле `sources` видалено. Workflow `Run HW4 Grounded RAG Answer` зберігає output як artifact і показує його у job summary.

## Prompt improvements

1. Відповідь обмежена retrieved context і має явний fallback.
2. Citation повертається структурованим списком та перевіряється проти дозволених IDs.
3. Слабкий retrieval відсікається до LLM, а кожен fallback має діагностичну причину.

## Тестування

```bash
.venv/bin/python -m unittest scripts/hw4/test_rag_answer.py
```

Тести охоплюють слабкий/порожній retrieval, валідну citation, відсутню або вигадану citation, LLM fallback і реальний exactly-once `chunk_id` із проблемного запуску.
