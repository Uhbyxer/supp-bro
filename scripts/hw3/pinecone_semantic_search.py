"""Check semantic search with the HW3 Pinecone vector index.

Run from the project root:
    python scripts/hw3/pinecone_semantic_search.py

This script queries vectors created by:
    scripts/hw3/build_pinecone_vector_index.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HW2_SCRIPTS_DIR = PROJECT_ROOT / "scripts/hw2"
sys.path.append(str(HW2_SCRIPTS_DIR))

from search_queries import QUERIES

DEFAULT_INDEX_NAME = "supp-bro"
DEFAULT_NAMESPACE = "supp-bro-pinecone-vector"
TOP_K = 5
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data/hw2/output/pinecone_semantic_search_summary.md"


def get_required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required. Set it to your Pinecone API key.")
    return value


def normalize_query_embedding(query_embedding: Any) -> Any:
    """Normalize the query exactly like the indexed chunk embeddings."""
    import faiss

    query_embedding = query_embedding.astype("float32")
    faiss.normalize_L2(query_embedding)
    return query_embedding


def search(
    query: str,
    model: Any,
    index: Any,
    namespace: str,
    top_k: int = TOP_K,
) -> list[dict[str, Any]]:
    query_embedding = model.encode([query], convert_to_numpy=True)
    query_embedding = normalize_query_embedding(query_embedding)
    response = index.query(
        vector=query_embedding[0].tolist(),
        namespace=namespace,
        top_k=top_k,
        include_metadata=True,
    )

    return [
        {
            "score": float(match.score),
            "chunk_id": match.id,
            "text": match.metadata.get("text", ""),
            "metadata": match.metadata,
        }
        for match in response.matches
    ]


def print_results(query: str, results: list[dict[str, Any]], top_k: int) -> None:
    """Print results in the same shape as the HW2 and MongoDB scripts."""
    print(f"Query: {query}")
    print(f"Top-k: {top_k}")
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


def escape_markdown_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def format_results_for_table(results: list[dict[str, Any]]) -> str:
    if not results:
        return "_No results_"

    formatted_results = []
    for rank, result in enumerate(results, start=1):
        chunk_id = escape_markdown_table_cell(str(result["chunk_id"]))
        formatted_results.append(f"{rank}. `{chunk_id}` (score: {result['score']:.4f})")
    return "<br>".join(formatted_results)


def write_markdown_summary(
    query_results: list[tuple[str, list[dict[str, Any]]]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# HW3 Pinecone Semantic Search Results",
        "",
        "| Query | Retrieved chunks and scores |",
        "| --- | --- |",
    ]
    for query, results in query_results:
        escaped_query = escape_markdown_table_cell(query)
        lines.append(f"| {escaped_query} | {format_results_for_table(results)} |")
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        load_dotenv = None

    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")

    api_key = get_required_env("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX", DEFAULT_INDEX_NAME)
    namespace = os.environ.get("PINECONE_NAMESPACE", DEFAULT_NAMESPACE)
    top_k = int(os.environ.get("PINECONE_SEARCH_TOP_K", TOP_K))
    summary_path = Path(os.environ.get("PINECONE_SEARCH_SUMMARY_PATH", DEFAULT_SUMMARY_PATH))

    from pinecone import Pinecone
    from sentence_transformers import SentenceTransformer

    print("=" * 80)
    print("HW 3: CHECK PINECONE SEMANTIC SEARCH")
    print("=" * 80)
    print(f"Embedding model: {MODEL_NAME}")
    print(f"Pinecone index: {index_name}")
    print(f"Namespace: {namespace}")
    print(f"Top-k: {top_k}")
    print()

    client = Pinecone(api_key=api_key)
    index = client.Index(index_name)
    model = SentenceTransformer(MODEL_NAME)

    query_results: list[tuple[str, list[dict[str, Any]]]] = []
    for query in QUERIES:
        results = search(query, model, index, namespace, top_k)
        query_results.append((query, results))
        print_results(query, results, top_k)
        print()

    write_markdown_summary(query_results, summary_path)
    print(f"Markdown summary: {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
