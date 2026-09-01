# Final Project Evals

## Evaluation Flows

| Flow | Що перевіряє | Як запустити |
|---|---|---|
| Retrieval eval | Чи Pinecone dense search + local BM25 + RRF знаходять правильні chunks. | `make final-retrieval-eval` · [GitHub Action](https://github.com/Uhbyxer/supp-bro/actions/workflows/final-retrieval-eval.yml) |
| Deterministic eval | Чи final chatbot вибирає правильний route, викликає потрібні tools, коректно fallback-иться або питає clarification. | `make final-workflow-eval` · [GitHub Action](https://github.com/Uhbyxer/supp-bro/actions/workflows/final-workflow-eval.yml) |
| RAGAS eval | Чи grounded-answer cases мають faithful/relevant answers і релевантний evidence. | `make final-ragas-eval` · локально |

### Retrieval Eval

Retrieval eval перевіряє якість пошуку **до генерації відповіді**. Поточний pipeline бере Top-15 кандидатів із Pinecone dense search і Top-15 із BM25, об'єднує rankings через RRF (`k=60`) і залишає final Top-5.

Останній зафіксований run: [Final Retrieval Eval #1 — 33307280563](https://github.com/Uhbyxer/supp-bro/actions/runs/33307280563). Його результат також закомічений у [`scripts/final/outputs/eval_retrieval_results.md`](./outputs/eval_retrieval_results.md).

#### Retrieval metrics

Ground truth задає expected chunk IDs або patterns для кожного query. Після retrieval береться final Top-5 і рахуються:

- **Top-1** — `1`, якщо перший retrieved chunk релевантний, інакше `0`. Aggregate Top-1 — середнє по всіх queries. Це найжорсткіша перевірка: **чи найкращий результат одразу правильний**.
- **Hit@5** — `1`, якщо хоча б один релевантний chunk є серед Top-5, інакше `0`. Aggregate Hit@5 — середнє по queries. Ціль: **чи взагалі потрапив потрібний evidence у context window**.
- **RR / MRR** — для одного query `RR = 1 / rank` першого релевантного chunk. Якщо він #1 → `1.0`, #2 → `0.5`, #3 → `0.333`; якщо релевантного chunk немає → `0`. Aggregate значення є **MRR** — середній RR по queries. Ціль: **наскільки високо система ставить перший правильний результат**.
- **Precision@5** — `кількість релевантних chunks у Top-5 / 5`. Ціль: **наскільки Top-5 очищений від зайвого evidence**. Важливо: якщо ground truth містить лише один relevant chunk/pattern, максимальний Precision@5 для такого case може бути лише `1/5 = 20%`, тому цю метрику треба читати разом із кількістю expected chunks.

Aggregate для зафіксованого run:

| Metric | Result | Що означає |
|---|---:|---|
| Top-1 | **80%** | У 8 з 10 queries перший chunk збігся з ground truth. |
| Hit@5 | **100%** | У всіх 10 queries хоча б один правильний chunk був у Top-5. |
| MRR | **0.900** | Перший relevant result у середньому знаходиться дуже високо; два невдалі Top-1 cases мали relevant chunk на позиції #2. |
| Precision@5 | **62%** | У середньому 3.1 із 5 результатів відповідають ground truth; значення залежить від того, скільки relevant chunks визначено для конкретного case. |

#### Retrieval Results — Run 33307280563

| Query | Expected chunks | Retrieved chunks | Top-1 | Hit@5 | RR | Precision@5 |
|---|---|---|---:|---:|---:|---:|
| How should Debezium persist connector offsets and schema history after a restart? | `storage:overview`, `kafka`, `file`, `jdbc`, `redis` | `file`, `kafka`, `issues:dbz:1407`, `overview`, `jdbc` | 100% | 100% | 1.000 | 80% |
| Which storage options are suitable for cloud deployments of Debezium state? | `amazon_s3`, `azure_blob_storage`, `kafka` | `azure_blob_storage`, `memory`, `file`, `amazon_s3`, `overview` | 100% | 100% | 1.000 | 40% |
| What is the difference between Kafka, file, and memory offset storage in Debezium? | `kafka`, `file`, `memory` | `memory`, `overview`, `file`, `kafka`, `azure_blob_storage` | 100% | 100% | 1.000 | 60% |
| How does Debezium achieve exactly-once delivery with Kafka Connect? | `eos:overview`, `kafka_connect_exactly_once_support`, `configuration` | `connectors_supporting_eos`, `kafka_connect_exactly_once_support`, `overview`, `configuration`, `storage:overview` | 0% | 100% | 0.500 | 60% |
| What must be configured before enabling exactly-once support for source connectors? | `configuration`, `kafka_connect_exactly_once_support` | `connectors_supporting_eos`, `kafka_connect_exactly_once_support`, `overview`, `issues:dbz:73`, `issues:dbz:1407` | 0% | 100% | 0.500 | 20% |
| Postgres connector resumes from an old or invalid LSN after restart and replication slot validation looks wrong | `issues:dbz:1407:*` | 5 chunks from `issues:dbz:1407` | 100% | 100% | 1.000 | 100% |
| Debezium connector crashes when two table columns have the same name except for letter case | `issues:dbz:4:*` | `dbz:4`, `dbz:73`, `dbz:4`, `dbz:1407`, `storage:jdbc` | 100% | 100% | 1.000 | 40% |
| MongoDB connector backpressure error says unable to acquire buffer lock and queue is full | `issues:dbz:3:*` | 5 chunks from `issues:dbz:3` | 100% | 100% | 1.000 | 100% |
| JDBC sink writes records in the correct topic order but batch processing causes foreign key violations | `issues:dbz:73:*` | 5 chunks from `issues:dbz:73` | 100% | 100% | 1.000 | 100% |
| Which issue is only about migrating tests from JUnit4 to a newer JUnit version? | `issues:dbz:11:chunk_001` | `dbz:11`, `dbz:73`, `dbz:73`, `dbz:73`, `dbz:1407` | 100% | 100% | 1.000 | 20% |

Загальний retrieval результат добрий: **Hit@5 = 100%**, тобто потрібний evidence не губиться. Основний простір для покращення — ranking/precision для documentation queries про exactly-once та cloud storage, де тематично близькі chunks іноді випереджають exact ground-truth chunk або додають шум у Top-5.

### Deterministic Eval

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

## RAGAS Eval

RAGAS є окремим локальним flow.

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
