"""Deterministic fixture extractor.

Each extraction spec carries the exact quote to locate in a source document. The
extractor grounds the fact by finding that quote verbatim and recording its span,
so later stages can re-check the grounding independently. The Stage 2 LLM
extractor replaces this without changing the Fact contract.
"""

from __future__ import annotations

from app.models import Citation, Document, Fact


class FixtureExtractor:
    name = "fixture"

    def extract(self, documents: list[Document], packet: dict) -> list[Fact]:
        facts: list[Fact] = []
        for spec in packet.get("extraction", []):
            key = str(spec["key"])
            quote = str(spec.get("quote", ""))
            document = self._pick(documents, spec.get("doc_id"))
            citation = self._ground(document, quote)
            facts.append(
                Fact(
                    key=key,
                    label=str(spec.get("label", key)),
                    value=spec.get("value"),
                    citation=citation,
                    method=self.name,
                )
            )
        return facts

    def _pick(self, documents: list[Document], doc_id: str | None) -> Document | None:
        if not documents:
            return None
        if doc_id:
            for document in documents:
                if document.doc_id == doc_id:
                    return document
        return documents[0]

    def _ground(self, document: Document | None, quote: str) -> Citation | None:
        if document is None or not quote:
            return None
        start = document.text.find(quote)
        if start < 0:
            return None
        return Citation(
            doc_id=document.doc_id,
            quote=quote,
            start=start,
            end=start + len(quote),
            grounded=True,
        )
