"""
HW 3: Build a MongoDB Atlas Vector Search index.

Run from the project root:
    python scripts/hw3/build_mongo_vector_index.py

This script reads:
    data/hw1/processed/chunks_large.jsonl
    data/hw1/processed/chunks_medium.json

And stores chunk documents with embeddings in MongoDB Atlas.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

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
DEFAULT_DATABASE_NAME = "supp-bro"
DEFAULT_COLLECTION_NAME = "chunks"
DEFAULT_VECTOR_INDEX_NAME = "vector_index"
PIPELINE_NAME = "hw3_mongo_vector"
EMBEDDING_FIELD = "embedding"
VECTOR_SIMILARITY = "dotProduct"


class MongoVectorIndexBackend:
    """
    Store chunks and create a MongoDB Atlas Vector Search index.
    """

    name = "mongodb_atlas_vector_search"

    def __init__(
        self,
        collection: Any,
        index_name: str,
        embedding_dimension: int,
    ) -> None:
        self.collection = collection
        self.index_name = index_name
        self.embedding_dimension = embedding_dimension

    def upsert_chunks(
        self,
        chunks: list[dict[str, Any]],
        embeddings: Any,
    ) -> Any:
        """
        Upsert one MongoDB document per chunk.
        """
        from pymongo import ReplaceOne

        operations = []
        for chunk, embedding in zip(chunks, embeddings):
            document = {
                "chunk_id": chunk["chunk_id"],
                "pipeline": PIPELINE_NAME,
                "text": chunk["text"],
                "metadata": chunk["metadata"],
                EMBEDDING_FIELD: embedding.tolist(),
                "embedding_model": MODEL_NAME,
                "embedding_dimension": self.embedding_dimension,
            }
            operations.append(
                ReplaceOne(
                    {"chunk_id": chunk["chunk_id"]},
                    document,
                    upsert=True,
                )
            )

        if not operations:
            return None

        return self.collection.bulk_write(operations, ordered=False)

    def delete_stale_chunks(self, current_chunk_ids: set[str]) -> int:
        """
        Delete documents from this pipeline that are no longer in the input chunks.
        """
        result = self.collection.delete_many(
            {
                "pipeline": PIPELINE_NAME,
                "chunk_id": {"$nin": list(current_chunk_ids)},
            }
        )
        return result.deleted_count

    def create_vector_index(self) -> str:
        """
        Create the Atlas Vector Search index for chunk embeddings.
        """
        from pymongo.operations import SearchIndexModel

        existing_indexes = self.collection.list_search_indexes()
        for index in existing_indexes:
            if index.get("name") == self.index_name:
                return self.index_name

        search_index_model = SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "path": EMBEDDING_FIELD,
                        "numDimensions": self.embedding_dimension,
                        "similarity": VECTOR_SIMILARITY,
                    },
                    {
                        "type": "filter",
                        "path": "pipeline",
                    },
                ]
            },
            name=self.index_name,
            type="vectorSearch",
        )
        return self.collection.create_search_index(model=search_index_model)


def path_for_display(path: Path) -> str:
    """
    Return project-relative path when possible.
    """
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def get_required_env(name: str) -> str:
    """
    Read a required environment variable.
    """
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required. Set it to your MongoDB Atlas connection string.")
    return value


def load_chunks(input_paths: list[Path]) -> list[dict[str, Any]]:
    """
    Load chunks from all configured HW1 chunk files.
    """
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
    """
    Validate the minimum retrieval fields required by the index builder.
    """
    if not chunks:
        raise ValueError("No chunks found. Please check the input chunk files.")

    for index, chunk in enumerate(chunks, start=1):
        chunk_label = chunk.get("chunk_id", f"record #{index}")
        for field in ("chunk_id", "text", "metadata"):
            if field not in chunk:
                raise ValueError(f"Chunk {chunk_label} is missing required field: {field}")
        if not isinstance(chunk["text"], str) or not chunk["text"].strip():
            raise ValueError(f"Chunk {chunk_label} has empty text")
        if not isinstance(chunk["metadata"], dict):
            raise ValueError(f"Chunk {chunk_label} metadata must be an object")


def normalize_embeddings(embeddings: Any) -> Any:
    """
    Normalize vectors so dotProduct behaves like cosine-like search.
    """
    import faiss

    embeddings = embeddings.astype("float32")
    faiss.normalize_L2(embeddings)
    return embeddings


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

    from pymongo import MongoClient
    from sentence_transformers import SentenceTransformer

    print("=" * 80)
    print("HW 3: BUILD MONGODB ATLAS VECTOR SEARCH INDEX")
    print("=" * 80)
    print(f"Index backend: {MongoVectorIndexBackend.name}")
    print(f"Embedding model: {MODEL_NAME}")
    print("Input chunks:")
    for input_path in INPUT_CHUNK_PATHS:
        print(f"- {path_for_display(input_path)}")
    print()
    print("Loading chunks...")

    chunks = load_chunks(INPUT_CHUNK_PATHS)
    validate_chunks(chunks)
    current_chunk_ids = {chunk["chunk_id"] for chunk in chunks}
    texts = [chunk["text"] for chunk in chunks]
    print(f"Chunks loaded: {len(chunks)}")
    print("Loading embedding model...")
    print()

    # First run may download model weights from Hugging Face.
    model = SentenceTransformer(MODEL_NAME)

    print("Creating embeddings...")
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
    print(f"Raw embeddings shape: {embeddings.shape}")

    normalized_embeddings = normalize_embeddings(embeddings)
    embedding_dimension = normalized_embeddings.shape[1]
    print(f"Embedding dimension: {embedding_dimension}")
    print("Connecting to MongoDB Atlas...")
    print()

    client = MongoClient(mongodb_uri)
    collection = client[database_name][collection_name]
    backend = MongoVectorIndexBackend(
        collection=collection,
        index_name=vector_index_name,
        embedding_dimension=embedding_dimension,
    )

    print("Uploading chunk documents...")
    bulk_result = backend.upsert_chunks(chunks, normalized_embeddings)
    print("Deleting stale chunk documents...")
    stale_deleted_count = backend.delete_stale_chunks(current_chunk_ids)
    print("Creating Atlas Vector Search index...")
    created_index_name = backend.create_vector_index()
    print()

    print("-" * 80)
    print("Saved outputs")
    print("-" * 80)
    print(f"MongoDB database: {database_name}")
    print(f"MongoDB collection: {collection_name}")
    if bulk_result is None:
        print("Chunk documents upserted: 0")
        print("Chunk documents modified: 0")
    else:
        print(f"Chunk documents upserted: {bulk_result.upserted_count}")
        print(f"Chunk documents modified: {bulk_result.modified_count}")
    print(f"Stale chunk documents deleted: {stale_deleted_count}")
    print(f"Vector index: {created_index_name}")
    print()

    print("-" * 80)
    print("Index summary")
    print("-" * 80)
    print(f"Index type: vectorSearch")
    print(f"Vector field: {EMBEDDING_FIELD}")
    print(f"Vector dimension: {embedding_dimension}")
    print(f"Similarity: {VECTOR_SIMILARITY}")
    print()
    print("MongoDB Atlas stores chunk text, metadata, and vectors in one collection.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
