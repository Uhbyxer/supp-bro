# HW4: grounded answer generation

Pipeline:

```text
question → source filter → Pinecone + BM25 → RRF → Top-5 → prompt → LLM → validated answer
```

Використано найкращий pipeline HW3: hybrid retrieval із правильним `source` дав Top-1 90%, Hit@5 100%, MRR 0.95 і Precision@5 64%.

## Prompt і grounding

Шаблон у `prompt_template.txt` наказує відповідати тільки з context, повертати точний fallback при нестачі даних і цитувати `chunk_id` після кожного факту. Код має два додаткові guardrails:

- порожній context або максимальний vector score нижче `0.30` завершується fallback без виклику LLM;
- відповідь без citation або з ID, якого немає в retrieved context, замінюється fallback.

## Запуск

Потрібні `PINECONE_API_KEY`, `OPENAI_API_KEY` та вже побудований HW3 namespace.

```bash
make setup
PINECONE_API_KEY="..." OPENAI_API_KEY="..." \
  make rag-answer QUESTION="How does Debezium achieve exactly-once delivery?" SOURCE=pages
```

Напряму:

```bash
.venv/bin/python scripts/hw4/rag_answer.py --source pages \
  "What must be configured before enabling exactly-once support?"
```

Параметри: `--source pages|issues`, `--top-k`, `--model`, `--min-vector-score`. Результат — JSON із question, retrieved chunks/scores, answer і перевіреними sources.

## Prompt improvements

1. **Загальна відповідь.** Початкове `Answer using the context` дозволяло додавати prior knowledge. Тепер явно дозволені тільки факти з context і потрібна citation для кожного твердження.
2. **Вигадана citation.** Загальна вимога `mention the source` не фіксувала формат. Тепер context має `CHUNK_ID`/`SOURCE_FILE`, потрібні квадратні дужки, а код перевіряє ID проти retrieved set.
3. **Відповідь зі слабкого context.** Prompt сам по собі іноді провокував helpful guess. Тепер deterministic score check повертає fallback ще до LLM.

## Тестування

`outputs/rag_answers_examples.md` містить 8 сценаріїв: прості, переформульовані, issues, слабкий retrieval і питання поза корпусом. Guardrail tests не потребують API:

```bash
.venv/bin/python -m unittest scripts/hw4/test_rag_answer.py
```

Workflow `Run HW4 Grounded RAG Answer` запускає тести й одне довільне питання. Threshold `0.30` — початкова евристика, яку варто калібрувати на фактичних запусках. Citation validation перевіряє ID, але semantic faithfulness кожного речення потребуватиме окремого evaluator.
