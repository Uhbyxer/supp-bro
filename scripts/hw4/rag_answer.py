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
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is installed through requirements.txt
    load_dotenv = None
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "scripts/hw3"))
from pinecone_hybrid_evaluation import (  # noqa: E402
    CANDIDATE_K, DEFAULT_INDEX, DEFAULT_NAMESPACE, bm25_search, load_chunks,
    reciprocal_rank_fusion, select_chunks,
)
from pinecone_retrieval_evaluation import EMBEDDING_MODEL, required_env, search  # noqa: E402

FALLBACK = "I do not have enough information in the retrieved context to answer this question."
PROMPT = Path(__file__).with_name("prompt_template.txt")
WEAK_PROMPT = Path(__file__).with_name("prompt_template_weak.txt")
LOGGER = logging.getLogger("hw4.rag_answer")
DEFAULT_MIN_VECTOR_SCORE = 0.30
NO_RETRIEVAL_FILTER_SCORE = 0.0
PROMPT_FLAVORS = ("strong", "weak")
POST_VALIDATOR_MODES = ("on", "off")
EXPERIMENTS = (
    ("weak_no_filter_no_validator", "weak", NO_RETRIEVAL_FILTER_SCORE, "off"),
    ("weak_no_filter_with_validator", "weak", NO_RETRIEVAL_FILTER_SCORE, "on"),
    ("strong_no_filter_no_validator", "strong", NO_RETRIEVAL_FILTER_SCORE, "off"),
    ("strong_no_filter_with_validator", "strong", NO_RETRIEVAL_FILTER_SCORE, "on"),
    ("weak_filter_no_validator", "weak", DEFAULT_MIN_VECTOR_SCORE, "off"),
    ("weak_filter_with_validator", "weak", DEFAULT_MIN_VECTOR_SCORE, "on"),
    ("strong_filter_no_validator", "strong", DEFAULT_MIN_VECTOR_SCORE, "off"),
    ("strong_filter_with_validator", "strong", DEFAULT_MIN_VECTOR_SCORE, "on"),
)

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
    if threshold > 0 and (not scores or max(scores) < threshold):
        return "weak_retrieval"
    return None


def context_is_weak(chunks: list[RetrievedChunk], threshold: float) -> bool:
    return weak_context_reason(chunks, threshold) is not None


def prompt_path(prompt_flavor: str) -> Path:
    if prompt_flavor == "strong":
        return PROMPT
    if prompt_flavor == "weak":
        return WEAK_PROMPT
    raise ValueError(f"Unsupported prompt flavor: {prompt_flavor}")


def build_prompt(question: str, chunks: list[RetrievedChunk], prompt_flavor: str = "strong") -> str:
    context = "\n\n".join(f"CHUNK_ID: {c.chunk_id}\nSOURCE_FILE: {c.source_file}\nTEXT:\n{c.text}" for c in chunks)
    return prompt_path(prompt_flavor).read_text(encoding="utf-8").format(retrieved_context=context, user_question=question)


def validate_payload(payload: dict[str, Any], chunks: list[RetrievedChunk]) -> GenerationResult:
    if not payload["has_enough_context"]:
        return GenerationResult("model_fallback", FALLBACK, [], "llm_reports_insufficient_context")
    citations = list(dict.fromkeys(payload["citations"]))
    allowed = {chunk.chunk_id for chunk in chunks}
    if not citations or any(citation not in allowed for citation in citations):
        return GenerationResult("model_fallback", FALLBACK, [], "invalid_or_missing_citation")
    answer = payload["answer"].strip()
    if not answer or answer == FALLBACK:
        return GenerationResult("model_fallback", FALLBACK, [], "invalid_llm_response")
    return GenerationResult("grounded_answer", answer, citations)


def accept_payload_without_post_validation(payload: dict[str, Any]) -> GenerationResult:
    answer = payload.get("answer", "").strip()
    if not answer or answer == FALLBACK:
        return GenerationResult("model_fallback", FALLBACK, [], "invalid_llm_response")
    citations = list(dict.fromkeys(payload.get("citations", [])))
    return GenerationResult("unvalidated_answer", answer, citations)


def generate(question: str, chunks: list[RetrievedChunk], client: Any, model: str, threshold: float, prompt_flavor: str, post_validator: str = "on") -> GenerationResult:
    reason = weak_context_reason(chunks, threshold)
    if reason:
        LOGGER.info("generation_status=retrieval_filter_fallback fallback_reason=%s prompt_flavor=%s min_vector_score=%s post_validator=%s", reason, prompt_flavor, threshold, post_validator)
        return GenerationResult("retrieval_filter_fallback", FALLBACK, [], reason)
    try:
        response = client.responses.create(
            model=model,
            input=build_prompt(question, chunks, prompt_flavor),
            temperature=0,
            text={"format": {"type": "json_schema", "name": "grounded_answer", "strict": True, "schema": RESPONSE_SCHEMA}},
        )
        payload = json.loads(response.output_text)
        if post_validator == "on":
            result = validate_payload(payload, chunks)
        elif post_validator == "off":
            result = accept_payload_without_post_validation(payload)
        else:
            raise ValueError(f"Unsupported post validator mode: {post_validator}")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        LOGGER.warning("invalid_llm_response error=%s", type(exc).__name__)
        result = GenerationResult("model_fallback", FALLBACK, [], "invalid_llm_response")
    LOGGER.info("generation_status=%s fallback_reason=%s prompt_flavor=%s post_validator=%s citations=%s", result.status, result.fallback_reason, prompt_flavor, post_validator, result.citations)
    return result


def best_vector_score(chunks: list[RetrievedChunk]) -> float | None:
    return max((c.vector_score for c in chunks if c.vector_score is not None), default=None)


def build_context_map(chunks: list[RetrievedChunk]) -> dict[str, dict[str, Any]]:
    return {
        chunk.chunk_id: {
            "text": chunk.text,
            "source_file": chunk.source_file,
            "rrf_score": chunk.rrf_score,
            "vector_score": chunk.vector_score,
        }
        for chunk in chunks
    }


def build_output(question: str, chunks: list[RetrievedChunk], result: GenerationResult, threshold: float, prompt_flavor: str, post_validator: str) -> dict[str, Any]:
    return {
        "question": question,
        "prompt_flavor": prompt_flavor,
        "post_validator": post_validator,
        "min_vector_score": threshold,
        "best_vector_score": best_vector_score(chunks),
        "retrieved_context_by_id": build_context_map(chunks),
        **asdict(result),
    }


def markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Experiment | Prompt | Post validator | Min vector score | Best vector score | Status | Fallback reason | Citations | Conclusion |",
        "|---|---|---|---:|---:|---|---|---|---|",
    ]
    for row in rows:
        citations = ", ".join(row.get("citations") or []) or "-"
        best = row.get("best_vector_score")
        best_text = "-" if best is None else f"{best:.3f}"
        threshold = row["min_vector_score"]
        threshold_text = f"{threshold:.2f}"
        conclusion = summarize_experiment(row)
        lines.append(
            f"| {row['experiment']} | {row['prompt_flavor']} | {row['post_validator']} | {threshold_text} | {best_text} | "
            f"{row['status']} | {row.get('fallback_reason') or '-'} | {citations} | {conclusion} |"
        )
    return "\n".join(lines)


def summarize_experiment(row: dict[str, Any]) -> str:
    if row["status"] == "grounded_answer":
        return "Answered with validated citations."
    if row["status"] == "unvalidated_answer":
        return "Answered without post-validation."
    if row["status"] == "retrieval_filter_fallback":
        return "Blocked before LLM by retrieval score filter."
    return "LLM or citation validator returned fallback."


def run_experiments(question: str, chunks: list[RetrievedChunk], client: Any, model: str) -> dict[str, Any]:
    outputs = []
    for experiment, prompt_flavor, threshold, post_validator in EXPERIMENTS:
        result = generate(question, chunks, client, model, threshold, prompt_flavor, post_validator)
        item = build_output(question, chunks, result, threshold, prompt_flavor, post_validator)
        item["experiment"] = experiment
        outputs.append(item)
    return {
        "question": question,
        "retrieved_context_by_id": build_context_map(chunks),
        "experiments": outputs,
        "summary_markdown": markdown_table(outputs),
    }


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
