# HW4: grounded answer generation

У попередньому завданні найкращим вийшов hybrid retrieval pipeline. У цьому завданні я вирішив покращити його трьома способами: через prompt, retrieval filter і post-validator.

Щоб це перевірити, я підготував різні queries: від повністю нерелевантних і нечітких до питань, де відповідь точно є в context. Кожен query проганяється через різні режими, щоб окремо побачити вплив prompt, filter і post-validator.

Prompt тестується у двох варіантах. Слабкий prompt просто просить модель відповісти на питання і додати citations, якщо це можливо. Сильний prompt суворіший: він вимагає відповідати тільки тоді, коли retrieved context справді підтримує відповідь.

Retrieval filter працює до виклику LLM. Він дивиться на найкращий vector score серед знайдених chunks і блокує відповідь, якщо score нижчий за поріг. Це потрібно, щоб не передавати моделі явно слабкий або нерелевантний context.

Post-validator працює вже після відповіді LLM. Він перевіряє, що модель дала citations і що ці citations точно збігаються з retrieved chunk IDs. Це потрібно, щоб відрізнити grounded answer від просто вільної відповіді моделі.

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

## План експериментів і спостереження

Загалом проганяємо 5 test queries через однакову 8-way matrix. Набір включає:

| # | Тип запиту | Мета |
|---:|---|---|
| 1 | Повністю нерелевантне питання | Перевірити, що слабкий retrieval і guardrails поводяться очікувано для питання поза Debezium context. |
| 2 | Нечітке Debezium-питання | Перевірити, чи no-filter режими покажуть поведінку моделі, а filter режими заблокують слабкий retrieval. |
| 3 | Нечітке переформульоване Debezium-питання | Перевірити, чи hybrid retrieval зможе знайти частково релевантний issue/page. |
| 4 | Пряме питання з відповіддю в context | Перевірити grounded answer із валідними citations. |
| 5 | Ще одне пряме питання з відповіддю в context | Перевірити стабільність grounded answer на іншому known-answer query. |

### Query 1: нерелевантне питання

Run: [31600084357](https://github.com/Uhbyxer/supp-bro/actions/runs/31600084357)

Питання:

```text
What is the weather today?
```

Найкращий retrieved vector score був лише `0.103`, тому retrieval знайшов нерелевантні Debezium chunks. Найслабша конфігурація все одно дала відповідь, бо retrieval filter і post-validator були вимкнені.

Відповідь скрипта в найслабшій конфігурації (`weak_no_filter_no_validator`):

```text
I'm unable to provide information about the weather today. Please check a reliable weather service or app for the latest updates.
```

| Experiment | Prompt | Post validator | Min vector score | Best vector score | Status | Fallback reason | Citations | Коментар | Очікувано? |
|---|---|---|---:|---:|---|---|---|---|---|
| `weak_no_filter_no_validator` | `weak` | `off` | 0.00 | 0.103 | `unvalidated_answer` | - | - | Модель відповіла вільно і сказала, що не може надати поточну погоду; це поведінка моделі без guardrails. | Так |
| `weak_no_filter_with_validator` | `weak` | `on` | 0.00 | 0.103 | `model_fallback` | `llm_reports_insufficient_context` | - | Weak prompt дійшов до моделі, але post-validation/model context check не дозволив grounded answer. | Так |
| `strong_no_filter_no_validator` | `strong` | `off` | 0.00 | 0.103 | `model_fallback` | `invalid_llm_response` | - | Strong prompt відмовився або повернув fallback-like відповідь; навіть без validator порожня/fallback-відповідь відхиляється як invalid. | Так |
| `strong_no_filter_with_validator` | `strong` | `on` | 0.00 | 0.103 | `model_fallback` | `llm_reports_insufficient_context` | - | Strong prompt коректно повідомив, що context недостатній. | Так |
| `weak_filter_no_validator` | `weak` | `off` | 0.30 | 0.103 | `retrieval_filter_fallback` | `weak_retrieval` | - | Retrieval filter заблокував відповідь до виклику LLM, бо score нижчий за threshold. | Так |
| `weak_filter_with_validator` | `weak` | `on` | 0.30 | 0.103 | `retrieval_filter_fallback` | `weak_retrieval` | - | Такий самий блок на retrieval filter; post-validator взагалі не запускався. | Так |
| `strong_filter_no_validator` | `strong` | `off` | 0.30 | 0.103 | `retrieval_filter_fallback` | `weak_retrieval` | - | Такий самий блок на retrieval filter для strong prompt. | Так |
| `strong_filter_with_validator` | `strong` | `on` | 0.30 | 0.103 | `retrieval_filter_fallback` | `weak_retrieval` | - | Production-like режим коректно відмовився відповідати до виклику LLM. | Так |

Висновок: нерелевантне питання про погоду показує всі guardrail layers. Коли обидва guardrails вимкнені, модель дає unvalidated general answer. Коли post-validation увімкнений, fallback стається після виклику моделі. Коли retrieval filter увімкнений, fallback стається ще до виклику моделі, бо retrieval слабкий.

### Query 2: нечітке Debezium-питання

Run: [31604105353](https://github.com/Uhbyxer/supp-bro/actions/runs/31604105353)

Питання:

```text
Something wrong with back pressure
```

Найкращий retrieved vector score був `0.169`, тобто нижче за поточний threshold `0.30`. Формально retrieval вважається слабким, але знайдені chunks не були повністю випадковими: вони стосувалися batch size, PostgreSQL foreign key constraint violations і можливого зв'язку з back pressure / buffer lock.

| Experiment | Prompt | Post validator | Min vector score | Best vector score | Status | Fallback reason | Citations | Коментар | Очікувано? |
|---|---|---|---:|---:|---|---|---|---|---|
| `weak_no_filter_no_validator` | `weak` | `off` | 0.00 | 0.169 | `unvalidated_answer` | - | `issues:dbz:73:chunk_002`, `issues:dbz:73:chunk_003` | Weak prompt без guardrails дав розгорнуту відповідь і використав частково релевантні chunks. | Так |
| `weak_no_filter_with_validator` | `weak` | `on` | 0.00 | 0.169 | `grounded_answer` | - | `issues:dbz:73:chunk_002`, `issues:dbz:73:chunk_003` | Навіть із post-validator відповідь пройшла, бо citations збіглися з retrieved chunk IDs. | Так |
| `strong_no_filter_no_validator` | `strong` | `off` | 0.00 | 0.169 | `model_fallback` | `invalid_llm_response` | - | Strong prompt був обережніший і відмовився відповідати на нечіткий context. | Так |
| `strong_no_filter_with_validator` | `strong` | `on` | 0.00 | 0.169 | `model_fallback` | `llm_reports_insufficient_context` | - | Strong prompt із validator підтвердив, що context недостатньо прямий. | Так |
| `weak_filter_no_validator` | `weak` | `off` | 0.30 | 0.169 | `retrieval_filter_fallback` | `weak_retrieval` | - | Retrieval filter заблокував відповідь до LLM через score нижче threshold. | Так |
| `weak_filter_with_validator` | `weak` | `on` | 0.30 | 0.169 | `retrieval_filter_fallback` | `weak_retrieval` | - | Такий самий блок на retrieval filter; validator не запускався. | Так |
| `strong_filter_no_validator` | `strong` | `off` | 0.30 | 0.169 | `retrieval_filter_fallback` | `weak_retrieval` | - | Filter однаково блокує strong prompt до виклику LLM. | Так |
| `strong_filter_with_validator` | `strong` | `on` | 0.30 | 0.169 | `retrieval_filter_fallback` | `weak_retrieval` | - | Production-like режим відмовився відповідати через слабкий retrieval. | Так |

Висновок: цей запит показує різницю між слабким і сильним prompt. Weak prompt без retrieval filter зміг використати частково релевантні chunks і навіть пройти post-validator, але strong prompt відмовився, бо питання було надто нечітким. Усі filter-режими повернули `weak_retrieval`, що очікувано для threshold `0.30`, але цей приклад показує ризик занадто суворого порога: частково корисна відповідь може бути заблокована.

Для подальшого розвитку агента це хороший кейс: замість одразу давати fallback або впевнено відповідати, агент міг би поставити уточнюючі питання. Наприклад, попросити вказати connector type, повний error message, batch size, database і фрагмент логів. Тоді система могла б перейти від нечіткого запиту до більш точного retrieval і дати grounded answer з меншим ризиком.

### Query 3: нечітке переформульоване Debezium-питання

Run: [31606966596](https://github.com/Uhbyxer/supp-bro/actions/runs/31606966596)

Питання:

```text
Debezium backpressure error: unable to acquire buffer lock because the queue is full
```

Найкращий retrieved vector score піднявся до `0.619`, тобто запит уже достатньо добре збігається з наявним context. Retrieval знайшов issue про MongoDB connector і помилку `Unable to acquire buffer lock, buffer queue is likely full`, тому filter із threshold `0.30` нічого не відсіяв.

Відповідь скрипта у слабкій конфігурації (`weak_no_filter_no_validator`):

```text
The error message you're encountering, "Unable to acquire buffer lock, buffer queue is likely full," indicates that the Debezium connector is experiencing backpressure. This typically happens when the connector is unable to process incoming change events quickly enough, causing the buffer queue to fill up.

Here are some steps you can take to address this issue:

1. Increase Buffer Size: You can increase the buffer size by adjusting the `debezium.source.mongodb.buffer.size` configuration parameter. This allows more events to be queued before backpressure occurs.
2. Optimize Processing: Review the processing logic in your application that consumes the change events. Ensure that it is efficient and can handle the incoming data rate.
3. Scale Out: If your application can handle it, consider scaling out your Debezium connector by running multiple instances to distribute the load.
4. Monitor Performance: Use monitoring tools to track the performance of your connector and the downstream application. This can help identify bottlenecks.
5. Adjust Heartbeat and Flush Intervals: You might also want to adjust the `debezium.source.heartbeat.interval.ms` and `debezium.source.offset.flush.interval.ms` settings to ensure that offsets are flushed more frequently, which can help manage the buffer more effectively.

If the problem persists after trying these solutions, consider checking the logs for more detailed error messages and consult the Debezium documentation for further troubleshooting steps.
```

Відповідь скрипта у сильній конфігурації з filter і validator (`strong_filter_with_validator`):

```text
The error "Unable to acquire buffer lock, buffer queue is likely full" indicates that the Debezium connector is experiencing backpressure due to the buffer queue being full.
```

| Experiment | Prompt | Post validator | Min vector score | Best vector score | Status | Fallback reason | Citations | Коментар | Очікувано? |
|---|---|---|---:|---:|---|---|---|---|---|
| `weak_no_filter_no_validator` | `weak` | `off` | 0.00 | 0.619 | `unvalidated_answer` | - | `issues:dbz:3:chunk_005`, `issues:dbz:3:chunk_006` | Weak prompt дав довгу відповідь із порадами, але без post-validation вона лишається unvalidated. | Так |
| `weak_no_filter_with_validator` | `weak` | `on` | 0.00 | 0.619 | `grounded_answer` | - | `issues:dbz:3:chunk_005`, `issues:dbz:3:chunk_006` | Validator пропустив відповідь, бо citations збіглися з retrieved chunk IDs. | Так |
| `strong_no_filter_no_validator` | `strong` | `off` | 0.00 | 0.619 | `unvalidated_answer` | - | `issues:dbz:3:chunk_005`, `issues:dbz:3:chunk_004` | Strong prompt відповів дуже коротко і обережно, але без validator це все ще unvalidated answer. | Так |
| `strong_no_filter_with_validator` | `strong` | `on` | 0.00 | 0.619 | `grounded_answer` | - | `issues:dbz:3:chunk_005`, `issues:dbz:3:chunk_004` | Strong prompt із validator дав grounded answer. | Так |
| `weak_filter_no_validator` | `weak` | `off` | 0.30 | 0.619 | `unvalidated_answer` | - | `issues:dbz:3:chunk_005`, `issues:dbz:3:chunk_006` | Filter не заблокував retrieval, бо score значно вищий за threshold. | Так |
| `weak_filter_with_validator` | `weak` | `on` | 0.30 | 0.619 | `grounded_answer` | - | `issues:dbz:3:chunk_005`, `issues:dbz:3:chunk_006` | Weak prompt проходить і filter, і validator, але відповідь містить загальні troubleshooting поради. | Так |
| `strong_filter_no_validator` | `strong` | `off` | 0.30 | 0.619 | `unvalidated_answer` | - | `issues:dbz:3:chunk_005`, `issues:dbz:3:chunk_006`, `issues:dbz:3:chunk_007` | Production-like retrieval проходить, але без validator відповідь маркується як unvalidated. | Так |
| `strong_filter_with_validator` | `strong` | `on` | 0.30 | 0.619 | `grounded_answer` | - | `issues:dbz:3:chunk_005`, `issues:dbz:3:chunk_004`, `issues:dbz:3:chunk_006`, `issues:dbz:3:chunk_007` | Основний production-like режим дав grounded answer із валідними citations. | Так |

Висновок: цей запит показує, що після додавання конкретного тексту помилки hybrid retrieval працює значно краще, ніж для попереднього нечіткого питання. Vector score `0.619` достатній, тому retrieval filter очікувано не блокує відповідь, а post-validator підтверджує citations.

Різниця між prompt modes тут особливо помітна. Weak prompt дає кориснішу з погляду support-відповіді реакцію, але частина порад виглядає загальною і не повністю підтвердженою context. Strong prompt поводиться обережніше: він майже тільки підтверджує, що це backpressure через заповнену queue. Це хороший наступний кейс для розвитку агента: коли context релевантний, але відповіді недостатньо для повного troubleshooting, агент міг би додати уточнюючі питання або явно відділити факти з context від загальних рекомендацій.

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
