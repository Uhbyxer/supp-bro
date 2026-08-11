"""Grounded QA over the HW3 Pinecone + BM25/RRF pipeline."""
from __future__ import annotations

import argparse, json, os, re, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/hw3"))
from pinecone_hybrid_evaluation import (CANDIDATE_K, DEFAULT_INDEX, DEFAULT_NAMESPACE, bm25_search, load_chunks, reciprocal_rank_fusion, select_chunks)  # noqa: E402
from pinecone_retrieval_evaluation import EMBEDDING_MODEL, required_env, search  # noqa: E402

FALLBACK = "I do not have enough information in the retrieved context to answer this question."
CITATION = re.compile(r"\[([^\[\]]+)\]")
PROMPT = Path(__file__).with_name("prompt_template.txt")

@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    source_file: str
    rrf_score: float
    vector_score: float | None

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

def context_is_weak(chunks: list[RetrievedChunk], threshold: float) -> bool:
    scores = [item.vector_score for item in chunks if item.vector_score is not None]
    return not chunks or not scores or max(scores) < threshold

def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(f"CHUNK_ID: {c.chunk_id}\nSOURCE_FILE: {c.source_file}\nTEXT:\n{c.text}" for c in chunks)
    return PROMPT.read_text(encoding="utf-8").format(retrieved_context=context, user_question=question)

def valid_citations(answer: str, chunks: list[RetrievedChunk]) -> bool:
    if answer.strip() == FALLBACK:
        return True
    found, allowed = CITATION.findall(answer), {c.chunk_id for c in chunks}
    return bool(found) and all(item in allowed for item in found)

def generate(question: str, chunks: list[RetrievedChunk], client: Any, model: str, threshold: float) -> str:
    if context_is_weak(chunks, threshold):
        return FALLBACK
    answer = client.responses.create(model=model, input=build_prompt(question, chunks), temperature=0).output_text.strip()
    return answer if valid_citations(answer, chunks) else FALLBACK

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--source", choices=("pages", "issues"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--min-vector-score", type=float, default=float(os.getenv("RAG_MIN_VECTOR_SCORE", "0.30")))
    args = parser.parse_args()
    from openai import OpenAI
    from pinecone import Pinecone
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)
    index = Pinecone(api_key=required_env("PINECONE_API_KEY")).Index(os.getenv("PINECONE_INDEX", DEFAULT_INDEX))
    chunks = retrieve(args.question, model, index, os.getenv("PINECONE_NAMESPACE", DEFAULT_NAMESPACE), load_chunks(), args.source, args.top_k)
    answer = generate(args.question, chunks, OpenAI(api_key=required_env("OPENAI_API_KEY")), args.model, args.min_vector_score)
    print(json.dumps({"question": args.question, "retrieved_chunks": [{"chunk_id": c.chunk_id, "source_file": c.source_file, "rrf_score": c.rrf_score, "vector_score": c.vector_score} for c in chunks], "answer": answer, "sources": sorted(set(CITATION.findall(answer)))}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    try: main()
    except (FileNotFoundError, ValueError) as exc: sys.exit(f"Error: {exc}")
