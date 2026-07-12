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
from ems_strategies import ARCH_LABELS

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

# --- Tema grafică (light implicit / dark iOS) --------------------------
_DARK = False


def set_dark(flag: bool) -> None:
    """Comută paleta graficelor Plotly între light (implicit) și dark iOS."""
    global _DARK
    _DARK = bool(flag)


def _theme_colors() -> dict:
    if _DARK:
        return dict(card="#1C1C1E", ink="#E5E5EA", font="#F2F2F7",
                    grid="rgba(84,84,88,0.45)", hover="#2C2C2E")
    return dict(card="#FFFFFF", ink="#3C3C43", font="#000000",
                grid=COLORS["grid"], hover="white")


def _grid(fig: go.Figure) -> go.Figure:
    c = _theme_colors()
    fig.update_xaxes(gridcolor=c["grid"], zerolinecolor=c["grid"],
                     tickfont=dict(color=c["ink"]),
                     title_font=dict(color=c["ink"]))
    fig.update_yaxes(gridcolor=c["grid"], zerolinecolor=c["grid"],
                     tickfont=dict(color=c["ink"]),
                     title_font=dict(color=c["ink"]))
    fig.update_layout(font_color=c["ink"],
                      hoverlabel=dict(bgcolor=c["hover"],
                                      font_color=c["font"]),
                      legend_font_color=c["ink"])
    for ann in fig.layout.annotations:      # titlurile de subgrafic etc.
        if ann.font is None or ann.font.color is None:
            ann.font = dict(color=c["ink"], size=(ann.font.size if ann.font else None))
    # Poziționare uniformă titlu/legendă pentru a evita suprapunerile:
    # titlul rămâne singur în banda de sus (stânga), iar legenda coboară sub
    # grafic. Poziția titlului se setează DOAR dacă există text de titlu —
    # altfel plotly.js afișează literal „undefined".
    if fig.layout.title.text:
        fig.update_layout(
            title=dict(x=0.01, xanchor="left", y=0.97, yanchor="top",
                       font=dict(size=15, color=c["font"])))
    fig.update_layout(
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
            x=t, y=r.SoC * 100, mode="lines",
            name=ARCH_LABELS.get(arch, arch).split(" (")[0],
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
    """Profil detaliat: viteza de deplasare + puterile MAI/motor electric + putere baterie (3 panouri)."""
    t = np.arange(len(cycle_kmh))
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("Viteza de deplasare", "Putere MAI și motor electric",
                                        "Flux de putere prin baterie"))
    th = _theme_colors()
    fig.add_trace(go.Scatter(x=t, y=cycle_kmh, name="Viteză",
                             line=dict(color=th["ink"], width=1.5),
                             fill="tozeroy",
                             fillcolor=("rgba(229,229,234,0.10)" if _DARK
                                        else "rgba(15,23,42,0.06)")), row=1, col=1)
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
        line=dict(color=_theme_colors()["ink"], width=2.5),
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
    fig.update_layout(**_LAYOUT_BASE,
                      title=dict(text="Harta consumului specific (BSFC)",
                                 font=dict(size=15)),
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
            name=ARCH_LABELS.get(arch, arch).split(" (")[0],
            x=cycles, y=[data[arch][c] for c in cycles],
            marker_color=COLORS.get(arch, "#666"),
            text=[f"{data[arch][c]:.2f}" for c in cycles],
            textposition="outside", textfont=dict(size=11),
        ))
    fig.update_layout(**_LAYOUT_BASE, barmode="group", title=title,
                      yaxis_title="Consum [L/100 km]",
                      legend=dict(orientation="h", y=1.12))
    # Etichetele ciclurilor (ex. "Real urban (Constanța)") sunt lungi și se
    # suprapun dacă rămân orizontale — le înclinăm și mărim marginea de jos
    # ca să încapă complet, fără să se calce una pe alta.
    fig.update_layout(xaxis=dict(tickangle=-25),
                      margin=dict(l=50, r=20, t=50, b=80))
    return _grid(fig)


def plot_tco_breakdown(tco_data: dict[str, dict]) -> go.Figure:
    """Bar chart stivuit: componentele TCO pe arhitecturi."""
    archs = list(tco_data.keys())
    comp_labels = [("price", "Achiziție"), ("cost_energy", "Energie"),
                   ("maintenance", "Mentenanță"), ("insurance", "Asigurare/taxe")]
    comp_colors = [("#8E8E93" if _DARK else "#3C3C43"),
                   "#FF9500", "#007AFF", "#AEAEB2"]
    fig = go.Figure()
    for (key, label), color in zip(comp_labels, comp_colors):
        fig.add_trace(go.Bar(name=label, x=[ARCH_LABELS.get(a, a).split(" (")[0] for a in archs],
                             y=[tco_data[a][key] for a in archs], marker_color=color))
    # Valoarea reziduală ca negativ
    fig.add_trace(go.Bar(name="Valoare reziduală (−)",
                         x=[ARCH_LABELS.get(a, a).split(" (")[0] for a in archs],
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
    fig.add_vline(x=0, line_color=_theme_colors()["ink"], line_width=1.5)
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


# ======================================================================
#  Derularea LIVE a ciclului + analiza pornirilor MAI
# ======================================================================
CYCLE_INFO: dict[str, str] = {
    "WLTC": (
        "**WLTC clasa 3b** — ciclul de omologare european (WLTP, UNECE GTR 15). "
        "Durează **1800 s (30 min)** pe **~23,3 km** și este împărțit în 4 faze "
        "după viteză: **Low** (589 s, urban, vârf 56,5 km/h), **Medium** (433 s, "
        "suburban, vârf 76,6 km/h), **High** (455 s, extraurban, vârf 97,4 km/h) "
        "și **Extra-High** (323 s, autostradă, vârf 131,3 km/h). Profil dinamic, "
        "cu opriri multiple în prima parte — acoperă întregul spectru de utilizare."
    ),
    "UDDS": (
        "**UDDS (FTP-72)** — ciclul urban american (EPA). Durează **1369 s "
        "(~23 min)** pe **~12,1 km**, cu vârf de 91,2 km/h și opriri frecvente "
        "(17 opriri) — reproduce traficul de oraș cu accelerări/frânări dese. "
        "Este ciclul cel mai favorabil hibridelor: multă frânare regenerativă și "
        "rulare electrică la viteze mici."
    ),
    "HWFET": (
        "**HWFET** — ciclul de autostradă american (EPA). Durează **765 s "
        "(~13 min)** pe **~16,5 km**, în curgere continuă, fără opriri, cu viteza "
        "medie ~77 km/h. Este cel mai defavorabil hibridelor: frânare "
        "regenerativă aproape absentă, motorul termic funcționează cvasi-permanent."
    ),
    "Real urban (Constanța)": (
        "**Traseu real urban** — înregistrat prin OBD-II (aplicația Torque) pe un "
        "vehicul propriu, pe naveta zilnică prin Constanța. ~13,4 km, cu opriri "
        "frecvente la semafoare — regim urban autentic, în care avantajul "
        "hibridelor (rulare electrică, recuperare la frânare) este maxim. Profil "
        "de viteză reeșantionat la 1 Hz din date reale."
    ),
    "Real mixt (Constanța)": (
        "**Traseu real mixt** — înregistrat prin OBD-II pe un vehicul propriu, pe "
        "un parcurs periurban Constanța–Năvodari. ~17,4 km, cu mai puține opriri "
        "și viteze susținute (până la ~78 km/h) — regim mixt, mai apropiat de "
        "condițiile de rulare constantă. Profil reeșantionat la 1 Hz din date reale."
    ),
}

# Limitele fazelor WLTC clasa 3b [s] (Low | Medium | High | Extra-High)
_WLTC_PHASES = [(0, 589, "Low"), (589, 1022, "Medium"),
                (1022, 1477, "High"), (1477, 1800, "Extra-High")]


def cycle_stats(speed_kmh: np.ndarray) -> dict:
    """Statistici de ciclu calculate din profilul de viteză (dt = 1 s)."""
    v = np.asarray(speed_kmh, dtype=float)
    dist_km = float(np.sum(v / 3.6)) / 1000.0
    moving = v > 0.5
    return dict(
        duration_s=int(len(v)),
        distance_km=dist_km,
        v_max=float(v.max()),
        v_avg=float(v.mean()),
        v_avg_moving=float(v[moving].mean()) if moving.any() else 0.0,
        idle_pct=float(np.mean(~moving)) * 100.0,
        n_stops=int(np.sum((~moving[1:]) & moving[:-1])),
    )


def ignition_events(r: SimulationResult, speed_kmh: np.ndarray,
                    thr_W: float = 500.0) -> dict:
    """Momentele în care pornește motorul termic + viteza și SoC-ul la pornire."""
    on = r.P_engine_W > thr_W
    starts = np.where(on[1:] & ~on[:-1])[0] + 1
    if on[0]:
        starts = np.concatenate([[0], starts])
    return dict(
        t=starts.astype(int),
        speed=np.asarray(speed_kmh)[starts],
        soc=r.SoC[starts] * 100.0,
        n=int(len(starts)),
        on_share_pct=float(np.mean(on)) * 100.0,
    )


def plot_cycle_live(r: SimulationResult, speed_kmh: np.ndarray,
                    p: VehicleParams, title: str, speed: int = 1) -> go.Figure:
    """
    Grafic animat (Play/Pauză + cursor): derularea în timp a ciclului.

    Redarea la viteza 1x durează exact cât ciclul real; parametrul `speed`
    (1/5/10/15/20/25/30) accelerează derularea. Tehnic, curbele sunt desenate
    complet, iar animația retrage o „cortină" albă și mută un cursor — cadrele
    conțin doar forme de layout, deci figura rămâne ușoară indiferent de durată.

    Rândul 1: viteza, colorată după starea MAI (roșu = pornit, verde = electric),
              cu marcaje la fiecare pornire a motorului termic.
    Rândul 2: consumul de combustibil cumulat [L] și CO₂ cumulat [g].
    Rândul 3: starea de încărcare a bateriei [%].
    """
    v = np.asarray(speed_kmh, dtype=float)
    n = len(v)
    t = np.arange(n)
    on = r.P_engine_W > 500.0
    fuel_cum_L = np.cumsum(r.fuel_rate_g_s) / (p.fuel_density_kg_L * 1000.0)
    co2_cum_g = np.cumsum(r.fuel_rate_g_s) * (p.fuel_CO2_kg_L / p.fuel_density_kg_L)
    soc_pct = r.SoC * 100.0
    ign = ignition_events(r, v)
    v_ice = np.where(on, v, 0.0)
    v_ev = np.where(~on, v, 0.0)
    th = _theme_colors()

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        row_heights=[0.40, 0.32, 0.28],
                        specs=[[{}], [{"secondary_y": True}], [{}]])

    fig.add_trace(go.Scatter(x=t, y=v, mode="lines",
                             line=dict(color=th["ink"], width=1.4),
                             name="Viteză [km/h]"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=v_ice, mode="lines",
                             line=dict(width=0), fill="tozeroy",
                             fillcolor="rgba(220,38,38,0.30)",
                             name="MAI pornit"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=v_ev, mode="lines",
                             line=dict(width=0), fill="tozeroy",
                             fillcolor="rgba(16,185,129,0.30)",
                             name="Electric (MAI oprit)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=ign["t"], y=ign["speed"], mode="markers",
                             marker=dict(symbol="triangle-up", size=9,
                                         color="#dc2626",
                                         line=dict(color="white", width=1)),
                             name="Pornire MAI"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=fuel_cum_L, mode="lines",
                             line=dict(color="#f59e0b", width=2),
                             name="Combustibil cumulat [L]"), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=co2_cum_g, mode="lines",
                             line=dict(color="#64748b", width=2, dash="dot"),
                             name="CO₂ cumulat [g]"), row=2, col=1,
                  secondary_y=True)
    fig.add_trace(go.Scatter(x=t, y=soc_pct, mode="lines",
                             line=dict(color="#8b5cf6", width=2),
                             name="SoC [%]"), row=3, col=1)
    fig.add_trace(go.Scatter(x=[0, n - 1], y=[p.SoC_target * 100] * 2,
                             mode="lines",
                             line=dict(color="#94a3b8", width=1, dash="dash"),
                             name="SoC țintă", showlegend=False), row=3, col=1)

    # Fazele WLTC — linii ca trasee statice + adnotări (rămân sub cortină)
    if 1790 <= n <= 1810:
        for x0, x1, name in _WLTC_PHASES:
            fig.add_trace(go.Scatter(x=[x1, x1], y=[0, v.max() * 1.12],
                                     mode="lines", showlegend=False,
                                     hoverinfo="skip",
                                     line=dict(color="#cbd5e1", width=1,
                                               dash="dot")), row=1, col=1)
            fig.add_annotation(x=(x0 + x1) / 2, y=0.94, yref="y domain",
                               xref="x", text=name, showarrow=False,
                               font=dict(size=9, color="#8E8E93"), row=1, col=1)

    # --- Animația: cortină + cursor (doar layout, cadre foarte ușoare) ---
    def _shapes(cur: int) -> list[dict]:
        return [
            dict(type="rect", xref="x", yref="paper", layer="above",
                 x0=cur, x1=n, y0=0, y1=1,
                 fillcolor=th["card"], opacity=1.0, line_width=0),
            dict(type="line", xref="x", yref="paper", layer="above",
                 x0=cur, x1=cur, y0=0, y1=1,
                 line=dict(color=th["ink"], width=1)),
        ]

    step_s = 2                                   # 1 cadru = 2 s de ciclu
    cuts = list(range(0, n, step_s)) + [n]
    frame_ms = step_s * 1000.0 / max(1, int(speed))
    fig.frames = [go.Frame(name=str(c), layout=dict(shapes=_shapes(c)))
                  for c in cuts]
    fig.update_layout(shapes=_shapes(0))

    # Axe fixe (nu se rescalează în timpul animației)
    fig.update_xaxes(range=[0, n], row=3, col=1, title_text="Timp [s]")
    fig.update_xaxes(range=[0, n], row=1, col=1)
    fig.update_xaxes(range=[0, n], row=2, col=1)
    fig.update_yaxes(range=[0, v.max() * 1.12], title_text="km/h", row=1, col=1)
    fig.update_yaxes(range=[0, max(fuel_cum_L[-1], 1e-3) * 1.12],
                     title_text="L", row=2, col=1, secondary_y=False)
    fig.update_yaxes(range=[0, max(co2_cum_g[-1], 1e-3) * 1.12],
                     title_text="g CO₂", row=2, col=1, secondary_y=True)
    fig.update_yaxes(range=[min(soc_pct.min() * 0.97, 45),
                            max(soc_pct.max() * 1.03, 65)],
                     title_text="SoC [%]", row=3, col=1)

    slider_cuts = cuts[::max(1, len(cuts) // 90)]
    fig.update_layout(
        template="plotly_dark" if th["card"] != "#FFFFFF" else "plotly_white",
        paper_bgcolor=th["card"], plot_bgcolor=th["card"],
        font=dict(color=th["ink"]),
        height=640,
        title=dict(text=title, x=0.01, y=0.98,
                   font=dict(size=15, color=th["font"])),
        legend=dict(orientation="h", y=-0.40, x=0.5, xanchor="center",
                    font=dict(size=10)),
        margin=dict(l=55, r=24, t=64, b=170),
        updatemenus=[dict(
            type="buttons", direction="left",
            x=0.99, y=1.10, xanchor="right", yanchor="top",
            pad=dict(r=0, t=0),
            bgcolor="#2C2C2E" if _DARK else "#FFFFFF",
            bordercolor="rgba(84,84,88,0.65)" if _DARK else "#cbd5e1",
            font=dict(color="#F2F2F7" if _DARK else "#000000"),
            buttons=[
                dict(label="▶ Redă", method="animate",
                     args=[None, dict(frame=dict(duration=frame_ms,
                                                 redraw=False),
                                      transition=dict(duration=0),
                                      fromcurrent=True)]),
                dict(label="❚❚ Pauză", method="animate",
                     args=[[None], dict(frame=dict(duration=0, redraw=False),
                                        mode="immediate")]),
            ])],
        sliders=[dict(
            active=0, x=0.0, y=-0.20, xanchor="left", yanchor="top",
            len=1.0, font=dict(size=9, color=th["ink"]),
            bordercolor=th["grid"], tickcolor=th["ink"],
            currentvalue=dict(prefix="t ≈ ", suffix=" s",
                              font=dict(size=11, color=th["ink"])),
            pad=dict(b=0, t=0),
            steps=[dict(method="animate", label=str(c),
                        args=[[str(c)], dict(frame=dict(duration=0,
                                                        redraw=False),
                                             mode="immediate")])
                   for c in slider_cuts])],
    )
    return fig


def plot_ignition_scatter(r: SimulationResult, speed_kmh: np.ndarray) -> go.Figure:
    """Pornirile MAI în planul SoC — viteză, colorate după momentul din ciclu."""
    ign = ignition_events(r, speed_kmh)
    fig = go.Figure(go.Scatter(
        x=ign["soc"], y=ign["speed"], mode="markers",
        marker=dict(size=10, color=ign["t"], colorscale="Viridis",
                    colorbar=dict(title="Timp [s]", thickness=12),
                    line=dict(color="white", width=1)),
        text=[f"t = {tt} s" for tt in ign["t"]],
        hovertemplate="SoC: %{x:.1f}%<br>Viteză: %{y:.1f} km/h<br>%{text}<extra></extra>",
    ))
    fig.update_layout(**_LAYOUT_BASE, height=360,
                      title="Pornirile motorului termic: viteză vs SoC",
                      xaxis_title="SoC la pornire [%]",
                      yaxis_title="Viteză la pornire [km/h]")
    return _grid(fig)
