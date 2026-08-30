# Final Project Evals

Цей шар оцінювання лежить у `scripts/final`, бо він перевіряє саме final SuppBro workflow, а не окрему домашню папку.

## Evaluation Flows

| Flow | Що перевіряє | Output |
|---|---|---|
| Retrieval eval | Чи Pinecone dense search + local BM25 + RRF знаходять правильні chunks. | `scripts/final/outputs/eval_retrieval_results.md` |
| Workflow regression eval | Чи final chatbot вибирає правильний route, викликає потрібні tools, коректно fallback-иться або питає clarification. | `scripts/final/outputs/eval_workflow_results.csv` |
| Optional RAGAS eval | Чи final answer grounded і relevant до question/evidence. | `scripts/final/outputs/eval_ragas_results.csv` |

## Manual GitHub Actions

Обидва workflow запускаються тільки вручну через `workflow_dispatch`.

### Final Retrieval Eval

```text
Actions -> Final Retrieval Eval -> Run workflow
```

Цей action reuse-ить HW3 hybrid retrieval evaluator, але пише outputs у final project folder:

```text
scripts/final/outputs/eval_retrieval_results.json
scripts/final/outputs/eval_retrieval_results.md
```

### Final Workflow Eval

```text
Actions -> Final Workflow Eval -> Run workflow
```

Цей action запускає `scripts/final/evals/run_workflow_eval.py`, який:

- читає `scripts/final/evals/eval_cases.json`;
- запускає final LangGraph workflow;
- збирає HW8-style eval table;
- рахує deterministic observability metrics;
- готує `ragas_input.json` для optional RAGAS pass.

Основні outputs:

```text
scripts/final/outputs/eval_workflow_results.csv
scripts/final/outputs/eval_summary.md
scripts/final/outputs/ragas_input.json
```

Якщо при ручному запуску `run_ragas=true`, action додатково встановлює RAGAS і запускає:

```text
scripts/final/evals/run_ragas_eval.py
```

RAGAS step потребує `OPENAI_API_KEY`. Якщо ключа немає, step записує skipped report і не ламає весь eval run.

GitHub Actions job summary навмисно містить тільки дві таблиці з конкретними метриками поточного запуску: deterministic workflow metrics і RAGAS metrics. Описові висновки та рекомендації зберігаються тут у README, а не дублюються в кожному run.

## Eval Set

`eval_cases.json` має 9 cases:

| Case | Scenario |
|---:|---|
| 1 | Documentation RAG про exactly-once delivery. |
| 2 | Local known issue context для MongoDB buffer lock. |
| 3 | Issue investigation + GitHub + Stack Overflow/community signal. |
| 4 | Stack Overflow troubleshooting query для MySQL history topic error. |
| 5 | Vague Debezium question -> clarification. |
| 6 | Out-of-domain question -> clarification/fallback. |
| 7 | No-session-memory limitation: `Does this issue have a workaround now?`. |
| 8 | Documentation RAG про schema history storage. |
| 9 | Ambiguous paraphrase that can break deterministic routing. |

## Metrics

Workflow regression eval рахує:

- `total_cases`;
- `success_rate`;
- `groundedness_good_rate`;
- `average_latency_ms`;
- `top_error_types`.

Це cheap deterministic checks. Вони не викликають LLM judge і не потребують RAGAS. Їхня задача — ловити regression у behavior:

```text
expected_route == actual_route
expected_tools are present
unexpected clarification did not happen
answer is not empty
```

RAGAS eval інший: він оцінює answer quality поверх уже зібраного evidence. Для tool-augmented cases у contexts передаються не тільки RAG chunks, а й GitHub/Stack Overflow observations, щоб judge бачив повний evidence.

## Quality Conclusions

### Where The System Works Well

- Direct documentation questions route to docs RAG.
- Concrete troubleshooting questions can combine local issue evidence with external tools.
- Vague or context-dependent questions are visible as clarification cases instead of silent hallucinations.

### 3 Main Problems

1. Deterministic routing is explainable but brittle for paraphrases without explicit Debezium/error keywords.
2. The workflow has no session memory, so follow-up questions such as `Does this issue have a workaround now?` need clarification.
3. Local BM25 is useful for the course corpus, but it is not production-ready for large document collections without a real keyword index.

### Next Steps

- Add a small LLM/router confidence layer or richer deterministic patterns for ambiguous troubleshooting queries.
- Add session memory for active issue/topic references.
- Replace local BM25 with a scalable inverted index if the corpus grows.
