"""Check semantic search with the HW3 Pinecone vector index."""

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
ALLOWED_SOURCES = frozenset({"pages", "issues"})

# Exact page chunks and document-prefix wildcards from scripts/hw2/README.md.
EXPECTED_CHUNKS: dict[str, tuple[str, ...]] = {
    QUERIES[0]: (
        "pages:configuration:storage:overview",
        "pages:configuration:storage:kafka",
        "pages:configuration:storage:file",
        "pages:configuration:storage:jdbc",
        "pages:configuration:storage:redis",
    ),
    QUERIES[1]: (
        "pages:configuration:storage:amazon_s3",
        "pages:configuration:storage:azure_blob_storage",
        "pages:configuration:storage:kafka",
    ),
    QUERIES[2]: (
        "pages:configuration:storage:kafka",
        "pages:configuration:storage:file",
        "pages:configuration:storage:memory",
    ),
    QUERIES[3]: (
        "pages:configuration:eos:overview",
        "pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector",
        "pages:configuration:eos:configuration",
    ),
    QUERIES[4]: (
        "pages:configuration:eos:configuration",
        "pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector",
    ),
    QUERIES[5]: ("issues:dbz:1407:*",),
    QUERIES[6]: ("issues:dbz:4:*",),
    QUERIES[7]: ("issues:dbz:3:*",),
    QUERIES[8]: ("issues:dbz:73:*",),
    QUERIES[9]: ("issues:dbz:11:chunk_001",),
}


def get_required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required. Set it to your Pinecone API key.")
    return value


def get_source_filter() -> str | None:
    source = os.environ.get("PINECONE_SOURCE", "").strip().lower()
    if not source:
        return None
    if source not in ALLOWED_SOURCES:
        allowed = ", ".join(sorted(ALLOWED_SOURCES))
        raise ValueError(f"PINECONE_SOURCE must be empty or one of: {allowed}; got: {source}")
    return source


def normalize_query_embedding(query_embedding: Any) -> Any:
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
    source: str | None = None,
) -> list[dict[str, Any]]:
    query_embedding = normalize_query_embedding(model.encode([query], convert_to_numpy=True))
    query_arguments: dict[str, Any] = {
        "vector": query_embedding[0].tolist(),
        "namespace": namespace,
        "top_k": top_k,
        "include_metadata": True,
    }
    if source:
        query_arguments["filter"] = {"source": {"$eq": source}}
    response = index.query(**query_arguments)
    return [
        {
            "score": float(match.score),
            "chunk_id": match.id,
            "text": match.metadata.get("text", ""),
            "metadata": match.metadata,
        }
        for match in response.matches
    ]


def is_relevant(chunk_id: str, expected: tuple[str, ...]) -> bool:
    return any(
        chunk_id.startswith(pattern[:-1]) if pattern.endswith("*") else chunk_id == pattern
        for pattern in expected
    )


def calculate_metrics(results: list[dict[str, Any]], expected: tuple[str, ...]) -> dict[str, float]:
    relevant = [is_relevant(str(result["chunk_id"]), expected) for result in results]
    first_rank = next((rank for rank, match in enumerate(relevant, start=1) if match), None)
    return {
        "top_1": float(bool(relevant and relevant[0])),
        "hit_at_5": float(any(relevant)),
        "rr": 1.0 / first_rank if first_rank else 0.0,
        "precision_at_5": sum(relevant) / TOP_K,
    }


def print_results(query: str, results: list[dict[str, Any]], top_k: int) -> None:
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


def format_chunks(chunks: tuple[str, ...]) -> str:
    return "<br>".join(f"`{escape_markdown_table_cell(chunk)}`" for chunk in chunks)


def format_results_for_table(results: list[dict[str, Any]]) -> str:
    if not results:
        return "_No results_"
    return "<br>".join(
        f"{rank}. `{escape_markdown_table_cell(str(result['chunk_id']))}` (score: {result['score']:.4f})"
        for rank, result in enumerate(results, start=1)
    )


def write_markdown_summary(
    query_results: list[tuple[str, list[dict[str, Any]]]],
    output_path: Path,
    source: str | None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_description = f"`source={source}`" if source else "disabled (all sources)"
    lines = [
        "# HW3 Pinecone Semantic Search Results",
        "",
        f"Source filter: **{source_description}**.",
        "",
        "| Query | Expected chunks | Retrieved chunks and scores | Top-1 | Hit@5 | RR | Precision@5 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for query, results in query_results:
        expected = EXPECTED_CHUNKS[query]
        metrics = calculate_metrics(results, expected)
        lines.append(
            f"| {escape_markdown_table_cell(query)} | {format_chunks(expected)} | "
            f"{format_results_for_table(results)} | {metrics['top_1']:.0%} | "
            f"{metrics['hit_at_5']:.0%} | {metrics['rr']:.3f} | "
            f"{metrics['precision_at_5']:.1%} |"
        )
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
    source = get_source_filter()
    summary_path = Path(os.environ.get("PINECONE_SEARCH_SUMMARY_PATH", DEFAULT_SUMMARY_PATH))

    from pinecone import Pinecone
    from sentence_transformers import SentenceTransformer

    print("=" * 80)
    print("HW 3: CHECK PINECONE SEMANTIC SEARCH")
    print("=" * 80)
    print(f"Embedding model: {MODEL_NAME}")
    print(f"Pinecone index: {index_name}")
    print(f"Namespace: {namespace}")
    print(f"Source filter: {source or 'disabled'}")
    print(f"Top-k: {top_k}")
    print()

    index = Pinecone(api_key=api_key).Index(index_name)
    model = SentenceTransformer(MODEL_NAME)
    query_results = []
    for query in QUERIES:
        results = search(query, model, index, namespace, top_k, source)
        query_results.append((query, results))
        print_results(query, results, top_k)
        print()

    write_markdown_summary(query_results, summary_path, source)
    print(f"Markdown summary: {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
