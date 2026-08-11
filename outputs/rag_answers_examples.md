# HW4 grounded QA examples

IDs базуються на HW3 evaluation; scores і точне формулювання LLM фіксуються artifact-ом живого workflow.

| # | Question | Retrieved chunks | Answer | Source | Comment |
|---:|---|---|---|---|---|
| 1 | How does Debezium achieve exactly-once delivery with Kafka Connect? | `pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector`, `pages:configuration:eos:overview` | Debezium can use Kafka Connect exactly-once support for source connectors, built on Kafka transactions [pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector]. | `data/hw1/raw/pages/configuration/eos.adoc` | Simple grounded answer with citation. |
| 2 | Can a Debezium source connector avoid duplicate events by relying on Kafka Connect? | `pages:configuration:eos:overview`, `pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector` | When deployed in Kafka Connect, it can use Kafka Connect's exactly-once support; Debezium has no internal deduplication layer [pages:configuration:eos:overview]. | `data/hw1/raw/pages/configuration/eos.adoc` | Paraphrased question. |
| 3 | What is the difference between Kafka, file, and memory offset storage? | `pages:configuration:storage:memory`, `...:file`, `...:kafka` | Live run must cite each storage chunk beside its corresponding claim. | storage documentation metadata | Multi-source/claim citation case. |
| 4 | Which storage options suit cloud deployments? | `pages:configuration:storage:azure_blob_storage`, `...:amazon_s3` | Azure Blob Storage and Amazon S3 are the retrieved cloud options [pages:configuration:storage:azure_blob_storage] [pages:configuration:storage:amazon_s3]. | storage documentation metadata | Relevant chunks only. |
| 5 | Which issue migrates tests from JUnit4? | `issues:dbz:11:chunk_001` | The matching issue is “Migrate from JUnit4 to JUnit 5” [issues:dbz:11:chunk_001]. | issue DBZ-11 metadata | Exact issue lookup. |
| 6 | Why can fields differing only by capitalization crash the connector? | `issues:dbz:4:chunk_001`, `issues:dbz:4:chunk_002` | Live answer must use only DBZ-4 facts and citations. | issue DBZ-4 metadata | Paraphrased issue. |
| 7 | What is the support policy for Oracle 30c? | none above threshold | I do not have enough information in the retrieved context to answer this question. | none | Insufficient context fallback. |
| 8 | What will the weather be in Kraków tomorrow? | weak unrelated chunks or none | I do not have enough information in the retrieved context to answer this question. | none | Out-of-domain fallback. |
