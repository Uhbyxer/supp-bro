# HW2: semantic index

HW2 будує semantic search index на основі chunks, підготовлених у HW1.

Скрипт `scripts/hw2/build_index.py` читає:

- `data/hw1/processed/chunks_large.jsonl`;
- `data/hw1/processed/chunks_medium.json`.

І створює:

- `data/hw2/processed/chunks_for_retrieval.jsonl`;
- `data/hw2/processed/embeddings.npy`;
- `data/hw2/index/faiss.index`.

Щоб зберегти результат перевірки semantic search у текстовий файл, запусти:

```bash
python scripts/hw2/semantic_search.py > data/hw2/output/semantic_search_output.txt
```

## Тестові queries для semantic index

Після побудови semantic index можна перевірити, чи пошук знаходить правильні chunks з `data/hw2/processed/chunks_for_retrieval.jsonl`.
Queries нижче спеціально підібрані так, щоб частина з них могла повертати кілька релевантних chunks з одного документа або схожих секцій.

### Pages

| Query користувача | Очікувані chunk_id | Очікуваний document_id | Документ | FAISS top 5 | Аналіз результату |
| --- | --- | --- | --- | --- | --- |
| How should Debezium persist connector offsets and schema history after a restart? | `pages:configuration:storage:overview`, `pages:configuration:storage:kafka`, `pages:configuration:storage:file`, `pages:configuration:storage:jdbc`, `pages:configuration:storage:redis` | `pages:configuration:storage` | Storing state of a Debezium connector | 1. `pages:configuration:storage:overview` (score: 0.7324)<br>2. `pages:configuration:storage:file` (score: 0.7253)<br>3. `pages:configuration:storage:kafka` (score: 0.7140)<br>4. `pages:configuration:storage:memory` (score: 0.6874)<br>5. `pages:configuration:storage:rocketmq` (score: 0.6755) | Відповідає частково добре: top-3 містить релевантні `overview`, `file` і `kafka`, які прямо описують persistence offsets і schema history після restart.<br>FAISS знайшов ці chunks через збіг за темами persistent storage, offsets, schema history і restart. Score `0.71-0.73` сильний для top-3, але `memory` і `rocketmq` нижче не були в очікуваному списку. |
| Which storage options are suitable for cloud deployments of Debezium state? | `pages:configuration:storage:amazon_s3`, `pages:configuration:storage:azure_blob_storage`, `pages:configuration:storage:kafka` | `pages:configuration:storage` | Storing state of a Debezium connector | 1. `pages:configuration:storage:azure_blob_storage` (score: 0.5903)<br>2. `pages:configuration:storage:amazon_s3` (score: 0.5703)<br>3. `pages:configuration:storage:file` (score: 0.5430)<br>4. `pages:configuration:storage:memory` (score: 0.5228)<br>5. `pages:configuration:storage:chronicle_queue` (score: 0.4601) | Відповідає частково: `azure_blob_storage` і `amazon_s3` точно відповідають cloud storage options.<br>FAISS також повернув `file`, `memory` і `chronicle_queue`, бо вони тематично належать до storage, але не є cloud-specific варіантами. Score `0.57-0.59` для перших двох помірний, тому результат корисний, але не ідеальний. |
| What is the difference between Kafka, file, and memory offset storage in Debezium? | `pages:configuration:storage:kafka`, `pages:configuration:storage:file`, `pages:configuration:storage:memory` | `pages:configuration:storage` | Storing state of a Debezium connector | 1. `pages:configuration:storage:memory` (score: 0.6740)<br>2. `pages:configuration:storage:overview` (score: 0.6688)<br>3. `pages:configuration:storage:file` (score: 0.6525)<br>4. `pages:configuration:storage:kafka` (score: 0.6237)<br>5. `pages:configuration:storage:azure_blob_storage` (score: 0.5705) | Відповідає добре: top-5 містить ключові очікувані chunks `memory`, `file` і `kafka`.<br>FAISS знайшов їх через прямий збіг із назвами storage типів і темою offset storage; `overview` теж релевантний, бо пояснює загальний механізм збереження offsets. Score `0.62-0.67` нормальний для порівняльного query, хоча порядок відрізняється від очікуваного. |
| How does Debezium achieve exactly-once delivery with Kafka Connect? | `pages:configuration:eos:overview`, `pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector`, `pages:configuration:eos:configuration` | `pages:configuration:eos` | Exactly once delivery | 1. `pages:configuration:eos:debezium_connectors_supporting_exactly_once_delivery` (score: 0.7798)<br>2. `pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector` (score: 0.7735)<br>3. `pages:configuration:eos:configuration` (score: 0.7697)<br>4. `pages:configuration:eos:overview` (score: 0.7660)<br>5. `issues:dbz:3:chunk_003` (score: 0.6272) | Відповідає добре: top-4 всі з `pages:configuration:eos` і напряму стосуються exactly-once delivery та Kafka Connect.<br>FAISS знайшов ці chunks через сильний семантичний збіг за словами exactly-once, Kafka Connect, source connector і configuration. Score `0.76-0.78` високий; `issues:dbz:3` на 5 місці нерелевантний, але має помітно нижчий score. |
| What must be configured before enabling exactly-once support for source connectors? | `pages:configuration:eos:configuration`, `pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector` | `pages:configuration:eos` | Exactly once delivery | 1. `issues:dbz:4:chunk_002` (score: 0.3762)<br>2. `issues:dbz:1407:chunk_002` (score: 0.3668)<br>3. `issues:dbz:1407:chunk_010` (score: 0.3429)<br>4. `issues:dbz:73:chunk_005` (score: 0.3358)<br>5. `issues:dbz:1407:chunk_011` (score: 0.3265) | Не відповідає очікуванню: top-5 повернув лише issue chunks, а не `pages:configuration:eos` chunks.<br>FAISS, ймовірно, зачепився за загальні слова про connector, configuration і support, але не знайшов потрібний EOS контекст. Score `0.32-0.38` низький, тому результат слабкий і його не варто вважати успішним. |

### Issues

| Query користувача | Очікувані chunk_id | Очікуваний document_id | Документ |
| --- | --- | --- | --- |
| Postgres connector resumes from an old or invalid LSN after restart and replication slot validation looks wrong | `issues:dbz:1407:*` | `issues:dbz:1407` | Postgres connector log position validation logic is flawed [DBZ-9535] |
| Debezium connector crashes when two table columns have the same name except for letter case | `issues:dbz:4:*` | `issues:dbz:4` | Debezium can break when two column names differs only in letter case |
| MongoDB connector backpressure error says unable to acquire buffer lock and queue is full | `issues:dbz:3:*` | `issues:dbz:3` | mongodb :  Unable to acquire buffer lock, buffer queue is likely full |
| JDBC sink writes records in the correct topic order but batch processing causes foreign key violations | `issues:dbz:73:*` | `issues:dbz:73` | Foreign Key Constraint Violation When Using Batch Processing in JDBC Sink Connector 2.7.0.Final [DBZ-8922] |
| Which issue is only about migrating tests from JUnit4 to a newer JUnit version? | `issues:dbz:11:chunk_001` | `issues:dbz:11` | Migrate from JUnit4 to JUnit 5 |
