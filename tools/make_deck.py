"""Build the finalist pitch deck in the Alternate Futures brand system.

Brand rules applied (docs.alternatefutures.ai/brand-guide):
  - Cream #F9F5EE page backgrounds (never pure white); Dark Blue #0000AF headings;
    body #1A1A1A; Brand Blue #000AFF on every slide; Terracotta #BE4200 for alerts
    and deck decoration only.
  - Instrument Sans for headings/body, Instrument Serif italic for taglines only,
    JetBrains Mono for URLs, image tags and technical labels.
  - Geometry: stars + rings only (max 2 types), 3-5 stars scattered asymmetrically,
    6-30% opacity on light backgrounds.

Run: python tools/make_deck.py
Output: Witness_Finalist_Deck.pptx (+ PDF via tools/export_deck.ps1)
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "submission" / "deck-assets"
OUT = REPO / "Witness_Finalist_Deck.pptx"

# ---------------------------------------------------------------- brand tokens
CREAM = RGBColor(0xF9, 0xF5, 0xEE)
DARK_BLUE = RGBColor(0x00, 0x00, 0xAF)
BRAND_BLUE = RGBColor(0x00, 0x0A, 0xFF)
TERRACOTTA = RGBColor(0xBE, 0x42, 0x00)
MED_BLUE = RGBColor(0xA5, 0xB2, 0xFF)
APRICOT = RGBColor(0xFF, 0xC7, 0xAA)
SKY = RGBColor(0xC8, 0xE0, 0xE4)
INK = RGBColor(0x1A, 0x1A, 0x1A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SANS = "Instrument Sans"
SERIF = "Instrument Serif"
MONO = "JetBrains Mono"

W, H = 13.333, 7.5
M = 0.85  # left margin


def rgba_alpha(shape, pct: int) -> None:
    """Set solid-fill transparency (python-pptx has no API for this)."""
    from pptx.oxml.ns import qn

    fill = shape.fill
    fill.solid()
    srgb = fill.fore_color._xFill
    for child in list(srgb):
        if child.tag == qn("a:alpha"):
            srgb.remove(child)
    alpha = srgb.makeelement(qn("a:alpha"), {"val": str(int(pct * 1000))})
    srgb.append(alpha)


def new_slide(prs, bg=CREAM):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    back = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    back.line.fill.background()
    back.fill.solid()
    back.fill.fore_color.rgb = bg
    back.shadow.inherit = False
    return slide


def text(
    slide,
    value,
    x,
    y,
    w,
    h,
    size=16,
    color=INK,
    font=SANS,
    bold=False,
    italic=False,
    align=PP_ALIGN.LEFT,
    spacing=1.15,
    space_after=0,
    tracking=None,
    anchor=MSO_ANCHOR.TOP,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = value.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(space_after)
        run = p.add_run()
        run.text = line
        f = run.font
        f.name = font
        f.size = Pt(size)
        f.bold = bold
        f.italic = italic
        f.color.rgb = color
        if tracking is not None:
            run.font._element.set("spc", str(int(tracking)))
    return box


def rule(slide, x, y, w, color=BRAND_BLUE, thickness=2.0):
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Pt(thickness))
    line.fill.solid()
    line.fill.fore_color.rgb = color
    line.line.fill.background()
    line.shadow.inherit = False
    return line


def star(slide, x, y, size, color=BRAND_BLUE, alpha=18, rotation=0):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.STAR_4_POINT, Inches(x), Inches(y), Inches(size), Inches(size)
    )
    shape.line.fill.background()
    shape.shadow.inherit = False
    shape.rotation = rotation
    rgba_alpha(shape, alpha)
    return shape


def ring(slide, x, y, size, color=BRAND_BLUE, alpha=22, width=1.6):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(size), Inches(size))
    shape.fill.background()
    shape.shadow.inherit = False
    shape.line.color.rgb = color
    shape.line.width = Pt(width)
    from pptx.oxml.ns import qn

    ln = shape.line._get_or_add_ln()
    solid = ln.find(qn("a:solidFill"))
    if solid is not None:
        srgb = solid.find(qn("a:srgbClr"))
        if srgb is not None:
            alpha_el = srgb.makeelement(qn("a:alpha"), {"val": str(int(alpha * 1000))})
            srgb.append(alpha_el)
    return shape


def eyebrow(slide, value, x=M, y=0.72, color=BRAND_BLUE, width=6.0):
    return text(slide, value.upper(), x, y, width, 0.3, size=10, color=color, font=MONO, tracking=180)


def heading(slide, value, x=M, y=1.12, w=11.6, size=42, color=DARK_BLUE):
    return text(slide, value, x, y, w, 1.5, size=size, color=color, bold=True, spacing=1.02)


def footer(slide, number, dark=False):
    color = RGBColor(0x9A, 0x94, 0x8A) if not dark else RGBColor(0x8E, 0x8E, 0xD8)
    text(slide, "Glue Sticks  |  Witness  |  Agentika 2.0", M, 7.05, 6.0, 0.3, size=9, color=color, font=MONO)
    text(slide, f"{number:02d}", 12.0, 7.05, 0.48, 0.3, size=9, color=color, font=MONO, align=PP_ALIGN.RIGHT)
    rule(slide, M, 6.95, W - 2 * M, BRAND_BLUE if not dark else RGBColor(0x44, 0x44, 0xD0), 0.75)


def notes(slide, value):
    slide.notes_slide.notes_text_frame.text = value


def picture(slide, path, x, y, w=None, h=None, border=True):
    kwargs = {}
    if w:
        kwargs["width"] = Inches(w)
    if h:
        kwargs["height"] = Inches(h)
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), **kwargs)
    if border:
        pic.line.color.rgb = RGBColor(0xC9, 0xC2, 0xB6)
        pic.line.width = Pt(0.75)
    pic.shadow.inherit = False
    return pic


def caption(slide, value, x, y, w=6.0, color=None):
    return text(slide, value, x, y, w, 0.3, size=9, color=color or RGBColor(0x7A, 0x74, 0x69), font=MONO)


def bullet_block(slide, items, x, y, w, size=15, color=INK, gap=0.58):
    for i, item in enumerate(items):
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y + i * gap + 0.09), Inches(0.07), Inches(0.07))
        dot.fill.solid()
        dot.fill.fore_color.rgb = BRAND_BLUE
        dot.line.fill.background()
        dot.shadow.inherit = False
        text(slide, item, x + 0.26, y + i * gap, w - 0.26, gap, size=size, color=color, spacing=1.18)


def card(slide, x, y, w, h, fill=WHITE, border=RGBColor(0xE2, 0xDA, 0xCC), bw=0.75):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.adjustments[0] = 0.06
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = border
    shape.line.width = Pt(bw)
    shape.shadow.inherit = False
    return shape


# ---------------------------------------------------------------- slides
def slide_cover(prs):
    s = new_slide(prs, BRAND_BLUE)

    star(s, 11.05, 0.85, 0.34, APRICOT, 55, 12)
    star(s, 12.05, 1.72, 0.16, CREAM, 32, 24)
    star(s, 11.62, 2.62, 0.24, APRICOT, 38, -8)
    star(s, 12.42, 4.05, 0.13, CREAM, 26, 0)
    star(s, 10.72, 5.42, 0.2, APRICOT, 26, 16)
    ring(s, 11.28, 5.62, 3.3, APRICOT, 30, 1.4)

    eyebrow(s, "Agentika 2.0  ·  NaSCon 2026", M, 1.62, APRICOT, 7.0)
    text(s, "Witness", M, 1.95, 8.6, 1.55, size=80, color=CREAM, bold=True, spacing=0.98)
    text(
        s,
        "AI proposes. A check audits. A human decides.",
        M,
        3.62,
        8.4,
        0.7,
        size=25,
        color=APRICOT,
        font=SERIF,
        italic=True,
    )
    rule(s, M, 4.62, 1.5, CREAM, 2.0)
    text(
        s,
        "A decision desk for high-stakes eligibility screening,\n"
        "where the automated pipeline has no way to deny an application.",
        M,
        4.88,
        7.2,
        1.1,
        size=15,
        color=RGBColor(0xE8, 0xE4, 0xF7),
        spacing=1.35,
    )
    text(s, "Glue Sticks", M, 6.28, 3.0, 0.3, size=11, color=CREAM, font=MONO, bold=True)
    text(s, "Aryan Zia  ·  Muhammad Rubait Zakria", M, 6.56, 5.2, 0.3, size=11, color=RGBColor(0xCF, 0xCB, 0xF0), font=MONO)
    text(s, "witness  ·  live on Clouds", 9.55, 6.28, 3.1, 0.3, size=9, color=RGBColor(0xB9, 0xB4, 0xEE), font=MONO, align=PP_ALIGN.RIGHT)
    notes(s, "Witness. Two students, one deployed system. The claim is narrow and testable: the machine may propose, an independent check may refuse, and only a named person may decide.")


def slide_problem(prs):
    s = new_slide(prs)
    eyebrow(s, "The problem")
    heading(s, "A denial has no owner.", size=46)

    card(s, M, 2.62, 5.5, 2.25)
    text(s, "01   The autonomous scorer", M + 0.34, 2.88, 4.8, 0.3, size=12, color=BRAND_BLUE, font=MONO, bold=True)
    text(
        s,
        "A model issues approve or deny. It is fast, but a refusal has\n"
        "no reviewable basis and nobody accountable for it.",
        M + 0.34,
        3.28,
        4.85,
        1.3,
        size=14.5,
        spacing=1.3,
    )

    card(s, M + 5.85, 2.62, 5.5, 2.25)
    text(s, "02   The cosmetic reviewer", M + 6.19, 2.88, 4.8, 0.3, size=12, color=BRAND_BLUE, font=MONO, bold=True)
    text(
        s,
        "A person clicks confirm on whatever the model produced.\n"
        "The human step exists on the diagram but holds no authority.",
        M + 6.19,
        3.28,
        4.85,
        1.3,
        size=14.5,
        spacing=1.3,
    )

    rule(s, M, 5.28, 1.1, TERRACOTTA, 3.0)
    text(
        s,
        "In benefits screening the cost of error is asymmetric. A wrongly refused applicant\n"
        "loses support, and an automated refusal is the hardest kind to contest.",
        M,
        5.48,
        11.4,
        1.0,
        size=15,
        color=INK,
        spacing=1.35,
    )

    star(s, 11.9, 6.05, 0.18, BRAND_BLUE, 14, 20)
    star(s, 12.5, 6.42, 0.11, BRAND_BLUE, 20, 0)
    footer(s, 2)
    notes(s, "Two failure modes, both common. An autonomous scorer puts the cost of error on the applicant; a cosmetic reviewer gives the appearance of oversight without the substance.")


def slide_rule(prs):
    s = new_slide(prs)
    eyebrow(s, "The design rule")
    heading(s, "The human is a stage, not a reviewer.", size=44)

    box_y = 2.72
    bw, bh = 1.95, 0.78
    xs = [M, M + 2.55, M + 5.1, M + 7.65]
    labels = [
        ("Received", "Case packet read"),
        ("Verified", "Every clause met"),
        ("Needs review", "Doubt or failure"),
        ("Officer decides", "Named, with a reason"),
    ]
    for i, (title, sub) in enumerate(labels):
        fill = BRAND_BLUE if i == 3 else WHITE
        fg = WHITE if i == 3 else INK
        sub_fg = RGBColor(0xDD, 0xE0, 0xFF) if i == 3 else RGBColor(0x6B, 0x66, 0x5C)
        card(s, xs[i], box_y, bw, bh, fill, BRAND_BLUE if i == 3 else RGBColor(0xDD, 0xD5, 0xC7))
        text(s, title, xs[i] + 0.16, box_y + 0.13, bw - 0.3, 0.3, size=12.5, color=fg, bold=True)
        text(s, sub, xs[i] + 0.16, box_y + 0.44, bw - 0.28, 0.28, size=9.5, color=sub_fg, font=MONO)
        if i < 3:
            arrow = s.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW, Inches(xs[i] + bw + 0.13), Inches(box_y + 0.29), Inches(0.28), Inches(0.19)
            )
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = BRAND_BLUE
            arrow.line.fill.background()
            arrow.shadow.inherit = False

    # outcomes of the officer stage
    text(s, "Outcomes of the officer stage", 6.55, 3.66, 4.8, 0.26, size=9, color=RGBColor(0x7A, 0x74, 0x69), font=MONO)
    outs = [("Approved", BRAND_BLUE), ("Denied", TERRACOTTA), ("Info requested", BRAND_BLUE)]
    for i, (title, color) in enumerate(outs):
        x = 6.55 + i * 2.0
        card(s, x, 3.96, 1.85, 0.4, WHITE, RGBColor(0xDD, 0xD5, 0xC7))
        text(s, title, x + 0.16, 4.03, 1.6, 0.26, size=10, color=color, bold=True)

    callout = card(s, M, 4.72, 11.6, 1.28, SKY, RGBColor(0xA9, 0xC4, 0xCA))
    text(
        s,
        "No code path in the automated pipeline writes Approved or Denied.",
        M + 0.34,
        4.96,
        10.9,
        0.4,
        size=17,
        color=DARK_BLUE,
        bold=True,
    )
    text(
        s,
        "The lowest state the pipeline can reach is Needs review. A final decision exists only as a recorded human act.",
        M + 0.34,
        5.38,
        10.8,
        0.4,
        size=12.5,
        color=RGBColor(0x2A, 0x4A, 0x52),
    )

    star(s, 12.15, 1.02, 0.16, BRAND_BLUE, 16, 18)
    star(s, 12.55, 1.5, 0.1, BRAND_BLUE, 22, 0)
    footer(s, 3)
    notes(s, "Case state is a closed set. Verified and Needs review are both pre-decision. Denied is only produced by an explicit officer action, which is recorded.")


def slide_pipeline(prs):
    s = new_slide(prs)
    eyebrow(s, "How a case moves")
    heading(s, "Six steps, one of which is a person.", size=40)

    steps = [
        ("01", "Read", "PDF or text becomes citable documents"),
        ("02", "Extract", "A model proposes values with quotations"),
        ("03", "Ground", "Each quotation is checked verbatim"),
        ("04", "Clauses", "Seven rules evaluated in code"),
        ("05", "Verify", "An independent check may abstain"),
        ("06", "Decide", "An officer records the decision"),
    ]
    top = 2.55
    cw = 1.72
    gap = 0.22
    for i, (num, title, desc) in enumerate(steps):
        x = M + i * (cw + gap)
        accent = i == 5
        card(s, x, top, cw, 2.55, BRAND_BLUE if accent else WHITE, BRAND_BLUE if accent else RGBColor(0xDD, 0xD5, 0xC7))
        text(s, num, x + 0.2, top + 0.2, 0.6, 0.3, size=10, color=APRICOT if accent else BRAND_BLUE, font=MONO, bold=True)
        text(s, title, x + 0.2, top + 0.52, cw - 0.4, 0.35, size=15, color=WHITE if accent else DARK_BLUE, bold=True)
        text(
            s,
            desc,
            x + 0.2,
            top + 1.02,
            cw - 0.38,
            1.3,
            size=10.5,
            color=RGBColor(0xDF, 0xE2, 0xFF) if accent else RGBColor(0x5C, 0x57, 0x4E),
            spacing=1.3,
        )

    text(
        s,
        "The model may add caution. It cannot remove it: an abstention is always allowed, a failed clause is never cleared.",
        M,
        5.48,
        11.4,
        0.7,
        size=14,
        color=INK,
        spacing=1.3,
    )
    rule(s, M, 5.34, 1.0, BRAND_BLUE, 3.0)

    star(s, 11.95, 6.18, 0.14, BRAND_BLUE, 18, 12)
    star(s, 12.45, 6.5, 0.09, BRAND_BLUE, 24, 0)
    footer(s, 4)
    notes(s, "Five of the six steps are automated. The sixth is a person, and it is the only one that can end a case.")


def slide_evidence(prs):
    s = new_slide(prs)
    eyebrow(s, "Grounded evidence")
    heading(s, "Every value carries the sentence it came from.", size=38)

    text(
        s,
        "The extractor returns a value and an exact quotation. Witness re-reads the\n"
        "quotation against the source document before the value is used.",
        M,
        2.18,
        4.75,
        1.0,
        size=14,
        color=RGBColor(0x3A, 0x36, 0x2F),
        spacing=1.35,
    )
    bullet_block(
        s,
        [
            "A value without a verbatim quotation is not grounded.",
            "Clicking a source opens the document and highlights the span.",
            "An invented quotation produces no citation.",
        ],
        M,
        3.46,
        4.7,
        size=13.5,
        gap=0.72,
    )

    picture(s, ASSETS / "evidence.png", 5.92, 2.16, w=6.55)
    caption(s, "Evidence tab, case 2026-0001: value, quotation, source, grounding", 5.92, 5.98, 6.5)

    star(s, 0.62, 6.3, 0.13, BRAND_BLUE, 16, 8)
    footer(s, 5)
    notes(s, "Grounding is not a prompt instruction, it is a check. The quotation is compared to the document text, and a mismatch removes the citation.")


def slide_abstain(prs):
    s = new_slide(prs)
    eyebrow(s, "Abstention")
    heading(s, "The verifier is allowed to refuse.", size=42)

    picture(s, ASSETS / "conflict.png", 5.92, 2.2, w=6.55)
    caption(s, "Case 2026-0003: two income figures, both quoted, state stays Needs review", 5.92, 5.86, 6.6)

    text(
        s,
        "Three conditions force an abstention:",
        M,
        2.2,
        4.7,
        0.35,
        size=14,
        color=DARK_BLUE,
        bold=True,
    )
    bullet_block(
        s,
        [
            "Quoted text does not appear in the source.",
            "The same field holds conflicting values.",
            "A clause cannot be decided from the evidence.",
        ],
        M,
        2.72,
        4.8,
        size=13.5,
        gap=0.66,
    )
    card(s, M, 4.86, 4.72, 1.16, RGBColor(0xFB, 0xF1, 0xE9), RGBColor(0xE3, 0xB9, 0xA0))
    text(
        s,
        "An abstention is a success, not a failure:\nthe case reaches the person who can resolve it.",
        M + 0.28,
        5.06,
        4.2,
        0.8,
        size=12,
        color=TERRACOTTA,
        spacing=1.3,
    )

    star(s, 12.5, 6.42, 0.1, BRAND_BLUE, 20, 0)
    footer(s, 6)
    notes(s, "This is the opposite of a confident chatbot. In the seeded set, 60 percent of cases abstain for exactly these reasons, and all of them reach a person.")


def slide_gate(prs):
    s = new_slide(prs, DARK_BLUE)
    eyebrow(s, "The decision gate", color=APRICOT)
    heading(s, "The officer's decision is enforced by the backend.", size=36, color=CREAM)

    text(
        s,
        "The interface is not the safeguard. The rules live in the service.",
        M,
        2.15,
        5.5,
        0.4,
        size=13,
        color=RGBColor(0xC9, 0xC6, 0xF2),
    )
    bullet_block(
        s,
        [
            "An officer name is required.",
            "A written reason is required, and retained.",
            "Invalid or duplicate decisions are rejected.",
            "If the ledger cannot be written, the request fails and the case is unchanged.",
        ],
        M,
        2.72,
        5.5,
        size=13.5,
        color=CREAM,
        gap=0.82,
    )

    frame = card(s, 6.3, 2.06, 2.45, 3.72, CREAM, RGBColor(0x3A, 0x3A, 0xC8))
    pic = s.shapes.add_picture(str(ASSETS / "panel.png"), Inches(6.4), Inches(2.16), height=Inches(3.52))
    caption(s, "Officer panel: action, name, written reason", 6.3, 5.9, 3.2, RGBColor(0xB7, 0xB2, 0xEA))

    text(
        s,
        "An override of an abstention is\nrecorded explicitly, not silently.",
        9.05,
        2.6,
        3.2,
        0.9,
        size=12,
        color=APRICOT,
        font=SERIF,
        italic=True,
        spacing=1.35,
    )

    star(s, 11.6, 4.55, 0.2, APRICOT, 40, 14)
    star(s, 12.35, 5.0, 0.12, CREAM, 26, 0)
    ring(s, 11.2, 3.4, 2.2, APRICOT, 18, 1.2)
    footer(s, 7, dark=True)
    notes(s, "The backend validates the actor, the action, the reason and the case state. A decision cannot be written without a record.")


def slide_ledger(prs):
    s = new_slide(prs)
    eyebrow(s, "Accountability")
    heading(s, "Every decision is hash-chained.", size=42)

    picture(s, ASSETS / "activity.png", M, 2.2, w=6.5)
    caption(s, "Activity tab: append-only entries, verification and tamper simulation", M, 5.94, 6.5)

    text(s, "Each entry stores the hash of the one before it.", M + 6.86, 2.3, 4.4, 0.7, size=13.5, color=INK, spacing=1.3)
    bullet_block(
        s,
        [
            "Verification recomputes the whole chain.",
            "A forged copy breaks at the changed entry.",
            "The real ledger is never modified by the demo.",
        ],
        M + 6.86,
        3.06,
        4.3,
        size=12.5,
        gap=0.7,
    )
    card(s, M + 6.86, 5.3, 4.3, 0.92, SKY, RGBColor(0xA9, 0xC4, 0xCA))
    text(
        s,
        "Integrity is proven. Durability is stated, not implied.",
        M + 7.06,
        5.52,
        3.95,
        0.5,
        size=11.5,
        color=DARK_BLUE,
        bold=True,
    )

    star(s, 12.5, 6.42, 0.11, BRAND_BLUE, 22, 0)
    footer(s, 8)
    notes(s, "A verifying chain proves integrity, not durability. The interface says which one it is instead of implying more.")


def slide_quality(prs):
    s = new_slide(prs)
    eyebrow(s, "Quality gate")
    heading(s, "The service checks itself before it serves.", size=40)

    metrics = [
        ("55 / 55", "Recorded expectations met"),
        ("97.1%", "Facts with a verbatim quotation"),
        ("60%", "Cases escalated instead of guessed"),
        ("Holds", "No automatic denial, before a human"),
    ]
    for i, (value, label) in enumerate(metrics):
        x = M + i * 2.94
        card(s, x, 2.55, 2.72, 1.62, WHITE, RGBColor(0xDD, 0xD5, 0xC7))
        text(s, value, x + 0.26, 2.78, 2.2, 0.6, size=30, color=BRAND_BLUE, bold=True)
        text(s, label, x + 0.26, 3.44, 2.25, 0.6, size=10.5, color=RGBColor(0x5C, 0x57, 0x4E), spacing=1.2)

    text(
        s,
        "The gate runs at start-up over a fixed case set. With the strict setting enabled,\n"
        "a failing expectation stops the service from serving requests at all.",
        M,
        4.48,
        8.6,
        0.9,
        size=14,
        color=INK,
        spacing=1.35,
    )
    caption(s, "/api/eval  ·  17 October 2026  ·  version 0.5.0", M, 5.72, 7.0)

    card(s, 9.55, 4.4, 2.9, 1.5, CREAM, RGBColor(0xDD, 0xD5, 0xC7))
    text(s, "7", 9.8, 4.58, 0.6, 0.5, size=26, color=DARK_BLUE, bold=True)
    text(s, "policy clauses,\neach traceable to a written rule", 9.8, 5.06, 2.4, 0.7, size=10.5, color=RGBColor(0x5C, 0x57, 0x4E), spacing=1.2)

    star(s, 12.45, 1.1, 0.15, BRAND_BLUE, 16, 12)
    footer(s, 9)
    notes(s, "Every number here is from the running service, not a slide. The gate is the reason we can claim reliability: it is checked, not asserted.")


def slide_live(prs):
    s = new_slide(prs)
    eyebrow(s, "Deployment")
    heading(s, "Live on Clouds by Alternate Futures.", size=38)

    text(
        s,
        "One container, one port, one public URL. The model is a dependency with a\n"
        "deterministic fallback, not a single point of failure.",
        M,
        2.18,
        7.4,
        0.9,
        size=13.5,
        color=INK,
        spacing=1.35,
    )

    card(s, M, 3.24, 7.45, 1.62, WHITE, RGBColor(0xDD, 0xD5, 0xC7))
    text(s, "https://alternate-echo-whale-5578-github-app.alternatefutures.ai", M + 0.28, 3.5, 6.9, 0.3, size=10.5, color=BRAND_BLUE, font=MONO)
    text(s, "status ok  ·  gate all_passed  ·  version 0.5.0", M + 0.28, 3.88, 6.9, 0.3, size=10, color=RGBColor(0x6B, 0x66, 0x5C), font=MONO)
    text(s, "Deployed from a public repository on every commit, with the image tag equal to the commit.", M + 0.28, 4.24, 6.8, 0.3, size=10, color=RGBColor(0x6B, 0x66, 0x5C), font=MONO)

    # architecture strip
    boxes = [("Browser", "hash-routed console"), ("Container", "FastAPI · port 8000"), ("Model", "Groq, with fallback"), ("Ledger", "SQLite hash chain")]
    for i, (title, sub) in enumerate(boxes):
        x = M + i * 1.94
        card(s, x, 5.18, 1.8, 0.98, RGBColor(0xF2, 0xEE, 0xE4), RGBColor(0xDD, 0xD5, 0xC7))
        text(s, title, x + 0.16, 5.32, 1.5, 0.28, size=10.5, color=DARK_BLUE, bold=True)
        text(s, sub, x + 0.16, 5.6, 1.55, 0.4, size=8.5, color=RGBColor(0x6B, 0x66, 0x5C), font=MONO, spacing=1.15)

    card(s, 8.72, 2.5, 3.72, 3.66, WHITE, RGBColor(0xDD, 0xD5, 0xC7))
    rule(s, 8.98, 2.74, 0.9, TERRACOTTA, 2.5)
    text(s, "Stated limits", 8.98, 2.9, 3.2, 0.3, size=11, color=TERRACOTTA, font=MONO, bold=True)
    limits = [
        "The ledger is local to the deployment: it survives a restart, not a redeploy.",
        "The policy is synthetic and inspired by social protection practice, not official.",
        "Unfamiliar documents abstain rather than guess.",
    ]
    for i, item in enumerate(limits):
        text(s, item, 8.98, 3.3 + i * 0.92, 3.2, 0.85, size=10.5, color=RGBColor(0x45, 0x40, 0x38), spacing=1.28)

    star(s, 12.5, 1.1, 0.12, BRAND_BLUE, 18, 10)
    footer(s, 10)
    notes(s, "Naming per brand guide: Clouds by Alternate Futures on first mention, then Clouds. The limits are on the slide because a judge will ask.")


def slide_impact(prs):
    s = new_slide(prs)
    eyebrow(s, "Impact and next")
    heading(s, "Built for the decision, not the demo.", size=42)

    cols = [
        (
            "Who it serves",
            [
                "Social protection agencies screening high volumes",
                "Caseworkers who must sign off on each outcome",
                "Auditors who need a verifiable trail",
            ],
        ),
        (
            "What is proven now",
            [
                "Seven clauses, deterministic and traceable",
                "Grounded extraction with abstention",
                "Enforced human gate and hash-chained ledger",
                "Quality gate in the running service",
            ],
        ),
        (
            "Next",
            [
                "Configurable policy per programme",
                "Durable ledger across deployments",
                "Officer identity and role separation",
                "Exportable decision packs for audit",
            ],
        ),
    ]
    for i, (title, items) in enumerate(cols):
        x = M + i * 3.94
        text(s, title, x, 2.42, 3.6, 0.32, size=11, color=BRAND_BLUE, font=MONO, bold=True, tracking=60)
        rule(s, x, 2.78, 3.5, RGBColor(0xDD, 0xD5, 0xC7), 0.9)
        for j, item in enumerate(items):
            text(s, item, x, 3.02 + j * 0.72, 3.5, 0.68, size=12.5, color=INK, spacing=1.28)

    card(s, M, 6.02, 11.6, 0.72, SKY, RGBColor(0xA9, 0xC4, 0xCA))
    text(
        s,
        "The design claim is modest and testable: the machine may propose, a check may refuse, and only a named person may decide.",
        M + 0.3,
        6.2,
        11.0,
        0.4,
        size=12,
        color=DARK_BLUE,
        bold=True,
    )

    star(s, 12.5, 1.42, 0.13, BRAND_BLUE, 20, 12)
    star(s, 12.1, 1.72, 0.08, BRAND_BLUE, 26, 0)
    footer(s, 11)
    notes(s, "Impact first, then the honest roadmap. Everything in the middle column exists today and can be shown in the live service.")


def slide_close(prs):
    s = new_slide(prs, BRAND_BLUE)
    star(s, 0.72, 0.72, 0.2, APRICOT, 40, 10)
    star(s, 1.18, 1.06, 0.11, CREAM, 26, 0)
    star(s, 11.9, 1.05, 0.16, APRICOT, 32, 18)
    star(s, 12.42, 1.44, 0.09, CREAM, 24, 0)
    ring(s, -0.9, 4.9, 2.6, APRICOT, 22, 1.3)

    eyebrow(s, "Thank you", M, 1.5, APRICOT, 6.0)
    text(s, "Witness", M, 1.82, 8.4, 1.1, size=60, color=CREAM, bold=True)
    text(s, "AI proposes. A check audits. A human decides.", M, 2.95, 9.0, 0.6, size=22, color=APRICOT, font=SERIF, italic=True)

    rule(s, M, 3.85, 1.4, CREAM, 2.0)

    text(s, "LIVE", M, 4.12, 1.2, 0.26, size=9, color=RGBColor(0xBF, 0xBB, 0xEE), font=MONO, tracking=140)
    text(s, "alternate-echo-whale-5578-github-app.alternatefutures.ai", M, 4.36, 7.6, 0.3, size=11, color=CREAM, font=MONO)
    text(s, "REPOSITORY", M, 4.88, 1.6, 0.26, size=9, color=RGBColor(0xBF, 0xBB, 0xEE), font=MONO, tracking=140)
    text(s, "github.com/anithepani/GlueSticks-agentika", M, 5.12, 7.6, 0.3, size=11, color=CREAM, font=MONO)

    text(s, "Glue Sticks", M + 8.1, 4.36, 3.3, 0.3, size=11, color=CREAM, font=MONO, bold=True, align=PP_ALIGN.RIGHT)
    text(s, "Aryan Zia\nMuhammad Rubait Zakria", M + 8.1, 4.66, 3.3, 0.6, size=10, color=RGBColor(0xD5, 0xD2, 0xF4), font=MONO, align=PP_ALIGN.RIGHT, spacing=1.35)

    text(s, "Agentika 2.0  ·  NaSCon 2026  ·  FAST NUCES Islamabad", M, 6.4, 8.0, 0.3, size=9, color=RGBColor(0xA9, 0xA4, 0xE4), font=MONO)
    notes(s, "Close on the rule, not on a feature list.")


def build() -> None:
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)

    slide_cover(prs)
    slide_problem(prs)
    slide_rule(prs)
    slide_pipeline(prs)
    slide_evidence(prs)
    slide_abstain(prs)
    slide_gate(prs)
    slide_ledger(prs)
    slide_quality(prs)
    slide_live(prs)
    slide_impact(prs)
    slide_close(prs)

    prs.core_properties.title = "Witness - Agentika 2.0 finalist deck"
    prs.core_properties.author = "Glue Sticks"
    prs.core_properties.subject = "Human-in-the-loop decision desk"

    prs.save(str(OUT))
    print(f"wrote {OUT} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build()
