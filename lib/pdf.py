"""Génération du PDF d'offre commerciale."""
from __future__ import annotations
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak)


def _fmt(n, suffix=" F CFA"):
    try:
        return f"{float(n):,.0f}".replace(",", " ") + suffix
    except Exception:
        return str(n)


def pdf_offre(offre: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=styles['Heading1'], textColor=colors.HexColor("#E30613"))
    elements = []

    elements.append(Paragraph("KORI TRANSPORT SA", h1))
    elements.append(Paragraph("Fiche d'offre commerciale — Livraison de Gaz Butane", styles['Heading3']))
    elements.append(Spacer(1, 6*mm))

    info = [
        ["N° Offre :", offre.get("numero", "")],
        ["Date :", str(offre.get("date_offre", ""))],
        ["Destination :", offre.get("destination", "")],
        ["Attelage :", offre.get("attelage", "")],
        ["Quantité :", f"{offre.get('quantite_kg',0):,.0f} kg".replace(",", " ")],
        ["Distance A/R :", f"{offre.get('distance_ar',0):,.0f} km".replace(",", " ")],
    ]
    t = Table(info, colWidths=[45*mm, 110*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8*mm))

    elements.append(Paragraph("Détail des charges", styles['Heading3']))
    charges = [
        ["Poste", "Montant"],
        ["Carburant", _fmt(offre.get("carburant"))],
        ["Maintenance", _fmt(offre.get("maintenance"))],
        ["Péages A/R", _fmt(offre.get("peages_ar"))],
        ["Frais de mission", _fmt(offre.get("frais_mission"))],
        ["Prime voyage", _fmt(offre.get("prime_voyage"))],
        ["Lettre de voiture", _fmt(offre.get("lettre_voiture"))],
        ["Autres dépenses", _fmt(offre.get("autres_depenses"))],
        ["Charges fixes attelage", _fmt(offre.get("charges_fixes_attelage"))],
        ["VT/km × distance", _fmt(offre.get("vt_km_distance"))],
        ["TOTAL CHARGES", _fmt(offre.get("total_charges"))],
    ]
    t = Table(charges, colWidths=[90*mm, 65*mm])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E30613")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F5F5F5")),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8*mm))

    elements.append(Paragraph("Prix & marge", styles['Heading3']))
    prix = [
        ["Prix plancher (F/kg)", _fmt(offre.get("prix_plancher_kg"), "")],
        ["Prix offert (F/kg)", _fmt(offre.get("prix_offert_kg"), "")],
        ["CA total", _fmt(offre.get("ca_total"))],
        ["Marge brute", _fmt(offre.get("marge_brute"))],
        ["Taux de marge", f"{float(offre.get('taux_marge',0))*100:.1f} %"],
    ]
    t = Table(prix, colWidths=[90*mm, 65*mm])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
    ]))
    elements.append(t)

    if offre.get("notes"):
        elements.append(Spacer(1, 8*mm))
        elements.append(Paragraph("Notes", styles['Heading3']))
        elements.append(Paragraph(offre["notes"], styles['Normal']))

    doc.build(elements)
    return buf.getvalue()
