"""
app.py — Simulator comparativ de arhitecturi de propulsie hibridă
==================================================================
Interfață web profesională (Streamlit) cu 5 module:
  Simulare · Sensibilitate · Comparație A/B · Validare fizică · Export PDF

Rulare:  streamlit run app.py
A.M. Beldugan, FIMIM, Universitatea Ovidius din Constanța, 2026. Licență MIT.
"""
import io
import json
import os
import sys
import tempfile
from dataclasses import fields as dc_fields

import numpy as np
import pandas as pd
import requests
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from vehicle_model import VehicleParams
from ems_strategies import simulate, ARCHITECTURES, ARCH_LABELS, STRATEGY_LABELS
from tco_model import (EconomicParams, compute_tco, compute_breakeven,
                       compare_with_sources)
from analysis import sensitivity_analysis, physical_validation
from visualizations import (plot_soc_trajectory, plot_power_profile, plot_bsfc_map,
                            plot_consumption_bars, plot_tco_breakdown,
                            plot_sensitivity_tornado, plot_vehicle_comparison,
                            plot_cycle_live, plot_ignition_scatter,
                            cycle_stats, ignition_events, CYCLE_INFO, set_dark)
from pdf_export import generate_pdf_report
from obd_import import parse_torque_log, build_track_map

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

    /* Carduri metrice — celule iOS */
    div[data-testid="stMetric"] {
        background: #FFFFFF; border: 0.5px solid rgba(60,60,67,.12);
        border-radius: 14px; padding: 14px 18px;
        box-shadow: 0 1px 2px rgba(0,0,0,.03);
    }
    div[data-testid="stMetric"] label { color: #8E8E93 !important;
        font-weight: 500; font-size: .82rem; text-transform: none; }
    div[data-testid="stMetric"] label p { white-space: normal; }
    div[data-testid="stMetricValue"] { color: #000; font-weight: 700;
        letter-spacing: -.01em; font-size: 1.5rem; }
    div[data-testid="stMetricValue"] > div { white-space: normal;
        overflow: visible; line-height: 1.25; }
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
    section[data-testid="stSidebar"] h1 {
        font-size: 1.25rem; color: #000; font-weight: 800;
        letter-spacing: -.01em; padding-bottom: 0;
    }
    section[data-testid="stSidebar"] h2 {
        font-size: 1.0rem; color: #000; font-weight: 700;
        text-transform: none; letter-spacing: 0;
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
    div[data-testid="stRadio"] label p { white-space: nowrap; font-size: .9rem; }

    /* Expander — antet uniform pentru toate submeniurile (drop-down) */
    div[data-testid="stExpander"] {
        background: #FFFFFF; border: 0.5px solid rgba(60,60,67,.12);
        border-radius: 14px;
    }
    div[data-testid="stExpander"] summary p,
    div[data-testid="stExpander"] summary span {
        font-size: .95rem; font-weight: 600; color: #000;
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

# ======================================================================
#  Tema grafică: light (implicit) / dark (stil iOS)
# ======================================================================
_DARK_CSS = """
<style>
    .stApp, [data-testid="stAppViewContainer"] { background: #000000; }
    .stApp p, .stApp label, .stApp li, .stApp span { color: #F2F2F7; }
    h1, h2, h3, h4, h5 { color: #FFFFFF !important; }

    section[data-testid="stSidebar"] {
        background: #000000; border-right: 0.5px solid rgba(84,84,88,.65);
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2 { color: #FFFFFF; }

    div[data-testid="stMetric"] {
        background: #1C1C1E; border-color: rgba(84,84,88,.65);
        box-shadow: none;
    }
    div[data-testid="stMetricValue"] { color: #FFFFFF; }

    div[data-testid="stRadio"] > div {
        background: #1C1C1E; border-color: rgba(84,84,88,.65);
    }
    div[data-testid="stExpander"] {
        background: #1C1C1E; border-color: rgba(84,84,88,.65);
    }
    div[data-testid="stExpander"] details,
    div[data-testid="stExpander"] summary {
        background: #1C1C1E !important;
    }
    div[data-testid="stExpander"] summary:hover { background: #2C2C2E !important; }
    div[data-testid="stExpander"] summary p,
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary svg { color: #FFFFFF; fill: #FFFFFF; }

    [data-baseweb="select"] > div {
        background: #1C1C1E !important; color: #F2F2F7 !important;
        border-color: rgba(84,84,88,.65) !important;
    }
    [data-baseweb="select"] svg { fill: #8E8E93; }
    [data-baseweb="menu"], [data-baseweb="popover"] div[role="listbox"] {
        background: #2C2C2E !important;
    }
    [data-baseweb="menu"] li { color: #F2F2F7 !important; }

    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextInput"] input {
        background: #1C1C1E !important; color: #F2F2F7 !important;
        border-color: rgba(84,84,88,.65) !important;
    }
    div[data-testid="stNumberInput"] button {
        background: #2C2C2E; color: #F2F2F7;
        border-color: rgba(84,84,88,.65);
    }
    [data-testid="stFileUploaderDropzone"] {
        background: #1C1C1E; border-color: rgba(84,84,88,.65);
        color: #F2F2F7;
    }

    .stButton > button, .stDownloadButton > button,
    [data-testid^="stBaseButton"] {
        background: #1C1C1E !important; color: #0A84FF !important;
        border: 0.5px solid rgba(84,84,88,.65) !important;
    }
    .stButton > button p, .stButton > button span,
    .stDownloadButton > button p { color: inherit !important; }
    .stButton > button[kind="primary"],
    [data-testid="stBaseButton-primary"] {
        background: #0A84FF !important; color: #FFFFFF !important;
        border: none !important;
    }
    .stButton > button[kind="primary"] p,
    [data-testid="stBaseButton-primary"] p { color: #FFFFFF !important; }
    .stButton > button[kind="tertiary"],
    [data-testid="stBaseButton-tertiary"] {
        background: transparent !important; border: none !important;
        color: #8E8E93 !important;
    }

    div[data-testid="stDataFrame"] {
        background: #1C1C1E; border-color: rgba(84,84,88,.65);
    }
    div[data-testid="stCaptionContainer"], .stCaption,
    small, [data-testid="stWidgetLabel"] p { color: #8E8E93 !important; }
    hr { border-top: 0.5px solid rgba(84,84,88,.65); }
</style>
"""

if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = "light"
if st.session_state.ui_theme == "dark":
    st.markdown(_DARK_CSS, unsafe_allow_html=True)
set_dark(st.session_state.ui_theme == "dark")

_sp_theme, _btn_theme = st.columns([0.94, 0.06])
with _btn_theme:
    _ic = (":material/dark_mode:" if st.session_state.ui_theme == "light"
           else ":material/light_mode:")
    if st.button(_ic, type="tertiary",
                 help="Comută tema luminoasă / întunecată"):
        st.session_state.ui_theme = ("dark" if st.session_state.ui_theme == "light"
                                     else "light")
        st.rerun()


# ======================================================================
#  Încărcarea ciclurilor (cache)
# ======================================================================
@st.cache_data
def load_vehicle_db() -> pd.DataFrame:
    here = os.path.dirname(os.path.abspath(__file__))
    return pd.read_csv(os.path.join(here, "data", "vehicles_db.csv"))


@st.cache_data
def load_eea_report() -> pd.DataFrame | None:
    """Raportul de audit EEA (produs de tools/verify_eea.py), dacă există."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "data", "eea_verification_report.csv")
    if os.path.exists(path):
        try:
            return pd.read_csv(path)
        except Exception:
            return None
    return None


@st.cache_data
def load_cycles() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    dd = os.path.join(here, "data")
    cycles = {}
    for label, fname in [("WLTC", "wltc_class3b_reference.csv"),
                         ("UDDS", "udds.csv"), ("HWFET", "hwfet.csv"),
                         ("Real urban (Constanța)", "real_urban_constanta.csv"),
                         ("Real mixt (Constanța)", "real_mixt_constanta.csv")]:
        path = os.path.join(dd, fname)
        if os.path.exists(path):
            cycles[label] = pd.read_csv(path)["speed_kmh"].values
    return cycles


@st.cache_data
def load_bundled_tracks() -> dict:
    """Traseele GPS pre-salvate pentru ciclurile reale incluse în aplicație."""
    import json
    here = os.path.dirname(os.path.abspath(__file__))
    dd = os.path.join(here, "data")
    tracks = {}
    for label, fn in [("Real urban (Constanța)", "real_urban_constanta_track.json"),
                      ("Real mixt (Constanța)", "real_mixt_constanta_track.json")]:
        p = os.path.join(dd, fn)
        if os.path.exists(p):
            try:
                tracks[label] = json.load(open(p, encoding="utf-8"))
            except Exception:
                pass
    return tracks


def params_from_widgets(defaults: VehicleParams | None = None) -> VehicleParams:
    """Widget-uri de parametri; funcționează în orice container (ex. expander)."""
    d = defaults or VehicleParams()
    return VehicleParams(
        name=st.text_input("Denumire", d.name, key="w_name"),
        mass_kg=st.number_input("Masă [kg]", 800.0, 3000.0, d.mass_kg, 10.0, key="w_m"),
        Cd=st.number_input("Cd", 0.20, 0.50, d.Cd, 0.01, key="w_cd"),
        Af=st.number_input("Arie frontală [m²]", 1.5, 3.5, d.Af, 0.05, key="w_af"),
        f_rr=st.number_input("Rezist. rulare", 0.006, 0.020, d.f_rr, 0.001,
                             format="%.3f", key="w_frr"),
        P_ICE_max_kW=st.number_input("Putere MCI [kW]", 40.0, 200.0, d.P_ICE_max_kW, 1.0, key="w_pice"),
        eta_th_peak=st.number_input("Randament termic", 0.30, 0.45, d.eta_th_peak, 0.01, key="w_eta"),
        P_EM_max_kW=st.number_input("Putere EM [kW]", 10.0, 150.0, d.P_EM_max_kW, 1.0, key="w_pem"),
        bat_energy_kWh=st.number_input("Baterie [kWh]", 0.5, 60.0, d.bat_energy_kWh, 0.1, key="w_bat"),
        price_EUR=st.number_input("Preț [EUR]", 15000.0, 90000.0, d.price_EUR, 100.0, key="w_pr"),
    )


# --- Încărcarea parametrilor din fișier (JSON/CSV) sau URL -----------------
_NUMERIC_FIELDS = {f.name for f in dc_fields(VehicleParams)
                   if f.type in ("float", "bool")} | {"name"}

_TEMPLATE_JSON = json.dumps({
    "name": "Vehiculul meu", "mass_kg": 1494, "Cd": 0.32, "Af": 2.65,
    "f_rr": 0.009, "P_ICE_max_kW": 80, "eta_th_peak": 0.41,
    "P_EM_max_kW": 37, "bat_energy_kWh": 1.4, "price_EUR": 28590,
}, indent=2, ensure_ascii=False)


def _params_from_mapping(d: dict) -> tuple[VehicleParams, list[str]]:
    """Construiește VehicleParams dintr-un dicționar; ignoră cheile necunoscute."""
    applied, ignored, kwargs = [], [], {}
    for k, v in d.items():
        if k in _NUMERIC_FIELDS:
            try:
                kwargs[k] = str(v) if k == "name" else float(v)
                applied.append(k)
            except (TypeError, ValueError):
                ignored.append(k)
        else:
            ignored.append(k)
    msgs = []
    if applied:
        msgs.append("Parametri preluați: " + ", ".join(applied) + ".")
    if ignored:
        msgs.append("Chei ignorate (necunoscute/nevalide): " + ", ".join(ignored) + ".")
    return VehicleParams(**kwargs), msgs


def _parse_csv_params(text: str) -> dict:
    """CSV cu două coloane: parametru, valoare (cu sau fără antet)."""
    df = pd.read_csv(io.StringIO(text), header=None, comment="#",
                     skip_blank_lines=True, dtype=str)
    if df.shape[1] < 2:
        raise ValueError("CSV-ul trebuie să aibă două coloane: parametru, valoare.")
    d = {}
    for _, row in df.iterrows():
        key = str(row[0]).strip()
        if key.lower() in ("parametru", "parameter", "key", "camp"):
            continue                              # rând de antet
        d[key] = str(row[1]).strip()
    return d


def load_external_params(uploaded, url: str) -> tuple[VehicleParams, list[str]]:
    """Parametri din fișier încărcat (JSON/CSV) sau dintr-un URL direct."""
    raw, kind, msgs = None, None, []
    if uploaded is not None:
        raw = uploaded.getvalue().decode("utf-8", errors="replace")
        kind = "json" if uploaded.name.lower().endswith(".json") else "csv"
    elif url.strip():
        try:
            resp = requests.get(url.strip(), timeout=10)
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "")
            u = url.strip().lower()
            if u.endswith(".json") or "json" in ctype:
                raw, kind = resp.text, "json"
            elif u.endswith(".csv") or "csv" in ctype or "text/plain" in ctype:
                raw, kind = resp.text, "csv"
            else:
                return VehicleParams(), [
                    "URL-ul indică o pagină HTML — paginile producătorilor nu pot fi "
                    "interpretate automat. Folosiți un link DIRECT către un fișier "
                    "JSON sau CSV (ex. raw GitHub, fișier găzduit)."]
        except requests.RequestException as e:
            return VehicleParams(), [f"URL inaccesibil: {e}"]
    if raw is None:
        return VehicleParams(), ["Niciun fișier/URL — se folosesc valorile din lucrare."]
    try:
        data = json.loads(raw) if kind == "json" else _parse_csv_params(raw)
        if not isinstance(data, dict):
            raise ValueError("JSON-ul trebuie să fie un obiect {cheie: valoare}.")
        p, m = _params_from_mapping(data)
        return p, msgs + m
    except Exception as e:
        return VehicleParams(), [f"Fișier neinterpretabil: {e}"]


# ======================================================================
#  Sidebar stânga: titlu, Configurare date de intrare, Meniu
# ======================================================================
PAGES = ["Simulare", "Sensibilitate", "Comparație A/B", "Validare", "Export PDF"]

with st.sidebar:
    st.markdown("# Simulator arhitecturi HEV")
    st.markdown("## Configurare date de intrare")
    mode = st.selectbox("Sursa datelor",
                        ["Preset: Bigster (lucrare)",
                         "Bază de date (marcă → model)",
                         "Introducere manuală",
                         "Fișier încărcat / URL"])
    strategy = st.selectbox("Strategie EMS",
                            options=["rule_based", "ecms", "dp"],
                            format_func=lambda s: STRATEGY_LABELS[s])
    if strategy == "dp":
        st.info("Benchmark PMP-shooting: ~10-20 s per rulare completă.")

    with st.expander("Parametrii vehiculului",
                     expanded=(mode != "Preset: Bigster (lucrare)")):
        if mode == "Introducere manuală":
            p_active = params_from_widgets()
        elif mode == "Bază de date (marcă → model)":
            vdb = load_vehicle_db()
            sel_marca = st.selectbox("Marcă", sorted(vdb["marca"].unique()))
            sub = vdb[vdb["marca"] == sel_marca]
            sel_model = st.selectbox("Model", sorted(sub["model"].unique()))
            sub2 = sub[sub["model"] == sel_model]
            sel_var = st.selectbox("Variantă", list(sub2["varianta"]))
            vrow = sub2[sub2["varianta"] == sel_var].iloc[0]
            p_active = VehicleParams(
                name=f'{vrow["marca"]} {vrow["model"]} {vrow["varianta"]}',
                mass_kg=float(vrow["mass_kg"]), Cd=float(vrow["Cd"]),
                Af=float(vrow["Af"]),
                P_ICE_max_kW=float(vrow["P_ICE_max_kW"]),
                eta_th_peak=float(vrow["eta_th_peak"]),
                P_EM_max_kW=float(vrow["P_EM_max_kW"]),
                bat_energy_kWh=float(vrow["bat_energy_kWh"]),
                price_EUR=float(vrow["price_EUR"]),
            )
            st.caption(
                f'**{vrow["tip"]}** · arhitectura reală: '
                f'**{ARCH_LABELS.get(vrow["arhitectura"], vrow["arhitectura"])}** · '
                f'CO₂ WLTP oficial: **{vrow["co2_wltp_g_km"]} g/km** '
                f'({vrow["consum_wltp_L_100km"]} L/100 km'
                + (", ponderat" if vrow["tip"] == "PHEV" else "") + ")")
            st.caption(f'Sursă: {vrow["sursa"]} · câmpuri estimate: '
                       f'{str(vrow["estimari"]).replace(";", ", ")}')
            eea_rep = load_eea_report()
            if eea_rep is not None:
                hit = eea_rep[(eea_rep["marca"] == vrow["marca"]) &
                              (eea_rep["model"] == vrow["model"]) &
                              (eea_rep["varianta"] == vrow["varianta"])]
                if len(hit):
                    h = hit.iloc[0]
                    if str(h["status"]).startswith("OK"):
                        st.success(f'Audit EEA: **OK** · abateri față de mediana '
                                   f'EEA — masă {h.get("abatere_masa_pct", "–")}%, '
                                   f'CO₂ {h.get("abatere_co2_pct", "–")}% '
                                   f'({int(h["eea_inregistrari"])} înregistrări)')
                    elif str(h["status"]).startswith("NEGĂSIT"):
                        st.warning("Audit EEA: **negăsit** în setul EEA "
                                   "(denumire comercială diferită sau model non-UE).")
                    else:
                        st.warning(f'Audit EEA: **de verificat** · masă '
                                   f'{h.get("abatere_masa_pct", "–")}%, CO₂ '
                                   f'{h.get("abatere_co2_pct", "–")}% față de '
                                   f'mediana EEA.')
            if vrow["tip"] == "PHEV":
                st.caption("PHEV: simularea rulează în regim charge-sustaining "
                           "(baterie descărcată la nivelul țintă), nu în modul "
                           "electric din priză.")
            elif vrow["tip"] == "MHEV":
                st.caption("MHEV: electrificare ușoară — mașina electrică mică "
                           "limitează rularea pur electrică; util ca referință "
                           "de tip baseline.")
        elif mode == "Fișier încărcat / URL":
            up = st.file_uploader("Fișier parametri (JSON sau CSV)",
                                  type=["json", "csv"])
            url_in = st.text_input("sau URL direct către un fișier JSON/CSV",
                                   placeholder="https://…/parametri.json")
            p_active, load_msgs = load_external_params(up, url_in)
            for m in load_msgs:
                st.caption(m)
            st.download_button("Descarcă model JSON", data=_TEMPLATE_JSON,
                               file_name="parametri_vehicul.json",
                               mime="application/json",
                               use_container_width=True)
        else:
            st.caption("Se folosesc valorile din lucrare — Dacia Bigster Hybrid 155.")
            p_active = VehicleParams()

    with st.expander("Parametrii economici", expanded=False):
        econ = EconomicParams(
            km_per_year=st.number_input("Kilometraj anual [km]", 5000.0, 40000.0, 15000.0, 1000.0),
            fuel_price_EUR_L=st.number_input("Preț benzină [EUR/L]", 1.0, 3.0, 1.83, 0.01),
            elec_price_EUR_kWh=st.number_input("Preț electricitate [EUR/kWh]", 0.10, 0.60, 0.28, 0.01),
            rabla_plus_EUR=st.number_input("Subvenție Rabla Plus [EUR]", 0.0, 10000.0, 0.0, 500.0),
        )

    run_btn = st.button("Rulează simularea", type="primary", use_container_width=True)

    st.markdown("## Meniu")
    st.session_state.active_page = st.selectbox(
        "Meniu", PAGES,
        index=PAGES.index(st.session_state.get("active_page", PAGES[0])),
        label_visibility="collapsed")

cycles = load_cycles()
PRICE_MAP = {"baseline": 0.84, "serie": 0.98, "paralel": 1.00, "serie_paralel": 1.04}

# --- Import de trasee reale OBD-II (Torque) ca ciclu propriu ---------------
with st.sidebar:
    with st.expander("Traseu real (OBD-II / Torque)", expanded=False):
        st.caption("Încarcă un log CSV exportat din aplicația Torque (înregistrat "
                   "prin adaptor OBD-II). Traseul devine ciclu selectabil, "
                   "reeșantionat la 1 Hz, cu staționările decupate.")
        obd_file = st.file_uploader("Log Torque (CSV)", type=["csv"], key="obd_up")
        obd_name = st.text_input("Nume traseu", "Traseul meu", key="obd_name")
        if obd_file is not None:
            try:
                res = parse_torque_log(obd_file)
                label = f"Real: {obd_name}"
                cycles[label] = res["speed_kmh"]
                st.session_state["obd_real_consum"] = res["consumption_L_100km"]
                if res.get("gps_track"):
                    st.session_state["gps_tracks"] = st.session_state.get("gps_tracks", {})
                    st.session_state["gps_tracks"][label] = res["gps_track"]
                st.success(f"Traseu adăugat: {res['distance_km']:.1f} km · "
                           f"{res['duration_s']//60} min · v_max "
                           f"{res['v_max']:.0f} km/h · {res['n_stops']} opriri")
                if res["consumption_L_100km"]:
                    st.caption(f"Consum real măsurat (din MAF): "
                               f"**{res['consumption_L_100km']:.2f} L/100 km** — "
                               f"util pentru validarea configurației baseline.")
                for w in res["warnings"]:
                    st.caption(f"• {w}")
            except Exception as e:
                st.warning(f"Log neinterpretabil: {e}")


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
        st.session_state["db_row_used"] = (
            vrow.to_dict() if mode == "Bază de date (marcă → model)" else None)

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
    c1.metric("Baseline · WLTC [L/100km]", f"{base_wltc:.2f}")
    c2.metric("Paralel · WLTC [L/100km]", f"{par_wltc:.2f}",
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

    with st.expander("Analiză detaliată pe arhitectură", expanded=False):
        sel_arch = st.selectbox("Arhitectura", [a for a in ARCHITECTURES],
                                format_func=lambda a: ARCH_LABELS[a])
        sel_cyc = st.selectbox("Ciclul", list(cycles.keys()))
        r_sel = results[sel_arch][sel_cyc]

        # --- Ce înseamnă ciclul selectat ---
        st.markdown("##### Despre ciclul selectat")
        st.markdown(CYCLE_INFO.get(sel_cyc, ""))

        # Harta traseului real, dacă ciclul selectat are traseu GPS
        _tracks = {**load_bundled_tracks(),
                   **st.session_state.get("gps_tracks", {})}
        if sel_cyc in _tracks:
            deck = build_track_map(_tracks[sel_cyc])
            if deck is not None:
                st.markdown("##### Traseul parcurs")
                st.pydeck_chart(deck, use_container_width=True)
                st.caption("Traseu real înregistrat prin OBD-II. Culoarea liniei "
                           "reflectă viteza: albastru = oprit/lent, verde-galben = "
                           "mediu, roșu = viteză mare. Marcaje: verde = start, "
                           "roșu = sfârșit.")
        st.caption("Valorile de mai jos sunt calculate din profilul de viteză "
                   "efectiv încărcat în aplicație:")
        cs = cycle_stats(cycles[sel_cyc])
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Durată [s]", f"{cs['duration_s']}")
        k2.metric("Distanță [km]", f"{cs['distance_km']:.2f}")
        k3.metric("Viteză medie / în mers [km/h]",
                  f"{cs['v_avg']:.1f} / {cs['v_avg_moving']:.1f}")
        k4.metric("Viteză maximă [km/h]", f"{cs['v_max']:.1f}")
        st.caption(f"Staționare: {cs['idle_pct']:.0f}% din durată · "
                   f"{cs['n_stops']} opriri complete.")

        # --- Derularea LIVE ---
        st.markdown("##### Derularea LIVE a ciclului")
        _SPEEDS = [1, 5, 10, 15, 20, 25, 30]
        spd_cur = st.session_state.get("live_speed", 1)
        b_l, b_r = st.columns([0.32, 0.68])
        lbl = "Redare: timp real (1×)" if spd_cur == 1 else f"Redare: {spd_cur}×"
        if b_l.button(lbl, help="Fiecare apăsare crește viteza de derulare cu 5×, "
                                "până la maximum 30×; apoi revine la timp real."):
            st.session_state["live_speed"] = _SPEEDS[
                (_SPEEDS.index(spd_cur) + 1) % len(_SPEEDS)]
            st.rerun()
        b_r.caption(f"La viteza curentă, redarea completă durează "
                    f"~{cs['duration_s'] // max(1, spd_cur)} s "
                    f"(ciclul real: {cs['duration_s']} s).")
        st.plotly_chart(
            plot_cycle_live(r_sel, cycles[sel_cyc], p_used,
                            f"{ARCH_LABELS[sel_arch]} · {sel_cyc}",
                            speed=spd_cur),
            use_container_width=True)
        st.caption("Apăsați **▶ Redă** pentru derularea în timp: banda roșie = "
                   "motorul termic pornit, banda verde = rulare electrică; "
                   "triunghiurile marchează pornirile MCI. Rândul 2: consumul de "
                   "combustibil și CO₂ cumulate; rândul 3: starea de încărcare a "
                   "bateriei. Cursorul de sus permite saltul la orice moment.")

        # --- Pornirile motorului termic ---
        if sel_arch != "baseline":
            st.markdown("##### Pornirile motorului termic")
            ign = ignition_events(r_sel, cycles[sel_cyc])
            if ign["n"] > 0:
                i1, i2, i3, i4 = st.columns(4)
                i1.metric("Număr porniri", f"{ign['n']}")
                i2.metric("Prima pornire",
                          f"t = {ign['t'][0]} s · {ign['speed'][0]:.0f} km/h")
                i3.metric("Viteză mediană la pornire [km/h]",
                          f"{np.median(ign['speed']):.1f}")
                i4.metric("SoC la porniri [%]",
                          f"{ign['soc'].min():.0f}–{ign['soc'].max():.0f}")
                st.plotly_chart(plot_ignition_scatter(r_sel, cycles[sel_cyc]),
                                use_container_width=True)
                low_soc = ign["soc"] <= p_used.SoC_target * 100
                st.caption(
                    f"Motorul termic pornește din două cauze, vizibile în grafic: "
                    f"**cerere de tracțiune** (puterea cerută depășește capabilitatea "
                    f"mașinii electrice — porniri la viteze mari, indiferent de SoC) "
                    f"și **reîncărcarea bateriei** (SoC sub ținta de "
                    f"{p_used.SoC_target*100:.0f}% — porniri și la viteze mici). "
                    f"Pe acest ciclu, {int(low_soc.sum())} din {ign['n']} porniri au "
                    f"avut loc cu SoC sub țintă; motorul a funcționat "
                    f"{ign['on_share_pct']:.0f}% din durata ciclului.")
            else:
                st.info("Motorul termic nu a pornit pe acest ciclu.")

        st.markdown("##### Profilul de putere și harta BSFC")
        st.plotly_chart(plot_power_profile(r_sel, cycles[sel_cyc]), use_container_width=True)
        st.plotly_chart(plot_bsfc_map(p_used, r_sel), use_container_width=True)

    with st.expander("Costul total de proprietate", expanded=False):
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

    with st.expander("Comparația cu valorile WLTP oficiale", expanded=False):
        # Metodologic: valorile WLTP de omologare se obțin EXCLUSIV pe ciclul
        # WLTC — comparația folosește deci doar simularea WLTC, nu media pe
        # cele trei cicluri (UDDS/HWFET sunt proceduri EPA, necomparabile).
        db_used = st.session_state.get("db_row_used")
        if db_used:
            arch_r = db_used["arhitectura"]
            sim_w = results[arch_r]["WLTC"].consumption_L_100km
            off = float(db_used["consum_wltp_L_100km"])
            st.caption(f"Vehicul din baza de date: **{db_used['marca']} "
                       f"{db_used['model']} {db_used['varianta']}** — comparația "
                       f"se face cu **propria valoare WLTP oficială**, pe "
                       f"arhitectura reală ({ARCH_LABELS.get(arch_r, arch_r)}).")
            if db_used["tip"] == "PHEV":
                st.dataframe(pd.DataFrame([{
                    "Mărime": "Consum WLTP oficial (ponderat, baterie plină)",
                    "Valoare": f"{off:.1f} L/100 km"}, {
                    "Mărime": "Consum simulat charge-sustaining · WLTC",
                    "Valoare": f"{sim_w:.3f} L/100 km"}]),
                    use_container_width=True, hide_index=True)
                st.caption("**PHEV:** valoarea de omologare este ponderată cu "
                           "factorul de utilitate (pornire cu bateria plină) și "
                           "NU este comparabilă direct cu simularea "
                           "charge-sustaining; consumul simulat corespunde "
                           "rulării cu bateria descărcată la nivelul țintă "
                           "(coloana „consum susținut” din fișele WLTP, acolo "
                           "unde constructorul o publică).")
            else:
                dev = (sim_w - off) / off * 100
                st.dataframe(pd.DataFrame([{
                    "Sursă (vehicul)": f"{db_used['marca']} {db_used['model']} "
                                       f"{db_used['varianta']}",
                    "WLTP oficial [L/100km]": off,
                    "Simulat · WLTC [L/100km]": round(sim_w, 3),
                    "Abatere [%]": round(dev, 1),
                    "Referință": db_used["sursa"]}]),
                    use_container_width=True, hide_index=True)
                st.caption(f"Abaterea de **{dev:+.1f}%** măsoară acuratețea "
                           f"modelului pe vehiculul selectat, cu parametrii din "
                           f"baza de date (câmpuri estimate: "
                           f"{str(db_used['estimari']).replace(';', ', ')}).")
        else:
            sp_wltc = results["serie_paralel"]["WLTC"].consumption_L_100km
            cmpv = compare_with_sources(sp_wltc, "serie_paralel", min_sources=3)
            st.caption(f"Consum simulat serie-paralel pe WLTC: **{sp_wltc:.3f} L/100 km** — "
                       "comparat exclusiv cu ciclul de omologare WLTP (WLTC), "
                       "nu cu media pe cele trei cicluri.")
            st.dataframe(pd.DataFrame([{
            "Sursă (vehicul)": c["name"], "WLTP [L/100km]": c["official_L_100km"],
            "Abatere [%]": c["deviation_pct"], "Referință": c["source"]}
            for c in cmpv["comparisons"]]), use_container_width=True, hide_index=True)
            st.caption("**Doar Dacia Bigster** este vehiculul modelat — abaterea față "
                       "de el măsoară acuratețea modelului. Symbioz și Corolla sunt "
                       "vehicule diferite (masă, motor, sistem hibrid diferite) și "
                       "servesc exclusiv la plasarea rezultatului într-un interval de "
                       "plauzibilitate al clasei de full-hybrid-uri, nu la validare.")

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

    # --- Auditul EEA al bazei de date de vehicule (dacă raportul există) ---
    eea_rep = load_eea_report()
    with st.expander("Audit EEA al bazei de date de vehicule", expanded=False):
        if eea_rep is None:
            st.info(
                "Raportul de audit nu a fost încă generat. Descărcați setul EEA "
                "de monitorizare CO₂ (Reg. UE 2019/631) de la "
                "co2cars.apps.eea.europa.eu — filtrat pe Ft = petrol/electric și "
                "diesel/electric — apoi rulați local:\n\n"
                "`python tools/verify_eea.py --eea <fișierul_EEA.csv>`\n\n"
                "Raportul se scrie în `data/eea_verification_report.csv`; după "
                "comitere în repo, această secțiune afișează automat abaterile "
                "de masă/putere/CO₂ față de mediana EEA și statusul per vehicul.")
        else:
            n_ok = int((eea_rep["status"].astype(str).str.startswith("OK")).sum())
            n_miss = int(eea_rep["status"].astype(str)
                         .str.startswith("NEGĂSIT").sum())
            n_chk = len(eea_rep) - n_ok - n_miss
            a1, a2, a3 = st.columns(3)
            a1.metric("OK (±6% masă, ±8% CO₂)", f"{n_ok}")
            a2.metric("De verificat", f"{n_chk}")
            a3.metric("Negăsite în EEA", f"{n_miss}")
            st.dataframe(eea_rep, use_container_width=True, hide_index=True,
                         height=380)
            st.caption("Comparație cu MEDIANA înregistrărilor EEA per model "
                       "(variantele de echipare nu există în EEA). Puterea EEA "
                       "(ep) este raportată neuniform de constructori — tratați "
                       "abaterile de putere orientativ. Câmpurile Cd/Af/η/baterie/"
                       "preț nu există în EEA și nu pot fi auditate aici.")

    st.markdown("##### Verificările fizice")
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
    all_cyc = list(cycles.keys())
    sel_cycles = st.multiselect(
        "Cicluri incluse în secțiunile detaliate (SoC, profiluri de putere, "
        "BSFC, validare, comparație WLTP)", all_cyc,
        default=[c for c in ["WLTC"] if c in all_cyc] or all_cyc[:1])
    if not sel_cycles:
        st.info("Selectează cel puțin un ciclu pentru secțiunile detaliate.")
    st.caption("Tabelele de sinteză (consum, CO₂, cotă EV, TCO) includ oricum "
               "toate ciclurile simulate; selecția de mai sus controlează doar "
               "capitolele cu grafice per ciclu.")
    if st.button("Generează raportul PDF", type="primary", disabled=not sel_cycles):
        with st.spinner("Se generează raportul…"):
            rows_pdf = [{"Arhitectură": ARCH_LABELS[a], "Ciclu": c,
                         "Consum [L/100km]": results[a][c].consumption_L_100km,
                         "CO₂ [g/km]": results[a][c].co2_g_km,
                         "Cotă EV [%]": results[a][c].ev_share_pct,
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
                                "Asigurare": t["insurance"], "Rezidual": t["residual"],
                                "TCO total": t["tco_total"]})
            be_pdf = compute_breakeven(p_used.price_EUR * PRICE_MAP["baseline"],
                                       p_used.price_EUR,
                                       np.mean([results["baseline"][c].consumption_L_100km for c in cycles]),
                                       np.mean([results["paralel"][c].consumption_L_100km for c in cycles]),
                                       econ_used)
            # Ciclul principal pentru secțiunile care rămân pe un singur ciclu
            # (comparația WLTP, sensibilitatea): WLTC dacă e selectat, altfel primul.
            main_cyc = "WLTC" if "WLTC" in sel_cycles else sel_cycles[0]
            checks_pdf = physical_validation(results["paralel"][main_cyc], p_used)
            # Comparația WLTP se face exclusiv pe ciclul de omologare WLTC.
            # Pentru un vehicul din baza de date: cu propria valoare oficială
            # (pe arhitectura lui reală); PHEV se omite (WLTP ponderat nu e
            # comparabil cu simularea charge-sustaining). Altfel: sursele
            # de referință ale lucrării (Bigster + context).
            db_u = st.session_state.get("db_row_used")
            wltp_cyc = "WLTC" if "WLTC" in cycles else main_cyc
            if db_u and db_u["tip"] != "PHEV":
                arch_r = db_u["arhitectura"]
                sim_w = results[arch_r][wltp_cyc].consumption_L_100km
                off = float(db_u["consum_wltp_L_100km"])
                cmp_pdf = {"n_sources": 1,
                           "avg_deviation_pct": round((sim_w - off) / off * 100, 1),
                           "comparisons": [{
                               "name": f'{db_u["marca"]} {db_u["model"]} '
                                       f'{db_u["varianta"]}',
                               "official_L_100km": off,
                               "deviation_pct": round((sim_w - off) / off * 100, 1),
                               "source": db_u["sursa"]}]}
            elif db_u:
                cmp_pdf = None
            else:
                sp_wltc = results["serie_paralel"][wltp_cyc].consumption_L_100km
                cmp_pdf = compare_with_sources(sp_wltc, "serie_paralel",
                                               min_sources=3)
            # SoC pentru fiecare ciclu selectat (arhitecturile hibride)
            soc_pdf = {c: {a: results[a][c].SoC for a in ARCHITECTURES if a != "baseline"}
                       for c in sel_cycles}
            sens_pdf = sensitivity_analysis("serie_paralel", p_used, econ_used,
                                            cycles[main_cyc], main_cyc)
            eea_rep = load_eea_report()
            eea_audit = None
            if eea_rep is not None:
                st_col = eea_rep["status"].astype(str)
                eea_audit = {
                    "n_ok": int(st_col.str.startswith("OK").sum()),
                    "n_missing": int(st_col.str.startswith("NEGĂSIT").sum()),
                    "total": len(eea_rep)}
                eea_audit["n_check"] = (eea_audit["total"] - eea_audit["n_ok"]
                                        - eea_audit["n_missing"])
                if db_u:
                    hit = eea_rep[(eea_rep["marca"] == db_u["marca"]) &
                                  (eea_rep["model"] == db_u["model"]) &
                                  (eea_rep["varianta"] == db_u["varianta"])]
                    if len(hit):
                        eea_audit["vehicle"] = hit.iloc[0].to_dict()
            out = os.path.join(tempfile.gettempdir(), "raport_simulare_hev.pdf")
            generate_pdf_report(p_used, econ_used, rows_pdf, tco_pdf, checks_pdf,
                                cmp_pdf, soc_pdf, STRATEGY_LABELS[strat_used], out,
                                results=results, cycles=cycles, breakeven=be_pdf,
                                sensitivity=sens_pdf,
                                sens_arch_label=ARCH_LABELS["serie_paralel"],
                                eea_audit=eea_audit,
                                report_cycles=sel_cycles, main_cycle=main_cyc)
        with open(out, "rb") as f:
            st.download_button("Descarcă raportul PDF", f,
                               file_name="raport_simulare_hev.pdf",
                               mime="application/pdf", type="primary")
        st.success("Raport generat cu succes.")

# ======================================================================
#  Dispatch — pagina aleasă din meniul din sidebar
# ======================================================================
PAGE_FUNCS = {
    "Simulare": page_simulare,
    "Sensibilitate": page_sensibilitate,
    "Comparație A/B": page_comparatie,
    "Validare": page_validare,
    "Export PDF": page_export,
}

PAGE_FUNCS[st.session_state.active_page]()

st.markdown("---")
st.caption("Model cvasi-static backward-forward · WLTC din biblioteca `wltp` (UNECE GTR15) · "
           "Cod sursă deschis, licență MIT · © 2026 A.M. Beldugan, FIMIM, Univ. Ovidius Constanța")
