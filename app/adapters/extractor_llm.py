"""LLM fact extractor.

The model proposes a value plus the exact quote it relies on. Witness then grounds
that quote verbatim in the source document. A quote the model invented does not
produce a citation, so the independent verifier abstains instead of trusting it.
Fields the model reports as absent are left out, which drives those rules to
UNKNOWN and therefore to a human.
"""

from __future__ import annotations

from app.adapters.llm_client import LLMClient
from app.models import Citation, Document, Fact
from app.schema import SCHEMA_BY_KEY, schema_block

SYSTEM = (
    "You are a careful information-extraction engine for a public benefits eligibility desk. "
    "You only output JSON. You never guess. If a field is not explicitly stated in the "
    "documents, you set its value to null. For every value you do extract you must copy the "
    "exact, character-for-character quote from the document that states it, and name the "
    "doc_id it came from."
)


class LLMExtractor:
    name = "llm"

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def extract(self, documents: list[Document], packet: dict) -> list[Fact]:
        if not documents:
            return []
        data = self._client.complete_json(SYSTEM, self._prompt(documents))
        raw_facts = data.get("facts", [])
        if not isinstance(raw_facts, list):
            raise ValueError("model did not return a 'facts' list")

        by_id = {document.doc_id: document for document in documents}
        facts: list[Fact] = []
        for item in raw_facts:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", ""))
            if key not in SCHEMA_BY_KEY:
                continue
            if item.get("value") is None:
                continue
            quote = str(item.get("quote") or "")
            document = by_id.get(str(item.get("doc_id") or "")) or self._find(documents, quote)
            facts.append(
                Fact(
                    key=key,
                    label=SCHEMA_BY_KEY[key].label,
                    value=item.get("value"),
                    citation=self._ground(document, quote),
                    method=self.name,
                )
            )
        return facts

    def _prompt(self, documents: list[Document]) -> str:
        doc_block = "\n\n".join(f"[{d.doc_id}] {d.title}\n{d.text}" for d in documents)
        return (
            "Extract these fields:\n"
            f"{schema_block()}\n\n"
            "Documents:\n"
            f"{doc_block}\n\n"
            "Return only this JSON shape:\n"
            '{"facts": [{"key": "<field>", "value": <int|bool|string|null>, '
            '"quote": "<exact text from the document>", "doc_id": "<doc_id>"}]}\n'
            "Use null for any field that is not present in the documents."
        )

    def _find(self, documents: list[Document], quote: str) -> Document | None:
        if not quote:
            return None
        for document in documents:
            if quote in document.text:
                return document
        return None

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
