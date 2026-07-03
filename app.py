"""
app.py — Simulator comparativ de arhitecturi de propulsie hibridă
==================================================================
Interfață web profesională (Streamlit) cu 5 module:
  Simulare · Sensibilitate · Comparație A/B · Validare fizică · Export PDF

Rulare:  streamlit run app.py
A.M. Beldugan, FIMIM, Universitatea Ovidius din Constanța, 2026. Licență MIT.
"""
import os
import sys
import tempfile
import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from vehicle_model import VehicleParams
from ems_strategies import simulate, ARCHITECTURES, ARCH_LABELS, STRATEGY_LABELS
from tco_model import (EconomicParams, compute_tco, compute_breakeven,
                       compare_with_sources)
from analysis import sensitivity_analysis, physical_validation
from visualizations import (plot_soc_trajectory, plot_power_profile, plot_bsfc_map,
                            plot_consumption_bars, plot_tco_breakdown,
                            plot_sensitivity_tornado, plot_vehicle_comparison)
from pdf_export import generate_pdf_report

# ======================================================================
#  Configurare pagină + CSS profesional
# ======================================================================
st.set_page_config(page_title="HEV Architecture Simulator",
                   page_icon="⚡", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
    /* ===== iOS Light Design System ===== */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text',
                     'SF Pro Display', 'Helvetica Neue', 'Segoe UI', sans-serif;
        -webkit-font-smoothing: antialiased;
    }
    .stApp { background: #F2F2F7; }
    .main .block-container { padding-top: 1.0rem; max-width: 1280px; }

    /* Header — card mare iOS, alb, titlu mare stânga */
    .app-header {
        background: #FFFFFF; border-radius: 16px; padding: 22px 26px;
        margin-bottom: 14px; box-shadow: 0 1px 2px rgba(0,0,0,.04);
        border: 0.5px solid rgba(60,60,67,.12);
    }
    .app-header h1 { margin: 0; font-size: 1.9rem; font-weight: 700;
                     color: #000; letter-spacing: -.02em; }
    .app-header p  { margin: 5px 0 0; color: #8E8E93; font-size: .92rem; }

    /* Carduri metrice — celule iOS */
    div[data-testid="stMetric"] {
        background: #FFFFFF; border: 0.5px solid rgba(60,60,67,.12);
        border-radius: 14px; padding: 14px 18px;
        box-shadow: 0 1px 2px rgba(0,0,0,.03);
    }
    div[data-testid="stMetric"] label { color: #8E8E93 !important;
        font-weight: 500; font-size: .82rem; text-transform: none; }
    div[data-testid="stMetricValue"] { color: #000; font-weight: 700;
        letter-spacing: -.01em; }
    div[data-testid="stMetricDelta"] { font-weight: 600; }

    /* Butoane — pill iOS albastru */
    .stButton>button[kind="primary"], .stDownloadButton>button {
        background: #007AFF; color: #fff; border: none; border-radius: 12px;
        font-weight: 600; padding: .6rem 1.5rem; box-shadow: none;
        transition: opacity .15s;
    }
    .stButton>button[kind="primary"]:hover, .stDownloadButton>button:hover {
        background: #0071EB; color: #fff;
    }
    .stButton>button[kind="primary"]:active { opacity: .7; }

    /* Sidebar — iOS Settings: fundal gri, grupuri albe */
    section[data-testid="stSidebar"] {
        background: #F2F2F7; border-right: 0.5px solid rgba(60,60,67,.15);
    }
    section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
    section[data-testid="stSidebar"] h2 {
        font-size: .8rem; color: #8E8E93; font-weight: 600;
        text-transform: uppercase; letter-spacing: .04em;
    }
    section[data-testid="stSidebar"] h3 {
        font-size: .8rem; color: #8E8E93; font-weight: 600;
        text-transform: uppercase; letter-spacing: .04em; margin-top: 1rem;
    }
    /* Inputuri sidebar ca celule iOS */
    section[data-testid="stSidebar"] div[data-testid="stNumberInput"] input,
    section[data-testid="stSidebar"] div[data-testid="stTextInput"] input,
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background: #FFFFFF; border-radius: 10px;
        border: 0.5px solid rgba(60,60,67,.15);
    }
    section[data-testid="stSidebar"] label { color: #000; font-size: .86rem; }

    /* Radio — listă iOS */
    div[data-testid="stRadio"] > div {
        background: #FFFFFF; border-radius: 12px; padding: 6px 12px;
        border: 0.5px solid rgba(60,60,67,.12);
    }

    /* Tabele */
    div[data-testid="stDataFrame"] {
        border: 0.5px solid rgba(60,60,67,.12); border-radius: 14px;
        overflow: hidden; background: #fff;
    }

    /* Selectbox principale */
    div[data-baseweb="select"] > div { border-radius: 10px; }

    /* Alerte info/succes — stil iOS banner */
    div[data-testid="stAlert"] { border-radius: 12px; border: none; }

    /* Badge-uri status — pill iOS */
    .badge-pass { background: #E8F9EE; color: #34C759; padding: 3px 12px;
                  border-radius: 999px; font-weight: 700; font-size: .8rem; }
    .badge-fail { background: #FFEBEA; color: #FF3B30; padding: 3px 12px;
                  border-radius: 999px; font-weight: 700; font-size: .8rem; }

    /* Separatoare fine */
    hr { border: none; border-top: 0.5px solid rgba(60,60,67,.18); }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="app-header">
  <h1>HEV Architecture Simulator</h1>
  <p>Analiza comparativă a configurațiilor de propulsie hibridă — serie · paralel · serie-paralel —
  pentru vehicule de clasă C-SUV · FIMIM, Universitatea Ovidius din Constanța, 2026</p>
</div>
""", unsafe_allow_html=True)


# ======================================================================
#  Încărcarea ciclurilor (cache)
# ======================================================================
@st.cache_data
def load_cycles() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    dd = os.path.join(here, "data")
    cycles = {}
    for label, fname in [("WLTC", "wltc_class3b_reference.csv"),
                         ("UDDS", "udds.csv"), ("HWFET", "hwfet.csv")]:
        path = os.path.join(dd, fname)
        if os.path.exists(path):
            cycles[label] = pd.read_csv(path)["speed_kmh"].values
    return cycles


def params_from_sidebar(prefix: str = "", defaults: VehicleParams | None = None) -> VehicleParams:
    d = defaults or VehicleParams()
    return VehicleParams(
        name=st.sidebar.text_input("Denumire", d.name, key=f"{prefix}name"),
        mass_kg=st.sidebar.number_input("Masă [kg]", 800.0, 3000.0, d.mass_kg, 10.0, key=f"{prefix}m"),
        Cd=st.sidebar.number_input("Cd", 0.20, 0.50, d.Cd, 0.01, key=f"{prefix}cd"),
        Af=st.sidebar.number_input("Arie frontală [m²]", 1.5, 3.5, d.Af, 0.05, key=f"{prefix}af"),
        f_rr=st.sidebar.number_input("Rezist. rulare", 0.006, 0.020, d.f_rr, 0.001,
                                     format="%.3f", key=f"{prefix}frr"),
        P_ICE_max_kW=st.sidebar.number_input("Putere MCI [kW]", 40.0, 200.0, d.P_ICE_max_kW, 1.0, key=f"{prefix}pice"),
        eta_th_peak=st.sidebar.number_input("Randament termic", 0.30, 0.45, d.eta_th_peak, 0.01, key=f"{prefix}eta"),
        P_EM_max_kW=st.sidebar.number_input("Putere EM [kW]", 10.0, 150.0, d.P_EM_max_kW, 1.0, key=f"{prefix}pem"),
        bat_energy_kWh=st.sidebar.number_input("Baterie [kWh]", 0.5, 60.0, d.bat_energy_kWh, 0.1, key=f"{prefix}bat"),
        price_EUR=st.sidebar.number_input("Preț [EUR]", 15000.0, 90000.0, d.price_EUR, 100.0, key=f"{prefix}pr"),
    )


# ======================================================================
#  Sidebar: mod + parametri
# ======================================================================
st.sidebar.markdown("## ⚙️ Configurare")
mode = st.sidebar.radio("Date de intrare",
                        ["📄 Preset: Bigster (lucrare)", "✏️ Introducere manuală"])
strategy = st.sidebar.selectbox("Strategie EMS",
                                options=["rule_based", "ecms", "dp"],
                                format_func=lambda s: STRATEGY_LABELS[s])
if strategy == "dp":
    st.sidebar.info("⏱️ Benchmark PMP-shooting: ~10-20 s per rulare completă.")

if mode == "✏️ Introducere manuală":
    st.sidebar.markdown("### Parametrii vehiculului")
    p_active = params_from_sidebar()
else:
    p_active = VehicleParams()

st.sidebar.markdown("### 💶 Parametri economici")
econ = EconomicParams(
    km_per_year=st.sidebar.number_input("Kilometraj anual [km]", 5000.0, 40000.0, 15000.0, 1000.0),
    fuel_price_EUR_L=st.sidebar.number_input("Preț benzină [EUR/L]", 1.0, 3.0, 1.83, 0.01),
    elec_price_EUR_kWh=st.sidebar.number_input("Preț electricitate [EUR/kWh]", 0.10, 0.60, 0.28, 0.01),
    rabla_plus_EUR=st.sidebar.number_input("Subvenție Rabla Plus [EUR]", 0.0, 10000.0, 0.0, 500.0),
)

run_btn = st.sidebar.button("▶ Rulează simularea", type="primary", use_container_width=True)

cycles = load_cycles()
PRICE_MAP = {"baseline": 0.84, "serie": 0.98, "paralel": 1.00, "serie_paralel": 1.04}


# ======================================================================
#  Rularea simulărilor (cu cache pe sesiune)
# ======================================================================
if run_btn or "results" not in st.session_state:
    if run_btn:
        prog = st.progress(0.0, "Se rulează simulările…")
        results, done = {}, 0
        total = len(ARCHITECTURES) * len(cycles)
        for arch in ARCHITECTURES:
            results[arch] = {}
            for cyc, speed in cycles.items():
                results[arch][cyc] = simulate(arch, p_active, speed, cyc, strategy=strategy)
                done += 1
                prog.progress(done / total, f"{ARCH_LABELS[arch]} · {cyc}")
        prog.empty()
        st.session_state["results"] = results
        st.session_state["params"] = p_active
        st.session_state["strategy"] = strategy
        st.session_state["econ"] = econ

if "results" not in st.session_state:
    st.info("Configurați parametrii în bara laterală și apăsați **Rulează simularea**.")
    st.stop()

results = st.session_state["results"]
p_used = st.session_state["params"]
strat_used = st.session_state["strategy"]
econ_used = st.session_state.get("econ", econ)


# ======================================================================
#  PAGINI — definite ca funcții; navigarea se face din meniul din dreapta
# ======================================================================
def page_simulare():
    # Metrici sumare
    base_wltc = results["baseline"]["WLTC"].consumption_L_100km
    par_wltc = results["paralel"]["WLTC"].consumption_L_100km
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Baseline · WLTC", f"{base_wltc:.2f} L/100km")
    c2.metric("Paralel · WLTC", f"{par_wltc:.2f} L/100km",
              f"−{(base_wltc-par_wltc)/base_wltc*100:.1f}%")
    best_arch = min((a for a in ARCHITECTURES if a != "baseline"),
                    key=lambda a: results[a]["WLTC"].consumption_L_100km)
    c3.metric("Configurația optimă", ARCH_LABELS[best_arch].split(" (")[0])
    c4.metric("Strategie", STRATEGY_LABELS[strat_used].split(" (")[0])

    rows = []
    for arch in ARCHITECTURES:
        for cyc in cycles:
            r = results[arch][cyc]
            base = results["baseline"][cyc].consumption_L_100km
            rows.append({"Arhitectură": ARCH_LABELS[arch], "Ciclu": cyc,
                         "Consum [L/100km]": r.consumption_L_100km,
                         "CO₂ [g/km]": r.co2_g_km,
                         "Cotă EV [%]": r.ev_share_pct,
                         "Reducere [%]": round((base - r.consumption_L_100km) / base * 100, 1)})
    df = pd.DataFrame(rows)
    with st.expander("Rezultate detaliate", expanded=False):
        st.dataframe(df, use_container_width=True, hide_index=True, height=420)

    colA, colB = st.columns(2)
    with colA:
        cons_data = {a: {c: results[a][c].consumption_L_100km for c in cycles}
                     for a in ARCHITECTURES}
        st.plotly_chart(plot_consumption_bars(cons_data), use_container_width=True)
    with colB:
        st.plotly_chart(plot_soc_trajectory(
            {a: results[a]["WLTC"] for a in ARCHITECTURES}, p_used),
            use_container_width=True)

    st.markdown("#### Analiză detaliată pe arhitectură")
    sel_arch = st.selectbox("Arhitectura", [a for a in ARCHITECTURES],
                            format_func=lambda a: ARCH_LABELS[a])
    sel_cyc = st.selectbox("Ciclul", list(cycles.keys()))
    r_sel = results[sel_arch][sel_cyc]
    st.plotly_chart(plot_power_profile(r_sel, cycles[sel_cyc]), use_container_width=True)
    st.plotly_chart(plot_bsfc_map(p_used, r_sel), use_container_width=True)

    st.markdown("#### 💶 Costul total de proprietate")
    tco_data = {}
    for arch in ARCHITECTURES:
        avg = np.mean([results[arch][c].consumption_L_100km for c in cycles])
        tco_data[arch] = compute_tco(p_used.price_EUR * PRICE_MAP[arch], avg,
                                     p_used.residual_frac, econ_used,
                                     is_hev=(arch != "baseline"))
    st.plotly_chart(plot_tco_breakdown(tco_data), use_container_width=True)
    be = compute_breakeven(p_used.price_EUR * PRICE_MAP["baseline"],
                           p_used.price_EUR,
                           np.mean([results["baseline"][c].consumption_L_100km for c in cycles]),
                           np.mean([results["paralel"][c].consumption_L_100km for c in cycles]),
                           econ_used)
    if be.get("years"):
        st.success(f"**Break-even Paralel vs Baseline:** {be['years']} ani "
                   f"(~{be['km']:,} km) · economie anuală {be['annual_saving']:.0f} EUR".replace(",", " "))

    st.markdown("#### 🌐 Comparația cu valorile WLTP oficiale")
    sp_avg = np.mean([results["serie_paralel"][c].consumption_L_100km for c in cycles])
    cmpv = compare_with_sources(sp_avg, "serie_paralel", min_sources=3)
    st.dataframe(pd.DataFrame([{
        "Sursă (vehicul)": c["name"], "WLTP [L/100km]": c["official_L_100km"],
        "Abatere [%]": c["deviation_pct"], "Referință": c["source"]}
        for c in cmpv["comparisons"]]), use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------
def page_sensibilitate():
    st.markdown("#### Analiza de sensibilitate completă")
    st.caption("Fiecare parametru este variat cu ±20%; se măsoară efectul asupra "
               "consumului și asupra TCO. Diagrama tornado ordonează parametrii "
               "după influență.")
    sens_arch = st.selectbox("Arhitectura analizată",
                             [a for a in ARCHITECTURES if a != "baseline"],
                             format_func=lambda a: ARCH_LABELS[a], key="sens_arch")
    if st.button("Rulează analiza de sensibilitate", type="primary"):
        prog = st.progress(0.0, "Se rulează variațiile de parametri…")
        sens = sensitivity_analysis(sens_arch, p_used, econ_used,
                                    cycles["WLTC"], "WLTC",
                                    progress_cb=lambda f: prog.progress(f))
        prog.empty()
        st.session_state["sens"] = sens
    if "sens" in st.session_state:
        sens = st.session_state["sens"]
        colL, colR = st.columns(2)
        with colL:
            st.plotly_chart(plot_sensitivity_tornado(
                sens["consumption"], sens["base_consumption"],
                "Consum [L/100km]"), use_container_width=True)
        with colR:
            st.plotly_chart(plot_sensitivity_tornado(
                sens["tco"], sens["base_tco"], "TCO [EUR]"),
                use_container_width=True)

# ----------------------------------------------------------------------
def page_comparatie():
    st.markdown("#### Comparație vehicul A vs vehicul B")
    st.caption("Definiți două seturi de parametri; aplicația le simulează pe aceeași "
               "arhitectură și același ciclu și afișează diferențele.")
    cmp_arch = st.selectbox("Arhitectura", ARCHITECTURES,
                            format_func=lambda a: ARCH_LABELS[a], key="cmp_arch", index=2)
    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Vehicul A**")
        mA = st.number_input("Masă A [kg]", 800.0, 3000.0, 1494.0, 10.0)
        cdA = st.number_input("Cd A", 0.20, 0.50, 0.32, 0.01)
        peA = st.number_input("Putere MCI A [kW]", 40.0, 200.0, 80.0, 1.0)
        batA = st.number_input("Baterie A [kWh]", 0.5, 60.0, 1.4, 0.1)
        prA = st.number_input("Preț A [EUR]", 15000.0, 90000.0, 28590.0, 100.0)
    with colB:
        st.markdown("**Vehicul B**")
        mB = st.number_input("Masă B [kg]", 800.0, 3000.0, 1650.0, 10.0)
        cdB = st.number_input("Cd B", 0.20, 0.50, 0.30, 0.01)
        peB = st.number_input("Putere MCI B [kW]", 40.0, 200.0, 95.0, 1.0)
        batB = st.number_input("Baterie B [kWh]", 0.5, 60.0, 1.8, 0.1)
        prB = st.number_input("Preț B [EUR]", 15000.0, 90000.0, 32000.0, 100.0)
    if st.button("Compară vehiculele", type="primary"):
        pA = VehicleParams(name="Vehicul A", mass_kg=mA, Cd=cdA,
                           P_ICE_max_kW=peA, bat_energy_kWh=batA, price_EUR=prA)
        pB = VehicleParams(name="Vehicul B", mass_kg=mB, Cd=cdB,
                           P_ICE_max_kW=peB, bat_energy_kWh=batB, price_EUR=prB)
        rA = simulate(cmp_arch, pA, cycles["WLTC"], "WLTC", strategy="rule_based")
        rB = simulate(cmp_arch, pB, cycles["WLTC"], "WLTC", strategy="rule_based")
        tA = compute_tco(prA, rA.consumption_L_100km, 0.20, econ_used)["tco_total"]
        tB = compute_tco(prB, rB.consumption_L_100km, 0.20, econ_used)["tco_total"]
        st.plotly_chart(plot_vehicle_comparison(
            dict(cons=rA.consumption_L_100km, co2=rA.co2_g_km, tco=tA, ev=rA.ev_share_pct),
            dict(cons=rB.consumption_L_100km, co2=rB.co2_g_km, tco=tB, ev=rB.ev_share_pct),
            "Vehicul A", "Vehicul B"), use_container_width=True)
        dcons = rB.consumption_L_100km - rA.consumption_L_100km
        st.info(f"**Diferență de consum (B − A):** {dcons:+.3f} L/100 km · "
                f"**Diferență TCO (B − A):** {tB - tA:+,} EUR".replace(",", " "))

# ----------------------------------------------------------------------
def page_validare():
    st.markdown("#### Validarea fizică a simulărilor")
    st.caption("Verifică respectarea limitelor fizice pentru fiecare simulare: "
               "SoC în interval, puteri sub maxime, bilanț energetic, consum plauzibil.")
    val_arch = st.selectbox("Arhitectura", ARCHITECTURES,
                            format_func=lambda a: ARCH_LABELS[a], key="val_arch", index=2)
    val_cyc = st.selectbox("Ciclul", list(cycles.keys()), key="val_cyc")
    checks = physical_validation(results[val_arch][val_cyc], p_used)
    n_pass = sum(1 for c in checks if c["status"] == "PASS")
    st.metric("Verificări trecute", f"{n_pass} / {len(checks)}")
    for c in checks:
        badge = ('<span class="badge-pass">PASS</span>' if c["status"] == "PASS"
                 else '<span class="badge-fail">FAIL</span>')
        st.markdown(f"{badge} &nbsp; **{c['check']}** — {c['detail']}",
                    unsafe_allow_html=True)

# ----------------------------------------------------------------------
def page_export():
    st.markdown("#### Export raport PDF complet")
    st.caption("Generează un raport PDF unic cu parametrii de intrare, tabelele de "
               "rezultate, graficele, validarea fizică, comparația cu sursele WLTP "
               "și interpretări automate.")
    if st.button("Generează raportul PDF", type="primary"):
        with st.spinner("Se generează raportul…"):
            rows_pdf = [{"Arhitectură": ARCH_LABELS[a], "Ciclu": c,
                         "Consum [L/100km]": results[a][c].consumption_L_100km,
                         "CO₂ [g/km]": results[a][c].co2_g_km,
                         "Reducere [%]": round((results["baseline"][c].consumption_L_100km -
                                                results[a][c].consumption_L_100km) /
                                               results["baseline"][c].consumption_L_100km * 100, 1)}
                        for a in ARCHITECTURES for c in cycles]
            tco_pdf = []
            for a in ARCHITECTURES:
                avg = np.mean([results[a][c].consumption_L_100km for c in cycles])
                t = compute_tco(p_used.price_EUR * PRICE_MAP[a], avg,
                                p_used.residual_frac, econ_used, is_hev=(a != "baseline"))
                tco_pdf.append({"Arhitectură": ARCH_LABELS[a], "Achiziție": t["price"],
                                "Energie": t["cost_energy"], "Mentenanță": t["maintenance"],
                                "TCO total": t["tco_total"]})
            checks_pdf = physical_validation(results["paralel"]["WLTC"], p_used)
            sp_avg = np.mean([results["serie_paralel"][c].consumption_L_100km for c in cycles])
            cmp_pdf = compare_with_sources(sp_avg, "serie_paralel", min_sources=3)
            soc_pdf = {a: results[a]["WLTC"].SoC for a in ARCHITECTURES if a != "baseline"}
            out = os.path.join(tempfile.gettempdir(), "raport_simulare_hev.pdf")
            generate_pdf_report(p_used, econ_used, rows_pdf, tco_pdf, checks_pdf,
                                cmp_pdf, soc_pdf, STRATEGY_LABELS[strat_used], out)
        with open(out, "rb") as f:
            st.download_button("⬇️ Descarcă raportul PDF", f,
                               file_name="raport_simulare_hev.pdf",
                               mime="application/pdf", type="primary")
        st.success("Raport generat cu succes.")

# ======================================================================
#  Navigare — meniu lateral dreapta, pliabil (stil sidebar iOS)
# ======================================================================
PAGES = ["Simulare", "Sensibilitate", "Comparație A/B", "Validare", "Export PDF"]
PAGE_FUNCS = {
    "Simulare": page_simulare,
    "Sensibilitate": page_sensibilitate,
    "Comparație A/B": page_comparatie,
    "Validare": page_validare,
    "Export PDF": page_export,
}

if "menu_open" not in st.session_state:
    st.session_state.menu_open = True
if "active_page" not in st.session_state:
    st.session_state.active_page = PAGES[0]

if st.session_state.menu_open:
    main_col, nav_col = st.columns([0.80, 0.20], gap="medium")
    with nav_col:
        with st.container(border=True):
            st.markdown('<p style="font-size:.8rem;color:#8E8E93;font-weight:600;'
                        'text-transform:uppercase;letter-spacing:.04em;margin:0 0 6px;">'
                        'Meniu</p>', unsafe_allow_html=True)
            choice = st.radio("Navigare", PAGES,
                              index=PAGES.index(st.session_state.active_page),
                              label_visibility="collapsed")
            st.session_state.active_page = choice
            if st.button("Ascunde meniul", use_container_width=True):
                st.session_state.menu_open = False
                st.rerun()
else:
    if st.button("☰ Meniu"):
        st.session_state.menu_open = True
        st.rerun()
    main_col = st.container()

with main_col:
    PAGE_FUNCS[st.session_state.active_page]()

st.markdown("---")
st.caption("Model cvasi-static backward-forward · WLTC din biblioteca `wltp` (UNECE GTR15) · "
           "Cod sursă deschis, licență MIT · © 2026 A.M. Beldugan, FIMIM, Univ. Ovidius Constanța")
