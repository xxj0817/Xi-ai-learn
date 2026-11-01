"""文档解析：PDF / DOCX / Markdown / 纯文本 → 纯文本。"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

import docx2txt
import pypdf

from app.core.exceptions import InvalidInput
from app.models.knowledge import KnowledgeSourceType

logger = logging.getLogger(__name__)

UNSUPPORTED_MESSAGE = "仅支持 PDF / Word / Markdown / TXT 文档"

_EXTENSION_TYPES: dict[str, KnowledgeSourceType] = {
    "pdf": KnowledgeSourceType.pdf,
    "docx": KnowledgeSourceType.docx,
    "md": KnowledgeSourceType.md,
    "markdown": KnowledgeSourceType.md,
    "txt": KnowledgeSourceType.txt,
}

_BLANK_LINES_RE = re.compile(r"\n{3,}")
_TRAILING_SPACES_RE = re.compile(r"[ \t]+\n")


def detect_source_type(filename: str) -> KnowledgeSourceType:
    suffix = Path((filename or "").strip()).suffix.lower().lstrip(".")
    source_type = _EXTENSION_TYPES.get(suffix)
    if source_type is None:
        raise InvalidInput(UNSUPPORTED_MESSAGE)
    return source_type


def load_bytes(filename: str, data: bytes) -> str:
    """把上传的原始字节解析成纯文本；失败统一抛 InvalidInput。"""
    source_type = detect_source_type(filename)
    if not data:
        raise InvalidInput("文件内容为空，请重新选择文件")

    if source_type is KnowledgeSourceType.pdf:
        text = _load_pdf(data)
    elif source_type is KnowledgeSourceType.docx:
        text = _load_docx(data)
    else:
        text = _load_text(data)

    cleaned = normalize_text(text)
    if not cleaned:
        raise InvalidInput("未能从文档中解析出文字内容，请换一个文件")
    return cleaned


def normalize_text(text: str) -> str:
    unified = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    unified = unified.replace("\x00", "")
    unified = _TRAILING_SPACES_RE.sub("\n", unified)
    unified = _BLANK_LINES_RE.sub("\n\n", unified)
    return unified.strip()


def _load_pdf(data: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:  # noqa: BLE001 - 加密文档按不可解析处理
                raise InvalidInput("该 PDF 已加密，无法解析") from exc
        pages = [page.extract_text() or "" for page in reader.pages]
    except InvalidInput:
        raise
    except Exception as exc:  # noqa: BLE001 - 损坏文件按不可解析处理
        logger.info("PDF 解析失败 error=%s", type(exc).__name__)
        raise InvalidInput("PDF 解析失败，请确认文件未损坏") from exc
    return "\n\n".join(pages)


def _load_docx(data: bytes) -> str:
    try:
        return docx2txt.process(io.BytesIO(data)) or ""
    except Exception as exc:  # noqa: BLE001 - 损坏文件按不可解析处理
        logger.info("DOCX 解析失败 error=%s", type(exc).__name__)
        raise InvalidInput("Word 文档解析失败，请确认文件未损坏") from exc


def _load_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise InvalidInput("文本编码无法识别，请保存为 UTF-8 后重新上传")
