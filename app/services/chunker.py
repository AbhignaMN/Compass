"""Markdown-aware ~300-token chunker for career knowledge base RAG."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentChunk:
    source_url: str
    title: str
    text: str


_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")


def chunk_markdown(
    content: str,
    source_url: str,
    default_title: str,
    target_words: int = 225,  # ~300 tokens (1 word ~= 1.33 tokens)
    overlap_words: int = 35,
) -> list[DocumentChunk]:
    """Split a markdown guide into ~300-token chunks while keeping section headings."""
    lines = content.splitlines()
    doc_title = default_title
    current_section = ""
    sections: list[tuple[str, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            heading = f"{doc_title} — {current_section}" if current_section else doc_title
            sections.append((heading, text))
        buffer.clear()

    for line in lines:
        match = _HEADING_RE.match(line.strip())
        if match:
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            flush()
            if level == 1:
                doc_title = heading_text
                current_section = ""
            else:
                current_section = heading_text
        else:
            buffer.append(line)
    flush()

    chunks: list[DocumentChunk] = []
    for heading, body in sections:
        words = body.split()
        if len(words) <= target_words:
            chunks.append(DocumentChunk(source_url=source_url, title=heading, text=body))
            continue

        start = 0
        part = 1
        while start < len(words):
            end = min(start + target_words, len(words))
            chunk_text = " ".join(words[start:end])
            chunk_title = f"{heading} (Part {part})" if start > 0 or end < len(words) else heading
            chunks.append(
                DocumentChunk(source_url=source_url, title=chunk_title, text=chunk_text)
            )
            if end >= len(words):
                break
            start = max(end - overlap_words, start + 1)
            part += 1

    return chunks
