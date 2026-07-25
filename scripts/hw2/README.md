# HW2: semantic index

HW2 будує semantic search index на основі chunks, підготовлених у HW1.

Скрипт `scripts/hw2/build_index.py` читає:

- `data/hw1/processed/chunks_large.jsonl`;
- `data/hw1/processed/chunks_medium.json`.

І створює:

- `data/hw2/processed/chunks_for_retrieval.jsonl`;
- `data/hw2/processed/embeddings.npy`;
- `data/hw2/index/faiss.index`.

## Тестові queries для semantic index

Після побудови semantic index можна перевірити, чи пошук знаходить правильні chunks з `data/hw2/processed/chunks_for_retrieval.jsonl`.
Для кожного query нижче очікуваний результат вказує chunk, який має бути серед найбільш релевантних результатів, і документ, до якого він належить.

| Query користувача | Очікуваний chunk_id | Очікуваний document_id | Документ |
| --- | --- | --- | --- |
| How do I enable exactly-once delivery for Debezium source connectors? | `pages:configuration:eos:configuration` | `pages:configuration:eos` | Exactly once delivery |
| Does Debezium guarantee exactly-once delivery or at-least-once delivery by default? | `pages:configuration:eos:overview` | `pages:configuration:eos` | Exactly once delivery |
| Which Debezium connectors support exactly-once delivery? | `pages:configuration:eos:debezium_connectors_supporting_exactly_once_delivery` | `pages:configuration:eos` | Exactly once delivery |
| Where should Debezium store offsets when running with Kafka Connect distributed mode? | `pages:configuration:storage:kafka` | `pages:configuration:storage` | Storing state of a Debezium connector |
| Can Debezium store offsets in a local file for testing or standalone use? | `pages:configuration:storage:file` | `pages:configuration:storage` | Storing state of a Debezium connector |
| Why is in-memory offset storage not suitable for production? | `pages:configuration:storage:memory` | `pages:configuration:storage` | Storing state of a Debezium connector |
| How can Debezium store schema history in Redis? | `pages:configuration:storage:redis` | `pages:configuration:storage` | Storing state of a Debezium connector |
| What storage backend should I use for Debezium state on Azure? | `pages:configuration:storage:azure_blob_storage` | `pages:configuration:storage` | Storing state of a Debezium connector |
| Postgres connector starts from an invalid LSN after restart | `issues:dbz:1407:chunk_001` або інший `issues:dbz:1407:*` | `issues:dbz:1407` | Postgres connector log position validation logic is flawed [DBZ-9535] |
| Debezium fails when table columns differ only by letter case | `issues:dbz:4:chunk_001` або інший `issues:dbz:4:*` | `issues:dbz:4` | Debezium can break when two column names differs only in letter case |
| MongoDB connector says unable to acquire buffer lock, buffer queue is likely full | `issues:dbz:3:chunk_001` або інший `issues:dbz:3:*` | `issues:dbz:3` | mongodb :  Unable to acquire buffer lock, buffer queue is likely full |
| JDBC sink connector foreign key constraint violation when batch size is greater than 1 | `issues:dbz:73:chunk_001` або інший `issues:dbz:73:*` | `issues:dbz:73` | Foreign Key Constraint Violation When Using Batch Processing in JDBC Sink Connector 2.7.0.Final [DBZ-8922] |
| Migrate Debezium tests from JUnit4 to JUnit5 | `issues:dbz:11:chunk_001` | `issues:dbz:11` | Migrate from JUnit4 to JUnit 5 |

Для першого smoke test достатньо взяти 8 queries: exactly-once configuration, Kafka offset storage, memory storage, Azure storage, Postgres LSN issue, case-sensitive column issue, MongoDB buffer lock issue і JDBC sink foreign key issue.
