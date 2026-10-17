"""Generate the submission PDF: "Where the Human Comes In".

Facts here are taken from the running service (v0.5.0):
the 7 policy clauses, the status machine, the decision gate, the audit ledger,
and the verified evaluation gate (55/55).

Run: python tools/make_pdf.py
Output: Witness_Where_The_Human_Comes_In.pdf (repository root)
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "Witness_Where_The_Human_Comes_In.pdf"
LIVE = "https://alternate-echo-whale-5578-github-app.alternatefutures.ai"

INK = colors.HexColor("#12202e")
MUTED = colors.HexColor("#5b6b7a")
ACCENT = colors.HexColor("#2f5fd0")
LINE = colors.HexColor("#c9d4de")
SOFT = colors.HexColor("#eef3f8")
WARN = colors.HexColor("#8a5a00")

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        "Body2",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.6,
        leading=14.2,
        textColor=INK,
        spaceAfter=6,
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        "H1x",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=INK,
        spaceBefore=12,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        "H2x",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=ACCENT,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        "Small2",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=11,
        textColor=MUTED,
    )
)
styles.add(
    ParagraphStyle(
        "CellT",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.3,
        leading=11,
        textColor=INK,
    )
)
styles.add(
    ParagraphStyle(
        "CellB",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8.3,
        leading=11,
        textColor=INK,
    )
)
styles.add(
    ParagraphStyle(
        "Quote2",
        parent=styles["BodyText"],
        fontName="Helvetica-Oblique",
        fontSize=9.6,
        leading=14,
        textColor=INK,
        leftIndent=10,
        borderPadding=6,
        backColor=SOFT,
        spaceBefore=4,
        spaceAfter=8,
    )
)


def P(text: str, style: str = "Body2"):
    return Paragraph(text, styles[style])


def bullets(items: list[str]):
    return [P("• " + item) for item in items]


def table(rows, widths, header=True, zebra=True):
    body = []
    for r_index, row in enumerate(rows):
        converted = []
        for c_index, cell in enumerate(row):
            if isinstance(cell, Paragraph):
                converted.append(cell)
            else:
                converted.append(P(str(cell), "CellB" if (header and r_index == 0) else "CellT"))
        body.append(converted)
    t = Table(body, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), SOFT))
    if zebra:
        for i in range(1, len(body)):
            if i % 2 == 0:
                commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7fafc")))
    t.setStyle(TableStyle(commands))
    return t


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10.5 * mm, "Witness - Agentika 2.0 - Human + AI: Better Together")
    canvas.drawRightString(A4[0] - 18 * mm, 10.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build() -> None:
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=20 * mm,
        title="Where the Human Comes In - Witness",
        author="Witness (GlueSticks)",
        subject="Structural human oversight for high-stakes AI decisions",
    )

    story = []

    # ---- Cover block -----------------------------------------------------
    story.append(P("Where the Human Comes In", "H1x"))
    story.append(
        P(
            '<font color="#5b6b7a" size="11">A structural human gate for high-stakes AI decisions</font>',
            "Body2",
        )
    )
    story.append(Spacer(1, 4))
    story.append(
        table(
            [
                ["Project", "Witness - a human-in-the-loop decision desk"],
                ["Event", "Agentika 2.0 (NaSCon'26, FAST NUCES Islamabad)"],
                ["Theme", "Human + AI: Better Together"],
                ["Live service", LIVE],
                ["Version / build", "0.5.0"],
                ["Date", "17 October 2026"],
            ],
            [36 * mm, 138 * mm],
            header=False,
            zebra=False,
        )
    )
    story.append(Spacer(1, 8))

    story.append(
        P(
            "Witness screens applicants for a simplified, synthetic income-support programme. "
            "A language model extracts evidence; ordinary code decides the rules; an independent "
            "check audits the result; and a human officer makes the decision. The question this "
            "document answers is narrow and deliberate: <b>where, exactly, does the human come in, "
            "and what stops the machine from deciding without them?</b>",
        )
    )
    story.append(
        P(
            "The short answer: the human is not a reviewer bolted on after the fact. The automated "
            "pipeline is structurally incapable of producing a denial. Its strongest possible output "
            "is <b>NEEDS_REVIEW</b>. <b>DENIED</b> exists only as the result of an explicit human action, "
            "recorded with the officer's name and a written reason in a tamper-evident ledger.",
            "Quote2",
        )
    )

    # ---- 1 ---------------------------------------------------------------
    story.append(P("1. The failure we design against", "H2x"))
    story.append(
        P(
            "In benefits screening the costly errors are asymmetric. A wrongly denied applicant may lose "
            "food support; a wrongly approved one costs money. Worse, an automated denial is hard to "
            "contest because nobody is accountable for it. Two common designs fail here:",
        )
    )
    story += bullets(
        [
            "<b>The autonomous scorer.</b> A model outputs approve/deny. It is fast, but a denial has no owner "
            "and no reviewable basis.",
            "<b>The cosmetic reviewer.</b> A person clicks 'confirm' on whatever the model produced. The human "
            "step exists on the diagram but has no authority and no information advantage.",
        ]
    )
    story.append(
        P(
            "Witness rejects both. The machine is allowed to be useful without being allowed to be final, "
            "and the human is given both the authority and the evidence needed to exercise it.",
        )
    )

    # ---- 2 ---------------------------------------------------------------
    story.append(P("2. The rule: the human is a stage in the pipeline", "H2x"))
    story.append(
        P(
            "Case state is a closed set. The automated pipeline can only move a case into VERIFIED or "
            "NEEDS_REVIEW. Both are pre-decision states. A final state requires a human decision.",
        )
    )
    story.append(
        table(
            [
                ["State", "Reached by", "Final?"],
                ["INTAKE", "Case received", "No"],
                ["VERIFIED", "Every rule PASS, every citation grounded, verifier OK", "No - awaiting officer"],
                ["NEEDS_REVIEW", "A rule FAILed, a rule is UNKNOWN, or the verifier abstained", "No - awaiting officer"],
                ["APPROVED", "Human officer approves, with a written reason", "Yes"],
                ["DENIED", "Human officer denies, with a written reason", "Yes"],
                ["INFO_REQUESTED", "Human officer asks for more evidence", "No - case reopens"],
            ],
            [30 * mm, 118 * mm, 26 * mm],
        )
    )
    story.append(Spacer(1, 4))
    story.append(
        P(
            "There is no code path in which the pipeline writes APPROVED or DENIED. This is enforced by the "
            "store's decision gate, not by a prompt instruction: only the human decision endpoint can set a "
            "final state, and it refuses to act on a case that is not in a decidable state.",
        )
    )

    # ---- 3 ---------------------------------------------------------------
    story.append(P("3. The pipeline, stage by stage", "H2x"))
    story.append(
        table(
            [
                ["Stage", "What it does", "What it may not do"],
                ["Reader", "Turns a text or PDF case packet into documents (PDF pages become citable units).", "Invent evidence."],
                ["Extractor", "Proposes a value plus the exact quote it came from; the quote is re-grounded verbatim.", "Return a fact without a verbatim citation."],
                ["Rules engine", "Ordinary Python compares grounded facts to published thresholds; each rule cites a clause.", "Let the model decide a rule."],
                ["Verifier", "Re-audits grounding, contradictions and undecided rules; may only ADD an abstention.", "Clear a deterministic failure or approve a case."],
                ["Human officer", "Approves, denies, or requests information - with a mandatory written reason.", "Decide without an identity or a reason."],
                ["Audit ledger", "Appends a SHA-256 hash-chained entry for every state change.", "Rewrite history undetected."],
            ],
            [26 * mm, 85 * mm, 63 * mm],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        P(
            "Two properties matter more than the individual stages. First, the model's opinion can only make "
            "the outcome <i>more cautious</i>: the LLM verifier may add an abstention but never removes a rule "
            "failure. Second, every claimed fact must survive a verbatim check against its source document, so a "
            "hallucinated quote produces no citation and the verifier abstains.",
        )
    )

    # ---- 4 ---------------------------------------------------------------
    story.append(P("4. Where the human acts", "H2x"))
    story.append(
        P(
            "An officer sees the evidence - each fact next to the exact quoted span - the rule results, the "
            "verifier's checks, and any conflicting values side by side. They then choose one of three actions:",
        )
    )
    story += bullets(
        [
            "<b>Approve</b> or <b>deny</b>: a final decision. A denial is possible <i>only</i> here.",
            "<b>Request more information</b>: the case becomes INFO_REQUESTED. New evidence is appended and the "
            "pipeline re-runs from the top; the case reopens with no decision attached.",
        ]
    )
    story.append(
        P(
            "The backend enforces the terms of the act, not just the UI: the officer name must be non-empty, the "
            "reason must contain real text, the action must be one of the three, and the case must be in "
            "VERIFIED or NEEDS_REVIEW. Duplicate decisions and invalid transitions are rejected. When an officer "
            "decides a case the verifier had abstained on, the ledger records <b>overrode_abstention: true</b>, so "
            "the override is visible rather than silent.",
        )
    )

    # ---- 5 ---------------------------------------------------------------
    story.append(P("5. Abstention instead of guessing", "H2x"))
    story.append(
        P(
            "The verifier is designed to refuse. It abstains, and forces NEEDS_REVIEW, when any of the following "
            "is true:",
        )
    )
    story += bullets(
        [
            "a fact's citation quote does not appear <b>verbatim</b> in its source document;",
            "the same field carries <b>conflicting</b> values across documents;",
            "a rule cannot be decided because its evidence is missing, unreadable, or contradictory.",
        ]
    )
    story.append(
        P(
            "This is the opposite of a confident chatbot. An abstention is a successful outcome: it routes an "
            "uncertain case to the person who is allowed to resolve it, instead of manufacturing a plausible "
            "answer. In the live evaluation set, 3 of 5 seeded cases abstain for exactly these reasons.",
        )
    )

    # ---- 6 ---------------------------------------------------------------
    story.append(P("6. Rules are code, not vibes", "H2x"))
    story.append(
        P(
            "Seven clauses are evaluated deterministically. The model never decides a rule, and each result "
            "names the clause it implements, so a decision traces back to written policy.",
        )
    )
    story.append(
        table(
            [
                ["Clause", "Rule id", "Plain rule", "Threshold"],
                ["1", "AGE_ADULT", "Applicant is 18 or older", "age >= 18"],
                ["2", "RESIDENCY", "Resident in a covered region", "province in covered list"],
                ["3", "HOUSEHOLD_SIZE", "Household size recorded", "household_size >= 1"],
                ["4", "INCOME_LIMIT", "Monthly income within limit", "monthly_income_pkr <= 60,000"],
                ["5", "ASSET_CAR", "No car declared", "owns_car == false"],
                ["6", "ASSET_LAND", "Land holding within limit", "land_acres <= 2"],
                ["7", "BANK_BALANCE", "Liquid savings within limit", "bank_balance_pkr <= 50,000"],
            ],
            [17 * mm, 30 * mm, 68 * mm, 59 * mm],
        )
    )
    story.append(Spacer(1, 4))
    story.append(
        P(
            "<b>Disclaimer.</b> The rule set is simplified, synthetic and BISP-inspired. It is a demonstration and "
            "does not represent the official policy of BISP or of any government or agency. Thresholds are "
            "illustrative.",
            "Small2",
        )
    )

    # ---- 7 ---------------------------------------------------------------
    story.append(P("7. Accountability: a hash-chained ledger", "H2x"))
    story.append(
        P(
            "Every state change is appended to an append-only ledger. Each entry stores the hash of the previous "
            "entry, so altering or removing a single field breaks verification at that point. "
            "<b>GET /api/audit/verify</b> recomputes the whole chain and reports the first break.",
        )
    )
    story.append(
        P(
            "The ledger is also written <b>before</b> in-memory state changes. If the ledger cannot be written, the "
            "API returns 503 and the case is left unchanged. A decision can therefore never appear to succeed "
            "without a record. This matters because a verifying chain proves <i>integrity</i>, not <i>durability</i>; "
            "Witness is explicit about the difference.",
        )
    )
    story.append(
        P(
            "A live demonstration endpoint, <b>POST /api/audit/tamper-demo</b>, tampers with an in-memory copy of the "
            "ledger, shows the chain breaking exactly at the forged entry, and then re-verifies the untouched "
            "ledger to show the real record is intact.",
        )
    )

    # ---- 8 ---------------------------------------------------------------
    story.append(P("8. What the AI is not allowed to do", "H2x"))
    story.append(
        table(
            [
                ["Capability", "Automated pipeline", "Human officer"],
                ["Extract facts with citations", "Yes", "Reviews them"],
                ["Decide a policy rule", "No (code does)", "May override with a reason"],
                ["Produce ELIGIBLE recommendation", "Yes", "May accept"],
                ["Produce a final denial", "<b>Never</b>", "Yes, with a written reason"],
                ["Clear a verifier abstention", "No", "Yes, recorded as overrode_abstention"],
                ["Write the audit entry", "Yes", "The entry names the officer"],
            ],
            [55 * mm, 55 * mm, 64 * mm],
        )
    )

    # ---- 9 ---------------------------------------------------------------
    story.append(P("9. Evidence from the live service", "H2x"))
    story.append(
        table(
            [
                ["Check", "Live result (17 Oct 2026)"],
                ["Startup evaluation gate", "55 / 55 expectations met; all_passed = true"],
                ["Grounding rate", "0.971 (facts carrying a verbatim citation)"],
                ["Abstain rate", "0.6 (cases escalated instead of guessed)"],
                ["No-auto-deny invariant", "true (pre-human states: INTAKE, VERIFIED, NEEDS_REVIEW)"],
                ["Audit chain", "verifies on the live ledger"],
                ["Deployed build", "v0.5.0"],
            ],
            [52 * mm, 122 * mm],
        )
    )

    # ---- 10 --------------------------------------------------------------
    story.append(P("10. Honest limits", "H2x"))
    story += bullets(
        [
            "<b>The ledger is local to the deployment.</b> It survives a process restart and is reset "
            "when the service is redeployed. A verifying hash chain proves integrity, not durability, "
            "and the interface states that rather than implying otherwise.",
            "<b>The policy is synthetic.</b> The rules are a demonstration of structure, not real "
            "eligibility law. Thresholds are illustrative.",
            "<b>Unfamiliar documents abstain.</b> If a pasted case does not contain the expected form "
            "labels, the fields stay unknown and the case is escalated instead of guessed.",
        ]
    )

    # ---- 11 --------------------------------------------------------------
    story.append(P("11. Verify it in sixty seconds", "H2x"))
    story.append(
        P(
            f"Open <font color='#2f5fd0'>{LIVE}</font> and try the following. Each step is a live check on the "
            "production service.",
        )
    )
    story.append(
        table(
            [
                ["What to do", "What it proves"],
                ["Open /api/eval", "The gate re-runs: 55/55, grounding, abstain rate, no_auto_deny."],
                ["Open a case with a contradiction (CASE-2026-0003)", "The verifier abstains; state is NEEDS_REVIEW, never DENIED."],
                ["Try to deny with an empty reason", "The backend returns 400; a human act requires a reason."],
                ["Approve a case, then reopen its audit trail", "The officer, reason, timestamp and hash are recorded."],
                ["Open the Activity tab and press 'Verify ledger'", "The chain recomputes to an intact head."],
                ["Press 'Simulate tampering'", "A forged copy breaks at the changed entry; the real ledger stays intact."],
                ["Open About", "The page states exactly which reader, model, verifier and ledger are running."],
            ],
            [62 * mm, 112 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        P(
            "The design claim is deliberately modest and testable: the machine may propose, an independent check "
            "may refuse, and only a named person may decide. Everything else in Witness exists to make that "
            "sentence true in code, visible in the interface, and provable from the ledger.",
            "Quote2",
        )
    )
    story.append(Spacer(1, 6))
    story.append(P(f"Live service: {LIVE}", "Small2"))
    story.append(P("Repository: https://github.com/anithepani/GlueSticks-agentika", "Small2"))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
