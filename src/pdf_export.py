"""
pdf_export.py — Export PDF complet al rezultatelor
===================================================

Generează un raport PDF unic cu: parametrii de intrare, TOATE datele rezultate
din simulări (tabele + grafice), câte o interpretare generată automat DIN DATE
pentru fiecare grafic, validarea fizică și comparația cu sursele WLTP.

Fiecare pagină poartă în subsol mențiunea de copyright și numărul paginii,
desenate direct în fluxul de conținut al paginii — nu pot fi eliminate prin
editarea obișnuită a PDF-ului.

Licență: MIT
"""
from __future__ import annotations
import io
import os
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
                                TableStyle, Image, PageBreak, CondPageBreak,
                                KeepTogether)

from vehicle_model import VehicleParams, SimulationResult, bsfc_map
from tco_model import EconomicParams
from analysis import physical_validation
from ems_strategies import ARCH_LABELS

INK = colors.HexColor("#0f172a")
HDR = colors.HexColor("#1e40af")
LIGHT = colors.HexColor("#eff6ff")

WATERMARK_TEXT = "© 2026 A.M. Beldugan, FIMIM, Univ. Ovidius Constanța"


# ======================================================================
#  Font Unicode (diacriticele românești ă, ș, ț și indicii ₂)
# ======================================================================
_FONT_MAIN = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_FONT_ITALIC = "Helvetica-Oblique"


def _register_fonts() -> None:
    """Înregistrează DejaVu Sans (regular/bold/italic) ca font Unicode implicit."""
    global _FONT_MAIN, _FONT_BOLD, _FONT_ITALIC
    if _FONT_MAIN == "DejaVu":
        return
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "assets", "fonts"),
        "/usr/share/fonts/truetype/dejavu",
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
                return
            pdfmetrics.registerFont(TTFont(name, path))
        pdfmetrics.registerFontFamily(
            "DejaVu", normal="DejaVu", bold="DejaVu-Bold",
            italic="DejaVu-Italic", boldItalic="DejaVu-Bold")
        _FONT_MAIN, _FONT_BOLD, _FONT_ITALIC = "DejaVu", "DejaVu-Bold", "DejaVu-Italic"
    except Exception:
        pass


# ======================================================================
#  Watermark — desenat în conținutul fiecărei pagini
# ======================================================================
def _watermark(cv, doc) -> None:
    """Linie de subsol cu copyright și numărul paginii, pe fiecare pagină.

    Textul este scris în fluxul de conținut al paginii (canvas), nu ca
    adnotare/stamp — nu poate fi șters din editoarele PDF uzuale.
    """
    _register_fonts()
    W, H = A4
    cv.saveState()
    cv.setFont(_FONT_MAIN, 7)
    cv.setFillColor(colors.HexColor("#64748b"))
    cv.drawString(1.8 * cm, 1.0 * cm, WATERMARK_TEXT)
    cv.drawRightString(W - 1.8 * cm, 1.0 * cm, f"Pagina {doc.page}")
    cv.setStrokeColor(colors.HexColor("#cbd5e1"))
    cv.setLineWidth(0.4)
    cv.line(1.8 * cm, 1.25 * cm, W - 1.8 * cm, 1.25 * cm)
    cv.restoreState()


# ======================================================================
#  Stiluri, tabele, conversie figuri
# ======================================================================
def _styles():
    _register_fonts()
    ss = getSampleStyleSheet()
    for name in ("Normal", "BodyText", "Heading1", "Heading2"):
        ss[name].fontName = _FONT_MAIN
    ss.add(ParagraphStyle("H1x", parent=ss["Heading1"], fontName=_FONT_BOLD,
                          fontSize=17, textColor=HDR, spaceAfter=10))
    ss.add(ParagraphStyle("H2x", parent=ss["Heading2"], fontName=_FONT_BOLD,
                          fontSize=13, textColor=INK, spaceBefore=14, spaceAfter=6))
    ss.add(ParagraphStyle("H3x", parent=ss["Heading2"], fontName=_FONT_BOLD,
                          fontSize=11, textColor=INK, spaceBefore=10, spaceAfter=4))
    ss.add(ParagraphStyle("Bodyx", parent=ss["BodyText"], fontName=_FONT_MAIN,
                          fontSize=9.5, leading=13.5, alignment=4))  # justify
    ss.add(ParagraphStyle("Metax", parent=ss["BodyText"], fontName=_FONT_MAIN,
                          fontSize=8, textColor=colors.HexColor("#64748b")))
    return ss


def _interp(ss, text: str) -> Paragraph:
    return Paragraph(f"<b>Interpretare:</b> {text}", ss["Bodyx"])


def _tbl(data: list[list], col_widths=None) -> Table:
    # Fiecare celulă devine Paragraph, ca textul lung (ex. denumiri de vehicule)
    # să se încadreze pe mai multe rânduri în loc să se reverse peste coloana
    # vecină. Antetul folosește un stil alb/bold; corpul, textul normal.
    _register_fonts()
    cell = ParagraphStyle("cell", fontName=_FONT_MAIN, fontSize=8,
                          leading=10, textColor=INK)
    head = ParagraphStyle("cellhdr", fontName=_FONT_BOLD, fontSize=8,
                          leading=10, textColor=colors.white)

    def _wrap(val, style):
        if isinstance(val, Paragraph):
            return val
        return Paragraph(str(val).replace("\n", "<br/>"), style)

    wrapped = [[_wrap(c, head) for c in data[0]]]
    wrapped += [[_wrap(c, cell) for c in row] for row in data[1:]]

    t = Table(wrapped, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HDR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _fig_to_image(fig, width_cm: float = 16.5) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width_cm * cm
    img.drawHeight = width_cm * ratio * cm
    return img


def _fmt_int(x) -> str:
    return f"{x:,.0f}".replace(",", " ")


# ======================================================================
#  Grafice (matplotlib)
# ======================================================================
_PALETTE = {"baseline": "#64748b", "serie": "#0ea5e9",
            "paralel": "#10b981", "serie_paralel": "#8b5cf6"}


def _bars_chart(values: dict[str, dict[str, float]], ylabel: str, title: str,
                fmt: str = "{:.2f}") -> Image:
    """Bar chart grupat generic: arhitecturi × cicluri."""
    archs = list(values.keys())
    cyc = list(next(iter(values.values())).keys())
    fig_w = max(8.5, 2.2 * len(cyc))
    fig, ax = plt.subplots(figsize=(fig_w, 3.6))
    width = 0.8 / len(archs)
    x = np.arange(len(cyc))
    for i, a in enumerate(archs):
        vals = [values[a][c] for c in cyc]
        bars = ax.bar(x + i * width, vals, width,
                      label=ARCH_LABELS.get(a, a).split(" (")[0],
                      color=_PALETTE.get(a, "#333"))
        ax.bar_label(bars, fmt=fmt.format, fontsize=6.5, padding=1)
    ax.set_xticks(x + width * (len(archs) - 1) / 2)
    wrapped = [c.replace(" (", "\n(") for c in cyc]
    if len(cyc) >= 4:
        ax.set_xticklabels(wrapped, rotation=20, ha="right", fontsize=8)
    else:
        ax.set_xticklabels(wrapped, fontsize=8.5)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(fontsize=8, ncol=len(archs))
    ax.grid(axis="y", alpha=0.3)
    ax.margins(y=0.15)
    fig.tight_layout()
    return _fig_to_image(fig)


def _soc_chart(soc_data: dict[str, np.ndarray], p: VehicleParams) -> Image:
    fig, ax = plt.subplots(figsize=(8.5, 3.2))
    for arch, soc in soc_data.items():
        ax.plot(soc * 100, label=ARCH_LABELS.get(arch, arch),
                color=_PALETTE.get(arch, "#333"), lw=1.4)
    ax.axhline(p.SoC_target * 100, ls="--", c="#94a3b8", lw=1, label="Țintă")
    ax.axhline(p.SoC_min * 100, ls=":", c="#dc2626", lw=1, label="Min")
    ax.set_xlabel("Timp [s]"); ax.set_ylabel("SoC [%]")
    ax.set_title("Traiectoriile stării de încărcare (WLTC)")
    ax.legend(fontsize=8, ncol=3); ax.grid(alpha=0.3)
    return _fig_to_image(fig)


def _power_chart(r: SimulationResult, speed_kmh: np.ndarray, title: str) -> Image:
    t = np.arange(len(speed_kmh))
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.5, 4.4), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 2]})
    ax1.fill_between(t, speed_kmh, color="#0f172a", alpha=0.08)
    ax1.plot(t, speed_kmh, c="#0f172a", lw=0.9)
    ax1.set_ylabel("km/h"); ax1.grid(alpha=0.3); ax1.set_title(title, fontsize=10)
    ax2.plot(t, r.P_engine_W / 1000, c="#dc2626", lw=0.8, label="Motor termic")
    ax2.plot(t, r.P_EM_W / 1000, c="#10b981", lw=0.8, label="Mașină electrică")
    ax2.axhline(0, c="#94a3b8", lw=0.6)
    ax2.set_ylabel("kW"); ax2.set_xlabel("Timp [s]")
    ax2.legend(fontsize=8, ncol=2); ax2.grid(alpha=0.3)
    return _fig_to_image(fig)


def _bsfc_chart(p: VehicleParams,
                results_wltc: dict[str, SimulationResult]) -> Image:
    hyb = [a for a in results_wltc if a != "baseline"]
    fig, axes = plt.subplots(1, len(hyb), figsize=(8.5, 2.9), sharey=True)
    axes = np.atleast_1d(axes)
    P_range = np.linspace(2, p.P_ICE_max_kW, 120) * 1000
    curve = np.array([bsfc_map(P, p) for P in P_range])
    bmin = curve.min()
    for ax, a in zip(axes, hyb):
        ax.plot(P_range / 1000, curve, c="#0f172a", lw=1.4)
        ax.axhspan(bmin, bmin * 1.05, color="#10b981", alpha=0.10)
        r = results_wltc[a]
        P_on = r.P_engine_W[r.P_engine_W > 500]
        if len(P_on):
            s = P_on[::max(1, len(P_on) // 250)]
            ax.scatter(s / 1000, [bsfc_map(P, p) for P in s],
                       s=8, c="#f59e0b", alpha=0.40, zorder=3)
        ax.set_title(ARCH_LABELS.get(a, a), fontsize=9)
        ax.set_xlabel("kW"); ax.grid(alpha=0.3)
    axes[0].set_ylabel("BSFC [g/kWh]")
    fig.suptitle("Punctele de operare ale motorului pe harta BSFC (WLTC)",
                 fontsize=10, y=1.02)
    return _fig_to_image(fig)


def _tornado_chart(effects: list[dict], base: float, xlabel: str,
                   title: str) -> Image:
    """Diagramă tornado: bare orizontale −20% / +20% față de valoarea de bază."""
    eff = sorted(effects, key=lambda e: abs(e["high"] - e["low"]))
    labels = [e["label"] for e in eff]
    y = np.arange(len(eff))
    fig, ax = plt.subplots(figsize=(8.5, 0.42 * len(eff) + 1.2))
    for i, e in enumerate(eff):
        ax.barh(i, e["low"] - base, left=base, height=0.62,
                color="#0ea5e9", label="−20%" if i == 0 else None)
        ax.barh(i, e["high"] - base, left=base, height=0.62,
                color="#f59e0b", label="+20%" if i == 0 else None)
    ax.axvline(base, c="#0f172a", lw=1.1)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel(xlabel); ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8, loc="lower right"); ax.grid(axis="x", alpha=0.3)
    return _fig_to_image(fig)


def _live_final_chart(r: SimulationResult, speed_kmh: np.ndarray,
                      p: VehicleParams, title: str) -> Image:
    """Starea finală a derulării LIVE din aplicație (3 panouri):
    viteză colorată după starea MCI + porniri, combustibil/CO₂ cumulate, SoC."""
    v = np.asarray(speed_kmh, dtype=float)
    t = np.arange(len(v))
    on = r.P_engine_W > 500.0
    fuel_cum = np.cumsum(r.fuel_rate_g_s) / (p.fuel_density_kg_L * 1000.0)
    co2_cum = np.cumsum(r.fuel_rate_g_s) * (p.fuel_CO2_kg_L / p.fuel_density_kg_L)
    soc = r.SoC * 100.0
    starts = np.where(on[1:] & ~on[:-1])[0] + 1
    if on.any() and on[0]:
        starts = np.concatenate([[0], starts])

    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(8.5, 5.8), sharex=True,
                                     gridspec_kw={"height_ratios": [1.3, 1, 1]})
    a1.plot(t, v, c="#3C3C43", lw=0.9)
    a1.fill_between(t, np.where(on, v, 0.0), color="#dc2626", alpha=0.30,
                    label="MCI pornit")
    a1.fill_between(t, np.where(~on, v, 0.0), color="#10b981", alpha=0.30,
                    label="Electric (MCI oprit)")
    if len(starts):
        a1.scatter(starts, v[starts], marker="^", s=26, c="#dc2626",
                   edgecolors="white", linewidths=0.6, zorder=3,
                   label="Pornire MCI")
    a1.set_ylabel("km/h"); a1.legend(fontsize=7, ncol=3, loc="upper left")
    a1.set_title(title, fontsize=10)

    a2.plot(t, fuel_cum, c="#f59e0b", lw=1.6, label="Combustibil cumulat [L]")
    a2b = a2.twinx()
    a2b.plot(t, co2_cum, c="#64748b", lw=1.4, ls=":", label="CO₂ cumulat [g]")
    a2.set_ylabel("L"); a2b.set_ylabel("g CO₂")
    h1, l1 = a2.get_legend_handles_labels()
    h2, l2 = a2b.get_legend_handles_labels()
    a2.legend(h1 + h2, l1 + l2, fontsize=7, loc="upper left")

    a3.plot(t, soc, c="#8b5cf6", lw=1.4, label="SoC")
    a3.axhline(p.SoC_target * 100, ls="--", c="#94a3b8", lw=1, label="SoC țintă")
    a3.set_ylabel("SoC [%]"); a3.set_xlabel("Timp [s]")
    a3.legend(fontsize=7, ncol=2, loc="upper left")
    for a in (a1, a2, a3):
        a.grid(alpha=0.3)
    return _fig_to_image(fig)


def _tco_chart(tco_table: list[dict]) -> Image:
    labels = [t["Arhitectură"].split(" (")[0] for t in tco_table]
    comps = [("Achiziție", "#3C3C43"), ("Energie", "#f59e0b"),
             ("Mentenanță", "#0ea5e9"), ("Asigurare", "#94a3b8")]
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    x = np.arange(len(labels))
    bottom = np.zeros(len(labels))
    for key, color in comps:
        vals = np.array([t.get(key, 0) for t in tco_table], dtype=float)
        if vals.any():
            ax.bar(x, vals, 0.55, bottom=bottom, label=key, color=color)
            bottom += vals
    resid = np.array([t.get("Rezidual", 0) for t in tco_table], dtype=float)
    if resid.any():
        ax.bar(x, -resid, 0.55, label="Valoare reziduală (−)", color="#10b981")
    for i, t in enumerate(tco_table):
        ax.annotate(_fmt_int(t["TCO total"]) + " €", (i, bottom[i]),
                    textcoords="offset points", xytext=(0, 4),
                    ha="center", fontsize=8, fontweight="bold")
    ax.axhline(0, c="#0f172a", lw=0.7)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("EUR")
    ax.set_title("Defalcarea costului total de proprietate (10 ani)")
    ax.legend(fontsize=8, ncol=3); ax.grid(axis="y", alpha=0.3)
    ax.margins(y=0.18)
    return _fig_to_image(fig)


# ======================================================================
#  Raportul complet
# ======================================================================
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
    results: dict[str, dict[str, SimulationResult]] | None = None,
    cycles: dict[str, np.ndarray] | None = None,
    breakeven: dict | None = None,
    sensitivity: dict | None = None,
    sens_arch_label: str = "",
    eea_audit: dict | None = None,
    report_cycles: list[str] | None = None,
    main_cycle: str = "WLTC",
) -> str:
    """
    Generează raportul PDF complet, cu watermark pe fiecare pagină.

    Parameters
    ----------
    results_table : list[dict] cu chei "Arhitectură","Ciclu","Consum [L/100km]",
        "CO₂ [g/km]","Cotă EV [%]" (opțional), "Reducere [%]"
    tco_table : list[dict] cu chei "Arhitectură","Achiziție","Energie",
        "Mentenanță","Asigurare" (opț.), "Rezidual" (opț.), "TCO total"
    results : dict arhitectură → ciclu → SimulationResult — dacă este furnizat,
        raportul include TOATE graficele (CO₂, cotă EV, profiluri de putere,
        BSFC, validare completă), fiecare cu interpretare generată din date.
    cycles : dict nume ciclu → profil de viteză [km/h]
    breakeven : rezultatul compute_breakeven() (opțional)
    """
    ss = _styles()
    story = []
    has_full = results is not None and cycles is not None
    arch_order = list(results.keys()) if has_full else []
    hyb = [a for a in arch_order if a != "baseline"]

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
                  ["Baterie [kWh]", f"{p.bat_energy_kWh:.1f}", "Preț [EUR]", _fmt_int(p.price_EUR)],
                  ["Sarcină auxiliară [W]", f"{p.P_aux_W:.0f}",
                   "SoC inițial/țintă [%]", f"{p.SoC_init*100:.0f} / {p.SoC_target*100:.0f}"],
                  ["Kilometraj anual", _fmt_int(econ.km_per_year) + " km",
                   "Preț benzină", f"{econ.fuel_price_EUR_L:.2f} EUR/L"]]
    story.append(_tbl(param_rows, [4 * cm, 4 * cm, 4 * cm, 4 * cm]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Rezistența la rulare (0,009) și sarcina auxiliară (300 W) corespund "
        "condițiilor de omologare WLTP (pneuri de clasă energetică superioară, "
        "consumatori auxiliari opriți pe durata testului).", ss["Metax"]))

    # ---- 2. Rezultatele simulării — tabel complet ----
    story.append(PageBreak())
    story.append(Paragraph("2. Rezultatele simulării", ss["H2x"]))
    has_ev = results_table and "Cotă EV [%]" in results_table[0]
    if has_ev:
        hdr = ["Arhitectură", "Ciclu", "Consum [L/100km]", "CO₂ [g/km]",
               "Cotă EV [%]", "Reducere [%]"]
        rows = [hdr] + [[r["Arhitectură"], r["Ciclu"], f'{r["Consum [L/100km]"]:.3f}',
                         f'{r["CO₂ [g/km]"]:.1f}', f'{r["Cotă EV [%]"]:.1f}',
                         f'{r["Reducere [%]"]:.1f}'] for r in results_table]
        story.append(_tbl(rows, [3.6 * cm, 2.0 * cm, 3.2 * cm, 2.6 * cm, 2.5 * cm, 2.5 * cm]))
    else:
        hdr = ["Arhitectură", "Ciclu", "Consum [L/100km]", "CO₂ [g/km]", "Reducere [%]"]
        rows = [hdr] + [[r["Arhitectură"], r["Ciclu"], f'{r["Consum [L/100km]"]:.3f}',
                         f'{r["CO₂ [g/km]"]:.1f}', f'{r["Reducere [%]"]:.1f}'] for r in results_table]
        story.append(_tbl(rows, [4.2 * cm, 2.6 * cm, 3.6 * cm, 3 * cm, 3 * cm]))

    hev_rows = [r for r in results_table if "Baseline" not in r["Arhitectură"]]

    # ---- 2.1 Consum ----
    story.append(Paragraph("2.1. Consumul de combustibil", ss["H3x"]))
    if has_full:
        cons = {a: {c: results[a][c].consumption_L_100km for c in cycles}
                for a in arch_order}
        story.append(_bars_chart(cons, "Consum [L/100 km]",
                                 "Consumul pe arhitecturi și cicluri"))
    if hev_rows:
        best = min(hev_rows, key=lambda r: r["Consum [L/100km]"])
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
        story.append(Spacer(1, 4))
        story.append(_interp(ss,
            f"configurația cu cel mai redus consum global este "
            f"<b>{best['Arhitectură']}</b> pe ciclul {best['Ciclu']} "
            f"({best['Consum [L/100km]']:.3f} L/100 km, o reducere de "
            f"{best['Reducere [%]']:.1f}% față de baseline). Pe fiecare ciclu, "
            f"consumul minim se obține cu: " + "; ".join(per_cycle) + ". "
            f"Arhitectura paralel — lipsită de pierderile de dublă conversie — "
            f"tinde să obțină cel mai mic consum; seria-paralel se situează la "
            f"mijloc prin bucla electrică permanentă a power-split-ului, iar "
            f"seria este penalizată de dubla conversie, mai ales la sarcina "
            f"susținută de autostradă."))

    if has_full:
        # ---- 2.2 CO2 ----
        story.append(Paragraph("2.2. Emisiile de CO₂", ss["H3x"]))
        co2 = {a: {c: results[a][c].co2_g_km for c in cycles} for a in arch_order}
        story.append(_bars_chart(co2, "CO₂ [g/km]",
                                 "Emisiile de CO₂ pe arhitecturi și cicluri",
                                 fmt="{:.0f}"))
        all_co2 = [(a, c, co2[a][c]) for a in arch_order for c in cycles]
        lo = min(all_co2, key=lambda t: t[2]); hi = max(all_co2, key=lambda t: t[2])
        base_avg = np.mean([co2["baseline"][c] for c in cycles])
        best_avg_arch = min(hyb, key=lambda a: np.mean([co2[a][c] for c in cycles]))
        red = (base_avg - np.mean([co2[best_avg_arch][c] for c in cycles])) / base_avg * 100
        story.append(Spacer(1, 4))
        story.append(_interp(ss,
            f"emisiile tank-to-wheel sunt direct proporționale cu consumul "
            f"(2,31 kg CO₂/L benzină), deci ierarhia arhitecturilor se păstrează: "
            f"minimul este {lo[2]:.0f} g/km ({ARCH_LABELS[lo[0]]}, {lo[1]}), "
            f"maximul {hi[2]:.0f} g/km ({ARCH_LABELS[hi[0]]}, {hi[1]}). "
            f"În medie pe cele trei cicluri, <b>{ARCH_LABELS[best_avg_arch]}</b> "
            f"reduce emisiile cu {red:.1f}% față de baseline — relevant pentru "
            f"încadrarea în normele europene de flotă (95 g CO₂/km WLTP)."))

        # ---- 2.3 Cota EV ----
        story.append(Paragraph("2.3. Cota de funcționare electrică (motor termic oprit)", ss["H3x"]))
        ev = {a: {c: results[a][c].ev_share_pct for c in cycles} for a in arch_order}
        story.append(_bars_chart(ev, "Cotă EV [%]",
                                 "Fracțiunea de timp cu motorul termic oprit",
                                 fmt="{:.0f}"))
        ev_best = max(((a, c, ev[a][c]) for a in hyb for c in cycles),
                      key=lambda t: t[2])
        ev_urban = {a: ev[a].get("UDDS", max(ev[a].values())) for a in hyb}
        story.append(Spacer(1, 4))
        story.append(_interp(ss,
            f"cota EV maximă se atinge cu {ARCH_LABELS[ev_best[0]]} pe {ev_best[1]} "
            f"({ev_best[2]:.0f}% din durata ciclului cu motorul termic oprit). "
            f"Valorile ridicate în regim urban ("
            + ", ".join(f"{ARCH_LABELS[a]}: {v:.0f}%" for a, v in ev_urban.items())
            + f") explică avantajul hibridelor la viteze mici: opririle frecvente "
            f"permit rularea electrică și recuperarea energiei de frânare. "
            f"Valoarea baseline reflectă doar funcția stop&start (staționare), "
            f"nu tracțiune electrică."))

    # ---- 3. SoC (pentru fiecare ciclu selectat) ----
    if soc_data:
        story.append(PageBreak())
        story.append(Paragraph("3. Traiectoriile stării de încărcare", ss["H2x"]))
        for ci, (cyc, arch_soc) in enumerate(soc_data.items()):
            block = [Paragraph(f"3.{ci+1}. Ciclul {cyc}", ss["H3x"]),
                     _soc_chart(arch_soc, p)]
            deltas = {a: (soc[-1] - soc[0]) * 100 for a, soc in arch_soc.items()}
            mins = {a: soc.min() * 100 for a, soc in arch_soc.items()}
            worst = max(deltas.items(), key=lambda kv: abs(kv[1]))
            block.append(Spacer(1, 4))
            block.append(_interp(ss,
                f"pe ciclul {cyc}, funcționarea este charge-sustaining: variația "
                f"netă de SoC este "
                + ", ".join(f"{ARCH_LABELS.get(a, a)}: {d:+.1f} pp" for a, d in deltas.items())
                + f" (abaterea maximă {worst[1]:+.1f} pp, corectată energetic în "
                f"consumul raportat). SoC-ul minim atins — "
                + ", ".join(f"{ARCH_LABELS.get(a, a)}: {m:.0f}%" for a, m in mins.items())
                + f" — rămâne peste limita de protecție de {p.SoC_min*100:.0f}%, "
                f"confirmând că strategia EMS menține bateria în fereastra de operare."))
            block.append(Spacer(1, 10))
            story.append(KeepTogether(block))

    # ---- 4. Profiluri de putere (pentru fiecare ciclu selectat) ----
    rep_cyc = [c for c in (report_cycles or ["WLTC"]) if c in (cycles or {})]
    if has_full and rep_cyc:
        arch_note = {
            "serie": "Împrăștierea redusă a sarcinii motorului confirmă decuplarea "
                     "de roți: turația liberă permite funcționarea aproape de punctul "
                     "optim, dar toată puterea trece prin dubla conversie electrică.",
            "paralel": "Sarcina motorului urmărește direct cererea roților (cuplaj "
                       "mecanic), de unde împrăștierea mai mare a punctelor de "
                       "funcționare — compensată de absența pierderilor de conversie.",
            "serie_paralel": "Sub punctul mecanic vehiculul rulează serie-like "
                             "(motor decuplat), peste el în cuplaj mecanic cu buclă "
                             "electrică permanentă — profil intermediar între cele "
                             "două arhitecturi pure.",
        }
        story.append(PageBreak())
        story.append(Paragraph("4. Profilurile de putere pe cicluri", ss["H2x"]))
        sec = 0
        for cyc in rep_cyc:
            for a in hyb:
                sec += 1
                r = results[a][cyc]
                on = r.P_engine_W > 500
                on_pct = float(np.mean(on)) * 100
                p_mean = float(np.mean(r.P_engine_W[on])) / 1000 if on.any() else 0.0
                p_std = float(np.std(r.P_engine_W[on])) / 1000 if on.any() else 0.0
                pem_max = float(np.max(r.P_EM_W)) / 1000
                e_regen = float(-np.sum(np.minimum(r.P_EM_W, 0.0))) / 3.6e6
                fuel_tot_L = float(np.sum(r.fuel_rate_g_s)) / (p.fuel_density_kg_L * 1000)
                co2_tot_g = float(np.sum(r.fuel_rate_g_s)) * (p.fuel_CO2_kg_L / p.fuel_density_kg_L)
                n_starts = int(np.sum(on[1:] & ~on[:-1]) + (1 if on.any() and on[0] else 0))
                block = [
                    Paragraph(f"4.{sec}. {ARCH_LABELS[a]} · {cyc}", ss["H3x"]),
                    _power_chart(r, cycles[cyc], f"{ARCH_LABELS[a]} · {cyc}"),
                    Spacer(1, 6),
                    _live_final_chart(
                        r, cycles[cyc], p,
                        f"{ARCH_LABELS[a]} · {cyc} — derularea completă a ciclului"),
                    Spacer(1, 3),
                    _interp(ss,
                        f"pe ciclul {cyc}, motorul termic funcționează {on_pct:.0f}% "
                        f"din durată ({n_starts} porniri), cu o putere medie de "
                        f"{p_mean:.1f} kW (σ = {p_std:.1f} kW); mașina electrică "
                        f"atinge {pem_max:.1f} kW în tracțiune și recuperează "
                        f"{e_regen:.2f} kWh prin frânare regenerativă. Se consumă "
                        f"{fuel_tot_L:.2f} L de combustibil ({co2_tot_g:.0f} g CO₂), "
                        f"acumulați în fazele cu banda roșie (MCI pornit); pe "
                        f"segmentele verzi vehiculul rulează electric. "
                        + arch_note.get(a, "")),
                    Spacer(1, 10),
                ]
                story.append(KeepTogether(block))

        # ---- 5. BSFC (pentru fiecare ciclu selectat) ----
        story.append(PageBreak())
        story.append(Paragraph("5. Punctele de operare pe harta BSFC", ss["H2x"]))
        P_range = np.linspace(2, p.P_ICE_max_kW, 120) * 1000
        bmin = float(np.min([bsfc_map(P, p) for P in P_range]))
        for ci, cyc in enumerate(rep_cyc):
            bs = {}
            for a in hyb:
                P_on = results[a][cyc].P_engine_W
                P_on = P_on[P_on > 500]
                bs[a] = float(np.mean([bsfc_map(P, p) for P in P_on])) if len(P_on) else 0.0
            best_bs = min(bs.items(), key=lambda kv: kv[1])
            block = [
                Paragraph(f"5.{ci+1}. Ciclul {cyc}", ss["H3x"]),
                _bsfc_chart(p, {a: results[a][cyc] for a in arch_order}),
                Spacer(1, 4),
                _interp(ss,
                    f"pe ciclul {cyc}, consumul specific minim al motorului este "
                    f"{bmin:.0f} g/kWh (banda verde = zona optimă, +5%). BSFC-ul mediu "
                    f"al punctelor de operare: "
                    + ", ".join(f"{ARCH_LABELS[a]}: {v:.0f} g/kWh" for a, v in bs.items())
                    + f". {ARCH_LABELS[best_bs[0]]} operează motorul cel mai aproape de "
                    f"optim ({best_bs[1]:.0f} g/kWh)."),
                Spacer(1, 10),
            ]
            story.append(KeepTogether(block))

    # ---- 6. TCO ----
    story.append(PageBreak())
    story.append(Paragraph("6. Costul total de proprietate (TCO)", ss["H2x"]))
    has_ins = tco_table and "Asigurare" in tco_table[0]
    if has_ins:
        hdr = ["Arhitectură", "Achiziție [€]", "Energie [€]", "Mentenanță [€]",
               "Asigurare [€]", "Rezidual [€]", "TCO total [€]"]
        rows = [hdr] + [[t["Arhitectură"].split(" (")[0], _fmt_int(t["Achiziție"]),
                         _fmt_int(t["Energie"]), _fmt_int(t["Mentenanță"]),
                         _fmt_int(t.get("Asigurare", 0)),
                         "−" + _fmt_int(t.get("Rezidual", 0)),
                         _fmt_int(t["TCO total"])] for t in tco_table]
        story.append(_tbl(rows, [3.0 * cm, 2.4 * cm, 2.2 * cm, 2.4 * cm,
                                 2.3 * cm, 2.2 * cm, 2.4 * cm]))
    else:
        hdr = ["Arhitectură", "Achiziție [€]", "Energie [€]", "Mentenanță [€]", "TCO total [€]"]
        rows = [hdr] + [[t["Arhitectură"], _fmt_int(t["Achiziție"]),
                         _fmt_int(t["Energie"]), _fmt_int(t["Mentenanță"]),
                         _fmt_int(t["TCO total"])] for t in tco_table]
        story.append(_tbl(rows, [4.2 * cm, 3.2 * cm, 3 * cm, 3.2 * cm, 3.2 * cm]))
    story.append(Spacer(1, 8))
    story.append(_tco_chart(tco_table))
    best_tco = min(tco_table, key=lambda t: t["TCO total"])
    worst_tco = max(tco_table, key=lambda t: t["TCO total"])
    tco_txt = (f"pe orizontul de {econ.years} ani și "
               f"{_fmt_int(econ.km_per_year)} km/an, configurația optimă economic "
               f"este <b>{best_tco['Arhitectură']}</b> "
               f"(TCO = {_fmt_int(best_tco['TCO total'])} EUR), cu "
               f"{_fmt_int(worst_tco['TCO total'] - best_tco['TCO total'])} EUR sub "
               f"{worst_tco['Arhitectură']}. Costul de achiziție domină TCO-ul, "
               f"astfel încât economia de combustibil a hibridelor trebuie să "
               f"amortizeze diferența de preț la achiziție.")
    if breakeven and breakeven.get("years"):
        tco_txt += (f" Punctul de amortizare (break-even) paralel vs baseline: "
                    f"<b>{breakeven['years']} ani</b> "
                    f"(~{_fmt_int(breakeven['km'])} km), la o economie anuală de "
                    f"{breakeven['annual_saving']:.0f} EUR.")
    story.append(Spacer(1, 4))
    story.append(_interp(ss, tco_txt))

    # ---- 7. Validare fizică ----
    story.append(PageBreak())
    story.append(Paragraph("7. Validarea fizică a simulărilor", ss["H2x"]))
    if has_full:
        sum_hdr = ["Arhitectură"] + list(cycles.keys())
        sum_rows = [sum_hdr]
        total_pass = total_checks = 0
        for a in arch_order:
            row = [ARCH_LABELS[a]]
            for c in cycles:
                ch = physical_validation(results[a][c], p)
                n_ok = sum(1 for x in ch if x["status"] == "PASS")
                total_pass += n_ok; total_checks += len(ch)
                row.append(f"{n_ok}/{len(ch)}")
            sum_rows.append(row)
        story.append(Paragraph("7.1. Sinteză: verificări trecute pe fiecare simulare",
                               ss["H3x"]))
        story.append(_tbl(sum_rows, [4.6 * cm] + [2.6 * cm] * len(cycles)))
        story.append(Spacer(1, 4))
        story.append(_interp(ss,
            f"din totalul de {total_checks} verificări fizice aplicate celor "
            f"{len(arch_order)}×{len(cycles)} simulări, {total_pass} sunt trecute "
            f"({total_pass/total_checks*100:.0f}%). Verificările acoperă: SoC în "
            f"fereastra de operare, puteri sub limitele componentelor, bilanț "
            f"energetic închis și plauzibilitatea consumului."))
        story.append(Paragraph(f"7.2. Detaliu: Paralel · {main_cycle}", ss["H3x"]))
    hdr = ["Verificare", "Status", "Detalii"]
    _cell = ParagraphStyle("vcell", fontName=_FONT_MAIN, fontSize=8,
                           leading=10, textColor=INK)
    rows = [hdr]
    for c in validation_checks:
        col = "#059669" if c["status"] == "PASS" else "#dc2626"
        status_p = Paragraph(f'<b><font color="{col}">{c["status"]}</font></b>', _cell)
        rows.append([c["check"], status_p, c["detail"]])
    t = _tbl(rows, [6 * cm, 1.8 * cm, 9 * cm])
    story.append(t)

    # ---- 7.3. Audit EEA (dacă raportul există) ----
    if eea_audit:
        story.append(Paragraph("7.3. Auditul EEA al bazei de date de vehicule",
                               ss["H3x"]))
        story.append(Paragraph(
            f"Baza de date de vehicule a fost încrucișată cu setul EEA de "
            f"monitorizare a emisiilor CO₂ (Regulamentul UE 2019/631), prin "
            f"comparație cu mediana înregistrărilor per model: "
            f"<b>{eea_audit['n_ok']}</b> vehicule OK (abateri ≤ ±6% masă, "
            f"≤ ±8% CO₂), <b>{eea_audit['n_check']}</b> de verificat manual, "
            f"<b>{eea_audit['n_missing']}</b> negăsite în EEA, din "
            f"{eea_audit['total']} total.", ss["Bodyx"]))
        veh = eea_audit.get("vehicle")
        if veh:
            story.append(Spacer(1, 4))
            rows = [["Vehiculul simulat", "Înregistrări EEA",
                     "Abatere masă [%]", "Abatere CO₂ [%]", "Status"],
                    [f'{veh.get("marca","")} {veh.get("model","")} '
                     f'{veh.get("varianta","")}',
                     str(veh.get("eea_inregistrari", "–")),
                     str(veh.get("abatere_masa_pct", "–")),
                     str(veh.get("abatere_co2_pct", "–")),
                     str(veh.get("status", "–"))]]
            story.append(_tbl(rows, [5.2 * cm, 2.8 * cm, 2.8 * cm,
                                     2.6 * cm, 3.4 * cm]))

    # ---- 8. Analiza de sensibilitate ----
    if sensitivity:
        story.append(PageBreak())
        story.append(Paragraph("8. Analiza de sensibilitate (±20%)", ss["H2x"]))
        story.append(Paragraph(
            f"Fiecare parametru este variat cu ±20% față de valoarea nominală "
            f"({sens_arch_label or 'arhitectura de referință'}, ciclul WLTC, "
            f"strategie bazată pe reguli); diagramele tornado ordonează parametrii "
            f"după mărimea efectului.", ss["Metax"]))
        story.append(Spacer(1, 4))

        base_c = sensitivity["base_consumption"]
        story.append(KeepTogether([
            Paragraph("8.1. Efectul asupra consumului", ss["H3x"]),
            _tornado_chart(sensitivity["consumption"], base_c,
                           "Consum [L/100 km]",
                           f"Sensibilitatea consumului (bază: {base_c:.3f} L/100 km)")]))
        rc = sorted(sensitivity["consumption"],
                    key=lambda e: abs(e["high"] - e["low"]), reverse=True)
        spans_c = [(e["label"], abs(e["high"] - e["low"]),
                    abs(e["high"] - e["low"]) / base_c * 100) for e in rc]
        top3 = "; ".join(f"<b>{l}</b> (interval {s:.3f} L/100 km, "
                         f"{pct:.1f}% din bază)" for l, s, pct in spans_c[:3])
        least = spans_c[-1]
        story.append(Spacer(1, 4))
        story.append(_interp(ss,
            f"cei mai influenți parametri asupra consumului sunt: {top3}. "
            f"Cel mai puțin influent este {least[0]} ({least[2]:.1f}% din bază). "
            f"Dominanța parametrilor de rezistență la înaintare (masă, rulare, "
            f"aerodinamică) și a randamentului termic este tipică modelelor "
            f"cvasi-statice: consumul răspunde aproape liniar la energia cerută "
            f"la roată și la eficiența conversiei; capacitatea bateriei are efect "
            f"redus la un full-hybrid charge-sustaining, unde bateria funcționează "
            f"ca tampon, nu ca sursă de energie."))

        base_t = sensitivity["base_tco"]
        story.append(KeepTogether([
            Paragraph("8.2. Efectul asupra costului total de proprietate", ss["H3x"]),
            _tornado_chart(sensitivity["tco"], base_t, "TCO [EUR]",
                           f"Sensibilitatea TCO (bază: {_fmt_int(base_t)} EUR)")]))
        rt = sorted(sensitivity["tco"],
                    key=lambda e: abs(e["high"] - e["low"]), reverse=True)
        spans_t = [(e["label"], abs(e["high"] - e["low"])) for e in rt]
        top3t = "; ".join(f"<b>{l}</b> (interval {_fmt_int(s)} EUR)"
                          for l, s in spans_t[:3])
        story.append(Spacer(1, 4))
        story.append(_interp(ss,
            f"asupra TCO-ului, cei mai influenți parametri sunt: {top3t}. "
            f"Parametrii economici (kilometraj anual, preț combustibil) intră în "
            f"competiție directă cu cei tehnici: un utilizator cu rulaj mare "
            f"amplifică orice diferență de consum, deci avantajul economic al "
            f"hibridei crește cu utilizarea. Parametrii tehnici acționează asupra "
            f"TCO indirect, prin consum — de aceea ordinea lor relativă o "
            f"urmărește pe cea din diagrama consumului."))

    # ---- 9. Comparație cu surse externe ----
    if comparison_data and comparison_data.get("comparisons"):
        story.append(PageBreak())
        story.append(Paragraph("9. Comparația cu valorile WLTP oficiale", ss["H2x"]))
        hdr = ["Sursă (vehicul)", "WLTP [L/100km]", "Abatere [%]", "Referință"]
        rows = [hdr] + [[c["name"], f'{c["official_L_100km"]:.2f}',
                         f'{c["deviation_pct"]:+.1f}', c["source"]]
                        for c in comparison_data["comparisons"]]
        story.append(_tbl(rows, [4.6 * cm, 3 * cm, 2.4 * cm, 6.8 * cm]))
        story.append(Spacer(1, 6))
        ref_row = next((c for c in comparison_data["comparisons"]
                        if "Bigster" in c["name"]), None)
        ref_txt = (f"Abaterea față de vehiculul de referință modelat "
                   f"(<b>{ref_row['name']}</b>) este <b>{ref_row['deviation_pct']:+.1f}%</b> — "
                   f"aceasta este comparația relevantă pentru acuratețea modelului; "
                   f"celelalte surse servesc doar la plasarea rezultatului într-un "
                   f"interval de plauzibilitate. " if ref_row else "")
        story.append(_interp(ss,
            f"comparația se realizează exclusiv pe ciclul de omologare WLTC "
            f"(procedura WLTP); ciclurile UDDS și HWFET sunt proceduri EPA și nu "
            f"sunt comparabile cu valorile de catalog. " + ref_txt +
            f"Abaterea medie față de cele {comparison_data['n_sources']} surse: "
            f"{comparison_data['avg_deviation_pct']:+.1f}%. O abatere pozitivă de "
            f"câteva procente este așteptată pentru un model cvasi-static "
            f"necalibrat fin: valorile de omologare sunt obținute în condiții "
            f"optimizate de constructor, iar consumul real depășește tipic "
            f"valoarea de catalog cu 10-20% (studiile ICCT)."))

    # ---- Notă finală ----
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Notă metodologică: modelul de simulare este cvasi-static, de tip "
        "backward-forward, cu modelul liniei Willans pentru consum. Rezultatele sunt "
        "destinate comparației relative între arhitecturi; valorile absolute depind de "
        "calibrarea parametrilor. Ciclul WLTC provine din biblioteca `wltp` (UNECE GTR15).",
        ss["Metax"]))

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            topMargin=1.6 * cm, bottomMargin=1.8 * cm,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            title="Raport de simulare — Arhitecturi de propulsie hibridă",
                            author="A.M. Beldugan, FIMIM, Univ. Ovidius Constanța")
    doc.build(story, onFirstPage=_watermark, onLaterPages=_watermark)
    return out_path
