"""Text/JSON reader: turns a case packet into source documents."""

from __future__ import annotations

from app.models import Document


class TextReader:
    name = "text"

    def read(self, packet: dict) -> list[Document]:
        documents: list[Document] = []
        for raw in packet.get("documents", []):
            doc_id = str(raw.get("doc_id", f"d{len(documents) + 1}"))
            documents.append(
                Document(
                    doc_id=doc_id,
                    title=str(raw.get("title", doc_id)),
                    text=str(raw.get("text", "")),
                )
            )
        return documents
