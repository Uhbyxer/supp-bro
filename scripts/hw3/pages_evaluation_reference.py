"""Pages ground truth used to compare the old and new Pinecone pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BASELINE_RUN_ID = 30763956563
BASELINE_RUN_URL = "https://github.com/Uhbyxer/supp-bro/actions/runs/30763956563"
EXPECTED_RESULTS_URL = "https://github.com/Uhbyxer/supp-bro/tree/main/scripts/hw2#pages"


@dataclass(frozen=True)
class EvaluationCase:
    query: str
    metadata_filter: dict[str, Any]
    relevant_ids: frozenset[str]


def page_case(
    query: str,
    relevant_ids: set[str],
) -> EvaluationCase:
    return EvaluationCase(
        query=query,
        metadata_filter={"source": {"$eq": "pages"}},
        relevant_ids=frozenset(relevant_ids),
    )


CASES = [
    page_case(
        "How should Debezium persist connector offsets and schema history after a restart?",
        {
            "pages:configuration:storage:overview",
            "pages:configuration:storage:kafka",
            "pages:configuration:storage:file",
            "pages:configuration:storage:jdbc",
            "pages:configuration:storage:redis",
        },
    ),
    page_case(
        "Which storage options are suitable for cloud deployments of Debezium state?",
        {
            "pages:configuration:storage:amazon_s3",
            "pages:configuration:storage:azure_blob_storage",
            "pages:configuration:storage:kafka",
        },
    ),
    page_case(
        "What is the difference between Kafka, file, and memory offset storage in Debezium?",
        {
            "pages:configuration:storage:kafka",
            "pages:configuration:storage:file",
            "pages:configuration:storage:memory",
        },
    ),
    page_case(
        "How does Debezium achieve exactly-once delivery with Kafka Connect?",
        {
            "pages:configuration:eos:overview",
            "pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector",
            "pages:configuration:eos:configuration",
        },
    ),
    page_case(
        "What must be configured before enabling exactly-once support for source connectors?",
        {
            "pages:configuration:eos:configuration",
            "pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector",
        },
    ),
]
