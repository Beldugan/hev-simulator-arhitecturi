"""
pdf_export.py — Export PDF complet al rezultatelor
===================================================

Generează un raport PDF unic cu: parametrii de intrare, tabelele de rezultate,
graficele (consum, SoC, TCO), verificările de validare și interpretări automate.

Licență: MIT
"""
from __future__ import annotations
import io
import os
import tempfile
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, PageBreak)

from vehicle_model import VehicleParams, SimulationResult
from tco_model import EconomicParams

INK = colors.HexColor("#0f172a")
HDR = colors.HexColor("#1e40af")
LIGHT = colors.HexColor("#eff6ff")


# ======================================================================
#  Font Unicode (repară diacriticele românești ă, ș, ț și indicii ₂)
# ======================================================================
# Fonturile implicite reportlab (Helvetica) folosesc codarea Latin-1, care NU
# conține ă (U+0103), ș (U+0219), ț (U+021B) sau indicele ₂ (U+2082) — de aceea
# acestea apăreau ca pătrățele „□". Înregistrăm DejaVu Sans (acoperire Unicode
# completă), livrat în `assets/fonts/`, cu revenire la fonturile de sistem.
_FONT_MAIN = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_FONT_ITALIC = "Helvetica-Oblique"


def _register_fonts() -> None:
    """Înregistrează DejaVu Sans (regular/bold/italic) ca font Unicode implicit."""
    global _FONT_MAIN, _FONT_BOLD, _FONT_ITALIC
    if _FONT_MAIN == "DejaVu":            # deja înregistrat
        return
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "assets", "fonts"),          # inclus în repo
        "/usr/share/fonts/truetype/dejavu",                    # sistem (Linux)
    ]
    variants = {
        "DejaVu": "DejaVuSans.ttf",
        "DejaVu-Bold": "DejaVuSans-Bold.ttf",
        "DejaVu-Italic": "DejaVuSans-Oblique.ttf",
    }
    try:
        for name, filename in variants.items():
            path = next((os.path.join(d, filename) for d in candidates
                         if os.path.exists(os.path.join(d, filename))), None)
            if path is None:
                return                    # font indisponibil → rămân fonturile core
            pdfmetrics.registerFont(TTFont(name, path))
        pdfmetrics.registerFontFamily(
            "DejaVu", normal="DejaVu", bold="DejaVu-Bold",
            italic="DejaVu-Italic", boldItalic="DejaVu-Bold")
        _FONT_MAIN, _FONT_BOLD, _FONT_ITALIC = "DejaVu", "DejaVu-Bold", "DejaVu-Italic"
    except Exception:
        pass                              # orice eroare → păstrăm fonturile implicite


def _styles():
    _register_fonts()
    ss = getSampleStyleSheet()
    # Aplicăm fontul Unicode tuturor stilurilor de bază moștenite
    for name in ("Normal", "BodyText", "Heading1", "Heading2"):
        ss[name].fontName = _FONT_MAIN
    ss.add(ParagraphStyle("H1x", parent=ss["Heading1"], fontName=_FONT_BOLD,
                          fontSize=17, textColor=HDR, spaceAfter=10))
    ss.add(ParagraphStyle("H2x", parent=ss["Heading2"], fontName=_FONT_BOLD,
                          fontSize=13, textColor=INK, spaceBefore=14, spaceAfter=6))
    ss.add(ParagraphStyle("Bodyx", parent=ss["BodyText"], fontName=_FONT_MAIN,
                          fontSize=9.5, leading=13.5, alignment=4))  # justify
    ss.add(ParagraphStyle("Metax", parent=ss["BodyText"], fontName=_FONT_MAIN,
                          fontSize=8, textColor=colors.HexColor("#64748b")))
    return ss


def _tbl(data: list[list], col_widths=None) -> Table:
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HDR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, -1), _FONT_MAIN),
        ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _fig_to_image(fig, width_cm: float = 16.5) -> Image:
    """Convertește o figură matplotlib într-un Image reportlab."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width_cm * cm
    img.drawHeight = width_cm * ratio * cm
    return img


def _consumption_chart(results_table: list[dict]) -> Image:
    archs = sorted(set(r["Arhitectură"] for r in results_table))
    cycles = sorted(set(r["Ciclu"] for r in results_table))
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    width = 0.8 / len(archs)
    palette = ["#64748b", "#0ea5e9", "#10b981", "#8b5cf6"]
    x = np.arange(len(cycles))
    for i, arch in enumerate(archs):
        vals = [next((r["Consum [L/100km]"] for r in results_table
                      if r["Arhitectură"] == arch and r["Ciclu"] == c), 0) for c in cycles]
        ax.bar(x + i * width, vals, width, label=arch, color=palette[i % 4])
    ax.set_xticks(x + width * (len(archs) - 1) / 2)
    ax.set_xticklabels(cycles)
    ax.set_ylabel("Consum [L/100 km]")
    ax.set_title("Consumul pe arhitecturi și cicluri")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(axis="y", alpha=0.3)
    return _fig_to_image(fig)


def _soc_chart(soc_data: dict[str, np.ndarray], p: VehicleParams) -> Image:
    fig, ax = plt.subplots(figsize=(8.5, 3.2))
    palette = {"serie": "#0ea5e9", "paralel": "#10b981", "serie_paralel": "#8b5cf6"}
    for arch, soc in soc_data.items():
        ax.plot(soc * 100, label=arch.replace("_", "-").title(),
                color=palette.get(arch, "#333"), lw=1.4)
    ax.axhline(p.SoC_target * 100, ls="--", c="#94a3b8", lw=1, label="Țintă")
    ax.set_xlabel("Timp [s]"); ax.set_ylabel("SoC [%]")
    ax.set_title("Traiectoriile stării de încărcare (WLTC)")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    return _fig_to_image(fig)


def generate_pdf_report(
    p: VehicleParams,
    econ: EconomicParams,
    results_table: list[dict],
    tco_table: list[dict],
    validation_checks: list[dict],
    comparison_data: dict | None,
    soc_data: dict[str, np.ndarray],
    strategy_label: str,
    out_path: str,
) -> str:
    """
    Generează raportul PDF complet.

    Parameters
    ----------
    results_table : list[dict] cu chei "Arhitectură","Ciclu","Consum [L/100km]","CO₂ [g/km]","Reducere [%]"
    tco_table : list[dict] cu chei "Arhitectură","Achiziție","Energie","Mentenanță","TCO total"
    validation_checks : rezultatul physical_validation()
    comparison_data : rezultatul compare_with_sources() sau None
    soc_data : dict arhitectură → traiectorie SoC (pentru grafic)
    """
    ss = _styles()
    story = []

    # ---- Copertă / titlu ----
    story.append(Paragraph("Raport de simulare — Arhitecturi de propulsie hibridă", ss["H1x"]))
    story.append(Paragraph(
        f"Generat: {datetime.now().strftime('%d.%m.%Y %H:%M')} · "
        f"Vehicul: <b>{p.name}</b> · Strategie EMS: <b>{strategy_label}</b>", ss["Metax"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Acest raport a fost generat automat de aplicația open-source asociată lucrării "
        "de disertație <i>«Analiza comparativă a configurațiilor de propulsie hibridă "
        "(serie, paralel, serie-paralel) pentru un vehicul de clasă C-SUV»</i> — "
        "A.M. Beldugan, FIMIM, Universitatea Ovidius din Constanța, 2026.", ss["Bodyx"]))

    # ---- 1. Parametrii de intrare ----
    story.append(Paragraph("1. Parametrii de intrare", ss["H2x"]))
    param_rows = [["Parametru", "Valoare", "Parametru", "Valoare"],
                  ["Masă [kg]", f"{p.mass_kg:.0f}", "Putere MCI [kW]", f"{p.P_ICE_max_kW:.0f}"],
                  ["Cd × Af [m²]", f"{p.Cd:.2f} × {p.Af:.2f}", "Randament termic", f"{p.eta_th_peak:.2f}"],
                  ["Rezist. rulare", f"{p.f_rr:.4f}", "Putere EM [kW]", f"{p.P_EM_max_kW:.0f}"],
                  ["Baterie [kWh]", f"{p.bat_energy_kWh:.1f}", "Preț [EUR]", f"{p.price_EUR:,.0f}".replace(",", " ")],
                  ["Kilometraj anual", f"{econ.km_per_year:,.0f} km".replace(",", " "),
                   "Preț benzină", f"{econ.fuel_price_EUR_L:.2f} EUR/L"]]
    story.append(_tbl(param_rows, [4 * cm, 4 * cm, 4 * cm, 4 * cm]))

    # ---- 2. Rezultatele simulării ----
    story.append(Paragraph("2. Rezultatele simulării", ss["H2x"]))
    hdr = ["Arhitectură", "Ciclu", "Consum [L/100km]", "CO₂ [g/km]", "Reducere [%]"]
    rows = [hdr] + [[r["Arhitectură"], r["Ciclu"], f'{r["Consum [L/100km]"]:.3f}',
                     f'{r["CO₂ [g/km]"]:.1f}', f'{r["Reducere [%]"]:.1f}'] for r in results_table]
    story.append(_tbl(rows, [4.2 * cm, 2.6 * cm, 3.6 * cm, 3 * cm, 3 * cm]))
    story.append(Spacer(1, 8))
    story.append(_consumption_chart(results_table))

    # Interpretare automată — generată DIN DATE (câștigătorul fiecărui ciclu)
    hev_rows = [r for r in results_table if "Baseline" not in r["Arhitectură"]]
    if hev_rows:
        best = min(hev_rows, key=lambda r: r["Consum [L/100km]"])
        # câștigătorul pe fiecare ciclu
        cycles_order = []
        for r in hev_rows:
            if r["Ciclu"] not in cycles_order:
                cycles_order.append(r["Ciclu"])
        per_cycle = []
        for c in cycles_order:
            cr = [r for r in hev_rows if r["Ciclu"] == c]
            w = min(cr, key=lambda r: r["Consum [L/100km]"])
            per_cycle.append(f"pe {c} — <b>{w['Arhitectură']}</b> "
                             f"({w['Consum [L/100km]']:.3f} L/100 km)")
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"<b>Interpretare:</b> configurația cu cel mai redus consum global este "
            f"<b>{best['Arhitectură']}</b> pe ciclul {best['Ciclu']} "
            f"({best['Consum [L/100km]']:.3f} L/100 km, o reducere de "
            f"{best['Reducere [%]']:.1f}% față de baseline). Pe fiecare ciclu, "
            f"consumul minim se obține cu: " + "; ".join(per_cycle) + ". "
            f"Sub strategia ECMS, arhitectura paralel — lipsită de pierderile de "
            f"dublă conversie — tinde să obțină cel mai mic consum, seria-paralel se "
            f"situează la mijloc prin bucla electrică permanentă a power-split-ului, "
            f"iar seria este penalizată de dubla conversie, mai ales la sarcină "
            f"susținută de autostradă.", ss["Bodyx"]))

    # ---- 3. SoC ----
    if soc_data:
        story.append(Paragraph("3. Traiectoriile stării de încărcare", ss["H2x"]))
        story.append(_soc_chart(soc_data, p))

    # ---- 4. TCO ----
    story.append(PageBreak())
    story.append(Paragraph("4. Costul total de proprietate (TCO)", ss["H2x"]))
    hdr = ["Arhitectură", "Achiziție [€]", "Energie [€]", "Mentenanță [€]", "TCO total [€]"]
    rows = [hdr] + [[t["Arhitectură"], f'{t["Achiziție"]:,}'.replace(",", " "),
                     f'{t["Energie"]:,}'.replace(",", " "),
                     f'{t["Mentenanță"]:,}'.replace(",", " "),
                     f'{t["TCO total"]:,}'.replace(",", " ")] for t in tco_table]
    story.append(_tbl(rows, [4.2 * cm, 3.2 * cm, 3 * cm, 3.2 * cm, 3.2 * cm]))
    best_tco = min(tco_table, key=lambda t: t["TCO total"])
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<b>Interpretare:</b> pe orizontul de {econ.years} ani și "
        f"{econ.km_per_year:,.0f} km/an".replace(",", " ") +
        f", configurația optimă economic este <b>{best_tco['Arhitectură']}</b> "
        f"(TCO = {best_tco['TCO total']:,} EUR".replace(",", " ") + ").", ss["Bodyx"]))

    # ---- 5. Validare fizică ----
    story.append(Paragraph("5. Validarea fizică a simulării", ss["H2x"]))
    hdr = ["Verificare", "Status", "Detalii"]
    rows = [hdr] + [[c["check"], c["status"], c["detail"]] for c in validation_checks]
    t = _tbl(rows, [6 * cm, 1.8 * cm, 9 * cm])
    for i, c in enumerate(validation_checks, start=1):
        color = colors.HexColor("#059669") if c["status"] == "PASS" else colors.HexColor("#dc2626")
        t.setStyle(TableStyle([("TEXTCOLOR", (1, i), (1, i), color),
                               ("FONTNAME", (1, i), (1, i), _FONT_BOLD)]))
    story.append(t)

    # ---- 6. Comparație cu surse externe ----
    if comparison_data and comparison_data.get("comparisons"):
        story.append(Paragraph("6. Comparația cu valorile WLTP oficiale", ss["H2x"]))
        hdr = ["Sursă (vehicul)", "WLTP [L/100km]", "Abatere [%]", "Referință"]
        rows = [hdr] + [[c["name"], f'{c["official_L_100km"]:.2f}',
                         f'{c["deviation_pct"]:+.1f}', c["source"]]
                        for c in comparison_data["comparisons"]]
        story.append(_tbl(rows, [4.6 * cm, 3 * cm, 2.4 * cm, 6.8 * cm]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"Abaterea medie a consumului simulat față de cele "
            f"{comparison_data['n_sources']} surse oficiale: "
            f"<b>{comparison_data['avg_deviation_pct']:+.1f}%</b>.", ss["Bodyx"]))

    # ---- Notă finală ----
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Notă metodologică: modelul de simulare este cvasi-static, de tip "
        "backward-forward, cu modelul liniei Willans pentru consum. Rezultatele sunt "
        "destinate comparației relative între arhitecturi; valorile absolute depind de "
        "calibrarea parametrilor. Ciclul WLTC provine din biblioteca `wltp` (UNECE GTR15).",
        ss["Metax"]))

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    doc.build(story)
    return out_path
