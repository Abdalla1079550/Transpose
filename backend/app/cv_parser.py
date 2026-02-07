from __future__ import annotations

from io import BytesIO

from docx import Document
from pypdf import PdfReader


class CVParseError(ValueError):
    """Raised when CV content cannot be parsed."""


def parse_cv(filename: str, payload: bytes) -> str:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return _parse_pdf(payload)
    if lowered.endswith(".docx"):
        return _parse_docx(payload)
    raise CVParseError("Unsupported CV format. Please upload PDF or DOCX.")


def _parse_pdf(payload: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(payload))
        chunks = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001
        raise CVParseError("Failed to parse PDF CV.") from exc

    text = "\n".join(chunks).strip()
    if not text:
        raise CVParseError("PDF CV appears empty.")
    return text


def _parse_docx(payload: bytes) -> str:
    try:
        document = Document(BytesIO(payload))
        chunks = [paragraph.text for paragraph in document.paragraphs]
    except Exception as exc:  # noqa: BLE001
        raise CVParseError("Failed to parse DOCX CV.") from exc

    text = "\n".join(chunks).strip()
    if not text:
        raise CVParseError("DOCX CV appears empty.")
    return text
