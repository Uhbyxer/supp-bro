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

| Query користувача | Очікувані chunk_id | Очікуваний document_id | Документ |
| --- | --- | --- | --- |
| How should Debezium persist connector offsets and schema history after a restart? | `pages:configuration:storage:overview`, `pages:configuration:storage:kafka`, `pages:configuration:storage:file`, `pages:configuration:storage:jdbc`, `pages:configuration:storage:redis` | `pages:configuration:storage` | Storing state of a Debezium connector |
| Which storage options are suitable for cloud deployments of Debezium state? | `pages:configuration:storage:amazon_s3`, `pages:configuration:storage:azure_blob_storage`, `pages:configuration:storage:kafka` | `pages:configuration:storage` | Storing state of a Debezium connector |
| What is the difference between Kafka, file, and memory offset storage in Debezium? | `pages:configuration:storage:kafka`, `pages:configuration:storage:file`, `pages:configuration:storage:memory` | `pages:configuration:storage` | Storing state of a Debezium connector |
| How does Debezium achieve exactly-once delivery with Kafka Connect? | `pages:configuration:eos:overview`, `pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector`, `pages:configuration:eos:configuration` | `pages:configuration:eos` | Exactly once delivery |
| What must be configured before enabling exactly-once support for source connectors? | `pages:configuration:eos:configuration`, `pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector` | `pages:configuration:eos` | Exactly once delivery |

### Issues

| Query користувача | Очікувані chunk_id | Очікуваний document_id | Документ |
| --- | --- | --- | --- |
| Postgres connector resumes from an old or invalid LSN after restart and replication slot validation looks wrong | `issues:dbz:1407:*` | `issues:dbz:1407` | Postgres connector log position validation logic is flawed [DBZ-9535] |
| Debezium connector crashes when two table columns have the same name except for letter case | `issues:dbz:4:*` | `issues:dbz:4` | Debezium can break when two column names differs only in letter case |
| MongoDB connector backpressure error says unable to acquire buffer lock and queue is full | `issues:dbz:3:*` | `issues:dbz:3` | mongodb :  Unable to acquire buffer lock, buffer queue is likely full |
| JDBC sink writes records in the correct topic order but batch processing causes foreign key violations | `issues:dbz:73:*` | `issues:dbz:73` | Foreign Key Constraint Violation When Using Batch Processing in JDBC Sink Connector 2.7.0.Final [DBZ-8922] |
| Which issue is only about migrating tests from JUnit4 to a newer JUnit version? | `issues:dbz:11:chunk_001` | `issues:dbz:11` | Migrate from JUnit4 to JUnit 5 |
