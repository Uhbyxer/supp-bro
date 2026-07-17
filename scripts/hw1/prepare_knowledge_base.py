"""
Lesson 3 Demo 1: Normalize source documents.

Run from the project root:
    python scripts/hw1/prepare_knowledge_base.py

Purpose:
    Show that different raw source types should be converted into one
    internal document format before chunking and indexing.

This script reads:
    - AsciiDoc files
    - Markdown files
    - CSV files

And produces:
    data/hw1/processed/normalized_documents.jsonl
"""

import csv
import json
from pathlib import Path
from typing import Any

RAW_DIR = Path("data/hw1/raw")
PROCESSED_DIR = Path("data/hw1/processed")
OUTPUT_PATH = PROCESSED_DIR / "normalized_documents.jsonl"


def extract_markdown_title(text: str) -> str | None:
    """
    Extract the first H1 heading from a Markdown document.
    """
    for line in text.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("# "):
            return stripped_line.replace("# ", "", 1).strip()
    return None


def extract_asciidoc_title(text: str) -> str | None:
    """
    Extract the document title from an AsciiDoc document.
    """
    for line in text.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("= ") and not stripped_line.startswith("== "):
            return stripped_line.replace("= ", "", 1).strip()
    return None


def read_asciidoc_file(file_path: Path) -> dict[str, Any]:
    """
    Read an AsciiDoc file and convert it into a normalized document object.
    """
    text = file_path.read_text(encoding="utf-8")
    title = extract_asciidoc_title(text) or file_path.stem.replace("_", " ").title()
    return {
        "document_id": file_path.stem,
        "source_file": str(file_path),
        "source_type": "asciidoc",
        "title": title,
        "text": text,
        "metadata": {
            "language": "en",
            "domain": "hr",
            "document_type": "policy",
        },
    }


def read_markdown_file(file_path: Path) -> dict[str, Any]:
    """
    Read a Markdown file and convert it into a normalized document object.
    """
    text = file_path.read_text(encoding="utf-8")
    title = extract_markdown_title(text) or file_path.stem.replace("_", " ").title()
    return {
        "document_id": file_path.stem,
        "source_file": str(file_path),
        "source_type": "markdown",
        "title": title,
        "text": text,
        "metadata": {
            "language": "en",
            "domain": "hr",
            "document_type": "policy",
        },
    }


def read_csv_file(file_path: Path) -> dict[str, Any]:
    """
    Read a CSV file and convert rows into one deterministic text block.
    """
    rows: list[dict[str, str]] = []
    with file_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            rows.append(dict(row))

    text_lines = [f"# {file_path.stem.replace('_', ' ').title()}"]
    for index, row in enumerate(rows, start=1):
        row_text = "; ".join(f"{key}: {value}" for key, value in row.items())
        text_lines.append(f"Row {index}: {row_text}")
    text = "\n".join(text_lines)

    return {
        "document_id": file_path.stem,
        "source_file": str(file_path),
        "source_type": "csv",
        "title": file_path.stem.replace("_", " ").title(),
        "text": text,
        "metadata": {
            "language": "en",
            "domain": "hr",
            "document_type": "policy_table",
            "row_count": len(rows),
        },
    }


def load_raw_sources(raw_dir: Path) -> list[dict[str, Any]]:
    """
    Load supported source files from the raw directory.
    Supported formats:
        - .adoc
        - .md
        - .csv
    """
    documents: list[dict[str, Any]] = []
    for file_path in sorted(raw_dir.iterdir()):
        if file_path.suffix.lower() == ".adoc":
            documents.append(read_asciidoc_file(file_path))
        elif file_path.suffix.lower() == ".md":
            documents.append(read_markdown_file(file_path))
        elif file_path.suffix.lower() == ".csv":
            documents.append(read_csv_file(file_path))
        else:
            print(f"Warning: unsupported file type skipped: {file_path}")
    return documents


def save_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    """
    Save records in JSONL format (one JSON object per line).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"Raw data directory not found: {RAW_DIR}. "
            "Please run this script from the project root."
        )

    documents = load_raw_sources(RAW_DIR)
    save_jsonl(documents, OUTPUT_PATH)

    print("=" * 80)
    print("LESSON 3 DEMO 1: NORMALIZE SOURCES")
    print("=" * 80)
    print(f"Raw directory: {RAW_DIR}")
    print(f"Normalized documents: {len(documents)}")
    print(f"Output file: {OUTPUT_PATH}")
    print()

    for doc in documents:
        print("-" * 80)
        print(f"Document ID: {doc['document_id']}")
        print(f"Source type: {doc['source_type']}")
        print(f"Title: {doc['title']}")
        preview = doc["text"][:180].replace("\n", " ")
        print(f"Text preview: {preview}...")


if __name__ == "__main__":
    main()
