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


#### Етап фільтрації

Фільтр було додано після порівняння baseline, reranking і hybrid. Він не змінює алгоритм сортування, а обмежує candidates за metadata `source`:

- `source=pages` — для запитів 1–5 Pinecone і BM25 шукають лише серед документації;
- `source=issues` — для запитів 6–10 пошук виконується лише серед GitHub issues;
- порожнє значення — використовуються обидва джерела, саме так були отримані результати в таблиці.

Фактичні filtered runs підтвердили, що основний ефект припав на Pages. Найсильніше покращився запит 5, де без фільтрації результати забруднювали chunks із `issues`. Для Issues метрики не змінилися, оскільки правильні issue chunks і до фільтрації вже домінували у Top-5.

| Pipeline | Top-1 без фільтра | Top-1 з фільтром | MRR без фільтра | MRR з фільтром | Precision@5 без фільтра | Precision@5 з фільтром |
|---|---:|---:|---:|---:|---:|---:|
| Baseline Pinecone | 80% | 80% | 0.85 | 0.90 | 56% | 60% |
| Cross-encoder reranking | 80% | 80% | 0.90 | 0.90 | 58% | 62% |
| Hybrid BM25 + RRF | 80% | **90%** | 0.90 | **0.95** | 62% | **64%** |

Зараз hybrid retrieval показує найкращий загальний результат, хоча перевага невелика й проявляється лише в Precision@5. Для Issues значення Precision@5 треба трактувати обережно: для частини тестів релевантним вважається будь-який chunk правильного issue, тоді як для Pages expected chunks задані точніше.

HW3 фокусується на покращенні retrieval pipeline після локального FAISS baseline з HW2.
Перше покращення - перенести semantic retrieval storage у MongoDB Atlas Vector Search, щоб chunk text, metadata та embeddings зберігалися в одній searchable collection.

Також HW3 містить альтернативний Pinecone backend: окремі скрипти створюють і наповнюють index та запускають semantic search для тих самих queries, що й HW2 і MongoDB.

## MongoDB Atlas Vector Search

Скрипт `scripts/hw3/build_mongo_vector_index.py` готує MongoDB Atlas retrieval backend.
Він читає ті самі HW1 chunk files, які використовувалися в HW2:

- `data/hw1/processed/chunks_large.jsonl`;
- `data/hw1/processed/chunks_medium.json`.

Скрипт створює embeddings через `sentence-transformers/all-MiniLM-L6-v2`, завантажує один MongoDB document на кожен chunk і створює Atlas Vector Search index для поля `embedding`.
Після цього `scripts/hw3/mongo_semantic_search.py` запускає ті самі тестові queries, що й HW2 FAISS baseline, щоб результати можна було порівнювати напряму.

## Environment variables для MongoDB

Обов'язково:

- `MONGODB_URI`: MongoDB Atlas connection string.

Опціонально:

- `MONGODB_DATABASE`: database name, default `supp-bro`;
- `MONGODB_COLLECTION`: collection name, default `chunks`;
- `MONGODB_VECTOR_INDEX`: vector index name, default `vector_index`.

Для локального запуску можна змінити `.env` у root папці repo:

```env
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/
MONGODB_DATABASE=supp-bro
MONGODB_COLLECTION=chunks
MONGODB_VECTOR_INDEX=vector_index
```

Файл `.env` містить placeholder values. Для локального запуску заміни `MONGODB_URI` на свій MongoDB Atlas connection string.

## Запуск

```bash
MONGODB_URI="mongodb+srv://..." make build-mongo-index
```

Перевірити semantic search через MongoDB Atlas Vector Search:

```bash
MONGODB_URI="mongodb+srv://..." make mongo-semantic-search
```

Зберегти результат MongoDB semantic search у текстовий файл для порівняння з HW2:

```bash
MONGODB_URI="mongodb+srv://..." make mongo-semantic-search > data/hw2/output/mongo_semantic_search_output.txt
```

Vector index використовує:

- vector path: `embedding`;
- filter path: `pipeline`;
- dimensions: `384`;
- similarity: `dotProduct`.

## Cleanup behavior для stale records

Скрипт завжди робить stale cleanup, але не очищає collection повністю.
Він робить idempotent upsert по `chunk_id`, тому повторний запуск оновлює існуючі chunk documents або додає нові.

Після upsert скрипт видаляє тільки stale documents цього pipeline:

- document має `pipeline: "hw3_mongo_vector"`;
- `chunk_id` більше не існує в поточних HW1 input chunks.

Скрипт не використовує `delete_many({})`, бо такий cleanup може випадково видалити інші retrieval experiments у тій самій collection.

## GitHub Actions

Для GitHub Actions credentials не беруться з `.env`.
`MONGODB_URI` потрібно додати як GitHub repository Secret.
Не секретні значення можна задати як workflow env або GitHub Variables:

```yaml
env:
  MONGODB_URI: ${{ secrets.MONGODB_URI }}
  MONGODB_DATABASE: supp-bro
  MONGODB_COLLECTION: chunks
  MONGODB_VECTOR_INDEX: vector_index
```

У цьому repo GitHub Actions workflows для MongoDB запускаються тільки вручну через `workflow_dispatch`.
Є два окремі workflows:

- `Build HW3 Mongo Vector Index`: будує embeddings, upsert documents у MongoDB і створює Atlas Vector Search index;
- `Check HW3 Mongo Semantic Search`: запускає MongoDB semantic search з тими самими queries, що й HW2, показує Markdown table у GitHub Actions summary і завантажує `mongo_semantic_search_output.txt` / `mongo_semantic_search_summary.md` як artifact.

Для GitHub-hosted runners треба врахувати Atlas IP allow-list: runner IP може змінюватися між запусками.
Для стабільнішого доступу можна використати self-hosted runner зі static IP або окремо налаштувати Atlas network access для CI.

## Pinecone Vector Index

`scripts/hw3/build_pinecone_vector_index.py` читає ті самі HW1 chunks, генерує нормалізовані 384-dimensional embeddings і idempotently завантажує їх у Pinecone serverless index.

Обов'язковий GitHub repository Secret:

- `PINECONE_API_KEY`: API key із Pinecone console.

Опціональні environment variables:

- `PINECONE_INDEX`: index name, default `supp-bro`;
- `PINECONE_NAMESPACE`: namespace, default `hw3-pinecone-vector`;
- `PINECONE_CLOUD`: serverless cloud, default `aws`;
- `PINECONE_REGION`: serverless region, default `us-east-1`.

Локальний запуск:

```bash
PINECONE_API_KEY="..." make build-pinecone-index
```

Перевірити semantic search у Pinecone:

```bash
PINECONE_API_KEY="..." make pinecone-semantic-search
```

Workflow `Build HW3 Pinecone Vector Index` запускається вручну через `workflow_dispatch`. Він створює index, якщо його ще немає, перевіряє dimension/metric існуючого index, upsert-ить поточні chunks у виділений namespace і видаляє з цього namespace stale vectors.

Workflow `Check HW3 Pinecone Semantic Search` також запускається вручну. Він виконує ті самі 10 test queries з `top_k=5`, додає Markdown table до GitHub Actions summary і завантажує текстовий output та Markdown summary як artifact.

## Pinecone retrieval evaluation

`scripts/hw3/pinecone_retrieval_evaluation.py` порівнює два pipelines на 5 queries із секції `Pages` у HW2:

- baseline: старий unfiltered Pinecone Top-5 pipeline, який використовувався в GitHub Actions run `30763956563`;
- improved: metadata filter `source=pages`, Pinecone `top_k=15`, reranking моделлю `cross-encoder/ms-marco-MiniLM-L-6-v2` і фінальний `top_k=5`.

Ground truth повністю повторює очікувані `chunk_id` з таблиці `scripts/hw2#pages`. Для обох варіантів скрипт рахує Top-1 accuracy, Hit@5, MRR та Precision@5 відносно цих IDs. Локальний запуск:

```bash
PINECONE_API_KEY="..." make pinecone-retrieval-evaluation
```

Workflow `Evaluate HW3 Pinecone Retrieval` додає порівняльну таблицю до GitHub Actions summary та завантажує повний JSON і Markdown reports як artifact.

## Pinecone hybrid retrieval evaluation

`scripts/hw3/pinecone_hybrid_evaluation.py` порівнює той самий старий baseline pipeline з run `30763956563` з hybrid pipeline на тих самих 5 `Pages` queries:

- metadata-filtered Pinecone Top-15;
- локальний BM25 Top-15 по всіх чанках, що пройшли той самий metadata filter;
- Reciprocal Rank Fusion (`k=60`);
- фінальний Top-5.

Локальний запуск:

```bash
PINECONE_API_KEY="..." make pinecone-hybrid-evaluation
```

Обидва evaluation workflows показують у GitHub Actions summary:

- aggregate metrics старого pipeline з run `30763956563` і нового pipeline;
- delta та висновок про покращення або regression;
- для кожного query — expected chunks із HW2 Pages та позицію першого релевантного baseline/new результату.
## Зміна pipeline після HW2

HW2 зберігає vectors локально у FAISS, а chunk text/metadata окремо в JSONL.
HW3 починає переносити retrieval у backend, який може зберігати vectors разом з chunk documents і підтримувати server-side vector search. Це спрощує наступні покращення, наприклад metadata filtering, порівняння MongoDB Atlas з Pinecone і побудову повнішого retrieval evaluation pipeline.
