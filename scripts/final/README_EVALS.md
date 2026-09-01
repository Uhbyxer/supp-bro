# Final Project Evals

Цей шар оцінювання лежить у `scripts/final`, бо він перевіряє саме final SuppBro workflow, а не окрему домашню папку.

## Evaluation Flows

| Flow | Що перевіряє | Output |
|---|---|---|
| Retrieval eval | Чи Pinecone dense search + local BM25 + RRF знаходять правильні chunks. | `scripts/final/outputs/eval_retrieval_results.md` |
| Workflow regression eval | Чи final chatbot вибирає правильний route, викликає потрібні tools, коректно fallback-иться або питає clarification. | `scripts/final/outputs/eval_workflow_results.csv` |
| RAGAS eval | Чи grounded-answer cases мають faithful/relevant answers і релевантний evidence. | `scripts/final/outputs/eval_ragas_results.csv` |

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
- не запускає RAGAS.

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

`Success` є результатом hardcoded regression rules, а не LLM-as-judge оцінкою.

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
- записує результат у `scripts/final/outputs/eval_ragas_results.csv`.

Deterministic і RAGAS eval-и незалежні та кожен сам запускає workflow для своїх cases. Окремий проміжний input-файл для RAGAS не потрібен.

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

### Deterministic checks

Workflow regression eval використовує deterministic checks поверх реального end-to-end execution:

```text
expected_route == actual_route
expected_tools are present
unexpected clarification did not happen
answer is not empty
```

Вони відповідають на питання: **чи система виконала правильний workflow?**

### RAGAS metrics

RAGAS відповідає на інше питання: **наскільки якісна фактична відповідь, якщо дивитися на question, retrieved/tool evidence і reference?**

У final eval використовуються три метрики, кожна в діапазоні приблизно `0..1`, де більше — краще:

- **Faithfulness** — перевіряє, наскільки твердження у відповіді реально підтримуються переданим evidence/context. Високий score означає, що бот не додає непідтверджених фактів, рекомендацій або висновків. Це головна метрика для hallucination/over-interpretation проблем.
- **Answer relevancy** — перевіряє, наскільки відповідь по суті відповідає на поставлене question. Високий score означає, що відповідь сфокусована на запиті, а не просто містить тематично близький текст.
- **Context precision** — перевіряє, наскільки retrieved contexts, які були передані моделі, релевантні до question/reference. Високий score означає, що retrieval/tool layer приніс переважно корисний evidence; низький score часто вказує на retrieval/query/filtering problem ще до generation.

Ціль цих трьох метрик — розділити різні типи проблем. Наприклад, `context_precision≈1.0` разом із низьким `faithfulness` означає: **evidence хороший, але бот погано ним скористався**. Низькі `answer_relevancy` і `context_precision` одночасно частіше означають, що проблема почалася ще на retrieval/community-search етапі.

Для tool-augmented cases у contexts передаються не тільки RAG chunks, а й GitHub/Stack Overflow observations, щоб judge бачив повний evidence.

Deterministic evaluation і RAGAS доповнюють один одного: перший ловить orchestration/routing regressions, другий — semantic answer-quality проблеми.

## Evaluation Snapshot Used For Conclusions

Висновки нижче зроблені вручну на основі двох конкретних результатів:

- **Deterministic GitHub Actions run:** https://github.com/Uhbyxer/supp-bro/actions/runs/33314524802
- **Committed local RAGAS results:** https://github.com/Uhbyxer/supp-bro/blob/main/scripts/final/outputs/eval_ragas_results.csv

Щоб аналіз було зручно читати без переходів між GitHub Action і CSV, ключові результати скопійовані нижче.

### Deterministic Results — Run 33314524802

| # | Question | Expected | Actual | Success | Latency | Errors |
|---:|---|---|---|---|---:|---|
| 1 | Can I get exactly once delivery with Debezium? | `docs_answer`, no tools | `docs_answer/rag`, no tools | `yes` | 13610 ms | `none` |
| 2 | Explain the known Debezium MongoDB buffer lock problem from the local context. | `issue_investigation`, `get_github_issue_context` | `issue_investigation/rag+tool`, GitHub issue tool | `yes` | 17685 ms | `none` |
| 3 | What should I do if Debezium MongoDB says unable to acquire buffer lock? | `issue_investigation`, GitHub + Stack Overflow | `issue_investigation/rag+tool`, GitHub + Stack Overflow | `yes` | 15297 ms | `none` |
| 4 | Debezium Mysql Connector Failed with IllegalStateException for history topic | `issue_investigation`, Stack Overflow | `issue_investigation/rag+tool`, Stack Overflow | `partial` | 13861 ms | `llm_reports_insufficient_context` |
| 5 | Help with Debezium | `clarification`, `ask_clarifying_question` | `clarification`, clarification tool | `yes` | 8 ms | `none` |
| 6 | How do I reset my iPhone password? | `clarification`, `ask_clarifying_question` | `docs_answer/fallback`, no tools | `no` | 8083 ms | `wrong_route; missing_tool` |
| 7 | Does this issue have a workaround now? | `clarification`, `ask_clarifying_question` | `community_lookup/rag+tool`, Stack Overflow | `no` | 11509 ms | `wrong_route; missing_tool` |
| 8 | What is the recommended storage for Debezium schema history? | `docs_answer`, no tools | `docs_answer/rag`, no tools | `yes` | 10455 ms | `none` |
| 9 | It worked yesterday, but after restart it cannot recover its internal state | `clarification`, `ask_clarifying_question` | `docs_answer/fallback`, no tools | `no` | 8066 ms | `wrong_route; missing_tool` |

### RAGAS Results — Committed Local Run

RAGAS запускається тільки для grounded-answer cases, тому clarification cases 5, 6, 7 і 9 тут відсутні. `Actual answer` — фактичний response бота з локального RAGAS run. `Expected answer` — reference/ground-truth expectation, з яким запускався evaluator.

| # | Question | Actual answer | Expected answer | Faithfulness | Answer relevancy | Context precision |
|---:|---|---|---|---:|---:|---:|
| 1 | Can I get exactly once delivery with Debezium? | Yes, exactly-once delivery can be achieved when Debezium runs as a supported Kafka Connect source connector with Kafka Connect exactly-once support. | Debezium documentation should be used to answer whether exactly-once delivery is supported. | 0.750 | 0.795 | 0.917 |
| 2 | Explain the known Debezium MongoDB buffer lock problem from the local context. | The warning `Unable to acquire buffer lock, buffer queue is likely full` was observed with Debezium MongoDB 3.2.5; the answer also suggests checking buffer settings/workload and points to the GitHub issue. | The answer should explain the MongoDB buffer lock issue using local issue context and GitHub issue evidence. | 0.571 | 0.882 | 1.000 |
| 3 | What should I do if Debezium MongoDB says unable to acquire buffer lock? | The answer suggests checking/increasing buffer capacity, monitoring connector load and following the GitHub issue, while noting that no relevant community workaround was found. | The answer should mention the known MongoDB buffer lock symptom and include any available project/community evidence. | 0.182 | 0.792 | 1.000 |
| 4 | Debezium Mysql Connector Failed with IllegalStateException for history topic | The answer reports insufficient local/project evidence and asks for connector logs, configuration and the exact `IllegalStateException` message instead of giving a confident fix. | The answer should use the community result for the MySQL history topic IllegalStateException without forcing a GitHub issue lookup. | 0.300 | 0.000 | 0.000 |
| 8 | What is the recommended storage for Debezium schema history? | The answer says Debezium recommends `RocketMqSchemaHistory`, `MemorySchemaHistory`, `FileSchemaHistory` and `RedisSchemaHistory` depending on the use case. | The answer should use Debezium documentation about schema history storage. | 0.000 | 0.901 | 0.917 |

> The table intentionally keeps the answers readable rather than duplicating the full raw retrieved-context payload. The complete response/context/reference fields remain available in `scripts/final/outputs/eval_ragas_results.csv`.

## Per-case Conclusions

Позначення в колонці `Verdict`:

- **OK** — поведінка бота і сам test case виглядають коректно;
- **Improve bot** — test case корисний і виявив реальну проблему workflow/answer;
- **Improve test** — поведінка системи допустима, але expectation або формулювання test case занадто жорстке/неоднозначне;
- **Improve both** — є окрема проблема в боті та окрема проблема в дизайні test case.

| # | Deterministic result | RAGAS (faith / relevancy / context precision) | Verdict | Conclusion |
|---:|---|---|---|---|
| 1 | `yes`: `docs_answer`, RAG, no tools | `0.75 / 0.80 / 0.92` | **OK** | Route і retrieval правильні, відповідь релевантна і переважно faithful. Невеликий запас для покращення: чіткіше сказати, що Debezium за замовчуванням дає at-least-once, а exactly-once залежить від Kafka Connect support/configuration і підтримуваного source connector. Сам test case коректний. |
| 2 | `yes`: `issue_investigation`, RAG + GitHub issue tool | `0.57 / 0.88 / 1.00` | **Improve bot** | Evidence підібраний дуже добре, route/tool правильні. Нижча faithfulness показує, що answer переходить від факту `buffer queue is likely full` до сильніших інтерпретацій і generic advice про buffer settings/workload, які evidence прямо не підтверджує. Треба чітко відділяти observed facts від припущень і не давати remediation без source support. Test case достатньо добрий. |
| 3 | `yes`: `issue_investigation`, GitHub + Stack Overflow tools | `0.18 / 0.79 / 1.00` | **Improve both** | Orchestration і context selection пройшли, але дуже низька faithfulness показує generation problem: бот радить `increase buffer size`, monitor workload тощо без підтвердженого workaround в evidence. Одночасно test question питає `What should I do`, а reference описує лише symptom/evidence і не визначає, яка remediation вважається правильною. Бот має відповідати evidence-backed кроками або прямо казати, що підтвердженого workaround немає; test case треба доповнити explicit expected remediation behavior. |
| 4 | `partial`: route/tool правильні, але `llm_reports_insufficient_context` | `0.30 / 0.00 / 0.00` | **Improve both** | Бот правильно не вигадує впевнену відповідь при недостатньому evidence, але community retrieval повернув нерелевантний матеріал, тому це реальна retrieval/query-quality проблема. Водночас test case занадто залежить від live Stack Overflow і очікує конкретно корисний community result, який може змінюватись або не існувати. Для стабільного regression test краще pin-нути відомий result/fixture або вважати валідним outcome `searched community + rejected irrelevant evidence`. |
| 5 | `yes`: clarification + `ask_clarifying_question` | N/A | **OK** | Правильна conversational-control поведінка: бот не вгадує connector/error і просить конкретизацію. Це хороший deterministic case; RAGAS тут свідомо не застосовується. |
| 6 | `no`: пішов у `docs_answer/fallback` замість clarification | N/A | **Improve both** | Реальна проблема router-а: out-of-domain iPhone question не повинно запускати Debezium docs RAG. Потрібен explicit out-of-domain/confidence guard. Але expectation тесту теж можна зробити точнішим: для явно чужого домену не обов'язково саме `ask_clarifying_question`; коректним може бути explicit out-of-domain fallback/refusal to route. Тест має перевіряти `do not use Debezium retrieval`, а не жорстко один implementation route. |
| 7 | `no`: `community_lookup` + Stack Overflow замість clarification | N/A | **Improve bot** | Сильний regression case. Без session memory фраза `this issue` не має достатнього referent, але бот сам вибрав конкретну JDBC Sink проблему і фактично hallucinated conversation context. Треба require explicit issue/topic або memory reference перед community lookup. Сам test case добре ловить небезпечну поведінку. |
| 8 | `yes`: `docs_answer`, RAG, no tools | `0.00 / 0.90 / 0.92` | **Improve both** | Retrieval релевантний, але answer перетворює перелік storage implementations на твердження, що Debezium їх `recommends`; це не підтримується retrieved docs, тому faithfulness провалена. Додатково `MemorySchemaHistory` не є persistent storage, що робить blanket recommendation ще слабшою. Сам question `What is the recommended storage` теж неоднозначний, бо docs радше описують варіанти. Краще питати `What schema history storage options are supported and which are persistent?` або додати точний expected recommendation у reference. |
| 9 | `no`: `docs_answer/fallback` замість clarification | N/A | **Improve bot** | Корисний ambiguity/paraphrase case. Запит не містить достатньо явних Debezium/schema-history ознак, тому safe behavior — уточнення, а не тихий docs retrieval з generic fallback. Потрібен confidence/ambiguity layer перед routing. Test case добре демонструє brittleness deterministic router-а. |

## Overall Findings

### What Works

- Direct documentation question #1 стабільно йде у docs RAG і має добрі semantic metrics.
- Concrete issue questions #2 і #3 правильно активують local issue retrieval та зовнішні tools.
- Явно vague Debezium query #5 коректно переходить у clarification.
- Deterministic + RAGAS разом дають корисніший сигнал, ніж будь-який один evaluator: #3 і #8 проходять orchestration checks, але RAGAS виявляє semantic answer problems.

### Main Bot Problems

1. **Unsupported remediation / over-interpretation.** У #2 і особливо #3 бот додає troubleshooting advice, якого немає в evidence.
2. **Weak ambiguity and out-of-domain routing.** #6 і #9 йдуть у docs retrieval замість safe clarification/out-of-domain behavior.
3. **Invented conversational context.** У #7 бот трактує `this issue` як конкретну проблему без session memory.
4. **Overstating source claims.** У #8 перелік підтримуваних storage implementations перетворюється на recommendation.
5. **Community retrieval quality.** У #4 external search повертає нерелевантний evidence і не дозволяє побудувати корисну troubleshooting answer.

### Test-set Improvements

1. **Case #3:** reference має чітко визначати, які remediation steps підтримуються evidence і чи правильним є висновок `no confirmed workaround`.
2. **Case #4:** live Stack Overflow search робить regression нестабільним. Або pin/fixture known community result, або перевіряти здатність відкинути нерелевантний result.
3. **Case #6:** expectation краще формулювати як `do not route into Debezium retrieval/tools`; конкретний out-of-domain route може бути implementation detail.
4. **Case #8:** замінити неоднозначне `recommended storage` на питання про supported/persistent schema-history options або додати точний source-backed recommendation.

### Next Steps

- Додати router confidence/out-of-domain guard перед docs/community routes.
- Для unresolved references типу `this issue` вимагати session context або clarification.
- Зробити answer generation більш evidence-constrained: remediation і recommendation повинні бути явно підтримані retrieved/tool evidence.
- Покращити filtering/relevance validation для community search result перед передачею його в generation.
- Підчистити cases #3, #4, #6 і #8, щоб regression expectations перевіряли бажану поведінку, а не випадкові implementation details або нестабільні зовнішні результати.
