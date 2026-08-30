# Final Project Evals

Цей шар оцінювання лежить у `scripts/final`, бо він перевіряє саме final SuppBro workflow, а не окрему домашню папку.

## Evaluation Flows

| Flow | Що перевіряє | Output |
|---|---|---|
| Retrieval eval | Чи Pinecone dense search + local BM25 + RRF знаходять правильні chunks. | `scripts/final/outputs/eval_retrieval_results.md` |
| Workflow regression eval | Чи final chatbot вибирає правильний route, викликає потрібні tools, коректно fallback-иться або питає clarification. | `scripts/final/outputs/eval_workflow_results.csv` |
| RAGAS eval | Чи grounded-answer cases мають faithful/relevant answers і якісний evidence. | `scripts/final/outputs/eval_ragas_results.csv` |

## Manual GitHub Actions

Обидва GitHub workflow запускаються тільки вручну через `workflow_dispatch`.

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

Це full end-to-end integration eval, а не unit/smoke test. GitHub Action запускає тільки deterministic workflow regression eval з увімкненим RAG і реальними tools для всіх test cases.

RAG не можна вимкнути через workflow input або CLI flag. Єдиний runtime input — `min_vector_score`.

Deterministic evaluator `scripts/final/evals/run_workflow_eval.py`:

- читає `scripts/final/evals/eval_cases.json`;
- запускає final LangGraph workflow з `enable_rag=True`;
- збирає таблицю по всіх test cases;
- перевіряє тільки те, що можна перевірити детерміновано: route, expected tools, clarification/fallback behavior, наявність answer;
- не оцінює semantic quality, faithfulness або groundedness відповіді;
- не готує input і не запускає RAGAS.

GitHub Actions job summary містить тільки deterministic test-case table. Action не запускає RAGAS і не публікує `eval_ragas_results.csv` як artifact.

Основні outputs GitHub Action:

```text
scripts/final/outputs/eval_workflow_results.csv
scripts/final/outputs/eval_summary.md
```

Deterministic summary показує тільки фактичні orchestration checks:

```text
Question
Expected route/tools
Actual route/mode/tools/answer preview
Success
Latency
Errors
```

`Success` є результатом hardcoded regression rules, а не LLM-as-judge оцінкою. Semantic висновки не виводяться як synthetic `good/partial/bad` поля.

## Local RAGAS Eval

RAGAS є окремим локальним flow:

```text
make final-ragas-eval
```

`run_ragas_eval.py` сам:

- читає `scripts/final/evals/eval_cases.json`;
- вибирає grounded-answer cases (`expected_route != clarification`);
- запускає final LangGraph workflow для цих cases з `enable_rag=True`;
- збирає фактичні answers, RAG contexts і external-tool evidence;
- запускає RAGAS поверх цих даних;
- записує результат у:

```text
scripts/final/outputs/eval_ragas_results.csv
```

Проміжний `ragas_input.json` більше не потрібен. Deterministic і RAGAS eval-и незалежні та кожен сам запускає workflow для своїх cases.

Результат локального RAGAS run можна закомітити в репозиторій як зафіксований evaluation result. RAGAS не запускається у GitHub Actions через нестабільну/повільну поведінку LLM-as-judge calls у hosted runner.

RAGAS потребує `OPENAI_API_KEY`.

## Local Commands

Після `make setup`:

```text
make final-workflow-eval
make final-ragas-eval
```

Це дві незалежні команди. За потреби обидві приймають однаковий retrieval threshold:

```text
make final-workflow-eval MIN_VECTOR_SCORE=0.30
make final-ragas-eval MIN_VECTOR_SCORE=0.30
```

## Eval Set

`eval_cases.json` має 9 cases:

| Case | Scenario | Evaluation |
|---:|---|---|
| 1 | Documentation RAG про exactly-once delivery. | Deterministic + RAGAS |
| 2 | Local known issue context для MongoDB buffer lock. | Deterministic + RAGAS |
| 3 | Issue investigation + GitHub + Stack Overflow/community signal. | Deterministic + RAGAS |
| 4 | Stack Overflow troubleshooting query для MySQL history topic error. | Deterministic + RAGAS |
| 5 | Vague Debezium question -> clarification. | Deterministic only |
| 6 | Out-of-domain question -> clarification/fallback. | Deterministic only |
| 7 | No-session-memory limitation: `Does this issue have a workaround now?`. | Deterministic only |
| 8 | Documentation RAG про schema history storage. | Deterministic + RAGAS |
| 9 | Ambiguous paraphrase that can break deterministic routing. | Deterministic only |

RAGAS selection is semantic rather than hardcoded by case ID: cases with `expected_route == clarification` are excluded. Це дозволяє deterministic eval перевіряти conversational control behavior, не штрафуючи правильні clarification/fallback responses метриками, розрахованими на substantive grounded answers.

## Metrics

Workflow regression eval використовує deterministic checks поверх реального end-to-end execution. Вони не замінюють сам flow і не мокають RAG/tools:

```text
expected_route == actual_route
expected_tools are present
unexpected clarification did not happen
answer is not empty
```

RAGAS eval оцінює answer quality поверх evidence, який він сам збирає у власному локальному workflow run. Для tool-augmented cases у contexts передаються не тільки RAG chunks, а й GitHub/Stack Overflow observations, щоб judge бачив повний evidence.

Ці два eval-и доповнюють один одного: deterministic evaluation ловить orchestration/routing regressions, а RAGAS — answer-quality проблеми, які можуть залишатися невидимими навіть коли route і tools вибрані правильно.

Описові висновки про те, що працює добре, які є обмеження і що покращувати, зберігаються нижче в README. Вони не генеруються deterministic evaluator-ом.

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
