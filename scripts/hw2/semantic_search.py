"""
HW 2: Check semantic search with FAISS.

Run from the project root:
    python scripts/hw2/semantic_search.py

This script reads:
    data/hw2/processed/chunks_for_retrieval.jsonl
    data/hw2/index/faiss.index
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HW1_SCRIPTS_DIR = PROJECT_ROOT / "scripts/hw1"
sys.path.append(str(HW1_SCRIPTS_DIR))

from jsonl_io import load_jsonl

CHUNKS_PATH = PROJECT_ROOT / "data/hw2/processed/chunks_for_retrieval.jsonl"
INDEX_PATH = PROJECT_ROOT / "data/hw2/index/faiss.index"
TOP_K = 5
QUERIES = [
    "How should Debezium persist connector offsets and schema history after a restart?",
    "Which storage options are suitable for cloud deployments of Debezium state?",
    "What is the difference between Kafka, file, and memory offset storage in Debezium?",
    "How does Debezium achieve exactly-once delivery with Kafka Connect?",
    "What must be configured before enabling exactly-once support for source connectors?",
    "Postgres connector resumes from an old or invalid LSN after restart and replication slot validation looks wrong",
    "Debezium connector crashes when two table columns have the same name except for letter case",
    "MongoDB connector backpressure error says unable to acquire buffer lock and queue is full",
    "JDBC sink writes records in the correct topic order but batch processing causes foreign key violations",
    "Which issue is only about migrating tests from JUnit4 to a newer JUnit version?",
]


def path_for_display(path: Path) -> str:
    """
    Return project-relative path when possible.
    """
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def normalize_query_embedding(query_embedding: np.ndarray) -> np.ndarray:
    """
    Normalize query embedding for cosine-like search with IndexFlatIP.
    """
    query_embedding = query_embedding.astype("float32")
    faiss.normalize_L2(query_embedding)
    return query_embedding


def search(
    query: str,
    model: SentenceTransformer,
    index: faiss.Index,
    chunks: list[dict[str, Any]],
    top_k: int = TOP_K,
) -> list[dict[str, Any]]:
    """
    Query FAISS and map vector indices back to chunk records.
    """
    query_embedding = model.encode([query], convert_to_numpy=True)
    query_embedding = normalize_query_embedding(query_embedding)
    scores, indices = index.search(query_embedding, top_k)

    results: list[dict[str, Any]] = []
    for score, chunk_index in zip(scores[0], indices[0]):
        if chunk_index == -1:
            continue
        chunk = chunks[int(chunk_index)]
        results.append(
            {
                "score": float(score),
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "metadata": chunk.get("metadata", {}),
            }
        )
    return results


def print_results(query: str, results: list[dict[str, Any]]) -> None:
    """
    Print one query result block.
    """
    print(f"Query: {query}")
    print(f"Top-k: {TOP_K}")
    print()
    print("-" * 80)
    print("Retrieved chunks")
    print("-" * 80)
    for rank, result in enumerate(results, start=1):
        metadata = result["metadata"]
        print(f"Rank: {rank}")
        print(f"Score: {result['score']:.4f}")
        print(f"Chunk ID: {result['chunk_id']}")
        print(f"Source file: {metadata.get('source_file')}")
        print(f"Title: {metadata.get('title')}")
        print("Text:")
        print(result["text"])
        print("-" * 80)


def main() -> None:
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(
            f"Chunks file not found: {CHUNKS_PATH}. "
            "Please run scripts/hw2/build_index.py first."
        )
    if not INDEX_PATH.exists():
        raise FileNotFoundError(
            f"FAISS index not found: {INDEX_PATH}. "
            "Please run scripts/hw2/build_index.py first."
        )

    print("=" * 80)
    print("HW 2: CHECK SEMANTIC SEARCH")
    print("=" * 80)
    print(f"Embedding model: {MODEL_NAME}")
    print(f"FAISS index: {path_for_display(INDEX_PATH)}")
    print(f"Chunks file: {path_for_display(CHUNKS_PATH)}")
    print(f"Top-k: {TOP_K}")
    print()

    chunks = load_jsonl(CHUNKS_PATH)
    index = faiss.read_index(str(INDEX_PATH))
    model = SentenceTransformer(MODEL_NAME)

    for query in QUERIES:
        results = search(
            query=query,
            model=model,
            index=index,
            chunks=chunks,
            top_k=TOP_K,
        )
        print_results(query, results)
        print()


if __name__ == "__main__":
    main()
