# HW2 vs HW3: semantic retrieval comparison

This document compares the local FAISS baseline from HW2 with MongoDB Atlas Vector Search from HW3.

## Evaluation setup

Both pipelines use:

- the same 10 test queries;
- the same HW1 chunks;
- the same `sentence-transformers/all-MiniLM-L6-v2` embedding model;
- the same Top-5 retrieval depth;
- cosine-based similarity.

Sources:

- HW2 baseline: [`scripts/hw2/README.md`](../hw2/README.md)
- HW3 result: [GitHub Actions run 30745733109](https://github.com/Uhbyxer/supp-bro/actions/runs/30745733109)
- HW3 artifact: `mongo-semantic-search-output`

## Executive summary

HW2 and HW3 produce the same retrieval result. For every query, MongoDB Atlas returns exactly the same five chunks in exactly the same order as FAISS.

| Metric | HW2 FAISS | HW3 MongoDB Atlas | Difference |
| --- | ---: | ---: | ---: |
| Queries evaluated | 10 | 10 | 0 |
| Correct Top-1 query results | 9/10 (90%) | 9/10 (90%) | 0 pp |
| Queries with an expected result in Top-5 | 9/10 (90%) | 9/10 (90%) | 0 pp |
| Expected/relevant entries among all Top-5 results | 28/50 (56%) | 28/50 (56%) | 0 pp |
| Top-5 set overlap between backends | — | 50/50 (100%) | identical |
| Exact rank agreement | — | 50/50 (100%) | identical |

The only failed query in both pipelines is:

> What must be configured before enabling exactly-once support for source connectors?

Neither backend retrieves an expected `pages:configuration:eos` chunk in its Top-5.

## Per-query comparison

| # | Query (shortened) | FAISS Top-1 | Atlas Top-1 | Same Top-5 order | Result |
| ---: | --- | --- | --- | :---: | --- |
| 1 | Persist offsets and schema history after restart | `storage:overview` | `storage:overview` | Yes | Partial: 3 expected chunks in Top-5 |
| 2 | Cloud storage options | `storage:azure_blob_storage` | `storage:azure_blob_storage` | Yes | Partial: 2 expected chunks in Top-5 |
| 3 | Kafka vs file vs memory offset storage | `storage:memory` | `storage:memory` | Yes | Good: all 3 expected chunks in Top-5 |
| 4 | Exactly-once delivery with Kafka Connect | `eos:debezium_connectors_supporting_exactly_once_delivery` | same | Yes | Good: all 3 expected chunks in Top-5 |
| 5 | Configuration before enabling exactly-once | `issues:dbz:4:chunk_002` | same | Yes | Failed: 0 expected chunks in Top-5 |
| 6 | Invalid Postgres LSN after restart | `issues:dbz:1407:chunk_011` | same | Yes | Excellent: 5/5 from expected issue |
| 7 | Columns differ only by letter case | `issues:dbz:4:chunk_001` | same | Yes | Partial: correct Top-1 only |
| 8 | MongoDB buffer lock / full queue | `issues:dbz:3:chunk_009` | same | Yes | Excellent: 5/5 from expected issue |
| 9 | JDBC batch foreign-key violations | `issues:dbz:73:chunk_001` | same | Yes | Excellent: 5/5 from expected issue |
| 10 | JUnit4 to JUnit 5 migration | `issues:dbz:11:chunk_001` | same | Yes | Partial: correct Top-1 only |

## Why Atlas scores are higher

The raw score ranges differ, but retrieval quality does not.

For the same cosine similarity (c), MongoDB Atlas Vector Search exposes a normalized score:

```text
atlas_score = (1 + cosine_similarity) / 2
```

Examples from the results:

| Query | FAISS cosine | Atlas score | `(1 + FAISS) / 2` |
| --- | ---: | ---: | ---: |
| Persist offsets after restart, rank 1 | 0.7324 | 0.8662 | 0.8662 |
| Exactly-once delivery, rank 1 | 0.7798 | 0.8899 | 0.8899 |
| MongoDB buffer lock, rank 1 | 0.6650 | 0.8325 | 0.8325 |
| JUnit migration, rank 1 | 0.4945 | 0.7472 | 0.7473 |

The tiny difference in the last row is caused by displaying scores rounded to four decimals. Atlas scores must therefore be converted back with `cosine = 2 * atlas_score - 1` before comparing score thresholds with FAISS.

## Interpretation

Moving from FAISS to MongoDB Atlas changes the retrieval infrastructure, not retrieval relevance:

- FAISS stores vectors locally while chunk text and metadata remain in separate files.
- Atlas stores embeddings, chunk text, and metadata together and performs vector search server-side.
- Atlas enables operational features such as centralized persistence, metadata filters, shared access, and managed indexing.
- Because the embeddings, similarity function, corpus, and query logic are unchanged, identical rankings are the expected outcome.

The migration is successful as a backend-equivalence test: HW3 preserves the HW2 baseline exactly.

## Recommended next improvements

1. Fix query 5 by reviewing the EOS chunk content and query-to-chunk alignment.
2. Add an automated evaluation script that calculates Top-1 accuracy, Top-5 hit rate, Precision@5, overlap, and rank agreement.
3. Normalize backend scores before applying shared relevance thresholds.
4. Test metadata filtering in Atlas, which is a capability improvement over the current FAISS workflow.
5. Add a reranking stage and compare it against this unchanged 90% Top-1 baseline.
