"""Grounded QA over the HW3 Pinecone + BM25/RRF pipeline."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is installed through requirements.txt
    load_dotenv = None
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/hw3"))
from pinecone_hybrid_evaluation import (  # noqa: E402
    CANDIDATE_K, DEFAULT_INDEX, DEFAULT_NAMESPACE, bm25_search, load_chunks,
    reciprocal_rank_fusion, select_chunks,
)
from pinecone_retrieval_evaluation import EMBEDDING_MODEL, required_env, search  # noqa: E402
from supp_bro.retrieval.rag import (  # noqa: E402
    DEFAULT_MIN_VECTOR_SCORE,
    EXPERIMENTS,
    FALLBACK,
    NO_RETRIEVAL_FILTER_SCORE,
    POST_VALIDATOR_MODES,
    PROMPT_FLAVORS,
    RESPONSE_SCHEMA,
    GenerationResult,
    RetrievedChunk,
    accept_payload_without_post_validation,
    best_vector_score,
    build_context_map,
    build_output,
    build_prompt,
    context_is_weak,
    generate,
    markdown_table,
    run_experiments,
    summarize_experiment,
    validate_payload,
    weak_context_reason,
)

PROMPT = Path(__file__).with_name("prompt_template.txt")
WEAK_PROMPT = Path(__file__).with_name("prompt_template_weak.txt")
LOGGER = logging.getLogger("hw4.rag_answer")


def retrieve(question: str, model: Any, index: Any, namespace: str, chunks: list[dict[str, Any]], source: str | None, top_k: int) -> list[RetrievedChunk]:
    scoped = select_chunks(chunks, source)
    dense = search(question, model, index, namespace, CANDIDATE_K, {"source": {"$eq": source}} if source else None)
    sparse = bm25_search(question, scoped, CANDIDATE_K)
    raw_by_id = {item["chunk_id"]: item for item in scoped}
    result = []
    for item in reciprocal_rank_fusion(dense, sparse)[:top_k]:
        raw = raw_by_id.get(item["chunk_id"])
        if raw:
            result.append(RetrievedChunk(item["chunk_id"], raw["text"], raw.get("metadata", {}).get("source_file", "unknown"), float(item["rrf_score"]), item.get("vector_score")))
    return result


def prompt_path(prompt_flavor: str) -> Path:
    if prompt_flavor == "strong":
        return PROMPT
    if prompt_flavor == "weak":
        return WEAK_PROMPT
    raise ValueError(f"Unsupported prompt flavor: {prompt_flavor}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--source", choices=("pages", "issues"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--min-vector-score", type=float, default=float(os.getenv("RAG_MIN_VECTOR_SCORE", str(DEFAULT_MIN_VECTOR_SCORE))))
    parser.add_argument("--prompt-flavor", choices=PROMPT_FLAVORS, default=os.getenv("RAG_PROMPT_FLAVOR", "strong"))
    parser.add_argument("--post-validator", choices=POST_VALIDATOR_MODES, default=os.getenv("RAG_POST_VALIDATOR", "on"))
    parser.add_argument("--experiment", action="store_true", help="Run weak/strong prompt experiments with and without the retrieval filter.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    from openai import OpenAI
    from pinecone import Pinecone
    from sentence_transformers import SentenceTransformer
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    index = Pinecone(api_key=required_env("PINECONE_API_KEY")).Index(os.getenv("PINECONE_INDEX", DEFAULT_INDEX))
    chunks = retrieve(args.question, embedding_model, index, os.getenv("PINECONE_NAMESPACE", DEFAULT_NAMESPACE), load_chunks(), args.source, args.top_k)
    LOGGER.info("retrieved_count=%d max_vector_score=%s chunk_ids=%s", len(chunks), best_vector_score(chunks), [c.chunk_id for c in chunks])
    client = OpenAI(api_key=required_env("OPENAI_API_KEY"))
    if args.experiment:
        output = run_experiments(args.question, chunks, client, args.model)
    else:
        result = generate(args.question, chunks, client, args.model, args.min_vector_score, args.prompt_flavor, args.post_validator)
        output = build_output(args.question, chunks, result, args.min_vector_score, args.prompt_flavor, args.post_validator)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"Error: {exc}")
