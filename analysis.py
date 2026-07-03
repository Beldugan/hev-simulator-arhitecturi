"""
visualizations.py — Grafice interactive profesionale (Plotly)
==============================================================

Toate graficele aplicației: traiectorii SoC, profiluri de putere, hărți BSFC,
comparații pe arhitecturi, grafice de sensibilitate și TCO.

Paletă de culori consistentă, stil profesional unitar.
Licență: MIT
"""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from vehicle_model import VehicleParams, SimulationResult, bsfc_map

# Paleta aplicației (profesională, consistentă)
COLORS = {
    "baseline": "#8E8E93",       # iOS system gray
    "serie": "#007AFF",          # iOS blue
    "paralel": "#34C759",        # iOS green
    "serie_paralel": "#AF52DE",  # iOS purple
    "accent": "#FF9500",         # iOS orange
    "danger": "#FF3B30",         # iOS red
    "ink": "#000000",            # iOS label
    "grid": "rgba(60,60,67,0.15)",
}

_LAYOUT_BASE = dict(
    font=dict(family="-apple-system, SF Pro Text, Helvetica Neue, sans-serif", size=13, color="#3C3C43"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=50, r=20, t=50, b=45),
    hoverlabel=dict(bgcolor="white", font_size=12),
)


def _grid(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
    fig.update_yaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
    # Poziționare uniformă titlu/legendă pentru a evita suprapunerile:
    # titlul rămâne singur în banda de sus (stânga), iar legenda coboară sub
    # grafic. update_layout fuzionează dicționarele, deci textul titlului și
    # orientarea orizontală a legendei setate anterior se păstrează.
    fig.update_layout(
        title=dict(x=0.01, xanchor="left", y=0.97, yanchor="top",
                   font=dict(size=15, color="#000000")),
        legend=dict(orientation="h", yanchor="top", y=-0.16,
                    x=0.5, xanchor="center"),
        margin=dict(l=55, r=24, t=58, b=88),
    )
    return fig


def plot_soc_trajectory(results: dict[str, SimulationResult],
                        p: VehicleParams) -> go.Figure:
    """Traiectoriile SoC suprapuse pentru toate arhitecturile hibride."""
    fig = go.Figure()
    for arch, r in results.items():
        if arch == "baseline":
            continue
        t = np.arange(len(r.SoC))
        fig.add_trace(go.Scatter(
            x=t, y=r.SoC * 100, mode="lines", name=arch.replace("_", "-").title(),
            line=dict(color=COLORS.get(arch, "#333"), width=2),
            hovertemplate="t=%{x}s · SoC=%{y:.1f}%<extra>%{fullData.name}</extra>",
        ))
    fig.add_hline(y=p.SoC_target * 100, line_dash="dash", line_color="#AEAEB2",
                  annotation_text=f"Țintă {p.SoC_target*100:.0f}%")
    fig.add_hline(y=p.SoC_min * 100, line_dash="dot", line_color=COLORS["danger"],
                  annotation_text=f"Min {p.SoC_min*100:.0f}%")
    fig.update_layout(**_LAYOUT_BASE, title="Evoluția stării de încărcare (SoC)",
                      xaxis_title="Timp [s]", yaxis_title="SoC [%]",
                      legend=dict(orientation="h", y=1.12))
    return _grid(fig)


def plot_power_profile(r: SimulationResult, cycle_kmh: np.ndarray) -> go.Figure:
    """Profil detaliat: viteză + puteri MCI/EM + putere baterie (3 panouri)."""
    t = np.arange(len(cycle_kmh))
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("Profil de viteză", "Puteri MCI și mașină electrică",
                                        "Flux de putere prin baterie"))
    fig.add_trace(go.Scatter(x=t, y=cycle_kmh, name="Viteză",
                             line=dict(color=COLORS["ink"], width=1.5),
                             fill="tozeroy", fillcolor="rgba(15,23,42,0.06)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=r.P_engine_W / 1000, name="Motor termic",
                             line=dict(color=COLORS["danger"], width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=r.P_EM_W / 1000, name="Mașină electrică",
                             line=dict(color=COLORS["paralel"], width=1.2)), row=2, col=1)
    pos = np.where(r.P_bat_W > 0, r.P_bat_W / 1000, 0)
    neg = np.where(r.P_bat_W < 0, r.P_bat_W / 1000, 0)
    fig.add_trace(go.Scatter(x=t, y=pos, name="Descărcare", fill="tozeroy",
                             line=dict(color=COLORS["danger"], width=0.6),
                             fillcolor="rgba(255,59,48,0.30)"), row=3, col=1)
    fig.add_trace(go.Scatter(x=t, y=neg, name="Încărcare", fill="tozeroy",
                             line=dict(color=COLORS["paralel"], width=0.6),
                             fillcolor="rgba(52,199,89,0.30)"), row=3, col=1)
    fig.update_layout(**_LAYOUT_BASE, height=620,
                      legend=dict(orientation="h", y=1.06))
    fig.update_yaxes(title_text="km/h", row=1, col=1)
    fig.update_yaxes(title_text="kW", row=2, col=1)
    fig.update_yaxes(title_text="kW", row=3, col=1)
    fig.update_xaxes(title_text="Timp [s]", row=3, col=1)
    return _grid(fig)


def plot_bsfc_map(p: VehicleParams, r: SimulationResult | None = None) -> go.Figure:
    """Harta BSFC a motorului + punctele de operare din simulare."""
    P_range = np.linspace(2, p.P_ICE_max_kW, 120) * 1000
    bsfc = np.array([bsfc_map(P, p) for P in P_range])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=P_range / 1000, y=bsfc, mode="lines", name="Curbă BSFC",
        line=dict(color=COLORS["ink"], width=2.5),
        hovertemplate="P=%{x:.0f} kW · BSFC=%{y:.0f} g/kWh<extra></extra>",
    ))
    # Zona optimă (BSFC minim +5%)
    bsfc_min = bsfc.min()
    mask = bsfc <= bsfc_min * 1.05
    if mask.any():
        fig.add_vrect(x0=P_range[mask][0] / 1000, x1=P_range[mask][-1] / 1000,
                      fillcolor="rgba(52,199,89,0.12)", line_width=0,
                      annotation_text="Zonă optimă", annotation_position="top left")
    # Puncte de operare din simulare
    if r is not None:
        P_on = r.P_engine_W[r.P_engine_W > 500]
        if len(P_on):
            sample = P_on[::max(1, len(P_on) // 300)]
            b_pts = np.array([bsfc_map(P, p) for P in sample])
            fig.add_trace(go.Scatter(
                x=sample / 1000, y=b_pts, mode="markers", name="Puncte de operare",
                marker=dict(color=COLORS["accent"], size=6, opacity=0.45),
            ))
    fig.update_layout(**_LAYOUT_BASE, title="Harta consumului specific (BSFC)",
                      xaxis_title="Putere motor [kW]", yaxis_title="BSFC [g/kWh]",
                      legend=dict(orientation="h", y=1.12))
    return _grid(fig)


def plot_consumption_bars(data: dict[str, dict[str, float]],
                          title: str = "Consum pe arhitecturi și cicluri") -> go.Figure:
    """Bar chart grupat: arhitecturi × cicluri."""
    fig = go.Figure()
    archs = list(data.keys())
    cycles = list(next(iter(data.values())).keys())
    for arch in archs:
        fig.add_trace(go.Bar(
            name=arch.replace("_", "-").title(),
            x=cycles, y=[data[arch][c] for c in cycles],
            marker_color=COLORS.get(arch, "#666"),
            text=[f"{data[arch][c]:.2f}" for c in cycles],
            textposition="outside", textfont=dict(size=11),
        ))
    fig.update_layout(**_LAYOUT_BASE, barmode="group", title=title,
                      yaxis_title="Consum [L/100 km]",
                      legend=dict(orientation="h", y=1.12))
    return _grid(fig)


def plot_tco_breakdown(tco_data: dict[str, dict]) -> go.Figure:
    """Bar chart stivuit: componentele TCO pe arhitecturi."""
    archs = list(tco_data.keys())
    comp_labels = [("price", "Achiziție"), ("cost_energy", "Energie"),
                   ("maintenance", "Mentenanță"), ("insurance", "Asigurare/taxe")]
    comp_colors = ["#3C3C43", "#FF9500", "#007AFF", "#AEAEB2"]
    fig = go.Figure()
    for (key, label), color in zip(comp_labels, comp_colors):
        fig.add_trace(go.Bar(name=label, x=[a.replace("_", "-").title() for a in archs],
                             y=[tco_data[a][key] for a in archs], marker_color=color))
    # Valoarea reziduală ca negativ
    fig.add_trace(go.Bar(name="Valoare reziduală (−)",
                         x=[a.replace("_", "-").title() for a in archs],
                         y=[-tco_data[a]["residual"] for a in archs],
                         marker_color="#34C759"))
    # Etichete TCO total
    for i, a in enumerate(archs):
        fig.add_annotation(x=i, y=sum(tco_data[a][k] for k, _ in comp_labels) + 800,
                           text=f"<b>{tco_data[a]['tco_total']:,} €</b>".replace(",", " "),
                           showarrow=False, font=dict(size=12))
    fig.update_layout(**_LAYOUT_BASE, barmode="relative",
                      title="Defalcarea costului total de proprietate (10 ani)",
                      yaxis_title="EUR", legend=dict(orientation="h", y=1.12))
    return _grid(fig)


def plot_sensitivity_tornado(results: list[dict], baseline_value: float,
                             metric_label: str = "TCO [EUR]") -> go.Figure:
    """Diagramă tornado: efectul variației fiecărui parametru asupra metricii."""
    results = sorted(results, key=lambda r: abs(r["high"] - r["low"]), reverse=True)
    names = [r["label"] for r in results]
    lows = [r["low"] - baseline_value for r in results]
    highs = [r["high"] - baseline_value for r in results]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=names, x=lows, orientation="h", name="Parametru −20%",
                         marker_color="#007AFF",
                         hovertemplate="%{y}: %{x:+,.0f}<extra>−20%</extra>"))
    fig.add_trace(go.Bar(y=names, x=highs, orientation="h", name="Parametru +20%",
                         marker_color="#FF9500",
                         hovertemplate="%{y}: %{x:+,.0f}<extra>+20%</extra>"))
    fig.add_vline(x=0, line_color=COLORS["ink"], line_width=1.5)
    fig.update_layout(**_LAYOUT_BASE, barmode="overlay",
                      title=f"Analiza de sensibilitate — {metric_label} "
                            f"(referință: {baseline_value:,.0f})".replace(",", " "),
                      xaxis_title=f"Variația {metric_label} față de referință",
                      legend=dict(orientation="h", y=1.1), height=420)
    return _grid(fig)


def plot_vehicle_comparison(res_a: dict, res_b: dict,
                            name_a: str, name_b: str) -> go.Figure:
    """Comparație radar/bare între două vehicule pe metrici cheie."""
    metrics = ["Consum WLTC", "CO₂", "TCO", "Cotă EV"]
    vals_a = [res_a["cons"], res_a["co2"], res_a["tco"] / 1000, res_a["ev"]]
    vals_b = [res_b["cons"], res_b["co2"], res_b["tco"] / 1000, res_b["ev"]]
    units = ["L/100km", "g/km", "k€", "%"]
    fig = make_subplots(rows=1, cols=4, subplot_titles=[f"{m} [{u}]" for m, u in zip(metrics, units)])
    for i, (va, vb) in enumerate(zip(vals_a, vals_b), start=1):
        fig.add_trace(go.Bar(x=[name_a], y=[va], marker_color="#007AFF",
                             showlegend=(i == 1), name=name_a,
                             text=[f"{va:.2f}"], textposition="outside"), row=1, col=i)
        fig.add_trace(go.Bar(x=[name_b], y=[vb], marker_color="#FF9500",
                             showlegend=(i == 1), name=name_b,
                             text=[f"{vb:.2f}"], textposition="outside"), row=1, col=i)
    fig.update_layout(**_LAYOUT_BASE, height=380,
                      title="Comparație vehicul A vs vehicul B",
                      legend=dict(orientation="h", y=1.18))
    return _grid(fig)
