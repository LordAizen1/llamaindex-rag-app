"""Unit tests for the document parsers (no OpenAI required)."""
import os

import pytest

from app.rag.parsers import (
    EmptyDocument,
    UnsupportedFileType,
    parse_file,
    parse_markdown,
)

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def test_markdown_sections_and_metadata(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# Title\n\nIntro text.\n\n## Section A\n\nBody of A.\n", encoding="utf-8")
    docs = parse_markdown(str(md), "doc.md")

    assert len(docs) == 2
    assert docs[0].metadata["section"] == "Title"
    assert docs[1].metadata["section"] == "Section A"
    assert all(d.metadata["source"] == "doc.md" for d in docs)
    assert all(d.metadata["file_type"] == "markdown" for d in docs)


def test_sample_markdown_parses():
    path = os.path.join(SAMPLES, "nimbus-api-guide.md")
    docs = parse_file(path, "nimbus-api-guide.md")
    assert len(docs) > 3
    sections = {d.metadata.get("section") for d in docs}
    assert "Authentication" in sections


def test_unsupported_type_raises(tmp_path):
    f = tmp_path / "data.xyz"
    f.write_text("nope", encoding="utf-8")
    with pytest.raises(UnsupportedFileType):
        parse_file(str(f), "data.xyz")


def test_empty_document_raises(tmp_path):
    f = tmp_path / "empty.md"
    f.write_text("   \n  \n", encoding="utf-8")
    with pytest.raises(EmptyDocument):
        parse_file(str(f), "empty.md")
