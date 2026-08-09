# HW3: retrieval pipeline improvements

Спочатку для пошуку потрібної інформації я використовував FAISS, а далі покращував retrieval у три кроки:

1. **MongoDB і Pinecone.** Я переніс vector search із FAISS у MongoDB Atlas Vector Search і Pinecone, але сама заміна сховища майже не покращила якість результатів.
2. **Hybrid search і reranking.** Я перевірив два підходи: hybrid retrieval, де BM25-пошук за словами об’єднується із semantic search у Pinecone через RRF, і cross-encoder reranking, який повторно сортує знайдені Pinecone результати. Обидва варіанти стали стабільніше знаходити правильну відповідь.
3. **Фільтрація.** На останньому кроці я додав фільтр за `source`, щоб можна було шукати в усіх даних або окремо лише в документації (`pages`) чи GitHub issues (`issues`).

## Як покращувався retrieval

Після переходу з локального FAISS на MongoDB Atlas Vector Search і Pinecone стало зрозуміло, що сама заміна vector storage не вирішує проблему якості пошуку. Тому далі були реалізовані й порівняні два окремі способи покращення:

- **Cross-encoder reranking** — Pinecone спочатку знаходить 15 кандидатів, після чого cross-encoder повторно оцінює їх разом із запитом і формує фінальний Top-5.
- **Hybrid retrieval** — результати semantic search у Pinecone поєднуються з BM25 keyword search, а фінальний порядок Top-5 визначається за допомогою RRF.

В обох pipeline можна вибрати фільтр за metadata-полем `source`:

- порожнє значення — пошук одночасно в `pages` та `issues`;
- `pages` — пошук лише в документації;
- `issues` — пошук лише в GitHub issues.

Evaluation використовує однаковий набір із 10 запитів: 5 для документації та 5 для issues. Якщо вибрано конкретний `source`, оцінюються лише відповідні 5 запитів.

### Результати без фільтрації

| Pipeline | Top-1 | Hit@5 | MRR | Precision@5 |
|---|---:|---:|---:|---:|
| Cross-encoder reranking | 80% | 100% | 0.90 | 58% |
| Hybrid BM25 + RRF | 80% | 100% | 0.90 | **62%** |

Обидва покращені підходи знаходять релевантний результат у Top-5 для всіх 10 запитів. За Top-1, Hit@5 і MRR вони показали однаковий результат. Hybrid retrieval має трохи вищий Precision@5, тобто частіше повертає додаткові релевантні chunks серед перших п’яти результатів.

Результати за типом джерела:

| Dataset | Pipeline | Top-1 | Hit@5 | MRR | Precision@5 |
|---|---|---:|---:|---:|---:|
| Pages | Cross-encoder reranking | 60% | 100% | 0.80 | 48% |
| Pages | Hybrid BM25 + RRF | 60% | 100% | 0.80 | **52%** |
| Issues | Cross-encoder reranking | 100% | 100% | 1.00 | 68% |
| Issues | Hybrid BM25 + RRF | 100% | 100% | 1.00 | **72%** |

### Порівняння результатів для кожного запиту

У таблиці показано повний Top-5 для однакових 10 запитів до і після фільтрації. Для запитів 1–5 використано `source=pages`, для запитів 6–10 — `source=issues`. **✓** означає expected chunk, **×** — нерелевантний chunk. Для wildcard на кшталт `issues:dbz:1407:*` релевантним вважається будь-який chunk цього issue.

| # | Запит | Expected chunks | Baseline без фільтра Top-5 | Cross-encoder без фільтра Top-5 | Hybrid без фільтра Top-5 | Baseline з фільтром Top-5 | Cross-encoder з фільтром Top-5 | Hybrid з фільтром Top-5 | Коментар |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | Збереження offsets і schema history після restart | `storage:overview`<br>`storage:kafka`<br>`storage:file`<br>`storage:jdbc`<br>`storage:redis` | ✓ `overview`<br>✓ `file`<br>✓ `kafka`<br>× `memory`<br>× `rocketmq` | ✓ `file`<br>✓ `kafka`<br>× `memory`<br>✓ `overview`<br>× `amazon_s3` | ✓ `file`<br>✓ `kafka`<br>× `issues:1407:010`<br>✓ `overview`<br>✓ `jdbc` | ✓ `overview`<br>✓ `file`<br>✓ `kafka`<br>× `memory`<br>× `rocketmq` | ✓ `file`<br>✓ `kafka`<br>× `memory`<br>✓ `redis`<br>✓ `overview` | ✓ `kafka`<br>✓ `file`<br>✓ `overview`<br>✓ `jdbc`<br>× `rocketmq` | Hybrid знайшов 4 із 5 expected chunks замість 3. Після фільтрації: Baseline без змін. Reranking зріс із 3 до 4 expected chunks. Hybrid зберіг 4 expected chunks, але прибрав сторонній `issue`. |
| 2 | Storage для cloud deployment | `storage:amazon_s3`<br>`storage:azure_blob_storage`<br>`storage:kafka` | ✓ `azure_blob_storage`<br>✓ `amazon_s3`<br>× `file`<br>× `memory`<br>× `chronicle_queue` | ✓ `amazon_s3`<br>× `memory`<br>× `overview`<br>× `redis`<br>✓ `azure_blob_storage` | ✓ `azure_blob_storage`<br>× `memory`<br>× `file`<br>✓ `amazon_s3`<br>× `overview` | ✓ `azure_blob_storage`<br>✓ `amazon_s3`<br>× `file`<br>× `memory`<br>× `chronicle_queue` | ✓ `amazon_s3`<br>× `memory`<br>× `overview`<br>× `redis`<br>✓ `azure_blob_storage` | ✓ `azure_blob_storage`<br>× `memory`<br>✓ `amazon_s3`<br>× `file`<br>× `overview` | Усі знайшли 2 із 3 expected chunks; `kafka` не потрапив у Top-5. Після фільтрації: Метрики не змінилися: усі pipelines і далі знаходять 2 із 3 expected chunks. |
| 3 | Різниця між Kafka, file і memory storage | `storage:kafka`<br>`storage:file`<br>`storage:memory` | ✓ `memory`<br>× `overview`<br>✓ `file`<br>✓ `kafka`<br>× `azure_blob_storage` | × `overview`<br>✓ `memory`<br>✓ `kafka`<br>✓ `file`<br>× `azure_blob_storage` | ✓ `memory`<br>× `overview`<br>✓ `file`<br>✓ `kafka`<br>× `azure_blob_storage` | ✓ `memory`<br>× `overview`<br>✓ `file`<br>✓ `kafka`<br>× `azure_blob_storage` | × `overview`<br>✓ `memory`<br>✓ `kafka`<br>✓ `file`<br>× `azure_blob_storage` | ✓ `memory`<br>× `overview`<br>✓ `file`<br>✓ `kafka`<br>× `azure_blob_storage` | Reranking погіршив Top-1; hybrid зберіг правильний chunk на першому місці. Після фільтрації: Метрики й порядок не змінилися. Фільтр не допоміг reranking повернути релевантний Top-1. |
| 4 | Exactly-once delivery з Kafka Connect | `eos:overview`<br>`eos:kafka_connect_exactly_once_...`<br>`eos:configuration` | × `eos:connectors_supporting_...`<br>✓ `eos:kafka_connect_exactly_once_...`<br>✓ `eos:configuration`<br>✓ `eos:overview`<br>× `issues:3:003` | × `eos:connectors_supporting_...`<br>✓ `eos:overview`<br>✓ `eos:configuration`<br>✓ `eos:kafka_connect_exactly_once_...`<br>× `storage:kafka` | × `eos:connectors_supporting_...`<br>✓ `eos:kafka_connect_exactly_once_...`<br>✓ `eos:overview`<br>✓ `eos:configuration`<br>× `storage:overview` | × `eos:connectors_supporting_...`<br>✓ `eos:kafka_connect_exactly_once_...`<br>✓ `eos:configuration`<br>✓ `eos:overview`<br>× `storage:overview` | × `eos:connectors_supporting_...`<br>✓ `eos:overview`<br>✓ `eos:configuration`<br>✓ `eos:kafka_connect_exactly_once_...`<br>× `storage:kafka` | × `eos:connectors_supporting_...`<br>✓ `eos:kafka_connect_exactly_once_...`<br>✓ `eos:overview`<br>✓ `eos:configuration`<br>× `storage:kafka` | Усі знайшли всі 3 expected chunks, але нерелевантний за ground truth chunk лишився на Top-1. Після фільтрації: Precision@5 не змінився. Сторонні issues зникли, але нерелевантний documentation chunk залишився на Top-1. |
| 5 | Що налаштувати перед exactly-once support | `eos:configuration`<br>`eos:kafka_connect_exactly_once_...` | × `issues:4:002`<br>× `issues:1407:002`<br>× `issues:1407:010`<br>× `issues:73:005`<br>× `issues:1407:011` | ✓ `eos:kafka_connect_exactly_once_...`<br>× `eos:connectors_supporting_...`<br>× `eos:overview`<br>× `issues:1407:012`<br>× `issues:73:005` | × `eos:connectors_supporting_...`<br>✓ `eos:kafka_connect_exactly_once_...`<br>× `eos:overview`<br>× `issues:73:005`<br>× `issues:1407:012` | × `storage:overview`<br>✓ `eos:kafka_connect_exactly_once_...`<br>× `eos:connectors_supporting_...`<br>× `eos:overview`<br>✓ `eos:configuration` | ✓ `eos:configuration`<br>✓ `eos:kafka_connect_exactly_once_...`<br>× `eos:connectors_supporting_...`<br>× `eos:overview`<br>× `storage:chronicle_queue` | ✓ `eos:kafka_connect_exactly_once_...`<br>✓ `eos:configuration`<br>× `eos:connectors_supporting_...`<br>× `storage:chronicle_queue`<br>× `eos:overview` | Baseline повністю промахнувся. Reranking підняв expected chunk на Top-1; hybrid знайшов його на Top-2. Після фільтрації: Найбільше покращення: baseline перейшов із повного промаху до 2 expected chunks; reranking знайшов обидва замість одного; hybrid підняв релевантний результат із Top-2 на Top-1 і теж знайшов обидва. |
| 6 | Старий або invalid LSN після restart | `issues:dbz:1407:*` | ✓ `1407:011`<br>✓ `1407:010`<br>✓ `1407:009`<br>✓ `1407:006`<br>✓ `1407:002` | ✓ `1407:011`<br>✓ `1407:009`<br>✓ `1407:010`<br>✓ `1407:002`<br>✓ `1407:006` | ✓ `1407:011`<br>✓ `1407:006`<br>✓ `1407:009`<br>✓ `1407:010`<br>✓ `1407:002` | ✓ `1407:011`<br>✓ `1407:010`<br>✓ `1407:009`<br>✓ `1407:006`<br>✓ `1407:002` | ✓ `1407:011`<br>✓ `1407:009`<br>✓ `1407:010`<br>✓ `1407:002`<br>✓ `1407:006` | ✓ `1407:011`<br>✓ `1407:006`<br>✓ `1407:009`<br>✓ `1407:010`<br>✓ `1407:002` | Уже baseline був ідеальним; змінився лише порядок релевантних chunks. Після фільтрації: Без змін: усі pipelines уже мали 100% Precision@5. |
| 7 | Однакові назви колонок з різним регістром | `issues:dbz:4:*` | ✓ `4:001`<br>× `73:009`<br>× `73:008`<br>× `1407:001`<br>× `1407:005` | ✓ `4:001`<br>× `1407:002`<br>× `storage:jdbc`<br>× `1407:004`<br>× `storage:rocketmq` | ✓ `4:001`<br>× `73:008`<br>✓ `4:002`<br>× `1407:004`<br>× `storage:jdbc` | ✓ `4:001`<br>× `73:009`<br>× `73:008`<br>× `1407:001`<br>× `1407:005` | ✓ `4:001`<br>× `1407:002`<br>× `1407:004`<br>× `73:006`<br>× `73:007` | ✓ `4:001`<br>× `73:009`<br>✓ `4:002`<br>× `1407:001`<br>× `73:008` | Hybrid знайшов 2 chunks правильного issue; baseline і reranking — лише 1. Після фільтрації: Метрики без змін: baseline і reranking мають 20% Precision@5, hybrid — 40%. Фільтр лише прибрав documentation chunks із reranking та hybrid. |
| 8 | MongoDB backpressure: buffer lock і full queue | `issues:dbz:3:*` | ✓ `3:009`<br>✓ `3:006`<br>✓ `3:007`<br>✓ `3:001`<br>✓ `3:010` | ✓ `3:001`<br>✓ `3:007`<br>✓ `3:006`<br>✓ `3:009`<br>✓ `3:011` | ✓ `3:001`<br>✓ `3:006`<br>✓ `3:009`<br>✓ `3:004`<br>✓ `3:010` | ✓ `3:009`<br>✓ `3:006`<br>✓ `3:007`<br>✓ `3:001`<br>✓ `3:010` | ✓ `3:001`<br>✓ `3:007`<br>✓ `3:006`<br>✓ `3:009`<br>✓ `3:011` | ✓ `3:006`<br>✓ `3:001`<br>✓ `3:009`<br>✓ `3:010`<br>✓ `3:011` | Усі три підходи дали 100% Precision@5. Після фільтрації: Без змін: усі Top-5 chunks залишилися релевантними. |
| 9 | JDBC sink: foreign key violations під час batch processing | `issues:dbz:73:*` | ✓ `73:001`<br>✓ `73:004`<br>✓ `73:005`<br>✓ `73:002`<br>✓ `73:008` | ✓ `73:001`<br>✓ `73:002`<br>✓ `73:005`<br>✓ `73:004`<br>✓ `73:008` | ✓ `73:001`<br>✓ `73:004`<br>✓ `73:002`<br>✓ `73:005`<br>✓ `73:008` | ✓ `73:001`<br>✓ `73:004`<br>✓ `73:005`<br>✓ `73:002`<br>✓ `73:008` | ✓ `73:001`<br>✓ `73:002`<br>✓ `73:005`<br>✓ `73:004`<br>✓ `73:008` | ✓ `73:001`<br>✓ `73:004`<br>✓ `73:002`<br>✓ `73:005`<br>✓ `73:008` | Усі три підходи дали 100% Precision@5; відрізняється лише порядок. Після фільтрації: Без змін: усі Top-5 chunks залишилися релевантними. |
| 10 | Issue про міграцію тестів із JUnit4 | `issues:dbz:11:chunk_001` | ✓ `11:001`<br>× `73:007`<br>× `73:005`<br>× `4:005`<br>× `1407:002` | ✓ `11:001`<br>× `1407:001`<br>× `73:001`<br>× `73:008`<br>× `1407:009` | ✓ `11:001`<br>× `73:005`<br>× `73:008`<br>× `73:001`<br>× `1407:005` | ✓ `11:001`<br>× `73:007`<br>× `73:005`<br>× `4:005`<br>× `1407:002` | ✓ `11:001`<br>× `1407:001`<br>× `73:001`<br>× `73:008`<br>× `1407:009` | ✓ `11:001`<br>× `73:005`<br>× `73:008`<br>× `73:001`<br>× `1407:002` | Усі відразу знайшли точний chunk; інші результати Top-5 нерелевантні. Після фільтрації: Без змін у метриках: точний chunk і далі Top-1, Precision@5 залишається 20%. |


### Короткий висновок

Найкращий результат показав **hybrid BM25 + Pinecone через RRF із правильним фільтром `source`**: Top-1 — **90%**, Hit@5 — **100%**, MRR — **0.95**, Precision@5 — **64%**.

Порівняно з baseline без фільтра hybrid із фільтром:

- підняв Top-1 з 80% до 90% (**+10 процентних пунктів**);
- зберіг Hit@5 на 100% — усі запити й далі мають релевантний chunk у Top-5;
- підняв MRR з 0.85 до 0.95 (**+0.10**), тобто правильний результат у середньому став ближчим до першої позиції;
- підняв Precision@5 з 56% до 64% (**+8 процентних пунктів**).

Сам фільтр дав різний ефект. Для baseline Top-1 не змінився, але MRR зріс на 0.05, а Precision@5 — на 4 п.п. Для reranking Top-1 і MRR не змінилися, а Precision@5 зріс на 4 п.п. Найбільше фільтр допоміг hybrid: Top-1 зріс на 10 п.п., MRR — на 0.05, Precision@5 — на 2 п.п. Регресії в загальних метриках не було. Найпомітніше покращився запит №5: фільтр прибрав chunks із `issues`, які витісняли потрібну документацію.

Reranking краще спрацював для окремих складних semantic-запитів, але іноді погіршував першу позицію. Hybrid виявився стабільнішим загалом і частіше повертав більше релевантних chunks у Top-5, тому це рекомендований варіант для основного retrieval pipeline.


## Методи покращення retrieval

У покращеному варіанті перевірялися три основні підходи: cross-encoder reranking, hybrid search і фільтрація за джерелом. Вони вирішують різні проблеми й можуть використовуватися окремо.

### Cross-encoder reranking

Пошук виконується у два етапи:

1. Pinecone за векторною схожістю повертає Top-15 candidates.
2. Cross-encoder `cross-encoder/ms-marco-MiniLM-L-6-v2` одночасно аналізує повний текст запиту і кожного chunk, повторно оцінює їхню відповідність та формує фінальний Top-5.

Звичайний vector search порівнює embeddings запиту й документа. Cross-encoder бачить саму пару «запит + chunk», тому може точніше врахувати їхній зміст і взаємозв'язок.

Водночас reranking не знаходить нових chunks: він лише пересортовує те, що Pinecone вже повернув у Top-15. Якщо потрібний chunk не потрапив до candidates, cross-encoder не може його відновити. У тестах цей підхід допоміг окремим складним semantic-запитам, але в одному випадку опустив правильний chunk із першої позиції на другу.

### Hybrid search: Pinecone + BM25

Hybrid search поєднує два незалежні способи пошуку:

- **Pinecone semantic search** знаходить chunks, близькі до запиту за змістом;
- **BM25 keyword search** знаходить точні слова й словосполучення в title та text.

Semantic search добре працює з перефразуваннями й загальним змістом, але може недооцінити точні назви конфігурацій, компонентів або помилок. BM25 добре знаходить такі технічні терміни, але гірше розуміє запити, сформульовані іншими словами.

Кожен пошук повертає власний Top-15. Далі списки об'єднуються за допомогою Reciprocal Rank Fusion:

```text
RRF(d) = Σ 1 / (k + rank_r(d))
```

У реалізації використано `k=60`. Chunk отримує вищий підсумковий бал, якщо займає високу позицію в одному або обох списках. RRF працює з позиціями, тому не потрібно напряму порівнювати Pinecone similarity score і BM25 score, які мають різний зміст та масштаб.

Hybrid виявився найстабільнішим підходом: він частіше повертав більше релевантних chunks у Top-5 і рідше погіршував першу позицію.

### Фільтрація за `source`

Кожен chunk має metadata-поле `source`:

- `pages` — документація;
- `issues` — GitHub issues.

Фільтр застосовується ще до формування candidates:

- Pinecone використовує server-side metadata filter;
- BM25 шукає лише серед chunks вибраного типу;
- evaluation запускається лише для запитів відповідного джерела.

Фільтрація не змінює алгоритм ранжування. Вона прибирає з конкуренції chunks неправильного типу. Найбільше це допомогло запиту №5 про exactly-once configuration, де без фільтра результати з `issues` витісняли потрібну документацію.

## Метрики оцінювання

Evaluation використовує 10 тестових запитів: 5 до документації та 5 до GitHub issues. Для кожного запиту наперед визначено expected chunks, які вважаються релевантними.

### Top-1

Top-1 — частка запитів, у яких перший результат релевантний:

```text
Top-1 = запити з релевантним результатом на позиції 1 / усі запити
```

Top-1 = 90% означає, що для 9 із 10 запитів правильний chunk стояв першим. Для RAG це важливо, коли відповідь найбільше спирається на найвище ранжований контекст.

### Hit@5

Hit@5 — частка запитів, для яких хоча б один релевантний chunk потрапив у перші п'ять:

```text
Hit@5 = запити з хоча б одним релевантним chunk у Top-5 / усі запити
```

Hit@5 = 100% означає, що система жодного разу повністю не промахнулася. Ця метрика не розрізняє, чи правильний результат був першим, чи п'ятим.

### MRR

MRR (Mean Reciprocal Rank) враховує позицію першого релевантного результату. Для одного запиту:

```text
RR = 1 / позиція першого релевантного результату
```

Тому позиція 1 дає RR = 1, позиція 2 — 0.5, позиція 3 — приблизно 0.33, а відсутність релевантного результату — 0. MRR є середнім RR для всіх запитів. Чим ближче значення до 1, тим частіше правильний chunk розташований на початку списку.

### Precision@5

Precision@5 показує, яка частина перших п'яти результатів є релевантною:

```text
Precision@5 = кількість релевантних chunks у Top-5 / 5
```

Один правильний chunk із п'яти дає 20%, три — 60%, усі п'ять — 100%. Метрика показує не лише наявність відповіді, а й кількість шуму в контексті, який буде передано LLM.

Для частини Issues-запитів ground truth задано wildcard-патерном, наприклад `issues:dbz:1407:*`: релевантним вважається будь-який chunk цього issue. Тому Precision@5 для Issues легше отримати високим і його не варто напряму порівнювати з Pages, де часто задано конкретні expected chunks.

### Підсумкове порівняння

| Метрика | Baseline без фільтра | Найкращий hybrid із фільтром | Зміна |
|---|---:|---:|---:|
| Top-1 | 80% | **90%** | **+10 п.п.** |
| Hit@5 | 100% | **100%** | без змін |
| MRR | 0.85 | **0.95** | **+0.10** |
| Precision@5 | 56% | **64%** | **+8 п.п.** |

Найкращим став **Hybrid BM25 + Pinecone через RRF із правильним фільтром `source`**. Reranking був сильним для окремих semantic-запитів, але hybrid дав стабільніший загальний результат завдяки поєднанню пошуку за змістом із точним пошуком за ключовими словами.


## Як запускати retrieval pipelines

Перед першим запуском потрібно один раз встановити залежності:

```bash
make setup
```

Для Pinecone потрібен `PINECONE_API_KEY`. За замовчуванням використовується index `supp-bro` і namespace `hw3-pinecone-vector`. Якщо index ще не створено або вхідні chunks змінилися, спочатку потрібно перебудувати його:

```bash
PINECONE_API_KEY="..." make build-pinecone-index
```

Повторно будувати index перед кожною evaluation не потрібно: build виконує idempotent upsert і видаляє stale vectors лише в namespace HW3.

### Який варіант запускати

| Варіант | Коли використовувати | GitHub Actions workflow | Локальна команда |
|---|---|---|---|
| Baseline Pinecone | Контрольний результат без додаткового сортування | `Check HW3 Pinecone Semantic Search` | `PINECONE_API_KEY="..." make pinecone-semantic-search` |
| Cross-encoder reranking | Коли важливіший semantic зміст і потрібно повторно оцінити Pinecone candidates | `Evaluate HW3 Pinecone Retrieval` | `PINECONE_API_KEY="..." make pinecone-retrieval-evaluation` |
| Hybrid BM25 + RRF | Рекомендований основний варіант: поєднує semantic і keyword matching | `Evaluate HW3 Pinecone Hybrid Retrieval` | `PINECONE_API_KEY="..." make pinecone-hybrid-evaluation` |

Якщо тип джерела відомий, варто додати фільтр:

- `PINECONE_SOURCE=pages` — шукати лише в документації та оцінити 5 Pages-запитів;
- `PINECONE_SOURCE=issues` — шукати лише в GitHub issues та оцінити 5 Issues-запитів;
- порожній `PINECONE_SOURCE` — шукати в обох джерелах та оцінити всі 10 запитів.

Наприклад, рекомендований hybrid pipeline лише для документації:

```bash
PINECONE_API_KEY="..." PINECONE_SOURCE=pages make pinecone-hybrid-evaluation
```

Hybrid pipeline лише для issues:

```bash
PINECONE_API_KEY="..." PINECONE_SOURCE=issues make pinecone-hybrid-evaluation
```

Повне порівняння без фільтра:

```bash
PINECONE_API_KEY="..." PINECONE_SOURCE="" make pinecone-hybrid-evaluation
```

Для reranking значення `PINECONE_SOURCE` задається так само, але запускається target `pinecone-retrieval-evaluation`.

### Запуск у GitHub Actions

1. Відкрити **Actions** у репозиторії.
2. Вибрати потрібний workflow із таблиці вище.
3. Натиснути **Run workflow**.
4. У полі `source` вибрати порожнє значення, `pages` або `issues`.
5. Після завершення відкрити job summary: там буде таблиця з expected і retrieved chunks та метриками для кожного запиту.
6. Повні JSON і Markdown reports доступні в artifacts запуску.

Для GitHub Actions `PINECONE_API_KEY` має бути доданий як repository secret. Workflow сам передає вибране поле `source` у `PINECONE_SOURCE`.

## Важливі деталі імплементації

### Baseline Pinecone

Baseline кодує запит моделлю `sentence-transformers/all-MiniLM-L6-v2`, нормалізує 384-вимірний embedding і робить vector search у Pinecone. Це контрольний pipeline, з яким порівнюються покращення.

### Cross-encoder reranking

Reranking працює у два етапи:

1. Pinecone повертає Top-15 semantic candidates.
2. `cross-encoder/ms-marco-MiniLM-L-6-v2` оцінює пари «запит + текст chunk» і формує фінальний Top-5.

Cross-encoder не створює нових candidates, а лише змінює порядок уже знайдених Pinecone результатів. Тому релевантний chunk спочатку повинен потрапити в Top-15.

### Hybrid BM25 + RRF

Hybrid pipeline формує два незалежні списки:

1. Pinecone повертає Top-15 за semantic similarity.
2. Локальний BM25 повертає Top-15 за словами з title і text.

Списки об'єднуються через Reciprocal Rank Fusion із `k=60`, після чого береться фінальний Top-5. RRF використовує позиції результатів, а не намагається напряму порівнювати Pinecone score і BM25 score.

### Фільтрація за source

Фільтр застосовується до формування candidates:

- у Pinecone — server-side metadata filter `{"source": {"$eq": "pages|issues"}}`;
- у hybrid — той самий source додатково обмежує локальний набір chunks для BM25;
- evaluation dataset також вибирається за source: `pages` або `issues`; без фільтра використовуються всі 10 cases.

Це важливо: фільтрація не виправляє сортування сама по собі, а не дозволяє chunks іншого типу потрапити до candidate list.

### Evaluation і результати

Обидва покращені evaluation scripts рахують однакові метрики: Top-1, Hit@5, MRR і Precision@5. Ground truth спільний для всіх pipelines. Для частини Issues-запитів використовується wildcard на рівні issue, наприклад `issues:dbz:1407:*`, тому їхній Precision@5 не можна напряму трактувати так само, як точні expected chunks для Pages.

Звіти зберігаються в:

- reranking: `data/hw3/output/pinecone_retrieval_evaluation.json` і `.md`;
- hybrid: `data/hw3/output/pinecone_hybrid_evaluation.json` і `.md`.

Моделі Sentence Transformers і cross-encoder завантажуються під час запуску. Тимчасовий Hugging Face `429 Too Many Requests` не означає помилку retrieval-коду; зазвичай достатньо повторити workflow.

## MongoDB Atlas як окремий експеримент

MongoDB Atlas Vector Search використовувався для перевірки, чи сама заміна FAISS на інше vector storage покращує retrieval. Помітного покращення якості це не дало, тому основне порівняння reranking, hybrid і source-фільтрації виконується на Pinecone.

Для локальної перевірки MongoDB потрібен `MONGODB_URI`:

```bash
MONGODB_URI="mongodb+srv://..." make build-mongo-index
MONGODB_URI="mongodb+srv://..." make mongo-semantic-search
```

У GitHub Actions цим командам відповідають workflows `Build HW3 Mongo Vector Index` і `Check HW3 Mongo Semantic Search`. Для GitHub-hosted runner також потрібно врахувати MongoDB Atlas IP allow-list.

