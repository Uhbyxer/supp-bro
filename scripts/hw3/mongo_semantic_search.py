"""
HW 3: Check semantic search with MongoDB Atlas Vector Search.

Run from the project root:
    python scripts/hw3/mongo_semantic_search.py

This script queries documents created by:
    scripts/hw3/build_mongo_vector_index.py
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

DEFAULT_DATABASE_NAME = "supp-bro"
DEFAULT_COLLECTION_NAME = "chunks"
DEFAULT_VECTOR_INDEX_NAME = "vector_index"
PIPELINE_NAME = "hw3_mongo_vector"
EMBEDDING_FIELD = "embedding"
TOP_K = 5
NUM_CANDIDATES = 100
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data/hw2/output/mongo_semantic_search_summary.md"


def get_required_env(name: str) -> str:
    """
    Read a required environment variable.
    """
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required. Set it to your MongoDB Atlas connection string.")
    return value


def normalize_query_embedding(query_embedding: Any) -> Any:
    """
    Normalize vectors so MongoDB dotProduct behaves like cosine-like search.
    """
    import faiss

    query_embedding = query_embedding.astype("float32")
    faiss.normalize_L2(query_embedding)
    return query_embedding


def search(
    query: str,
    model: Any,
    collection: Any,
    vector_index_name: str,
    top_k: int = TOP_K,
    num_candidates: int = NUM_CANDIDATES,
) -> list[dict[str, Any]]:
    """
    Query MongoDB Atlas Vector Search and return top chunk documents.
    """
    query_embedding = model.encode([query], convert_to_numpy=True)
    query_embedding = normalize_query_embedding(query_embedding)
    query_vector = query_embedding[0].tolist()

    pipeline = build_vector_search_pipeline(
        query_vector=query_vector,
        vector_index_name=vector_index_name,
        top_k=top_k,
        num_candidates=num_candidates,
        include_filter=True,
    )
    try:
        return list(collection.aggregate(pipeline))
    except Exception as exc:
        if not is_vector_filter_error(exc):
            raise
        print(
            "Warning: MongoDB vector index does not support the pipeline pre-filter; "
            "retrying without filter.",
            file=sys.stderr,
        )
        fallback_pipeline = build_vector_search_pipeline(
            query_vector=query_vector,
            vector_index_name=vector_index_name,
            top_k=top_k,
            num_candidates=num_candidates,
            include_filter=False,
        )
        return list(collection.aggregate(fallback_pipeline))


def build_vector_search_pipeline(
    query_vector: list[float],
    vector_index_name: str,
    top_k: int,
    num_candidates: int,
    include_filter: bool,
) -> list[dict[str, Any]]:
    """
    Build a MongoDB Atlas Vector Search aggregation pipeline.
    """
    vector_search_stage: dict[str, Any] = {
        "index": vector_index_name,
        "path": EMBEDDING_FIELD,
        "queryVector": query_vector,
        "numCandidates": num_candidates,
        "limit": top_k,
    }
    if include_filter:
        vector_search_stage["filter"] = {"pipeline": PIPELINE_NAME}

    return [
        {
            "$vectorSearch": vector_search_stage
        },
        {
            "$project": {
                "_id": 0,
                "score": {"$meta": "vectorSearchScore"},
                "chunk_id": 1,
                "text": 1,
                "metadata": 1,
            }
        },
    ]


def is_vector_filter_error(exc: Exception) -> bool:
    """
    Detect Atlas errors caused by filtering on a field missing from the vector index.
    """
    message = str(exc).lower()
    return "filter" in message and ("vector" in message or "index" in message)


def print_results(query: str, results: list[dict[str, Any]], top_k: int) -> None:
    """
    Print one query result block in the same shape as HW2 semantic_search.py.
    """
    print(f"Query: {query}")
    print(f"Top-k: {top_k}")
    print()
    print("-" * 80)
    print("Retrieved chunks")
    print("-" * 80)
    for rank, result in enumerate(results, start=1):
        metadata = result.get("metadata", {})
        print(f"Rank: {rank}")
        print(f"Score: {result['score']:.4f}")
        print(f"Chunk ID: {result['chunk_id']}")
        print(f"Source file: {metadata.get('source_file')}")
        print(f"Title: {metadata.get('title')}")
        print("Text:")
        print(result["text"])
        print("-" * 80)


def escape_markdown_table_cell(value: str) -> str:
    """
    Escape characters that break GitHub Markdown tables.
    """
    return value.replace("|", "\\|").replace("\n", " ")


def format_results_for_table(results: list[dict[str, Any]]) -> str:
    """
    Format retrieved chunk ids and scores for a compact Markdown table cell.
    """
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
    """
    Write a GitHub Actions-friendly Markdown table with one row per query.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# HW3 MongoDB Semantic Search Results",
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

    mongodb_uri = get_required_env("MONGODB_URI")
    database_name = os.environ.get("MONGODB_DATABASE", DEFAULT_DATABASE_NAME)
    collection_name = os.environ.get("MONGODB_COLLECTION", DEFAULT_COLLECTION_NAME)
    vector_index_name = os.environ.get("MONGODB_VECTOR_INDEX", DEFAULT_VECTOR_INDEX_NAME)
    top_k = int(os.environ.get("MONGODB_SEARCH_TOP_K", TOP_K))
    num_candidates = int(os.environ.get("MONGODB_SEARCH_NUM_CANDIDATES", NUM_CANDIDATES))
    summary_path = Path(os.environ.get("MONGODB_SEARCH_SUMMARY_PATH", DEFAULT_SUMMARY_PATH))

    from pymongo import MongoClient
    from sentence_transformers import SentenceTransformer

    print("=" * 80)
    print("HW 3: CHECK MONGODB ATLAS SEMANTIC SEARCH")
    print("=" * 80)
    print(f"Embedding model: {MODEL_NAME}")
    print(f"MongoDB database: {database_name}")
    print(f"MongoDB collection: {collection_name}")
    print(f"Vector index: {vector_index_name}")
    print(f"Top-k: {top_k}")
    print(f"Num candidates: {num_candidates}")
    print()

    client = MongoClient(mongodb_uri)
    collection = client[database_name][collection_name]
    model = SentenceTransformer(MODEL_NAME)

    query_results: list[tuple[str, list[dict[str, Any]]]] = []
    for query in QUERIES:
        results = search(
            query=query,
            model=model,
            collection=collection,
            vector_index_name=vector_index_name,
            top_k=top_k,
            num_candidates=num_candidates,
        )
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
