"""Compare baseline Pinecone retrieval with filtering and cross-encoder reranking."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from pages_evaluation_reference import (
    BASELINE_RUN_ID,
    BASELINE_RUN_URL,
    CASES,
    EXPECTED_RESULTS_URL,
)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX = "supp-bro"
DEFAULT_NAMESPACE = "hw3-pinecone-vector"
DEFAULT_FILTER_BY_DOMAIN = False
BASELINE_K, CANDIDATE_K, FINAL_K = 5, 15, 5
DEFAULT_JSON_PATH = PROJECT_ROOT / "data/hw3/output/pinecone_retrieval_evaluation.json"
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data/hw3/output/pinecone_retrieval_evaluation.md"


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def boolean_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value, got: {value}")


def search(query: str, model: Any, index: Any, namespace: str, top_k: int, metadata_filter: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    import faiss

    embedding = model.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(embedding)
    arguments: dict[str, Any] = {
        "vector": embedding[0].tolist(),
        "namespace": namespace,
        "top_k": top_k,
        "include_metadata": True,
    }
    if metadata_filter is not None:
        arguments["filter"] = metadata_filter
    response = index.query(**arguments)
    return [
        {
            "chunk_id": match.id,
            "vector_score": float(match.score),
            "text": match.metadata.get("text", ""),
        }
        for match in response.matches
    ]


def rerank(query: str, candidates: list[dict[str, Any]], reranker: Any) -> list[dict[str, Any]]:
    if not candidates:
        return []
    scores = reranker.predict([(query, candidate["text"]) for candidate in candidates])
    scored = [{**candidate, "rerank_score": float(score)} for candidate, score in zip(candidates, scores)]
    return sorted(scored, key=lambda item: item["rerank_score"], reverse=True)


def calculate_metrics(results: list[dict[str, Any]], relevant_ids: frozenset[str]) -> dict[str, float]:
    ids = [result["chunk_id"] for result in results]
    ranks = [rank for rank, chunk_id in enumerate(ids, 1) if chunk_id in relevant_ids]
    return {
        "top_1": float(bool(ids and ids[0] in relevant_ids)),
        "hit_at_5": float(bool(ranks)),
        "mrr": 1.0 / ranks[0] if ranks else 0.0,
        "precision_at_5": sum(chunk_id in relevant_ids for chunk_id in ids) / FINAL_K,
    }


def first_relevant_rank(results: list[dict[str, Any]], relevant_ids: frozenset[str]) -> int | None:
    return next((rank for rank, result in enumerate(results, 1) if result["chunk_id"] in relevant_ids), None)


def aggregate(rows: list[dict[str, Any]], pipeline: str) -> dict[str, float]:
    names = ("top_1", "hit_at_5", "mrr", "precision_at_5")
    return {name: sum(row[pipeline]["metrics"][name] for row in rows) / len(rows) for name in names}


def compact(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in result.items() if key != "text"} for result in results]


def evaluate(model: Any, reranker: Any, index: Any, namespace: str, filter_by_domain: bool) -> dict[str, Any]:
    rows = []
    for case in CASES:
        metadata_filter = case.metadata_filter if filter_by_domain else None
        baseline = search(case.query, model, index, namespace, BASELINE_K, metadata_filter)
        candidates = search(case.query, model, index, namespace, CANDIDATE_K, metadata_filter)
        improved = rerank(case.query, candidates, reranker)[:FINAL_K]
        rows.append(
            {
                "query": case.query,
                "metadata_filter": metadata_filter,
                "relevant_chunk_ids": sorted(case.relevant_ids),
                "baseline": {
                    "metrics": calculate_metrics(baseline, case.relevant_ids),
                    "first_relevant_rank": first_relevant_rank(baseline, case.relevant_ids),
                    "results": compact(baseline),
                },
                "improved": {
                    "metrics": calculate_metrics(improved, case.relevant_ids),
                    "first_relevant_rank": first_relevant_rank(improved, case.relevant_ids),
                    "results": compact(improved),
                },
            }
        )
    baseline_metrics = aggregate(rows, "baseline")
    improved_metrics = aggregate(rows, "improved")
    delta = {name: improved_metrics[name] - baseline_metrics[name] for name in baseline_metrics}
    improved_count = sum(value > 1e-12 for value in delta.values())
    regressed_count = sum(value < -1e-12 for value in delta.values())
    if improved_count and not regressed_count:
        verdict = "Improved retrieval is better on at least one aggregate metric with no measured regression."
    elif improved_count:
        verdict = "Mixed result: some aggregate metrics improved and others regressed."
    else:
        verdict = "No aggregate retrieval improvement was demonstrated."
    return {
        "configuration": {"embedding_model": EMBEDDING_MODEL, "reranker_model": RERANKER_MODEL, "baseline_k": BASELINE_K, "candidate_k": CANDIDATE_K, "final_k": FINAL_K, "filter_by_domain": filter_by_domain, "baseline_run_id": BASELINE_RUN_ID},
        "references": {"baseline_run": BASELINE_RUN_URL, "expected_results": EXPECTED_RESULTS_URL},
        "aggregate": {"baseline": baseline_metrics, "improved": improved_metrics, "delta": delta},
        "verdict": verdict,
        "queries": rows,
    }


def escape_markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def format_chunk_ids(results: list[dict[str, Any]]) -> str:
    if not results:
        return "—"
    return "<br>".join(
        f"{rank}. `{escape_markdown(result['chunk_id'])}`"
        for rank, result in enumerate(results, 1)
    )


def format_metric(value: float, percentage: bool = True) -> str:
    return f"{value:.1%}" if percentage else f"{value:.3f}"


def write_outputs(report: dict[str, Any], json_path: Path, summary_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    baseline, improved = report["aggregate"]["baseline"], report["aggregate"]["improved"]
    filter_by_domain = report["configuration"]["filter_by_domain"]
    filter_description = "enabled (`source=pages`)" if filter_by_domain else "disabled"
    lines = [
        "# Pinecone retrieval: baseline vs improved", "",
        f"Domain filter: **{filter_description}**. The same setting is applied to baseline and improved retrieval.  ",
        f"Baseline: Pinecone Top-{BASELINE_K} (reference: [run {BASELINE_RUN_ID}]({BASELINE_RUN_URL})).  ",
        f"Ground truth: expected chunk IDs from [HW2 Pages]({EXPECTED_RESULTS_URL}).  ",
        f"Improved: Pinecone Top-{CANDIDATE_K}, cross-encoder reranking, final Top-{FINAL_K}.", "",
        "| Pipeline | Top-1 | Hit@5 | MRR | Precision@5 |", "| --- | ---: | ---: | ---: | ---: |",
        f"| Baseline | {baseline['top_1']:.1%} | {baseline['hit_at_5']:.1%} | {baseline['mrr']:.3f} | {baseline['precision_at_5']:.1%} |",
        f"| Improved | {improved['top_1']:.1%} | {improved['hit_at_5']:.1%} | {improved['mrr']:.3f} | {improved['precision_at_5']:.1%} |", "",
        f"**Verdict:** {report['verdict']}", "",
    ]
    lines.extend([
        "## Per-query metrics", "",
        "| Query | Baseline Top-1 | Baseline Hit@5 | Baseline RR | Baseline Precision@5 | Improved Top-1 | Improved Hit@5 | Improved RR | Improved Precision@5 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in report["queries"]:
        baseline_metrics = row["baseline"]["metrics"]
        improved_metrics = row["improved"]["metrics"]
        lines.append(
            f"| {escape_markdown(row['query'])} | {format_metric(baseline_metrics['top_1'])} | "
            f"{format_metric(baseline_metrics['hit_at_5'])} | {format_metric(baseline_metrics['mrr'], percentage=False)} | "
            f"{format_metric(baseline_metrics['precision_at_5'])} | {format_metric(improved_metrics['top_1'])} | "
            f"{format_metric(improved_metrics['hit_at_5'])} | {format_metric(improved_metrics['mrr'], percentage=False)} | "
            f"{format_metric(improved_metrics['precision_at_5'])} |"
        )
    lines.extend([
        "", "## Retrieved chunks", "",
        "| Query | Expected chunks | Baseline retrieved chunks | Improved retrieved chunks | Baseline first relevant rank | Improved first relevant rank |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ])
    for row in report["queries"]:
        baseline_rank = row["baseline"]["first_relevant_rank"] or "—"
        improved_rank = row["improved"]["first_relevant_rank"] or "—"
        expected = "<br>".join(f"`{chunk_id}`" for chunk_id in row["relevant_chunk_ids"])
        baseline_results = format_chunk_ids(row["baseline"]["results"])
        improved_results = format_chunk_ids(row["improved"]["results"])
        lines.append(
            f"| {escape_markdown(row['query'])} | {expected} | {baseline_results} | "
            f"{improved_results} | {baseline_rank} | {improved_rank} |"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        load_dotenv = None
    if load_dotenv:
        load_dotenv(PROJECT_ROOT / ".env")

    from pinecone import Pinecone
    from sentence_transformers import CrossEncoder, SentenceTransformer

    index_name = os.environ.get("PINECONE_INDEX", DEFAULT_INDEX)
    namespace = os.environ.get("PINECONE_NAMESPACE", DEFAULT_NAMESPACE)
    filter_by_domain = boolean_env("PINECONE_FILTER_BY_DOMAIN", DEFAULT_FILTER_BY_DOMAIN)
    json_path = Path(os.environ.get("PINECONE_EVALUATION_JSON_PATH", DEFAULT_JSON_PATH))
    summary_path = Path(os.environ.get("PINECONE_EVALUATION_SUMMARY_PATH", DEFAULT_SUMMARY_PATH))
    model = SentenceTransformer(EMBEDDING_MODEL)
    reranker = CrossEncoder(RERANKER_MODEL)
    index = Pinecone(api_key=required_env("PINECONE_API_KEY")).Index(index_name)
    report = evaluate(model, reranker, index, namespace, filter_by_domain)
    write_outputs(report, json_path, summary_path)
    print(json.dumps(report["aggregate"], indent=2))
    print(report["verdict"])
    print(f"JSON report: {json_path}")
    print(f"Markdown summary: {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
