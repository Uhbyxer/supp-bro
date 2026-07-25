"""
HW 2: Build a FAISS index for semantic search.

Run from the project root:
    python scripts/hw2/build_index.py

This script reads:
    data/hw1/processed/chunks_large.jsonl
    data/hw1/processed/chunks_medium.json

And produces:
    data/hw2/processed/chunks_for_retrieval.jsonl
    data/hw2/processed/embeddings.npy
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

from jsonl_io import load_jsonl, save_jsonl

HW1_PROCESSED_DIR = PROJECT_ROOT / "data/hw1/processed"
HW2_PROCESSED_DIR = PROJECT_ROOT / "data/hw2/processed"
HW2_INDEX_DIR = PROJECT_ROOT / "data/hw2/index"
INPUT_CHUNK_PATHS = [
    HW1_PROCESSED_DIR / "chunks_large.jsonl",
    HW1_PROCESSED_DIR / "chunks_medium.json",
]
OUTPUT_CHUNKS_PATH = HW2_PROCESSED_DIR / "chunks_for_retrieval.jsonl"
OUTPUT_EMBEDDINGS_PATH = HW2_PROCESSED_DIR / "embeddings.npy"
OUTPUT_INDEX_PATH = HW2_INDEX_DIR / "faiss.index"


class FaissIndexBackend:
    """
    Build and store a FAISS vector index.
    """

    name = "faiss"

    def build(self, embeddings: np.ndarray) -> faiss.Index:
        """
        Build an inner-product FAISS index from normalized embeddings.
        """
        embedding_dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(embedding_dimension)
        index.add(embeddings)
        return index

    def save(self, index: faiss.Index, output_path: Path) -> None:
        """
        Save the FAISS index to disk.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(output_path))


def path_for_display(path: Path) -> str:
    """
    Return project-relative path when possible.
    """
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


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


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """
    Normalize vectors so IndexFlatIP behaves like cosine-like search.
    """
    embeddings = embeddings.astype("float32")
    faiss.normalize_L2(embeddings)
    return embeddings


def main() -> None:
    backend = FaissIndexBackend()

    print("=" * 80)
    print("HW 2: BUILD SEMANTIC SEARCH INDEX")
    print("=" * 80)
    print(f"Index backend: {backend.name}")
    print(f"Embedding model: {MODEL_NAME}")
    print("Input chunks:")
    for input_path in INPUT_CHUNK_PATHS:
        print(f"- {path_for_display(input_path)}")
    print()
    print("Loading chunks...")

    chunks = load_chunks(INPUT_CHUNK_PATHS)
    validate_chunks(chunks)
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
    print("Building FAISS index with IndexFlatIP...")
    print()

    index = backend.build(normalized_embeddings)

    HW2_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUTPUT_EMBEDDINGS_PATH, normalized_embeddings)
    backend.save(index, OUTPUT_INDEX_PATH)
    save_jsonl(chunks, OUTPUT_CHUNKS_PATH)

    print("-" * 80)
    print("Saved outputs")
    print("-" * 80)
    print(f"Chunks for retrieval: {path_for_display(OUTPUT_CHUNKS_PATH)}")
    print(f"Embeddings matrix: {path_for_display(OUTPUT_EMBEDDINGS_PATH)}")
    print(f"FAISS index: {path_for_display(OUTPUT_INDEX_PATH)}")
    print()

    print("-" * 80)
    print("Index summary")
    print("-" * 80)
    print(f"Index type: {type(index).__name__}")
    print(f"Vectors in index: {index.ntotal}")
    print(f"Vector dimension: {embedding_dimension}")
    print()
    print("FAISS stores vectors for similarity search.")
    print("Chunk text and metadata are stored separately in JSONL.")


if __name__ == "__main__":
    main()
