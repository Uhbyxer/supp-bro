"""Grounded QA over the HW3 Pinecone + BM25/RRF pipeline."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/hw3"))
from pinecone_hybrid_evaluation import (  # noqa: E402
    CANDIDATE_K, DEFAULT_INDEX, DEFAULT_NAMESPACE, bm25_search, load_chunks,
    reciprocal_rank_fusion, select_chunks,
)
from pinecone_retrieval_evaluation import EMBEDDING_MODEL, required_env, search  # noqa: E402

FALLBACK = "I do not have enough information in the retrieved context to answer this question."
PROMPT = Path(__file__).with_name("prompt_template.txt")
LOGGER = logging.getLogger("hw4.rag_answer")

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "has_enough_context": {"type": "boolean"},
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["has_enough_context", "answer", "citations"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    source_file: str
    rrf_score: float
    vector_score: float | None


@dataclass(frozen=True)
class GenerationResult:
    status: str
    answer: str
    citations: list[str]
    fallback_reason: str | None = None


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


def weak_context_reason(chunks: list[RetrievedChunk], threshold: float) -> str | None:
    if not chunks:
        return "empty_retrieval"
    scores = [item.vector_score for item in chunks if item.vector_score is not None]
    if not scores or max(scores) < threshold:
        return "weak_retrieval"
    return None


def context_is_weak(chunks: list[RetrievedChunk], threshold: float) -> bool:
    return weak_context_reason(chunks, threshold) is not None


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(f"CHUNK_ID: {c.chunk_id}\nSOURCE_FILE: {c.source_file}\nTEXT:\n{c.text}" for c in chunks)
    return PROMPT.read_text(encoding="utf-8").format(retrieved_context=context, user_question=question)


def validate_payload(payload: dict[str, Any], chunks: list[RetrievedChunk]) -> GenerationResult:
    if not payload["has_enough_context"]:
        return GenerationResult("fallback", FALLBACK, [], "llm_reports_insufficient_context")
    citations = list(dict.fromkeys(payload["citations"]))
    allowed = {chunk.chunk_id for chunk in chunks}
    if not citations or any(citation not in allowed for citation in citations):
        return GenerationResult("fallback", FALLBACK, [], "invalid_or_missing_citation")
    answer = payload["answer"].strip()
    if not answer or answer == FALLBACK:
        return GenerationResult("fallback", FALLBACK, [], "invalid_llm_response")
    return GenerationResult("grounded_answer", answer, citations)


def generate(question: str, chunks: list[RetrievedChunk], client: Any, model: str, threshold: float) -> GenerationResult:
    reason = weak_context_reason(chunks, threshold)
    if reason:
        LOGGER.info("generation_status=fallback fallback_reason=%s", reason)
        return GenerationResult("fallback", FALLBACK, [], reason)
    try:
        response = client.responses.create(
            model=model,
            input=build_prompt(question, chunks),
            temperature=0,
            text={"format": {"type": "json_schema", "name": "grounded_answer", "strict": True, "schema": RESPONSE_SCHEMA}},
        )
        payload = json.loads(response.output_text)
        result = validate_payload(payload, chunks)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        LOGGER.warning("invalid_llm_response error=%s", type(exc).__name__)
        result = GenerationResult("fallback", FALLBACK, [], "invalid_llm_response")
    LOGGER.info("generation_status=%s fallback_reason=%s citations=%s", result.status, result.fallback_reason, result.citations)
    return result


def build_output(question: str, chunks: list[RetrievedChunk], result: GenerationResult, threshold: float) -> dict[str, Any]:
    return {
        "question": question,
        "min_vector_score": threshold,
        "retrieved_context_by_id": {
            chunk.chunk_id: {
                "text": chunk.text,
                "source_file": chunk.source_file,
                "rrf_score": chunk.rrf_score,
                "vector_score": chunk.vector_score,
            }
            for chunk in chunks
        },
        **asdict(result),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--source", choices=("pages", "issues"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--min-vector-score", type=float, default=float(os.getenv("RAG_MIN_VECTOR_SCORE", "0.30")))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    from openai import OpenAI
    from pinecone import Pinecone
    from sentence_transformers import SentenceTransformer
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    index = Pinecone(api_key=required_env("PINECONE_API_KEY")).Index(os.getenv("PINECONE_INDEX", DEFAULT_INDEX))
    chunks = retrieve(args.question, embedding_model, index, os.getenv("PINECONE_NAMESPACE", DEFAULT_NAMESPACE), load_chunks(), args.source, args.top_k)
    LOGGER.info("retrieved_count=%d max_vector_score=%s chunk_ids=%s", len(chunks), max((c.vector_score for c in chunks if c.vector_score is not None), default=None), [c.chunk_id for c in chunks])
    result = generate(args.question, chunks, OpenAI(api_key=required_env("OPENAI_API_KEY")), args.model, args.min_vector_score)
    print(json.dumps(build_output(args.question, chunks, result, args.min_vector_score), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"Error: {exc}")
