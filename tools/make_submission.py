"""Build the single submission PDF required by the handbook (sections 1-5).

Reads submission/submission.json and optional images from submission/shots/.
Missing links are rendered as clearly visible placeholders, so the document can be
generated now and finalised in one re-run once the video and posts exist.

Appends the four-page essay "Where the Human Comes In" as an appendix.

Run: python tools/make_submission.py
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "submission" / "submission.json"
OUT = REPO / "Witness_Submission.pdf"
ESSAY = REPO / "Witness_Where_The_Human_Comes_In.pdf"

INK = colors.HexColor("#0d1b26")
INK2 = colors.HexColor("#3d4f5e")
MUTED = colors.HexColor("#6b7c8c")
FAINT = colors.HexColor("#8b99a6")
ACCENT = colors.HexColor("#1b4dd8")
LINE = colors.HexColor("#dde3e9")
SOFT = colors.HexColor("#f4f6f8")
OK = colors.HexColor("#157347")
WARN = colors.HexColor("#8a5a00")
BAD = colors.HexColor("#b42318")

styles = getSampleStyleSheet()


def st(name, **kwargs):
    base = dict(
        fontName="Helvetica",
        fontSize=9.6,
        leading=14,
        textColor=INK,
        spaceAfter=6,
    )
    base.update(kwargs)
    styles.add(ParagraphStyle(name, **base))
    return name


S_BODY = st("s_body")
S_SMALL = st("s_small", fontSize=8.4, leading=11.5, textColor=MUTED)
S_H1 = st("s_h1", fontName="Helvetica-Bold", fontSize=17, leading=21, spaceBefore=4, spaceAfter=10)
S_H2 = st("s_h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=ACCENT, spaceBefore=14, spaceAfter=5, keepWithNext=True)
S_H3 = st("s_h3", fontName="Helvetica-Bold", fontSize=9.8, leading=13, spaceBefore=8, spaceAfter=3, keepWithNext=True)
S_CELL = st("s_cell", fontSize=8.6, leading=11.5, spaceAfter=0)
S_CELLB = st("s_cellb", fontName="Helvetica-Bold", fontSize=8.6, leading=11.5, spaceAfter=0)
S_COVER = st("s_cover", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=INK, spaceAfter=4)
S_SUB = st("s_sub", fontSize=12.5, leading=17, textColor=MUTED, spaceAfter=16)
S_QUOTE = st("s_quote", fontName="Helvetica-Oblique", fontSize=10, leading=15, textColor=INK2,
             leftIndent=10, borderPadding=7, backColor=SOFT, spaceBefore=4, spaceAfter=10)


def P(text, style=S_BODY):
    return Paragraph(text, styles[style])


def table(rows, widths, header=True, zebra=True):
    body = []
    for r_i, row in enumerate(rows):
        converted = []
        for cell in row:
            if isinstance(cell, Paragraph):
                converted.append(cell)
            else:
                converted.append(P(str(cell), S_CELLB if (header and r_i == 0) else S_CELL))
        body.append(converted)
    t = Table(body, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), SOFT))
    if zebra:
        for i in range(1, len(body)):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fafbfc")))
    t.setStyle(TableStyle(cmds))
    return t


def placeholder(text):
    t = Table([[P(f"<b>{text}</b>", S_CELL)]], colWidths=[168 * mm], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#ecd9a8")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fdf6e3")),
                ("TEXTCOLOR", (0, 0), (-1, -1), WARN),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return t


def image_or_placeholder(path: Path, caption: str, width_mm=168, max_height_mm=105):
    if path and path.exists():
        from reportlab.lib.utils import ImageReader

        iw, ih = ImageReader(str(path)).getSize()
        w = width_mm * mm
        h = w * ih / iw
        if h > max_height_mm * mm:
            h = max_height_mm * mm
            w = h * iw / ih
        img = Image(str(path), width=w, height=h)
        img.hAlign = "LEFT"
        return [img, P(caption, S_SMALL)]
    return [placeholder(f"[ADD SCREENSHOT: {caption}]")]


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10.5 * mm, "Glue Sticks | Witness | Agentika 2.0 (NaSCon 2026)")
    canvas.drawRightString(A4[0] - 18 * mm, 10.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    team, project, links = cfg["team"], cfg["project"], cfg["links"]
    shots = cfg.get("screenshots", {})

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=20 * mm,
        title="Witness - Agentika 2.0 submission",
        author=team["name"],
    )
    s = []

    # ---------------- cover ----------------
    s.append(P("Witness", S_COVER))
    s.append(P("A human-in-the-loop decision desk for high-stakes eligibility screening", S_SUB))
    s.append(
        table(
            [
                ["Team", team["name"]],
                ["Event", "Agentika 2.0 - NaSCon 2026, FAST NUCES Islamabad"],
                ["Theme", "Human + AI: Better Together"],
                ["Live service", links["live"]],
                ["Repository", links["repo"]],
                ["Submitted", "17 October 2026"],
            ],
            [34 * mm, 134 * mm],
            header=False,
            zebra=False,
        )
    )
    s.append(Spacer(1, 8))
    s.append(
        P(
            "One-line pitch: <b>" + project["pitch"] + "</b>",
            S_QUOTE,
        )
    )
    s.append(PageBreak())

    # ---------------- 1. team ----------------
    s.append(P("1. Team details", S_H1))
    rows = [["Role", "Name", "Email", "Discord"]]
    for i, m in enumerate(team["members"], start=1):
        rows.append([f"Member {i}", m["name"], m["email"], m["discord"]])
    s.append(table(rows, [22 * mm, 48 * mm, 60 * mm, 38 * mm]))
    s.append(Spacer(1, 6))
    s.append(P(f"Team contact (WhatsApp): <b>{team['whatsapp']}</b>"))
    s.append(P(f"Team name: <b>{team['name']}</b>"))

    # ---------------- 2. project ----------------
    s.append(P("2. About the project", S_H1))
    s.append(P(f"<b>Project name.</b> {project['name']}"))
    s.append(P(f"<b>One-line pitch.</b> {project['pitch']}"))
    s.append(P("<b>The problem and who it is for.</b>"))
    s.append(P(project["problem"]))
    s.append(P("<b>Where the human comes in.</b>"))
    s.append(P(project["human"]))
    s.append(P("<b>What we built with.</b>"))
    s.append(P(project["built_with"]))

    s.append(P("What the AI may not do", S_H3))
    s.append(
        table(
            [
                ["Capability", "Automated pipeline", "Human officer"],
                ["Extract facts with citations", "Yes", "Reviews them"],
                ["Decide a policy clause", "No — code does", "May override, with a reason"],
                ["Recommend an outcome", "Yes", "May accept"],
                ["Produce a final denial", "Never", "Yes, with a written reason"],
                ["Clear a verifier abstention", "No", "Yes, recorded as an override"],
            ],
            [58 * mm, 55 * mm, 55 * mm],
        )
    )

    # ---------------- 3. links ----------------
    s.append(P("3. Required links", S_H1))
    s.append(
        table(
            [
                ["Item", "Link"],
                ["Live deployment (Alternate Clouds)", links["live"]],
                ["GitHub repository", links["repo"]],
                ["Demo video (2-3 minutes)", links["video"]],
                ["Original LinkedIn post", links["linkedin_post"]],
                ["Teammate reshare", links["linkedin_reshare"]],
                ["X / Twitter (optional)", links["x_post"] or "Not posted"],
            ],
            [62 * mm, 106 * mm],
        )
    )
    s.append(Spacer(1, 6))
    s.append(
        P(
            "The application has no login: every link above opens directly for the judges. "
            "No API keys or personal credentials appear in the repository, the video or these screenshots.",
            S_SMALL,
        )
    )

    # ---------------- 4. proof ----------------
    s.append(PageBreak())
    s.append(P("4. Proof", S_H1))
    s.append(P("Discord — both team members in the Alternate Futures server", S_H3))
    s.extend(image_or_placeholder(REPO / shots.get("discord", ""), "Discord membership, both members", 120, 80))
    s.append(Spacer(1, 6))
    s.append(P("Alternate Clouds — service and deployment status", S_H3))
    s.extend(image_or_placeholder(REPO / shots.get("clouds", ""), "Alternate Clouds dashboard (do not show environment variables)", 168, 95))

    app_shots = [REPO / p for p in shots.get("app", [])]
    existing = [p for p in app_shots if p.exists()]
    if existing:
        s.append(PageBreak())
        s.append(P("Application", S_H3))
        for path in existing:
            s.extend(image_or_placeholder(path, path.stem.replace("app-", "").replace("-", " ").title(), 168, 92))
            s.append(Spacer(1, 4))

    # ---------------- 5. confirmations ----------------
    s.append(P("5. Confirmations", S_H1))
    for line in [
        "We wrote our LinkedIn post ourselves. Only grammar-only tools were used.",
        "Our project is deployed on Alternate Clouds and will stay running until the closing ceremony.",
        "No API keys or personal or production passwords appear in our repository, video or screenshots.",
        "Third-party components are credited: FastAPI, Uvicorn, pypdf, ReportLab, and a hosted Groq model.",
        "We will not change our code or deployment after 12:45 PM PKT on 17 October.",
        "The policy we demonstrate is simplified and synthetic; it is not official government policy.",
    ]:
        s.append(P("<font color='#157347'><b>Confirmed.</b></font>  " + line))

    s.append(Spacer(1, 10))
    s.append(
        P(
            "<b>Verification at submission time.</b> The live service reports v0.5.0, an evaluation gate of "
            "55/55 expectations with grounding 0.971 and abstention 0.6, and the invariant that no case is "
            "automatically denied. The audit chain verifies on the running ledger.",
            S_SMALL,
        )
    )

    doc.build(s, onFirstPage=on_page, onLaterPages=on_page)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")

    # ---------------- appendix ----------------
    if ESSAY.exists():
        from pypdf import PdfReader, PdfWriter

        writer = PdfWriter()
        for page in PdfReader(str(OUT)).pages:
            writer.add_page(page)
        for page in PdfReader(str(ESSAY)).pages:
            writer.add_page(page)
        with open(OUT, "wb") as handle:
            writer.write(handle)
        print(f"appended essay; total pages = {len(PdfReader(str(OUT)).pages)}")


if __name__ == "__main__":
    build()
