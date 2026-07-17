"""
Shared JSONL helpers for HW 1 scripts.
"""

import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """
    Load records from a JSONL file.
    """
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue
            try:
                records.append(json.loads(stripped_line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} in {path}") from exc
    return records


def save_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    """
    Save records in JSONL format (one JSON object per line).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
