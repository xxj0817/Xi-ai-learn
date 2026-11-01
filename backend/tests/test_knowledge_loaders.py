from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.core.exceptions import InvalidInput
from app.knowledge.loaders import detect_source_type, load_bytes
from app.knowledge.splitter import split_text
from app.models.knowledge import KnowledgeSourceType


def build_pdf(text: str) -> bytes:
    """构造一个 pypdf 可解析的最小单页 PDF。"""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    safe_text = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    stream = f"BT /F1 12 Tf 20 150 Td ({safe_text}) Tj ET".encode("latin-1")
    objects[3] = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode())
        buffer.write(body)
        buffer.write(b"\nendobj\n")

    xref_offset = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode())
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets:
        buffer.write(f"{offset:010d} 00000 n \n".encode())
    buffer.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return buffer.getvalue()


def build_docx(paragraphs: list[str]) -> bytes:
    """构造一个 docx2txt 可解析的最小 DOCX。"""
    body = "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("培训手册.pdf", KnowledgeSourceType.pdf),
        ("知识库.DOCX", KnowledgeSourceType.docx),
        ("notes.md", KnowledgeSourceType.md),
        ("readme.markdown", KnowledgeSourceType.md),
        ("faq.txt", KnowledgeSourceType.txt),
    ],
)
def test_detect_source_type(filename: str, expected: KnowledgeSourceType) -> None:
    assert detect_source_type(filename) is expected


@pytest.mark.parametrize("filename", ["video.mp4", "sheet.xlsx", "noext", "image.png"])
def test_detect_source_type_rejects_unsupported(filename: str) -> None:
    with pytest.raises(InvalidInput):
        detect_source_type(filename)


def test_load_markdown_keeps_readable_text() -> None:
    raw = "# 客服话术\n\n退货政策：7 天无理由退货。".encode()

    text = load_bytes("policy.md", raw)

    assert "退货政策" in text
    assert "7 天无理由退货" in text


def test_load_txt_handles_chinese_encoding() -> None:
    raw = "内部培训：新员工第一周需要完成入职课程。".encode("utf-8")

    text = load_bytes("training.txt", raw)

    assert "内部培训" in text


def test_load_pdf_extracts_page_text() -> None:
    raw = build_pdf("Harness engineering interview guide")

    text = load_bytes("guide.pdf", raw)

    assert "Harness engineering" in text


def test_load_docx_extracts_paragraphs() -> None:
    raw = build_docx(["客服岗位培训", "第一课：工单分级"])

    text = load_bytes("training.docx", raw)

    assert "客服岗位培训" in text
    assert "工单分级" in text


def test_load_bytes_rejects_empty_file() -> None:
    with pytest.raises(InvalidInput):
        load_bytes("empty.txt", b"")


def test_load_bytes_rejects_blank_content() -> None:
    with pytest.raises(InvalidInput):
        load_bytes("blank.md", b"   \n\n\t  ")


def test_load_bytes_rejects_broken_pdf() -> None:
    with pytest.raises(InvalidInput):
        load_bytes("broken.pdf", b"not a real pdf")


def test_split_text_creates_numbered_chunks_with_metadata() -> None:
    text = "第一段内容。" * 200

    chunks = split_text(
        text,
        doc_id="doc_1",
        title="培训手册",
        source_type=KnowledgeSourceType.md,
        chunk_size=200,
        chunk_overlap=20,
    )

    assert len(chunks) > 1
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert chunk.metadata["doc_id"] == "doc_1"
        assert chunk.metadata["title"] == "培训手册"
        assert chunk.metadata["source_type"] == "md"
        assert chunk.page_content.strip()


def test_split_text_returns_single_chunk_for_short_text() -> None:
    chunks = split_text(
        "短文本",
        doc_id="doc_2",
        title="短文档",
        source_type=KnowledgeSourceType.txt,
        chunk_size=800,
        chunk_overlap=100,
    )

    assert len(chunks) == 1
    assert chunks[0].page_content == "短文本"


def test_split_text_rejects_blank_text() -> None:
    with pytest.raises(InvalidInput):
        split_text(
            "   ",
            doc_id="doc_3",
            title="空文档",
            source_type=KnowledgeSourceType.txt,
            chunk_size=800,
            chunk_overlap=100,
        )


def test_split_text_does_not_emit_trailing_blank_chunks() -> None:
    chunks = split_text(
        "段落一。\n\n段落二。\n\n\n",
        doc_id="doc_4",
        title="文档",
        source_type=KnowledgeSourceType.txt,
        chunk_size=800,
        chunk_overlap=0,
    )

    assert all(chunk.page_content.strip() for chunk in chunks)
