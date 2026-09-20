"""Render the summary + original email list into a downloadable PDF."""

import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from categorizer import categorize_email

# ReportLab's built-in fonts don't cover CJK glyphs. Embedding this font means
# the PDF still renders correctly even if an email's content isn't in English.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CJK_FONT_PATH = os.path.join(BASE_DIR, "fonts", "wqy-zenhei.ttf")
CJK_FONT = "CJKFont"

if CJK_FONT not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont(CJK_FONT, CJK_FONT_PATH))

NAVY = colors.HexColor("#16293A")
BRASS = colors.HexColor("#8C692C")
LINE = colors.HexColor("#D8D2C2")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Title2", fontName=CJK_FONT, fontSize=18, leading=24,
        textColor=NAVY, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Meta2", fontName=CJK_FONT, fontSize=9, leading=13,
        textColor=colors.grey, spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="Heading2b", fontName=CJK_FONT, fontSize=12, leading=17,
        textColor=NAVY, spaceBefore=14, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Body2", fontName=CJK_FONT, fontSize=10.5, leading=17,
        textColor=colors.HexColor("#1B2732"),
    ))
    styles.add(ParagraphStyle(
        name="EmailMeta2", fontName=CJK_FONT, fontSize=8.5, leading=12,
        textColor=colors.grey, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="CategoryTag", fontName=CJK_FONT, fontSize=8, leading=11,
        textColor=BRASS, spaceAfter=4,
    ))
    return styles


def build_pdf(summary, emails):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )
    styles = _styles()
    story = []

    story.append(Paragraph("Email Summary Report", styles["Title2"]))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Meta2"]))

    story.append(Paragraph("Summary", styles["Heading2b"]))
    for para in summary.split("\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), styles["Body2"]))

    story.append(Paragraph(f"Source emails ({len(emails)})", styles["Heading2b"]))
    for i, e in enumerate(emails, start=1):
        subject = e.get("subject", "(no subject)")
        meta = f"{i}. From: {e.get('from','')} | Date: {e.get('date','')}"
        categories = categorize_email(e)
        story.append(Paragraph(subject, styles["Body2"]))
        story.append(Paragraph(meta, styles["EmailMeta2"]))
        story.append(Paragraph(" · ".join(categories), styles["CategoryTag"]))
        story.append(Spacer(1, 6))

    doc.build(story)
    buf.seek(0)
    return buf
