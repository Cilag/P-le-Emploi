import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_JUSTIFY


def generate_letter_pdf(
    lettre_contenu: str,
    entreprise: str,
    titre_poste: str,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=3 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
    elements = [
        Paragraph(f"Candidature — {titre_poste} chez {entreprise}", styles["Heading2"]),
        Spacer(1, 0.5 * cm),
    ]
    for line in lettre_contenu.split("\n"):
        elements.append(Paragraph(line or "&nbsp;", body_style))

    doc.build(elements)
    return buffer.getvalue()
