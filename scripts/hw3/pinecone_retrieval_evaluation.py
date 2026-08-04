"""Compare baseline Pinecone retrieval with filtering and cross-encoder reranking."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX = "supp-bro"
DEFAULT_NAMESPACE = "hw3-pinecone-vector"
BASELINE_K, CANDIDATE_K, FINAL_K = 5, 15, 5
DEFAULT_JSON_PATH = PROJECT_ROOT / "data/hw3/output/pinecone_retrieval_evaluation.json"
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data/hw3/output/pinecone_retrieval_evaluation.md"


@dataclass(frozen=True)
class EvaluationCase:
    query: str
    metadata_filter: dict[str, Any]
    relevant_ids: frozenset[str]


def issue_chunks(issue_id: int, count: int) -> frozenset[str]:
    return frozenset(f"issues:dbz:{issue_id}:chunk_{number:03d}" for number in range(1, count + 1))


CASES = [
    EvaluationCase(
        "How should Debezium persist connector offsets and schema history after a restart?",
        {"source": {"$eq": "pages"}},
        frozenset({"pages:configuration:storage:overview", "pages:configuration:storage:kafka", "pages:configuration:storage:file"}),
    ),
    EvaluationCase(
        "Which storage options are suitable for cloud deployments of Debezium state?",
        {"source": {"$eq": "pages"}},
        frozenset({"pages:configuration:storage:amazon_s3", "pages:configuration:storage:azure_blob_storage"}),
    ),
    EvaluationCase(
        "What is the difference between Kafka, file, and memory offset storage in Debezium?",
        {"source": {"$eq": "pages"}},
        frozenset({"pages:configuration:storage:kafka", "pages:configuration:storage:file", "pages:configuration:storage:memory"}),
    ),
    EvaluationCase(
        "How does Debezium achieve exactly-once delivery with Kafka Connect?",
        {"source": {"$eq": "pages"}},
        frozenset({"pages:configuration:eos:overview", "pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector", "pages:configuration:eos:debezium_connectors_supporting_exactly_once_delivery"}),
    ),
    EvaluationCase(
        "What must be configured before enabling exactly-once support for source connectors?",
        {"source": {"$eq": "pages"}},
        frozenset({"pages:configuration:eos:configuration"}),
    ),
    EvaluationCase(
        "Postgres connector resumes from an old or invalid LSN after restart and replication slot validation looks wrong",
        {"source": {"$eq": "issues"}},
        issue_chunks(1407, 12),
    ),
    EvaluationCase(
        "Debezium connector crashes when two table columns have the same name except for letter case",
        {"source": {"$eq": "issues"}},
        issue_chunks(4, 6),
    ),
    EvaluationCase(
        "MongoDB connector backpressure error says unable to acquire buffer lock and queue is full",
        {"source": {"$eq": "issues"}},
        issue_chunks(3, 12),
    ),
    EvaluationCase(
        "JDBC sink writes records in the correct topic order but batch processing causes foreign key violations",
        {"source": {"$eq": "issues"}},
        issue_chunks(73, 10),
    ),
    EvaluationCase(
        "Which issue is only about migrating tests from JUnit4 to a newer JUnit version?",
        {"source": {"$eq": "issues"}},
        frozenset({"issues:dbz:11:chunk_001"}),
    ),
]


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def search(query: str, model: Any, index: Any, namespace: str, top_k: int, metadata_filter: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    import faiss

    embedding = model.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(embedding)
    arguments: dict[str, Any] = {
        "vector": embedding[0].tolist(),
        "namespace": namespace,
        "top_k": top_k,
        "include_metadata": True,
    }
    if metadata_filter is not None:
        arguments["filter"] = metadata_filter
    response = index.query(**arguments)
    return [
        {
            "chunk_id": match.id,
            "vector_score": float(match.score),
            "text": match.metadata.get("text", ""),
        }
        for match in response.matches
    ]


def rerank(query: str, candidates: list[dict[str, Any]], reranker: Any) -> list[dict[str, Any]]:
    if not candidates:
        return []
    scores = reranker.predict([(query, candidate["text"]) for candidate in candidates])
    scored = [{**candidate, "rerank_score": float(score)} for candidate, score in zip(candidates, scores)]
    return sorted(scored, key=lambda item: item["rerank_score"], reverse=True)


def calculate_metrics(results: list[dict[str, Any]], relevant_ids: frozenset[str]) -> dict[str, float]:
    ids = [result["chunk_id"] for result in results]
    ranks = [rank for rank, chunk_id in enumerate(ids, 1) if chunk_id in relevant_ids]
    return {
        "top_1": float(bool(ids and ids[0] in relevant_ids)),
        "hit_at_5": float(bool(ranks)),
        "mrr": 1.0 / ranks[0] if ranks else 0.0,
        "precision_at_5": sum(chunk_id in relevant_ids for chunk_id in ids) / FINAL_K,
    }


def first_relevant_rank(results: list[dict[str, Any]], relevant_ids: frozenset[str]) -> int | None:
    return next((rank for rank, result in enumerate(results, 1) if result["chunk_id"] in relevant_ids), None)


def aggregate(rows: list[dict[str, Any]], pipeline: str) -> dict[str, float]:
    names = ("top_1", "hit_at_5", "mrr", "precision_at_5")
    return {name: sum(row[pipeline]["metrics"][name] for row in rows) / len(rows) for name in names}


def compact(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in result.items() if key != "text"} for result in results]


def evaluate(model: Any, reranker: Any, index: Any, namespace: str) -> dict[str, Any]:
    rows = []
    for case in CASES:
        baseline = search(case.query, model, index, namespace, BASELINE_K)
        candidates = search(case.query, model, index, namespace, CANDIDATE_K, case.metadata_filter)
        improved = rerank(case.query, candidates, reranker)[:FINAL_K]
        rows.append(
            {
                "query": case.query,
                "metadata_filter": case.metadata_filter,
                "relevant_chunk_ids": sorted(case.relevant_ids),
                "baseline": {
                    "metrics": calculate_metrics(baseline, case.relevant_ids),
                    "first_relevant_rank": first_relevant_rank(baseline, case.relevant_ids),
                    "results": compact(baseline),
                },
                "improved": {
                    "metrics": calculate_metrics(improved, case.relevant_ids),
                    "first_relevant_rank": first_relevant_rank(improved, case.relevant_ids),
                    "results": compact(improved),
                },
            }
        )
    baseline_metrics = aggregate(rows, "baseline")
    improved_metrics = aggregate(rows, "improved")
    delta = {name: improved_metrics[name] - baseline_metrics[name] for name in baseline_metrics}
    improved_count = sum(value > 1e-12 for value in delta.values())
    regressed_count = sum(value < -1e-12 for value in delta.values())
    if improved_count and not regressed_count:
        verdict = "Improved retrieval is better on at least one aggregate metric with no measured regression."
    elif improved_count:
        verdict = "Mixed result: some aggregate metrics improved and others regressed."
    else:
        verdict = "No aggregate retrieval improvement was demonstrated."
    return {
        "configuration": {"embedding_model": EMBEDDING_MODEL, "reranker_model": RERANKER_MODEL, "baseline_k": BASELINE_K, "candidate_k": CANDIDATE_K, "final_k": FINAL_K},
        "aggregate": {"baseline": baseline_metrics, "improved": improved_metrics, "delta": delta},
        "verdict": verdict,
        "queries": rows,
    }


def escape_markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def write_outputs(report: dict[str, Any], json_path: Path, summary_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    baseline, improved = report["aggregate"]["baseline"], report["aggregate"]["improved"]
    lines = [
        "# Pinecone retrieval: baseline vs improved", "",
        f"Baseline: unfiltered vector Top-{BASELINE_K}.  ",
        f"Improved: metadata-filtered vector Top-{CANDIDATE_K}, cross-encoder reranking, final Top-{FINAL_K}.", "",
        "| Pipeline | Top-1 | Hit@5 | MRR | Precision@5 |", "| --- | ---: | ---: | ---: | ---: |",
        f"| Baseline | {baseline['top_1']:.1%} | {baseline['hit_at_5']:.1%} | {baseline['mrr']:.3f} | {baseline['precision_at_5']:.1%} |",
        f"| Improved | {improved['top_1']:.1%} | {improved['hit_at_5']:.1%} | {improved['mrr']:.3f} | {improved['precision_at_5']:.1%} |", "",
        f"**Verdict:** {report['verdict']}", "",
        "| Query | Filter | Baseline first relevant rank | Improved first relevant rank |", "| --- | --- | ---: | ---: |",
    ]
    for row in report["queries"]:
        baseline_rank = row["baseline"]["first_relevant_rank"] or "—"
        improved_rank = row["improved"]["first_relevant_rank"] or "—"
        lines.append(f"| {escape_markdown(row['query'])} | `{json.dumps(row['metadata_filter'])}` | {baseline_rank} | {improved_rank} |")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        load_dotenv = None
    if load_dotenv:
        load_dotenv(PROJECT_ROOT / ".env")

    from pinecone import Pinecone
    from sentence_transformers import CrossEncoder, SentenceTransformer

    index_name = os.environ.get("PINECONE_INDEX", DEFAULT_INDEX)
    namespace = os.environ.get("PINECONE_NAMESPACE", DEFAULT_NAMESPACE)
    json_path = Path(os.environ.get("PINECONE_EVALUATION_JSON_PATH", DEFAULT_JSON_PATH))
    summary_path = Path(os.environ.get("PINECONE_EVALUATION_SUMMARY_PATH", DEFAULT_SUMMARY_PATH))
    model = SentenceTransformer(EMBEDDING_MODEL)
    reranker = CrossEncoder(RERANKER_MODEL)
    index = Pinecone(api_key=required_env("PINECONE_API_KEY")).Index(index_name)
    report = evaluate(model, reranker, index, namespace)
    write_outputs(report, json_path, summary_path)
    print(json.dumps(report["aggregate"], indent=2))
    print(report["verdict"])
    print(f"JSON report: {json_path}")
    print(f"Markdown summary: {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
