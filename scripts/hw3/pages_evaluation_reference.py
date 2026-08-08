"""Shared Pages and Issues ground truth for Pinecone evaluation pipelines."""

from __future__ import annotations

from dataclasses import dataclass
EXPECTED_RESULTS_URL = "https://github.com/Uhbyxer/supp-bro/tree/main/scripts/hw2"


@dataclass(frozen=True)
class EvaluationCase:
    query: str
    source: str
    relevant_patterns: tuple[str, ...]

    def is_relevant(self, chunk_id: str) -> bool:
        return any(
            chunk_id.startswith(pattern[:-1]) if pattern.endswith("*") else chunk_id == pattern
            for pattern in self.relevant_patterns
        )


def case(query: str, source: str, *relevant_patterns: str) -> EvaluationCase:
    return EvaluationCase(
        query=query,
        source=source,
        relevant_patterns=tuple(relevant_patterns),
    )


CASES = [
    case(
        "How should Debezium persist connector offsets and schema history after a restart?",
        "pages",
        "pages:configuration:storage:overview",
        "pages:configuration:storage:kafka",
        "pages:configuration:storage:file",
        "pages:configuration:storage:jdbc",
        "pages:configuration:storage:redis",
    ),
    case(
        "Which storage options are suitable for cloud deployments of Debezium state?",
        "pages",
        "pages:configuration:storage:amazon_s3",
        "pages:configuration:storage:azure_blob_storage",
        "pages:configuration:storage:kafka",
    ),
    case(
        "What is the difference between Kafka, file, and memory offset storage in Debezium?",
        "pages",
        "pages:configuration:storage:kafka",
        "pages:configuration:storage:file",
        "pages:configuration:storage:memory",
    ),
    case(
        "How does Debezium achieve exactly-once delivery with Kafka Connect?",
        "pages",
        "pages:configuration:eos:overview",
        "pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector",
        "pages:configuration:eos:configuration",
    ),
    case(
        "What must be configured before enabling exactly-once support for source connectors?",
        "pages",
        "pages:configuration:eos:configuration",
        "pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector",
    ),
    case(
        "Postgres connector resumes from an old or invalid LSN after restart and replication slot validation looks wrong",
        "issues",
        "issues:dbz:1407:*",
    ),
    case(
        "Debezium connector crashes when two table columns have the same name except for letter case",
        "issues",
        "issues:dbz:4:*",
    ),
    case(
        "MongoDB connector backpressure error says unable to acquire buffer lock and queue is full",
        "issues",
        "issues:dbz:3:*",
    ),
    case(
        "JDBC sink writes records in the correct topic order but batch processing causes foreign key violations",
        "issues",
        "issues:dbz:73:*",
    ),
    case(
        "Which issue is only about migrating tests from JUnit4 to a newer JUnit version?",
        "issues",
        "issues:dbz:11:chunk_001",
    ),
]


def cases_for_source(source: str | None) -> list[EvaluationCase]:
    """Match evaluation cases to the same source scope used by retrieval."""
    if source is None:
        return CASES
    return [evaluation_case for evaluation_case in CASES if evaluation_case.source == source]
