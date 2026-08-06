"""Compare Pinecone vector retrieval with metadata-filtered BM25/RRF hybrid search."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from evaluation_comparison import compare_with_previous, previous_comparison_markdown

from pinecone_retrieval_evaluation import (
    BASELINE_K,
    CASES,
    EMBEDDING_MODEL,
    FINAL_K,
    PROJECT_ROOT,
    aggregate,
    calculate_metrics,
    compact,
    escape_markdown,
    first_relevant_rank,
    required_env,
    search,
)

DEFAULT_INDEX = "supp-bro"
DEFAULT_NAMESPACE = "hw3-pinecone-vector"
CANDIDATE_K = 15
RRF_K = 60
DEFAULT_JSON_PATH = PROJECT_ROOT / "data/hw3/output/pinecone_hybrid_evaluation.json"
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data/hw3/output/pinecone_hybrid_evaluation.md"
DEFAULT_PREVIOUS_JSON_PATH = PROJECT_ROOT / "data/hw3/previous/pinecone_hybrid_evaluation.json"
CHUNK_PATHS = [
    PROJECT_ROOT / "data/hw1/processed/chunks_large.jsonl",
    PROJECT_ROOT / "data/hw1/processed/chunks_medium.json",
]
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[._:/-][a-z0-9]+)*", re.IGNORECASE)


def tokenize(value: str) -> list[str]:
    """Tokenize natural language while keeping technical IDs such as DBZ-8922."""
    return TOKEN_PATTERN.findall(value.lower())


def load_chunks(paths: list[Path] = CHUNK_PATHS) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Chunk file not found: {path}")
        with path.open(encoding="utf-8") as source:
            chunks.extend(json.loads(line) for line in source if line.strip())
    return chunks


def filter_chunks(chunks: list[dict[str, Any]], metadata_filter: dict[str, Any]) -> list[dict[str, Any]]:
    source = metadata_filter.get("source", {}).get("$eq")
    if not source:
        raise ValueError(f"Unsupported metadata filter: {metadata_filter}")
    return [chunk for chunk in chunks if chunk.get("metadata", {}).get("source") == source]


def bm25_search(query: str, chunks: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    from rank_bm25 import BM25Okapi

    if not chunks:
        return []
    documents = [
        tokenize(f"{chunk.get('metadata', {}).get('title', '')} {chunk['text']}")
        for chunk in chunks
    ]
    index = BM25Okapi(documents)
    scores = index.get_scores(tokenize(query))
    ranked = sorted(zip(chunks, scores), key=lambda item: float(item[1]), reverse=True)[:top_k]
    return [
        {
            "chunk_id": chunk["chunk_id"],
            "bm25_score": float(score),
            "text": chunk["text"],
        }
        for chunk, score in ranked
    ]


def reciprocal_rank_fusion(*rankings: list[dict[str, Any]], rrf_k: int = RRF_K) -> list[dict[str, Any]]:
    fused: dict[str, dict[str, Any]] = {}
    for ranking in rankings:
        for rank, result in enumerate(ranking, start=1):
            chunk_id = result["chunk_id"]
            entry = fused.setdefault(chunk_id, {"chunk_id": chunk_id, "rrf_score": 0.0, "ranks": {}})
            entry["rrf_score"] += 1.0 / (rrf_k + rank)
            if "vector_score" in result:
                entry["vector_score"] = result["vector_score"]
                entry["ranks"]["vector"] = rank
            if "bm25_score" in result:
                entry["bm25_score"] = result["bm25_score"]
                entry["ranks"]["bm25"] = rank
    return sorted(fused.values(), key=lambda item: (-item["rrf_score"], item["chunk_id"]))


def evaluate(model: Any, index: Any, namespace: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in CASES:
        baseline = search(case.query, model, index, namespace, BASELINE_K)
        dense = search(case.query, model, index, namespace, CANDIDATE_K, case.metadata_filter)
        filtered_chunks = filter_chunks(chunks, case.metadata_filter)
        sparse = bm25_search(case.query, filtered_chunks, CANDIDATE_K)
        hybrid = reciprocal_rank_fusion(dense, sparse)[:FINAL_K]
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
                "hybrid": {
                    "metrics": calculate_metrics(hybrid, case.relevant_ids),
                    "first_relevant_rank": first_relevant_rank(hybrid, case.relevant_ids),
                    "results": hybrid,
                },
            }
        )
    baseline_metrics = aggregate(rows, "baseline")
    hybrid_metrics = aggregate(rows, "hybrid")
    delta = {name: hybrid_metrics[name] - baseline_metrics[name] for name in baseline_metrics}
    improved_count = sum(value > 1e-12 for value in delta.values())
    regressed_count = sum(value < -1e-12 for value in delta.values())
    if improved_count and not regressed_count:
        verdict = "Hybrid retrieval is better on at least one aggregate metric with no measured regression."
    elif improved_count:
        verdict = "Mixed result: some aggregate metrics improved and others regressed."
    else:
        verdict = "No aggregate hybrid retrieval improvement was demonstrated."
    return {
        "configuration": {
            "embedding_model": EMBEDDING_MODEL,
            "baseline_k": BASELINE_K,
            "dense_candidate_k": CANDIDATE_K,
            "bm25_candidate_k": CANDIDATE_K,
            "rrf_k": RRF_K,
            "final_k": FINAL_K,
            "fuzzy_search": False,
        },
        "aggregate": {"baseline": baseline_metrics, "hybrid": hybrid_metrics, "delta": delta},
        "verdict": verdict,
        "queries": rows,
    }


def write_outputs(report: dict[str, Any], json_path: Path, summary_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    baseline, hybrid = report["aggregate"]["baseline"], report["aggregate"]["hybrid"]
    lines = [
        "# Pinecone retrieval: baseline vs BM25/RRF hybrid", "",
        f"Baseline: unfiltered Pinecone vector Top-{BASELINE_K}.  ",
        f"Hybrid: metadata filter, Pinecone Top-{CANDIDATE_K} + BM25 Top-{CANDIDATE_K}, RRF (k={RRF_K}), final Top-{FINAL_K}.", "",
        "| Pipeline | Top-1 | Hit@5 | MRR | Precision@5 |", "| --- | ---: | ---: | ---: | ---: |",
        f"| Baseline | {baseline['top_1']:.1%} | {baseline['hit_at_5']:.1%} | {baseline['mrr']:.3f} | {baseline['precision_at_5']:.1%} |",
        f"| Hybrid | {hybrid['top_1']:.1%} | {hybrid['hit_at_5']:.1%} | {hybrid['mrr']:.3f} | {hybrid['precision_at_5']:.1%} |", "",
        f"**Verdict:** {report['verdict']}", "",
    ]
    lines.extend(previous_comparison_markdown(report["previous_run_comparison"], "metadata filter + BM25 + RRF"))
    lines.extend(["| Query | Filter | Baseline first relevant rank | Hybrid first relevant rank |", "| --- | --- | ---: | ---: |"])
    for row in report["queries"]:
        baseline_rank = row["baseline"]["first_relevant_rank"] or "—"
        hybrid_rank = row["hybrid"]["first_relevant_rank"] or "—"
        lines.append(f"| {escape_markdown(row['query'])} | `{json.dumps(row['metadata_filter'])}` | {baseline_rank} | {hybrid_rank} |")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        load_dotenv = None
    if load_dotenv:
        load_dotenv(PROJECT_ROOT / ".env")

    from pinecone import Pinecone
    from sentence_transformers import SentenceTransformer

    index_name = os.environ.get("PINECONE_INDEX", DEFAULT_INDEX)
    namespace = os.environ.get("PINECONE_NAMESPACE", DEFAULT_NAMESPACE)
    json_path = Path(os.environ.get("PINECONE_HYBRID_JSON_PATH", DEFAULT_JSON_PATH))
    summary_path = Path(os.environ.get("PINECONE_HYBRID_SUMMARY_PATH", DEFAULT_SUMMARY_PATH))
    previous_json_path = Path(os.environ.get("PINECONE_HYBRID_PREVIOUS_JSON_PATH", DEFAULT_PREVIOUS_JSON_PATH))
    model = SentenceTransformer(EMBEDDING_MODEL)
    index = Pinecone(api_key=required_env("PINECONE_API_KEY")).Index(index_name)
    report = evaluate(model, index, namespace, load_chunks())
    report["previous_run_comparison"] = compare_with_previous(
        report["aggregate"]["hybrid"], previous_json_path, "hybrid"
    )
    write_outputs(report, json_path, summary_path)
    print(json.dumps(report["aggregate"], indent=2))
    print(report["verdict"])
    print(f"JSON report: {json_path}")
    print(f"Markdown summary: {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"Error: {exc}")
