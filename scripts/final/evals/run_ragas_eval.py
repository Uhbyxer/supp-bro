"""RAGAS evaluation for final SuppBro outputs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_PATH = PROJECT_ROOT / "scripts/final/outputs/ragas_input.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "scripts/final/outputs/eval_ragas_results.csv"


def compact_contexts(contexts: list[str], max_contexts: int, max_chars: int) -> list[str]:
    return [context[:max_chars] for context in contexts[:max_contexts] if context]


def load_rows(path: Path, max_contexts: int, max_chars: int) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        row["contexts"] = compact_contexts(row.get("contexts") or [], max_contexts, max_chars)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAGAS eval for final SuppBro results.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--max-contexts", type=int, default=5)
    parser.add_argument("--max-context-chars", type=int, default=1500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")

    from datasets import Dataset
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import answer_relevancy, context_precision, faithfulness

    rows = load_rows(args.input, args.max_contexts, args.max_context_chars)
    dataset = Dataset.from_list(
        [
            {
                "question": row["question"],
                "answer": row["answer"],
                "contexts": row["contexts"],
                "ground_truth": row.get("ground_truth", ""),
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
    frame.to_csv(args.output, index=False)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - external evaluator can fail for provider reasons
        sys.exit(f"RAGAS eval failed: {exc}")
