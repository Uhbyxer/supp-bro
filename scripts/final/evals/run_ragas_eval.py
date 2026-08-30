"""Run local RAGAS evaluation for grounded-answer final SuppBro cases."""

from __future__ import annotations

import argparse
import json
import os
import sys
import types
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES_PATH = PROJECT_ROOT / "scripts/final/evals/eval_cases.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "scripts/final/outputs/eval_ragas_results.csv"

sys.path.insert(0, str(PROJECT_ROOT))

from scripts.final.langgraph_flow import run_langgraph_workflow  # noqa: E402

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")


def ensure_ragas_langchain_compat() -> None:
    """Shim removed LangChain modules that ragas 0.3.9 still imports."""
    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return
    try:
        __import__(module_name)
    except ModuleNotFoundError:
        shim = types.ModuleType(module_name)

        class ChatVertexAI:  # pragma: no cover - compatibility shim only
            pass

        shim.ChatVertexAI = ChatVertexAI
        sys.modules[module_name] = shim


def normalize_context(context: Any) -> str:
    if isinstance(context, str):
        return context
    if isinstance(context, dict):
        if isinstance(context.get("text"), str):
            return context["text"]
        return json.dumps(context, ensure_ascii=False)
    return str(context)


def collect_contexts(state: dict[str, Any], max_contexts: int, max_chars: int) -> list[str]:
    contexts: list[Any] = []
    for rag_call in state.get("rag_calls", []):
        contexts.extend((rag_call.get("retrieved_context_by_id") or {}).values())
    contexts.extend(state.get("external_tool_results", []))
    normalized = [normalize_context(context) for context in contexts[:max_contexts]]
    return [context[:max_chars] for context in normalized if context]


def load_grounded_cases(path: Path) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    return [case for case in cases if case.get("expected_route") != "clarification"]


def build_rows(
    cases: list[dict[str, Any]],
    min_vector_score: float,
    max_contexts: int,
    max_chars: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        state = run_langgraph_workflow(
            question=case["question"],
            allow_external_community_search=case.get("allow_external_community_search", False),
            issue_number=case.get("issue_number"),
            min_vector_score=min_vector_score,
            enable_rag=True,
        )
        rows.append(
            {
                "id": case["id"],
                "question": case["question"],
                "answer": state.get("final_answer", ""),
                "contexts": collect_contexts(state, max_contexts, max_chars),
                "ground_truth": case.get("ground_truth", ""),
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local RAGAS eval for final SuppBro grounded-answer cases.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--min-vector-score", type=float, default=0.30)
    parser.add_argument("--max-contexts", type=int, default=5)
    parser.add_argument("--max-context-chars", type=int, default=1500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")

    ensure_ragas_langchain_compat()

    from datasets import Dataset
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import answer_relevancy, context_precision, faithfulness

    rows = build_rows(
        load_grounded_cases(args.cases),
        args.min_vector_score,
        args.max_contexts,
        args.max_context_chars,
    )
    dataset = Dataset.from_list(
        [
            {
                "question": row["question"],
                "answer": row["answer"],
                "contexts": row["contexts"],
                "ground_truth": row["ground_truth"],
            }
            for row in rows
        ]
    )

    llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", temperature=0))
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
        llm=llm,
        embeddings=embeddings,
    )
    frame = result.to_pandas()
    frame.insert(0, "id", [row["id"] for row in rows])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - external evaluator can fail for provider reasons
        sys.exit(f"RAGAS eval failed: {exc}")
