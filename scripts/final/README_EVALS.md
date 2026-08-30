# Final Project Evals

Цей шар оцінювання лежить у `scripts/final`, бо він перевіряє саме final SuppBro workflow, а не окрему домашню папку.

## Evaluation Flows

| Flow | Що перевіряє | Output |
|---|---|---|
| Retrieval eval | Чи Pinecone dense search + local BM25 + RRF знаходять правильні chunks. | `scripts/final/outputs/eval_retrieval_results.md` |
| Workflow regression eval | Чи final chatbot у повному end-to-end flow вибирає правильний route, запускає RAG, викликає потрібні tools, коректно fallback-иться або питає clarification. | `scripts/final/outputs/eval_workflow_results.csv` |
| RAGAS eval | Чи final answer grounded і relevant до question/evidence, зібраного тим самим full-flow запуском. | `scripts/final/outputs/eval_ragas_results.csv` |

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

Один запуск завжди виконує два етапи послідовно:

1. full end-to-end workflow regression eval з увімкненим RAG;
2. RAGAS LLM-as-judge eval поверх результатів цього ж запуску.

Немає `run_ragas` або `disable_rag` inputs: RAG і RAGAS завжди увімкнені. Це integration/e2e eval реального final flow, а не unit/smoke test.

Workflow використовує один `pip install -r requirements.txt`; RAGAS dependencies є частиною project requirements.

Evaluator `scripts/final/evals/run_workflow_eval.py`:

- читає `scripts/final/evals/eval_cases.json`;
- запускає final LangGraph workflow з `enable_rag=True`;
- виконує реальний retrieval і доступні external tools;
- збирає детальну таблицю по test cases;
- рахує deterministic behavior metrics;
- готує `ragas_input.json` із реально отриманими answers/evidence.

Після нього `scripts/final/evals/run_ragas_eval.py` завжди запускає RAGAS і записує per-case metrics.

Основні outputs:

```text
scripts/final/outputs/eval_workflow_results.csv
scripts/final/outputs/eval_summary.md
scripts/final/outputs/ragas_input.json
scripts/final/outputs/eval_ragas_results.csv
```

RAGAS потребує `OPENAI_API_KEY`. Якщо ключа або dependency немає, eval завершується помилкою замість тихого `skipped`, щоб GitHub Action не виглядав успішним без реального RAGAS evaluation.

GitHub Actions job summary містить дві детальні таблиці поточного запуску: deterministic test cases і RAGAS metrics по кожному test case. Описові висновки та рекомендації зберігаються тут у README, а не дублюються в кожному run.

## Local Commands

Після `make setup`:

```text
make final-workflow-eval
make final-ragas-eval
make final-evals
```

`make final-evals` послідовно запускає повний workflow evaluator, а потім RAGAS. Опціонально можна змінити тільки retrieval threshold:

```text
make final-workflow-eval MIN_VECTOR_SCORE=0.30
```

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

Workflow regression eval використовує deterministic checks поверх повного реального flow. Вони не підміняють workflow mocks/unit tests; вони перевіряють фактичний результат end-to-end запуску:

```text
expected_route == actual_route
expected_tools are present
unexpected clarification did not happen
answer is not empty
```

RAGAS eval оцінює answer quality поверх уже зібраного evidence. Для tool-augmented cases у contexts передаються не тільки RAG chunks, а й GitHub/Stack Overflow observations, щоб judge бачив повний evidence.

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
