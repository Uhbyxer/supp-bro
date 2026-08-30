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

Описові висновки нижче зроблені вручну на основі deterministic GitHub Actions run `33314524802` та закоміченого локального `scripts/final/outputs/eval_ragas_results.csv`. Вони не генеруються evaluator-ом автоматично.

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
| 3 | `yes`: `issue_investigation`, GitHub + Stack Overflow tools | `0.18 / 0.79 / 1.00` | **Improve both** | Orchestration і context selection пройшли, але дуже низька faithfulness показує реальну generation problem: бот радить `increase buffer size`, monitor workload тощо без підтвердженого workaround в evidence. Одночасно test question питає `What should I do`, а reference описує лише symptom/evidence і не визначає, яка remediation вважається правильною. Бот має відповідати evidence-backed кроками або прямо казати, що підтвердженого workaround немає; test case треба доповнити explicit expected remediation behavior. |
| 4 | `partial`: route/tool правильні, але `llm_reports_insufficient_context` | `0.30 / 0.00 / 0.00` | **Improve both** | Бот правильно не вигадує впевнену відповідь при недостатньому evidence, але community retrieval повернув нерелевантний матеріал, тому це реальна retrieval/query-quality проблема. Водночас test case занадто залежить від live Stack Overflow і очікує конкретно корисний community result, який може змінюватись або не існувати. Для стабільного regression test краще pin-нути відомий result/fixture або вважати валідним outcome `searched community + rejected irrelevant evidence`. |
| 5 | `yes`: clarification + `ask_clarifying_question` | N/A | **OK** | Правильна conversational-control поведінка: бот не вгадує connector/error і просить конкретизацію. Це хороший deterministic case; RAGAS тут свідомо не застосовується. |
| 6 | `no`: пішов у `docs_answer/fallback` замість clarification | N/A | **Improve both** | Реальна проблема router-а: out-of-domain iPhone question не повинно запускати Debezium docs RAG. Потрібен explicit out-of-domain/confidence guard. Але expectation тесту теж можна зробити точнішим: для явно чужого домену не обов'язково саме `ask_clarifying_question`; коректним може бути explicit out-of-domain fallback/refusal to route. Тест має перевіряти `do not use Debezium retrieval`, а не жорстко один implementation route. |
| 7 | `no`: `community_lookup` + Stack Overflow замість clarification | N/A | **Improve bot** | Сильний regression case. Без session memory фраза `this issue` не має достатнього referent, але бот сам вибрав конкретну JDBC Sink проблему і фактично hallucinated conversation context. Треба require explicit issue/topic або memory reference перед community lookup. Сам test case добре ловить небезпечну поведінку. |
| 8 | `yes`: `docs_answer`, RAG, no tools | `0.00 / 0.90 / 0.92` | **Improve both** | Retrieval релевантний, але answer перетворює перелік storage implementations на твердження, що Debezium їх `recommends`; це не підтримується retrieved docs, тому faithfulness провалена. Додатково `MemorySchemaHistory` не є persistent storage, що робить blanket recommendation ще слабшою. Сам question `What is the recommended storage` теж неоднозначний, бо docs радше описують варіанти. Краще питати `What schema history storage options are supported and which are persistent?` або додати точний expected recommendation у reference. |
| 9 | `no`: `docs_answer/fallback` замість clarification | N/A | **Improve bot** | Корисний ambiguity/paraphrase case. Запит не містить достатньо явних Debezium/schema-history ознак, тому safe behavior — уточнення, а не тихий docs retrieval з generic fallback. Потрібен confidence/ambiguity layer перед routing. Test case добре демонструє brittleness deterministic router-а. |

## Overall Findings

### What Works

- Direct documentation questions (#1) стабільно йдуть у docs RAG і дають релевантну grounded відповідь.
- Concrete issue questions (#2, #3) правильно активують local issue retrieval та зовнішні tools.
- Явно vague Debezium query (#5) коректно переходить у clarification.
- Deterministic + RAGAS разом дають корисніший сигнал, ніж будь-який один evaluator: #3 і #8 проходять orchestration checks, але RAGAS виявляє semantic answer problems.

### Main Bot Problems

1. **Unsupported remediation / over-interpretation.** У #2 і особливо #3 бот додає troubleshooting advice, якого немає в evidence; у #8 перетворює список supported implementations на recommendation.
2. **Weak ambiguity and domain routing.** #6, #7 і #9 показують, що router занадто охоче вибирає retrieval/tool route замість clarification/out-of-domain handling.
3. **Community retrieval quality.** #4 показує, що сам факт виклику Stack Overflow tool ще не означає, що знайдений result релевантний; потрібен relevance gate перед використанням external evidence.
4. **No session memory/reference validation.** #7 демонструє, що unresolved pronouns (`this issue`) треба блокувати до отримання конкретного referent.

### Test-set Improvements

1. **Case #3:** reference має явно визначати допустимі troubleshooting steps і вимагати не вигадувати workaround, якщо evidence його не містить.
2. **Case #4:** live community search робить expectation нестабільним. Або pin/fixture конкретний result, або тестувати behavior `search + relevance check + safe fallback` замість гарантованої відповіді з Stack Overflow.
3. **Case #6:** expectation краще формулювати як `do not route into Debezium RAG/tools`; clarification і explicit out-of-domain fallback можуть бути обидва валідні outcomes.
4. **Case #8:** замінити неоднозначне `recommended storage` на питання про supported storage options/persistence або дати reference з конкретною рекомендацією.

### Next Steps

- Додати evidence-aware generation instruction: не перетворювати observations на remediation/recommendation без прямої підтримки source context.
- Додати router confidence/domain guard для out-of-domain та ambiguous queries.
- Додати unresolved-reference check для follow-up phrases без session context.
- Додати relevance validation для Stack Overflow/community results перед включенням у final answer.
- Уточнити test cases #3, #4, #6 і #8 згідно з висновками вище.
- Якщо corpus виросте, замінити local BM25 на scalable inverted index.
