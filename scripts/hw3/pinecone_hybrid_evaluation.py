"""Evaluate Pinecone and BM25 retrieval fused with reciprocal rank fusion."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from pinecone_retrieval_evaluation import (
    EMBEDDING_MODEL,
    FINAL_K,
    PROJECT_ROOT,
    aggregate,
    calculate_metrics,
    compact,
    escape_markdown,
    first_relevant_rank,
    format_chunk_ids,
    required_env,
    search,
    source_env,
)
from pages_evaluation_reference import (
    CASES,
    EXPECTED_RESULTS_URL,
)

DEFAULT_INDEX = "supp-bro"
DEFAULT_NAMESPACE = "hw3-pinecone-vector"
CANDIDATE_K = 15
RRF_K = 60
DEFAULT_JSON_PATH = PROJECT_ROOT / "data/hw3/output/pinecone_hybrid_evaluation.json"
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data/hw3/output/pinecone_hybrid_evaluation.md"
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


def select_chunks(chunks: list[dict[str, Any]], source: str | None) -> list[dict[str, Any]]:
    if source is None:
        return chunks
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


def evaluate(
    model: Any,
    index: Any,
    namespace: str,
    chunks: list[dict[str, Any]],
    source: str | None,
) -> dict[str, Any]:
    rows = []
    metadata_filter = {"source": {"$eq": source}} if source else None
    bm25_chunks = select_chunks(chunks, source)
    for case in CASES:
        dense = search(case.query, model, index, namespace, CANDIDATE_K, metadata_filter)
        sparse = bm25_search(case.query, bm25_chunks, CANDIDATE_K)
        hybrid = reciprocal_rank_fusion(dense, sparse)[:FINAL_K]
        rows.append(
            {
                "query": case.query,
                "metadata_filter": metadata_filter,
                "relevant_chunk_ids": sorted(case.relevant_ids),
                "metrics": calculate_metrics(hybrid, case.relevant_ids),
                "first_relevant_rank": first_relevant_rank(hybrid, case.relevant_ids),
                "results": compact(hybrid),
            }
        )
    return {
        "configuration": {
            "embedding_model": EMBEDDING_MODEL,
            "dense_candidate_k": CANDIDATE_K,
            "bm25_candidate_k": CANDIDATE_K,
            "rrf_k": RRF_K,
            "final_k": FINAL_K,
            "fuzzy_search": False,
            "source": source,
        },
        "references": {"expected_results": EXPECTED_RESULTS_URL},
        "aggregate": aggregate(rows),
        "queries": rows,
    }


def write_outputs(report: dict[str, Any], json_path: Path, summary_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    metrics = report["aggregate"]
    source = report["configuration"]["source"]
    filter_description = f"`source={source}`" if source else "disabled (all sources)"
    lines = [
        "# Pinecone retrieval with BM25/RRF hybrid search", "",
        f"Source filter: **{filter_description}**.  ",
        f"Ground truth: expected chunk IDs from [HW2 Pages]({EXPECTED_RESULTS_URL}).  ",
        f"Pipeline: Pinecone Top-{CANDIDATE_K} + BM25 Top-{CANDIDATE_K}, RRF (k={RRF_K}), final Top-{FINAL_K}.", "",
        "| Top-1 | Hit@5 | MRR | Precision@5 |", "| ---: | ---: | ---: | ---: |",
        f"| {metrics['top_1']:.1%} | {metrics['hit_at_5']:.1%} | {metrics['mrr']:.3f} | {metrics['precision_at_5']:.1%} |", "",
    ]
    lines.extend([
        "## Per-query metrics", "",
        "| Query | Top-1 | Hit@5 | RR | Precision@5 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for row in report["queries"]:
        row_metrics = row["metrics"]
        lines.append(
            f"| {escape_markdown(row['query'])} | {row_metrics['top_1']:.1%} | "
            f"{row_metrics['hit_at_5']:.1%} | {row_metrics['mrr']:.3f} | "
            f"{row_metrics['precision_at_5']:.1%} |"
        )
    lines.extend([
        "", "## Retrieved chunks", "",
        "| Query | Expected chunks | Retrieved chunks | First relevant rank |",
        "| --- | --- | --- | ---: |",
    ])
    for row in report["queries"]:
        first_rank = row["first_relevant_rank"] or "—"
        expected = "<br>".join(f"`{chunk_id}`" for chunk_id in row["relevant_chunk_ids"])
        results = format_chunk_ids(row["results"])
        lines.append(
            f"| {escape_markdown(row['query'])} | {expected} | {results} | {first_rank} |"
        )
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
    source = source_env("PINECONE_SOURCE")
    json_path = Path(os.environ.get("PINECONE_HYBRID_JSON_PATH", DEFAULT_JSON_PATH))
    summary_path = Path(os.environ.get("PINECONE_HYBRID_SUMMARY_PATH", DEFAULT_SUMMARY_PATH))
    model = SentenceTransformer(EMBEDDING_MODEL)
    index = Pinecone(api_key=required_env("PINECONE_API_KEY")).Index(index_name)
    report = evaluate(model, index, namespace, load_chunks(), source)
    write_outputs(report, json_path, summary_path)
    print(json.dumps(report["aggregate"], indent=2))
    print(f"JSON report: {json_path}")
    print(f"Markdown summary: {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"Error: {exc}")
