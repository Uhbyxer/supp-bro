"""Provider-free RAG answer core extracted from the HW4 proof of concept."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from supp_bro.domain.contracts import RagObservation

FALLBACK = "I do not have enough information in the retrieved context to answer this question."
LOGGER = logging.getLogger("supp_bro.retrieval.rag")
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
PROMPT_TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "scripts" / "hw4"

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

STRONG_PROMPT_TEMPLATE = """You are a grounded technical support assistant for Debezium.
Answer using ONLY the context below. Do not use prior knowledge.

Return a structured response with:
- has_enough_context: true only when the context directly supports the answer;
- answer: a concise grounded answer, or the exact fallback sentence below;
- citations: the exact CHUNK_ID values supporting the answer.

If the context is empty, weak, conflicting, or insufficient, set has_enough_context to false,
use "I do not have enough information in the retrieved context to answer this question."
as the answer, and return an empty citations list.
Never invent a citation or include a source not shown in the context.

Context:
{retrieved_context}

Question:
{user_question}
"""

WEAK_PROMPT_TEMPLATE = """You are a technical support assistant for Debezium.
Answer the user's question directly and helpfully.
Add citations from the retrieved CHUNK_ID values when possible.

Context:
{retrieved_context}

Question:
{user_question}
"""


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


def weak_context_reason(chunks: list[RetrievedChunk], threshold: float) -> str | None:
    if not chunks:
        return "empty_retrieval"
    scores = [item.vector_score for item in chunks if item.vector_score is not None]
    if threshold > 0 and (not scores or max(scores) < threshold):
        return "weak_retrieval"
    return None


def context_is_weak(chunks: list[RetrievedChunk], threshold: float) -> bool:
    return weak_context_reason(chunks, threshold) is not None


def prompt_template(prompt_flavor: str) -> str:
    if prompt_flavor == "strong":
        path = PROMPT_TEMPLATE_DIR / "prompt_template.txt"
        return path.read_text(encoding="utf-8") if path.exists() else STRONG_PROMPT_TEMPLATE
    if prompt_flavor == "weak":
        path = PROMPT_TEMPLATE_DIR / "prompt_template_weak.txt"
        return path.read_text(encoding="utf-8") if path.exists() else WEAK_PROMPT_TEMPLATE
    raise ValueError(f"Unsupported prompt flavor: {prompt_flavor}")


def build_prompt(question: str, chunks: list[RetrievedChunk], prompt_flavor: str = "strong") -> str:
    context = "\n\n".join(f"CHUNK_ID: {c.chunk_id}\nSOURCE_FILE: {c.source_file}\nTEXT:\n{c.text}" for c in chunks)
    return prompt_template(prompt_flavor).format(retrieved_context=context, user_question=question)


def _validate_payload_shape(payload: dict[str, Any]) -> None:
    if not isinstance(payload.get("has_enough_context"), bool):
        raise TypeError("has_enough_context must be a boolean")
    if not isinstance(payload.get("answer"), str):
        raise TypeError("answer must be a string")
    citations = payload.get("citations")
    if not isinstance(citations, list) or not all(isinstance(citation, str) for citation in citations):
        raise TypeError("citations must be a list of strings")


def validate_payload(payload: dict[str, Any], chunks: list[RetrievedChunk]) -> GenerationResult:
    _validate_payload_shape(payload)
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
    _validate_payload_shape(payload)
    answer = payload.get("answer", "").strip()
    if not answer or answer == FALLBACK:
        return GenerationResult("model_fallback", FALLBACK, [], "invalid_llm_response")
    citations = list(dict.fromkeys(payload.get("citations", [])))
    return GenerationResult("unvalidated_answer", answer, citations)


def generate(
    question: str,
    chunks: list[RetrievedChunk],
    client: Any,
    model: str,
    threshold: float,
    prompt_flavor: str,
    post_validator: str = "on",
) -> GenerationResult:
    if prompt_flavor not in PROMPT_FLAVORS:
        raise ValueError(f"Unsupported prompt flavor: {prompt_flavor}")
    if post_validator not in POST_VALIDATOR_MODES:
        raise ValueError(f"Unsupported post validator mode: {post_validator}")
    reason = weak_context_reason(chunks, threshold)
    if reason:
        LOGGER.info(
            "generation_status=retrieval_filter_fallback fallback_reason=%s prompt_flavor=%s min_vector_score=%s post_validator=%s",
            reason,
            prompt_flavor,
            threshold,
            post_validator,
        )
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
        else:
            result = accept_payload_without_post_validation(payload)
    except Exception as exc:
        LOGGER.warning("invalid_llm_response error=%s", type(exc).__name__)
        result = GenerationResult("model_fallback", FALLBACK, [], "invalid_llm_response")
    LOGGER.info(
        "generation_status=%s fallback_reason=%s prompt_flavor=%s post_validator=%s citations=%s",
        result.status,
        result.fallback_reason,
        prompt_flavor,
        post_validator,
        result.citations,
    )
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


def build_output(
    question: str,
    chunks: list[RetrievedChunk],
    result: GenerationResult,
    threshold: float,
    prompt_flavor: str,
    post_validator: str,
) -> dict[str, Any]:
    return {
        "question": question,
        "prompt_flavor": prompt_flavor,
        "post_validator": post_validator,
        "min_vector_score": threshold,
        "best_vector_score": best_vector_score(chunks),
        "retrieved_context_by_id": build_context_map(chunks),
        **asdict(result),
    }


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


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
            f"| {_markdown_cell(row['experiment'])} | {_markdown_cell(row['prompt_flavor'])} | {_markdown_cell(row['post_validator'])} | "
            f"{threshold_text} | {best_text} | {_markdown_cell(row['status'])} | {_markdown_cell(row.get('fallback_reason') or '-')} | "
            f"{_markdown_cell(citations)} | {_markdown_cell(conclusion)} |"
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


def to_rag_observation(
    question: str,
    chunks: list[RetrievedChunk],
    result: GenerationResult,
    source: str = "retrieval.rag",
) -> RagObservation:
    return RagObservation(
        source=source,
        success=result.status in {"grounded_answer", "unvalidated_answer"},
        status=result.status,
        answer=result.answer,
        citations=result.citations,
        retrieved_context_by_id=build_context_map(chunks),
        fallback_reason=result.fallback_reason,
        error=None,
    )
