"""PDF intake test: a real (hand-built) PDF flows through the same pipeline.

Run: python tests/test_pdf.py
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ["AUDIT_DB"] = str(Path(os.environ.get("TEMP", ".")) / "witness_pdf_test.db")
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

from app.adapters.reader_pdf import PdfReader

LINES = [
    "Form B-1: Income Support Application",
    "Name: Hina Aslam",
    "Age: 44 years",
    "Province of residence: Punjab",
    "Household size: 5 persons",
    "Monthly household income: PKR 41,000",
    "Owns a car: No",
    "Land owned (acres): 1",
    "Bank balance: PKR 15,000",
]


def make_pdf(lines: list[str]) -> bytes:
    escaped = [line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)") for line in lines]
    body = "BT /F1 12 Tf 72 720 Td " + " ".join(f"({line}) Tj 0 -16 Td" for line in escaped) + " ET"
    content = body.encode("latin-1")
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        b"<</Length " + str(len(content)).encode() + b">>stream\n" + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def test_reader_extracts_pages():
    pdf = make_pdf(LINES)
    payload = base64.b64encode(pdf).decode()
    documents = PdfReader().read({"documents": [{"doc_id": "d1", "title": "Form", "pdf_base64": payload}]})
    assert documents, "no documents produced"
    text = "\n".join(document.text for document in documents)
    assert "Hina Aslam" in text, text
    assert documents[0].doc_id.startswith("d1p1"), documents[0].doc_id
    print(f"OK: PDF read into {len(documents)} page document(s)")


def test_pdf_reaches_eligible_decision():
    from fastapi.testclient import TestClient
    import app.main as main

    payload = base64.b64encode(make_pdf(LINES)).decode()
    with TestClient(main.app) as client:
        response = client.post(
            "/api/cases",
            json={
                "applicant_name": "Hina Aslam",
                "province": "Punjab",
                "documents": [{"title": "Form B-1", "pdf_base64": payload}],
            },
        )
        assert response.status_code == 200, response.text
        case = response.json()
        assert case["status"] == "VERIFIED", (case["status"], case["verification"]["reasons"])
        assert case["recommendation"]["outcome"] == "ELIGIBLE", case["recommendation"]
        assert all(fact["citation"] for fact in case["facts"]), case["facts"]
        assert any(fact["citation"]["doc_id"].startswith("d1p") for fact in case["facts"])
        print(f"OK: PDF case {case['id']} -> {case['status']} with {len(case['facts'])} grounded facts")

        bad = client.post(
            "/api/cases",
            json={"applicant_name": "Broken", "documents": [{"title": "bad", "pdf_base64": "not-base64!!"}]},
        )
        assert bad.status_code == 400, bad.text
        print("OK: invalid PDF payload rejected cleanly:", bad.json()["detail"])


def main() -> int:
    test_reader_extracts_pages()
    test_pdf_reaches_eligible_decision()
    print("ALL PDF TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
