"""Build the HW3 Pinecone vector index without running search queries.

Run from the project root:
    python scripts/hw3/build_pinecone_vector_index.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterable

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HW1_SCRIPTS_DIR = PROJECT_ROOT / "scripts/hw1"
sys.path.append(str(HW1_SCRIPTS_DIR))

from jsonl_io import load_jsonl

HW1_PROCESSED_DIR = PROJECT_ROOT / "data/hw1/processed"
INPUT_CHUNK_PATHS = [
    HW1_PROCESSED_DIR / "chunks_large.jsonl",
    HW1_PROCESSED_DIR / "chunks_medium.json",
]
DEFAULT_INDEX_NAME = "supp-bro"
DEFAULT_NAMESPACE = "hw3-pinecone-vector"
DEFAULT_CLOUD = "aws"
DEFAULT_REGION = "us-east-1"
VECTOR_METRIC = "cosine"
UPSERT_BATCH_SIZE = 100
DELETE_BATCH_SIZE = 1000


def get_required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required. Set it to your Pinecone API key.")
    return value


def load_chunks(input_paths: list[Path]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for input_path in input_paths:
        if not input_path.exists():
            raise FileNotFoundError(
                f"Input chunks file not found: {input_path}. "
                "Please run scripts/hw1/chunk_documents.py first."
            )
        chunks.extend(load_jsonl(input_path))
    return chunks


def validate_chunks(chunks: list[dict[str, Any]]) -> None:
    if not chunks:
        raise ValueError("No chunks found. Please check the input chunk files.")

    for position, chunk in enumerate(chunks, start=1):
        chunk_label = chunk.get("chunk_id", f"record #{position}")
        for field in ("chunk_id", "text", "metadata"):
            if field not in chunk:
                raise ValueError(f"Chunk {chunk_label} is missing required field: {field}")
        if not isinstance(chunk["text"], str) or not chunk["text"].strip():
            raise ValueError(f"Chunk {chunk_label} has empty text")
        if not isinstance(chunk["metadata"], dict):
            raise ValueError(f"Chunk {chunk_label} metadata must be an object")


def normalize_embeddings(embeddings: Any) -> Any:
    import faiss

    embeddings = embeddings.astype("float32")
    faiss.normalize_L2(embeddings)
    return embeddings


def pinecone_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    """Build Pinecone-compatible metadata, omitting unsupported null values."""
    metadata = {
        key: value
        for key, value in chunk["metadata"].items()
        if value is not None and isinstance(value, (str, int, float, bool, list))
    }
    metadata.update(
        {
            "text": chunk["text"],
            "size": chunk.get("size", "unknown"),
            "embedding_model": MODEL_NAME,
        }
    )
    return metadata


def batches(items: list[Any], batch_size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def ensure_index(
    client: Any,
    serverless_spec_class: Any,
    index_name: str,
    dimension: int,
    cloud: str,
    region: str,
) -> bool:
    """Create the index once and reject incompatible existing configuration."""
    if client.has_index(index_name):
        description = client.describe_index(index_name)
        existing_dimension = int(description.dimension)
        existing_metric = str(description.metric)
        if existing_dimension != dimension or existing_metric != VECTOR_METRIC:
            raise ValueError(
                f"Pinecone index {index_name!r} already exists with dimension "
                f"{existing_dimension} and metric {existing_metric!r}; expected "
                f"dimension {dimension} and metric {VECTOR_METRIC!r}."
            )
        return False

    client.create_index(
        name=index_name,
        dimension=dimension,
        metric=VECTOR_METRIC,
        vector_type="dense",
        spec=serverless_spec_class(cloud=cloud, region=region),
        deletion_protection="disabled",
        timeout=300,
    )
    return True


def delete_stale_vectors(index: Any, namespace: str, current_ids: set[str]) -> int:
    existing_ids = [vector_id for page in index.list(namespace=namespace) for vector_id in page]
    stale_ids = [vector_id for vector_id in existing_ids if vector_id not in current_ids]
    for stale_batch in batches(stale_ids, DELETE_BATCH_SIZE):
        index.delete(ids=stale_batch, namespace=namespace)
    return len(stale_ids)


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
    cloud = os.environ.get("PINECONE_CLOUD", DEFAULT_CLOUD)
    region = os.environ.get("PINECONE_REGION", DEFAULT_REGION)

    from pinecone import Pinecone, ServerlessSpec
    from sentence_transformers import SentenceTransformer

    print("=" * 80)
    print("HW 3: BUILD PINECONE VECTOR INDEX")
    print("=" * 80)
    print(f"Embedding model: {MODEL_NAME}")
    print("Loading chunks...")

    chunks = load_chunks(INPUT_CHUNK_PATHS)
    validate_chunks(chunks)
    texts = [chunk["text"] for chunk in chunks]
    print(f"Chunks loaded: {len(chunks)}")
    print("Loading embedding model...")

    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
    normalized_embeddings = normalize_embeddings(embeddings)
    dimension = int(normalized_embeddings.shape[1])
    print(f"Embedding dimension: {dimension}")

    client = Pinecone(api_key=api_key)
    created = ensure_index(
        client=client,
        serverless_spec_class=ServerlessSpec,
        index_name=index_name,
        dimension=dimension,
        cloud=cloud,
        region=region,
    )
    index = client.Index(index_name)

    vectors = [
        {
            "id": chunk["chunk_id"],
            "values": embedding.tolist(),
            "metadata": pinecone_metadata(chunk),
        }
        for chunk, embedding in zip(chunks, normalized_embeddings)
    ]
    for vector_batch in batches(vectors, UPSERT_BATCH_SIZE):
        index.upsert(vectors=vector_batch, namespace=namespace)

    current_ids = {chunk["chunk_id"] for chunk in chunks}
    stale_deleted = delete_stale_vectors(index, namespace, current_ids)

    print()
    print("-" * 80)
    print("Index summary")
    print("-" * 80)
    print(f"Pinecone index: {index_name}")
    print(f"Created now: {created}")
    print(f"Namespace: {namespace}")
    print(f"Cloud/region: {cloud}/{region}")
    print(f"Vector dimension: {dimension}")
    print(f"Metric: {VECTOR_METRIC}")
    print(f"Vectors upserted: {len(vectors)}")
    print(f"Stale vectors deleted: {stale_deleted}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"Error: {exc}")
