"""PDF-capable reader.

Handles packets whose documents carry base64 PDF bytes (`pdf_base64`) as well as
plain `text`. Each PDF page becomes its own document so citations still point at a
specific page (`<doc_id>p<page>`). pypdf is imported lazily; if it is missing or the
file cannot be parsed, a ValueError is raised so the caller can fall back.
"""

from __future__ import annotations

import base64
import os
from io import BytesIO

from app.models import Document

MAX_PAGES = int(os.getenv("WITNESS_MAX_PDF_PAGES", "20"))


class PdfReader:
    name = "pdf"

    def read(self, packet: dict) -> list[Document]:
        documents: list[Document] = []
        for index, raw in enumerate(packet.get("documents", [])):
            base_id = str(raw.get("doc_id") or f"d{index + 1}")
            title = str(raw.get("title") or base_id)
            if raw.get("pdf_base64"):
                documents.extend(self._read_pdf(base_id, title, str(raw["pdf_base64"])))
            else:
                documents.append(Document(doc_id=base_id, title=title, text=str(raw.get("text", ""))))
        return documents

    def _read_pdf(self, base_id: str, title: str, payload: str) -> list[Document]:
        try:
            data = base64.b64decode(payload, validate=True)
        except Exception as exc:
            raise ValueError(f"'{title}' is not valid base64") from exc
        try:
            from pypdf import PdfReader as _PdfReader
        except ImportError as exc:
            raise ValueError("pypdf is not installed, cannot read PDFs") from exc

        try:
            reader = _PdfReader(BytesIO(data))
            pages = reader.pages[:MAX_PAGES]
        except Exception as exc:
            raise ValueError(f"could not parse PDF '{title}': {exc}") from exc

        documents: list[Document] = []
        for number, page in enumerate(pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            documents.append(
                Document(doc_id=f"{base_id}p{number}", title=f"{title} — page {number}", text=text)
            )
        return documents
