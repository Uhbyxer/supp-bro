"""
HW 1: Chunk normalized documents.

Run from the project root:
    python scripts/hw1/chunk_documents.py

This script reads:
    data/hw1/processed/normalized_documents.jsonl

And produces:
    data/hw1/processed/chunks.jsonl
"""

import re
from pathlib import Path
from typing import Any

from jsonl_io import load_jsonl, save_jsonl
from slugify import slugify

PROCESSED_DIR = Path("data/hw1/processed")
INPUT_PATH = PROCESSED_DIR / "normalized_documents.jsonl"
OUTPUT_PATH = PROCESSED_DIR / "chunks.jsonl"
SECTION_HEADING_PATTERN = re.compile(r"^==(?!=)\s+(.+?)\s*$")
OVERVIEW_OVERLAP_LIMIT = 1000


def snake_case(value: str) -> str:
    """
    Convert a section title into a stable chunk key segment.
    """
    return slugify(value, separator="_")


def split_top_level_sections(text: str) -> list[dict[str, str]]:
    """
    Split text by top-level AsciiDoc sections.
    """
    sections: list[dict[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        heading_match = SECTION_HEADING_PATTERN.match(line.strip())
        if heading_match:
            if current_title is not None:
                sections.append(
                    {
                        "title": current_title,
                        "text": "\n".join(current_lines).strip(),
                    }
                )
            current_title = heading_match.group(1).strip()
            current_lines = [line]
            continue

        if current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        sections.append(
            {
                "title": current_title,
                "text": "\n".join(current_lines).strip(),
            }
        )

    return sections


def find_overview_section(
    sections: list[dict[str, str]], document_id: str
) -> dict[str, str]:
    """
    Return the required Overview section.
    """
    for section in sections:
        if section["title"] == "Overview":
            return section

    raise ValueError(f"Document {document_id} does not contain a top-level Overview section")


def split_section_paragraphs(text: str) -> list[str]:
    """
    Split section text into paragraphs, keeping the section heading with the first body paragraph.
    """
    paragraphs = [
        paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()
    ]
    if len(paragraphs) > 1 and SECTION_HEADING_PATTERN.match(paragraphs[0]):
        return [f"{paragraphs[0]}\n\n{paragraphs[1]}", *paragraphs[2:]]

    return paragraphs


def build_overview_overlap(
    overview_paragraphs: list[str],
    section_text: str,
) -> str:
    """
    Select Overview paragraphs until overlap plus section text reaches the limit.
    """
    selected_paragraphs: list[str] = []
    for paragraph in overview_paragraphs:
        selected_paragraphs.append(paragraph)
        overlap_text = "\n\n".join(selected_paragraphs)
        if len(f"{overlap_text}\n\n{section_text}") >= OVERVIEW_OVERLAP_LIMIT:
            break

    return "\n\n".join(selected_paragraphs)


def build_chunk_metadata(
    document: dict[str, Any],
    section_title: str,
    chunk_index: int,
) -> dict[str, Any]:
    """
    Build chunk metadata from the parent document and section data.
    """
    metadata = {
        "document_id": document["document_id"],
        "source_file": document["source_file"],
        "source_type": document["source_type"],
        "title": document["title"],
    }
    metadata.update(document.get("metadata", {}))
    metadata["section"] = section_title
    metadata["chunk_index"] = chunk_index
    return metadata


def add_chunk_navigation_metadata(
    chunks: list[dict[str, Any]],
    root_chunk_id: str,
) -> None:
    """
    Add same-document navigation links to each chunk metadata object.
    """
    for index, chunk in enumerate(chunks):
        chunk["metadata"]["prev_chunk_id"] = (
            chunks[index - 1]["chunk_id"] if index > 0 else None
        )
        chunk["metadata"]["next_chunk_id"] = (
            chunks[index + 1]["chunk_id"] if index < len(chunks) - 1 else None
        )
        chunk["metadata"]["root_chunk_id"] = root_chunk_id


def chunk_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert one normalized document into section chunks with Overview overlap.
    """
    document_id = document["document_id"]
    sections = split_top_level_sections(document["text"])
    overview_section = find_overview_section(sections, document_id)
    overview_paragraphs = split_section_paragraphs(overview_section["text"])
    chunks: list[dict[str, Any]] = []

    for chunk_index, section in enumerate(sections, start=1):
        section_title = section["title"]
        section_key = snake_case(section_title)
        if not section_key:
            raise ValueError(
                f"Document {document_id} contains a section title without a valid key"
            )

        if section_title == "Overview":
            chunk_text = section["text"]
        else:
            overview_overlap = build_overview_overlap(
                overview_paragraphs,
                section["text"],
            )
            chunk_text = f"{overview_overlap}\n\n{section['text']}"

        chunks.append(
            {
                "chunk_id": f"{document_id}:{section_key}",
                "text": chunk_text,
                "metadata": build_chunk_metadata(
                    document,
                    section_title,
                    chunk_index,
                ),
            }
        )

    root_chunk_id = f"{document_id}:{snake_case(overview_section['title'])}"
    add_chunk_navigation_metadata(chunks, root_chunk_id)
    return chunks


def chunk_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert normalized documents into chunks.
    """
    chunks: list[dict[str, Any]] = []
    for document in documents:
        chunks.extend(chunk_document(document))
    return chunks


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Normalized documents not found: {INPUT_PATH}. "
            "Run scripts/hw1/prepare_knowledge_base.py first."
        )

    documents = load_jsonl(INPUT_PATH)
    chunks = chunk_documents(documents)
    save_jsonl(chunks, OUTPUT_PATH)

    print("=" * 80)
    print("LESSON 3 DEMO 2: CHUNK DOCUMENTS")
    print("=" * 80)
    print(f"Input file: {INPUT_PATH}")
    print(f"Normalized documents: {len(documents)}")
    print(f"Chunks: {len(chunks)}")
    print(f"Output file: {OUTPUT_PATH}")
    print()
    print("Chunk sizes:")
    for chunk in chunks:
        print(f"- {chunk['chunk_id']}: {len(chunk['text'])} symbols")


if __name__ == "__main__":
    main()
