# HW3: retrieval pipeline improvements

HW3 фокусується на покращенні retrieval pipeline після локального FAISS baseline з HW2.
Перше покращення - перенести semantic retrieval storage у MongoDB Atlas Vector Search, щоб chunk text, metadata та embeddings зберігалися в одній searchable collection.

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
- `Check HW3 Mongo Semantic Search`: запускає MongoDB semantic search з тими самими queries, що й HW2, і завантажує `mongo_semantic_search_output.txt` як artifact.

Для GitHub-hosted runners треба врахувати Atlas IP allow-list: runner IP може змінюватися між запусками.
Для стабільнішого доступу можна використати self-hosted runner зі static IP або окремо налаштувати Atlas network access для CI.

## Зміна pipeline після HW2

HW2 зберігає vectors локально у FAISS, а chunk text/metadata окремо в JSONL.
HW3 починає переносити retrieval у backend, який може зберігати vectors разом з chunk documents і підтримувати server-side vector search. Це спрощує наступні покращення, наприклад metadata filtering, порівняння MongoDB Atlas з Pinecone і побудову повнішого retrieval evaluation pipeline.
