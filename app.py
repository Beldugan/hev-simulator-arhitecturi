"""
app.py — Simulator comparativ de arhitecturi de propulsie hibridă
==================================================================
Interfață web profesională (Streamlit) cu 5 module:
  Simulare · Sensibilitate · Comparație A/B · Validare fizică · Export PDF

Rulare:  streamlit run app.py
A.M. Beldugan, FIMIM, Universitatea Ovidius din Constanța, 2026. Licență MIT.
"""
import io
import ipaddress
import json
import os
import re
import socket
import sys
import tempfile
from datetime import datetime
from dataclasses import fields as dc_fields
from urllib.parse import urlparse

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

    /* Selectbox principale (inclusiv cele din conținutul principal, nu
       doar din bara laterală — fără acest fundal alb explicit, casetele se
       confundă vizual cu fundalul gri-deschis al paginii). */
    div[data-baseweb="select"] > div {
        background: #FFFFFF; border-radius: 10px;
        border: 0.5px solid rgba(60,60,67,.15);
    }

    /* Alerte info/succes — stil iOS banner */
    div[data-testid="stAlert"] { border-radius: 12px; border: none; }

    /* Badge-uri status — pill iOS */
    .badge-pass { background: #E8F9EE; color: #34C759; padding: 3px 12px;
                  border-radius: 999px; font-weight: 700; font-size: .8rem; }
    .badge-fail { background: #FFEBEA; color: #FF3B30; padding: 3px 12px;
                  border-radius: 999px; font-weight: 700; font-size: .8rem; }

    /* Separatoare fine */
    hr { border: none; border-top: 0.5px solid rgba(60,60,67,.18); }

    /* Strategie/vehicul/meniu/OBD apar DOAR la interacțiune (hover), fără
       niciun buton „?" — poziționate FIX pe ecran (position:fixed), pentru
       că trăiesc într-o bară laterală scurtă, unde riscul de suprapunere
       cu alt conținut aflat mai jos pe pagină, la un scroll diferit, e
       neglijabil (verificat live, funcționează corect). */
    .strategy-hover-box, .vehicle-hover-box, .menu-hover-box, .obd-hover-box {
        display: none;
        position: fixed;
        top: 16vh;
        left: 50%;
        transform: translateX(-50%);
        max-width: min(560px, 92vw);
        max-height: 70vh;
        overflow-y: auto;
        border-radius: 10px;
        padding: 16px 18px;
        z-index: 9999;
    }
    .strategy-hover-box { background: #EAF2FF; border: 1px solid #CFE3FF; }
    .vehicle-hover-box, .menu-hover-box, .obd-hover-box { background: #EAF9EF; border: 1px solid #BEE8CC; }

    /* .cycle-hover-box și .chart-hover-box trăiesc pe o pagină LUNGĂ, cu
       mai multe grafice răsfirate pe verticală (consum, SoC, redare live,
       putere, BSFC, TCO). Cu position:fixed (varianta inițială), oricare
       dintre ele apărea mereu la ACEEAȘI poziție din FEREASTRĂ — nu din
       PAGINĂ — deci dacă utilizatorul derula pagina și apoi trecea
       cursorul peste un titlu de grafic aflat sus, box-ul apărea exact
       acolo unde se întâmpla să fie derulată pagina în acel moment,
       suprapunându-se peste orice grafic era vizibil atunci (verificat
       direct pe aplicația publicată: box-ul de la SoC apărea peste
       graficul de redare live, aflat mult mai jos pe pagină). Soluție:
       position:absolute, relativ la propriul container din pagină (care
       scrolează normal, împreună cu restul conținutului) — pentru
       consum/SoC, ancora este rândul cu cele 2 coloane
       (stHorizontalBlock, făcut position:relative mai jos), ca boxul să
       rămână centrat pe tot rândul, nu doar pe o singură coloană îngustă;
       pentru celelalte (ciclu, redare live, putere, BSFC, TCO), ancora e
       chiar containerul individual al fiecărui marcaj/box (deja făcut
       position:relative prin aceeași regulă de mai jos care le colapsează
       la înălțime 0). */
    .cycle-hover-box, .chart-hover-box {
        display: none;
        position: absolute;
        top: 40px;
        left: 50%;
        transform: translateX(-50%);
        max-width: min(560px, 92vw);
        max-height: 70vh;
        overflow-y: auto;
        border-radius: 10px;
        padding: 16px 18px;
        z-index: 9999;
        background: #FFFFFF; border: 1px solid rgba(60,60,67,.18);
        box-shadow: 0 8px 28px rgba(0,0,0,.14);
    }
    div[data-testid="stHorizontalBlock"] { position: relative; }
    /* Interpretările pentru graficele tip tornado (analiza de
       sensibilitate) au fundal verde (stil identic cu
       .vehicle-hover-box/.menu-hover-box), pentru a semnala vizual că
       explică o convenție de citire a graficului, nu o interpretare
       directă a rezultatelor. */
    .chart-hover-box.chart-hover-sens { background: #EAF9EF; border: 1px solid #BEE8CC; }

    /* Consum/SoC și analiza de sensibilitate (Consum/TCO) stau în perechi,
       pe câte 2 coloane. Poziționarea inițială (centrată pe tot rândul,
       DEASUPRA graficului) făcea boxul să înceapă foarte jos față de
       vârful conținutului paginii pe ferestre mai puțin înalte, ieșind
       din zona vizibilă / suprapunându-se peste conținutul de SUB rând
       (expanderele următoare), iar utilizatorul nu putea vedea simultan
       graficul și textul integral al explicației. Soluție: fiecare box e
       ancorat acum la PROPRIUL grafic (nu la tot rândul) și apare ÎN
       LATERALUL acestuia — la dreapta pentru graficul din coloana stângă,
       la stânga pentru cel din coloana dreaptă — aliniat pe verticală cu
       vârful graficului, ca ambele (grafic + text integral) să rămână
       vizibile simultan, indiferent de înălțimea ferestrei. */
    /* NOTĂ TEHNICĂ: containerul individual (colapsat la înălțime 0) al
       acestor box-uri capătă, empiric (verificat live), lățimea ÎNTREGULUI
       rând cu 2 coloane, nu doar a propriei coloane — de-aia "left:100%"
       ar sări cu mult peste marginea ferestrei. "50%"/"50%" din DREAPTA
       cade exact pe granița dintre cele 2 coloane, indiferent de lățimea
       reală a ferestrei, ceea ce oferă poziționarea corectă: boxul începe
       chiar la granița dintre coloane și se extinde spre coloana
       cealaltă — nu acoperă NICIODATĂ propriul grafic (pe care îl
       explică), deși poate acoperi temporar graficul pereche cât timp
       cursorul stă deasupra titlului. */
    .chart-hover-cons, .chart-hover-sens-cons {
        top: 8px; left: 50%; right: auto; transform: none;
        margin-left: 10px; max-width: min(400px, 46vw);
    }
    .chart-hover-soc, .chart-hover-sens-tco {
        top: 8px; left: auto; right: 50%; transform: none;
        margin-right: 10px; max-width: min(400px, 46vw);
    }

    /* Redare live / Profil de putere / BSFC / TCO ocupă întreaga lățime a
       coloanei principale — nu există spațiu liber în lateral unde să
       apară boxul fără să iasă din zona vizibilă. Pentru acestea, boxul
       NU se mai suprapune peste grafic (position:absolute), ci apare în
       flux normal, IMEDIAT SUB grafic (position:static), împingând
       conținutul următor în jos cât timp e afișat — astfel graficul
       rămâne mereu complet vizibil, iar textul integral apare imediat
       lângă cursor, fără a-l acoperi. */
    .chart-hover-live, .chart-hover-power, .chart-hover-bsfc, .chart-hover-tco {
        position: static;
        top: auto; left: auto; right: auto; transform: none;
        max-width: 100%;
        margin: 10px 0 4px 0;
        box-shadow: 0 2px 10px rgba(0,0,0,.10);
    }

    /* Streamlit rezervă automat un spațiu vertical ("gap" de flexbox,
       16px) între FIECARE element dintr-o coloană/bara laterală. Verificat
       LIVE, pe aplicația publicată: display:contents NU elimină acest gap
       — Chrome tot inserează cate un gap complet în jurul fiecărui
       container, chiar dacă el nu generează nicio cutie vizibilă — și,
       fiind display:contents, containerul nici nu mai poate primi margin
       (o cutie inexistentă nu poate avea margine), deci acea variantă de
       reparație a fost abandonată. Soluția verificată funcțional: lăsăm
       containerul ca o cutie normală, de înălțime 0 (copilul lui e oricum
       fie display:none, fie position:fixed — nu contribuie la înălțime),
       și anulăm exact gap-ul din jurul lui cu margine negativă simetrică
       (-0.5rem sus/jos = -8px + -8px = -16px per container). Matematic,
       pentru N containere-fantomă la rând între două elemente reale:
       (N+1) goluri de 16px − N containere × 16px anulați = exact 16px
       rămași, adică un singur gol normal, indiferent câte containere sunt
       înlănțuite (1, ca la Variantă, sau 5, ca la Meniu). Selectorul de
       atribut e dublat intenționat (`[data-testid=...][data-testid=...]`)
       ca să crească specificitatea peste regula originală — Streamlit
       reinserează periodic propriul <style> mai jos în <head>, iar la
       specificitate egală ultima regulă din DOM câștigă indiferent care
       a fost scrisă prima; fără acest boost, propriul <style> al
       aplicației redevenea câștigător la fiecare rerun și anula fix-ul. */
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.strategy-hover-box),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.vehicle-hover-box),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.menu-hover-box),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.obd-hover-box),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.cycle-hover-box),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.chart-hover-cons),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.chart-hover-soc),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.chart-hover-sens-cons),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.chart-hover-sens-tco),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-variant-q),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-obd-upload-q),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-cycle-q),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-cons-chart-q),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-soc-chart-q),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-live-q),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-power-q),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-bsfc-q),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-tco-q),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-sens-cons-q),
    div[data-testid="stElementContainer"][data-testid="stElementContainer"]:has(div.anchor-sens-tco-q) {
        display: block !important;
        margin: -0.5rem 0 !important;
        padding: 0 !important;
        height: 0 !important;
        min-height: 0 !important;
        overflow: visible !important;
    }

    /* Ancoră de poziționare (position:relative) pentru boxurile care
       încă folosesc position:absolute — fiecare pe propriul container
       individual (nu pe tot rândul): ciclu, consum, SoC, cele 2 casete
       verzi de la analiza de sensibilitate. Redare live/putere/BSFC/TCO
       NU mai apar în listă — ele folosesc acum position:static (flux
       normal, vezi mai sus), nu mai au nevoie de o ancoră relative. */
    div[data-testid="stElementContainer"]:has(div.cycle-hover-box),
    div[data-testid="stElementContainer"]:has(div.chart-hover-cons),
    div[data-testid="stElementContainer"]:has(div.chart-hover-soc),
    div[data-testid="stElementContainer"]:has(div.chart-hover-sens-cons),
    div[data-testid="stElementContainer"]:has(div.chart-hover-sens-tco) {
        position: relative !important;
    }

    /* Strategia de management energetic: doar un singur dropdown poate fi
       deschis simultan în toată aplicația, deci verificăm explicit că
       ACEST select (identificat stabil după eticheta lui, nu după un id
       generat aleator de bibliotecă) e cel deschis (aria-expanded="true")
       înainte să arătăm explicația opțiunii aflate sub cursor. Astfel nu
       există risc de coliziune cu alte dropdown-uri din pagină (Marcă,
       Model, Variantă, Meniu etc.) care ar putea avea aceeași poziție de
       opțiune. */
    body:has(input[aria-label$="Strategia de management energetic"][aria-expanded="true"]):has(li[role="option"]:nth-of-type(1):hover) .strategy-hover-0 { display: block !important; }
    body:has(input[aria-label$="Strategia de management energetic"][aria-expanded="true"]):has(li[role="option"]:nth-of-type(2):hover) .strategy-hover-1 { display: block !important; }
    body:has(input[aria-label$="Strategia de management energetic"][aria-expanded="true"]):has(li[role="option"]:nth-of-type(3):hover) .strategy-hover-2 { display: block !important; }

    /* Variantă (bază de date vehicule): box-ul apare la hover pe selector.
       Notă tehnică: CSS nu permite :has() imbricat în :has() (nu e valid
       să verificăm "un element care conține un descendent hovered" atunci
       când identificatorul stă pe acel descendent) — de-aia identificăm
       selectorul „Variantă" printr-un marcaj invizibil pus imediat înainte
       de el (.anchor-variant-q) și folosim combinatori de frați ("+"/"~"),
       nu un al doilea :has(). Funcționează identic pentru toate vehiculele
       din bază, pentru că doar conținutul textului din box se schimbă în
       funcție de selecție, nu regula CSS. */
    div[data-testid="stElementContainer"]:has(div.anchor-variant-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .vehicle-hover-box {
        display: block !important;
    }

    /* Meniu: aceeași logică ca la strategie — un singur dropdown poate fi
       deschis simultan, deci verificăm explicit că select-ul „Meniu" e cel
       deschis înainte de a arăta descrierea paginii aflate sub cursor. */
    body:has(input[aria-label$="Meniu"][aria-expanded="true"]):has(li[role="option"]:nth-of-type(1):hover) .menu-hover-0 { display: block !important; }
    body:has(input[aria-label$="Meniu"][aria-expanded="true"]):has(li[role="option"]:nth-of-type(2):hover) .menu-hover-1 { display: block !important; }
    body:has(input[aria-label$="Meniu"][aria-expanded="true"]):has(li[role="option"]:nth-of-type(3):hover) .menu-hover-2 { display: block !important; }
    body:has(input[aria-label$="Meniu"][aria-expanded="true"]):has(li[role="option"]:nth-of-type(4):hover) .menu-hover-3 { display: block !important; }
    body:has(input[aria-label$="Meniu"][aria-expanded="true"]):has(li[role="option"]:nth-of-type(5):hover) .menu-hover-4 { display: block !important; }

    /* Traseu real (OBD-II / Torque): explicația apare la hover pe butonul
       de upload, aceeași tehnică (marcaj invizibil + frați), validată
       anterior direct pe aplicația publicată. */
    div[data-testid="stElementContainer"]:has(div.anchor-obd-upload-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .obd-hover-box {
        display: block !important;
    }

    /* Ciclul selectat: box alb cu toate informațiile, la hover pe selector
       — aceeași tehnică (marcaj invizibil + frați), fără niciun buton. */
    div[data-testid="stElementContainer"]:has(div.anchor-cycle-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .cycle-hover-box {
        display: block !important;
    }

    /* Interpretări (box alb) pentru graficele principale — fiecare cu
       propriul marcaj invizibil și propria clasă unică, ca să nu se
       declanșeze greșit unul pe celălalt atunci când sunt pe aceeași
       pagină (chiar dacă toate au clasa vizuală comună .chart-hover-box). */
    div[data-testid="stElementContainer"]:has(div.anchor-cons-chart-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .chart-hover-cons {
        display: block !important;
    }
    div[data-testid="stElementContainer"]:has(div.anchor-soc-chart-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .chart-hover-soc {
        display: block !important;
    }
    div[data-testid="stElementContainer"]:has(div.anchor-sens-cons-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .chart-hover-sens-cons {
        display: block !important;
    }
    div[data-testid="stElementContainer"]:has(div.anchor-sens-tco-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .chart-hover-sens-tco {
        display: block !important;
    }
    div[data-testid="stElementContainer"]:has(div.anchor-live-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .chart-hover-live {
        display: block !important;
    }
    div[data-testid="stElementContainer"]:has(div.anchor-power-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .chart-hover-power {
        display: block !important;
    }
    div[data-testid="stElementContainer"]:has(div.anchor-bsfc-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .chart-hover-bsfc {
        display: block !important;
    }
    div[data-testid="stElementContainer"]:has(div.anchor-tco-q)
        + div[data-testid="stElementContainer"]:hover
        ~ div[data-testid="stElementContainer"] .chart-hover-tco {
        display: block !important;
    }
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
    .fused-metric-divider { border-top-color: rgba(84,84,88,.65) !important; }

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
def _md_bold_to_html(text: str) -> str:
    """Convertește **bold** (Markdown) în <b>bold</b> (HTML), ca textul să
    poată fi inclus în siguranță într-un bloc HTML randat dintr-un singur
    apel st.markdown(..., unsafe_allow_html=True) — Streamlit nu (mai)
    interpretează sintaxa Markdown în interiorul unui bloc HTML brut."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


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
        P_ICE_max_kW=st.number_input("Putere MAI [kW]", 40.0, 200.0, d.P_ICE_max_kW, 1.0, key="w_pice"),
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


def _is_safe_external_url(url: str) -> tuple[bool, str]:
    """Verificare de securitate de bază înainte de a accesa un URL introdus de
    utilizator (protecție SSRF): permite doar http(s) către un host public,
    blochează adresele private/loopback/link-local (ex. localhost, rețeaua
    internă, adresele de metadate cloud 169.254.169.254)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "URL invalid."
    if parsed.scheme not in ("http", "https"):
        return False, "Sunt acceptate doar adrese http:// sau https://."
    if not parsed.hostname:
        return False, "URL-ul nu conține un nume de host valid."
    try:
        resolved_ip = socket.gethostbyname(parsed.hostname)
        ip_obj = ipaddress.ip_address(resolved_ip)
    except (socket.gaierror, ValueError):
        return False, "Numele de host nu poate fi rezolvat."
    if (ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
            or ip_obj.is_reserved or ip_obj.is_multicast):
        return False, ("Din motive de securitate, aplicația nu accesează adrese "
                       "din rețele private/interne — folosiți un link public "
                       "(ex. raw GitHub, fișier găzduit public).")
    return True, ""


def load_external_params(uploaded, url: str) -> tuple[VehicleParams, list[str]]:
    """Parametri din fișier încărcat (JSON/CSV) sau dintr-un URL direct."""
    raw, kind, msgs = None, None, []
    if uploaded is not None:
        raw = uploaded.getvalue().decode("utf-8", errors="replace")
        kind = "json" if uploaded.name.lower().endswith(".json") else "csv"
    elif url.strip():
        ok, why = _is_safe_external_url(url.strip())
        if not ok:
            return VehicleParams(), [f"URL respins: {why}"]
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
            return VehicleParams(), [
                "Nu s-a putut descărca fișierul de la URL-ul indicat "
                "(conexiune eșuată, adresă greșită sau server indisponibil). "
                f"Detaliu tehnic: {type(e).__name__}: {e}"]
    if raw is None:
        return VehicleParams(), ["Niciun fișier/URL — se folosesc valorile din lucrare."]
    try:
        data = json.loads(raw) if kind == "json" else _parse_csv_params(raw)
        if not isinstance(data, dict):
            raise ValueError("JSON-ul trebuie să fie un obiect {cheie: valoare}.")
        p, m = _params_from_mapping(data)
        return p, msgs + m
    except Exception as e:
        return VehicleParams(), [
            "Fișierul nu a putut fi interpretat — verificați că este un JSON "
            "valid ({cheie: valoare}) sau un CSV cu două coloane (parametru, "
            f"valoare). Detaliu tehnic: {type(e).__name__}: {e}"]


# ======================================================================
#  Sidebar stânga: titlu, Configurare date de intrare, Meniu
# ======================================================================
PAGES = ["Simulare", "Sensibilitate", "Comparație A/B", "Validare", "Export PDF"]

with st.sidebar:
    st.image(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "assets", "logo_hybrid.png"),
               use_container_width=True)
    st.markdown("## Configurare date de intrare")
    mode = st.selectbox("Sursa datelor",
                        ["Preset: Bigster (lucrare)",
                         "Bază de date (marcă → model)",
                         "Introducere manuală",
                         "Fișier încărcat / URL"])
    strategy = st.selectbox("Strategia de management energetic",
                            options=["rule_based", "ecms", "dp"],
                            format_func=lambda s: STRATEGY_LABELS[s])
    # Explicația fiecărei strategii apare doar când cursorul stă deasupra
    # opțiunii respective în dropdown-ul deschis (fără niciun buton „?").
    # Cele 3 box-uri sunt randate mereu în DOM (ascunse), iar CSS-ul de mai
    # jos le arată condiționat — vezi regulile .strategy-hover-N din <style>.
    st.markdown(
        '<div class="strategy-hover-box strategy-hover-0">'
        '<p style="margin:0 0 6px 0;"><b>Strategie bazată pe reguli</b></p>'
        '<p style="margin:0;">Strategia bazată pe reguli stabilește, la '
        'fiecare pas de timp, contribuția motorului termic și a mașinii '
        'electrice pe baza unui set predefinit de reguli euristice: '
        'motorul termic este oprit în regim de staționare; energia de '
        'frânare este recuperată prin regenerare în baterie; la cereri de '
        'putere reduse și un nivel suficient de energie stocată, '
        'propulsia se realizează exclusiv electric; la cereri ridicate, '
        'cele două surse funcționează simultan. Este strategia cu cel mai '
        'redus grad de complexitate algoritmică, cea mai apropiată de '
        'soluțiile implementate în prezent de majoritatea autovehiculelor '
        'hibride comerciale — ușor de implementat și de verificat, dar '
        'fără garanția atingerii consumului minim teoretic.</p>'
        '</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="strategy-hover-box strategy-hover-1">'
        '<p style="margin:0 0 6px 0;"><b>Minimizarea consumului '
        'echivalent</b></p>'
        '<p style="margin:0;">Strategia calculează, la fiecare pas de '
        'timp, un cost echivalent asociat fiecărei decizii posibile de '
        'repartizare a puterii: utilizării energiei electrice stocate în '
        'baterie i se atribuie un preț virtual exprimat în combustibil, '
        'permițând compararea directă a celor două surse de energie pe o '
        'unitate de măsură comună. Este selectată, la fiecare moment, '
        'combinația cu costul instantaneu minim. Strategia oferă o '
        'eficiență superioară strategiei bazate pe reguli, cu o '
        'complexitate de calibrare mai ridicată, întrucât factorul de '
        'echivalență trebuie ajustat astfel încât starea de încărcare a '
        'bateriei la finalul ciclului să revină în vecinătatea valorii '
        'inițiale.</p>'
        '</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="strategy-hover-box strategy-hover-2">'
        '<p style="margin:0 0 6px 0;"><b>Programare dinamică</b></p>'
        '<p style="margin:0;">Strategia nu adoptă decizii secvențiale, ci '
        'determină, prin optimizare numerică asupra întregului profil de '
        'viteză cunoscut a priori, combinația optimă globală de utilizare '
        'a motorului termic și a mașinii electrice pe toată durata '
        'ciclului. Rezultatul reprezintă limita inferioară teoretică a '
        'consumului pentru traseul respectiv — un etalon de referință '
        'față de care sunt evaluate celelalte două strategii — însă nu '
        'este aplicabilă în condiții reale de conducere, deoarece '
        'presupune cunoașterea integrală, din start, a profilului de '
        'viteză, ipoteză nerealistă în traficul real.</p>'
        '</div>', unsafe_allow_html=True)
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
            # Marcaj invizibil folosit doar de CSS (regula .vehicle-hover-box
            # de mai jos), ca să identifice exact acest selector printre
            # toate din bara laterală, fără ambiguitate.
            st.markdown('<div class="anchor-variant-q"></div>',
                        unsafe_allow_html=True)
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
            _vehicle_line1 = (
                f'<b>{vrow["tip"]}</b> · arhitectura reală: '
                f'<b>{ARCH_LABELS.get(vrow["arhitectura"], vrow["arhitectura"])}</b> · '
                f'CO₂ WLTP oficial: <b>{vrow["co2_wltp_g_km"]} g/km</b> '
                f'({vrow["consum_wltp_L_100km"]} L/100 km'
                + (", ponderat" if vrow["tip"] == "PHEV" else "") + ")")
            _vehicle_line2 = (
                f'Sursă: {vrow["sursa"]} · câmpuri estimate: '
                f'{str(vrow["estimari"]).replace(";", ", ")}')
            eea_rep = load_eea_report()
            audit_html = None
            if eea_rep is not None:
                hit = eea_rep[(eea_rep["marca"] == vrow["marca"]) &
                              (eea_rep["model"] == vrow["model"]) &
                              (eea_rep["varianta"] == vrow["varianta"])]
                if len(hit):
                    h = hit.iloc[0]
                    if str(h["status"]).startswith("OK"):
                        audit_html = (
                            '<span style="color:#1FA971;font-weight:700;">Audit '
                            f'EEA: OK</span> · abateri față de mediana EEA — masă '
                            f'{h.get("abatere_masa_pct", "–")}%, CO₂ '
                            f'{h.get("abatere_co2_pct", "–")}% '
                            f'({int(h["eea_inregistrari"])} înregistrări)')
                    elif str(h["status"]).startswith("NEGĂSIT"):
                        audit_html = (
                            '<span style="color:#8E8E93;font-weight:700;">Audit '
                            'EEA: negăsit</span> în setul EEA (denumire '
                            'comercială diferită sau model non-UE).')
                    else:
                        audit_html = (
                            '<span style="color:#B8860B;font-weight:700;">Audit '
                            f'EEA: de verificat</span> · masă '
                            f'{h.get("abatere_masa_pct", "–")}%, CO₂ '
                            f'{h.get("abatere_co2_pct", "–")}% față de mediana '
                            'EEA.')
                else:
                    audit_html = ('<span style="color:#8E8E93;">Acest vehicul nu '
                                  'apare încă în auditul EEA local.</span>')
            else:
                audit_html = ('<span style="color:#8E8E93;">Raportul de audit '
                              'EEA nu a fost generat local încă.</span>')

            if vrow["tip"] == "PHEV":
                tip_html = (
                    '<b>Rezultatele simulate nu corespund regimului uzual de '
                    'exploatare al unui vehicul PHEV</b> (care pornește, în '
                    'mod obișnuit, cu bateria complet încărcată, prin '
                    'reîncărcare la rețea). Simularea este rulată în regim de '
                    'menținere a stării de încărcare (charge-sustaining) — '
                    'bateria debutează și încheie ciclul la același nivel de '
                    'încărcare, acesta fiind menținut constant de motorul '
                    'termic, fără reîncărcare la rețea pe durata simulării.')
            elif vrow["tip"] == "MHEV":
                tip_html = (
                    '<b>Electrificare ușoară — acest vehicul este recomandat '
                    'a fi utilizat cu precădere ca referință de tip '
                    'convențional, nu ca arhitectură hibridă completă.</b> '
                    'Mașina electrică are o putere redusă, ceea ce limitează '
                    'semnificativ capacitatea de propulsie exclusiv '
                    'electrică.')
            else:  # HEV
                tip_html = (
                    '<b>Hibrid complet (Full HEV)</b> — mașina electrică este '
                    'capabilă să asigure singură propulsia pe distanțe scurte, '
                    'fără reîncărcare la rețea; bateria se reîncarcă exclusiv '
                    'prin frânare regenerativă și prin funcționarea motorului '
                    'termic.')

            # Rezumatul, auditul EEA și descrierea tipului de electrificare
            # apar doar când cursorul stă deasupra selectorului „Variantă"
            # (fără niciun buton „?") — vezi regula .vehicle-hover-box din
            # <style>. Generalizat automat pentru orice vehicul din bază,
            # pentru că tot conținutul de mai jos e recalculat la fiecare
            # selecție.
            st.markdown(
                '<div class="vehicle-hover-box">'
                f'<p style="margin:0 0 10px 0;">{_vehicle_line1}</p>'
                f'<p style="margin:0 0 14px 0;color:#555;">{_vehicle_line2}</p>'
                f'<p style="margin:0 0 14px 0;">{audit_html}</p>'
                f'<p style="margin:0;">{tip_html}</p>'
                '</div>', unsafe_allow_html=True)
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

    # --- Import de trasee reale OBD-II (Torque) ca ciclu propriu ---------
    cycles = load_cycles()
    with st.expander("Traseu real (OBD-II / Torque)", expanded=False):
        # Explicația apare doar la trecerea cursorului peste butonul de
        # upload (fără text mereu vizibil) — vezi regula .obd-hover-box.
        st.markdown('<div class="anchor-obd-upload-q"></div>',
                    unsafe_allow_html=True)
        obd_file = st.file_uploader("Log Torque (CSV)", type=["csv"], key="obd_up")
        st.markdown(
            '<div class="obd-hover-box">Se poate încărca un fișier CSV '
            'exportat din aplicația Torque, obținut prin înregistrare cu '
            'adaptor OBD-II. Traseul este integrat ca ciclu de testare '
            'selectabil, fiind reeșantionat la o frecvență de 1 Hz, iar '
            'intervalele de staționare sunt eliminate din analiză.</div>',
            unsafe_allow_html=True)
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
                st.success(f"Traseu integrat cu succes: {res['distance_km']:.1f} km · "
                           f"{res['duration_s']//60} min · viteză maximă "
                           f"{res['v_max']:.0f} km/h · {res['n_stops']} opriri "
                           f"complete")
                if res["consumption_L_100km"]:
                    st.caption(f"Consum real determinat experimental (din "
                               f"debitul de aer măsurat, MAF): "
                               f"**{res['consumption_L_100km']:.2f} L/100 km** — "
                               f"valoare utilizabilă pentru validarea "
                               f"configurației de referință.")
                for w in res["warnings"]:
                    st.caption(f"• {w}")
            except ValueError as e:
                # parse_torque_log() ridică deja mesaje explicative în română
                # pentru cazurile așteptate (coloane lipsă, prea puține puncte
                # etc.) — le afișăm direct, fără alt strat de traducere.
                st.warning(str(e))
            except Exception as e:
                st.warning(
                    "Fișierul nu a putut fi interpretat — vă rugăm să "
                    "verificați că reprezintă un export CSV valid din "
                    "aplicația Torque (necesită antet cu coloane de viteză și "
                    "timp). "
                    f"Detaliu tehnic: {type(e).__name__}: {e}")

    run_btn = st.button("Rulează simularea", type="primary", use_container_width=True)

    st.markdown("## Selectează secțiunea")
    st.session_state.active_page = st.selectbox(
        "Meniu", PAGES,
        index=PAGES.index(st.session_state.get("active_page", PAGES[0])),
        label_visibility="collapsed")
    # Descrierea fiecărei pagini apare doar când cursorul stă deasupra
    # opțiunii respective în dropdown-ul deschis (fără niciun buton „?"),
    # la fel ca la strategie — vezi regulile .menu-hover-N din <style>.
    _page_desc = [
        "Execută simularea celor patru arhitecturi de propulsie pe "
        "ansamblul ciclurilor de testare selectate și prezintă consumul "
        "de combustibil, emisiile de CO₂, evoluția stării de încărcare a "
        "bateriei și derularea temporală animată a fiecărei simulări.",
        "Evaluează sensibilitatea rezultatelor la variația independentă a "
        "masei vehiculului, a prețului combustibilului și a celorlalți "
        "parametri de intrare, cu ±20% față de valoarea de referință — "
        "util pentru identificarea factorilor cu influență determinantă "
        "asupra rezultatelor.",
        "Permite compararea directă a două seturi de parametri de vehicul "
        "(de exemplu, două variante de echipare) pentru aceeași "
        "arhitectură de propulsie și același ciclu de testare.",
        "Verifică respectarea limitelor fizice reale ale sistemului "
        "(capacitatea bateriei, puterile instalate ale motoarelor) și "
        "compară rezultatele simulării cu valorile omologate, publicate "
        "de producători.",
        "Generează un raport PDF complet, incluzând tabelele de rezultate, "
        "graficele și interpretările asociate, pregătit pentru anexare la "
        "lucrarea de disertație sau pentru tipărire.",
    ]
    for _i, (_name, _desc) in enumerate(zip(PAGES, _page_desc)):
        st.markdown(
            f'<div class="menu-hover-box menu-hover-{_i}">'
            f'<p style="margin:0;"><b>{_name}</b><br>{_desc}</p>'
            '</div>', unsafe_allow_html=True)

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
        st.session_state["db_row_used"] = (
            vrow.to_dict() if mode == "Bază de date (marcă → model)" else None)

if "results" not in st.session_state:
    st.info("Configurați parametrii de intrare în bara laterală și apăsați "
            "butonul **Rulează simularea** pentru a iniția calculul.")
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
    best_arch = min((a for a in ARCHITECTURES if a != "baseline"),
                    key=lambda a: results[a]["WLTC"].consumption_L_100km)
    opt_wltc = results[best_arch]["WLTC"].consumption_L_100km
    # Variația e semnul real (Python "-") — nu un caracter minus decorativ —
    # ca Streamlit să poată determina corect direcția săgeții: în jos pentru
    # scădere (verde, e un lucru bun aici), în sus pentru creștere (roșu).
    pct_vs_ref = (opt_wltc - base_wltc) / base_wltc * 100
    # Layout pe 2 coloane (nu 3): "Strategie" a fost mutat sub cardul de
    # consum referință, în aceeași coloană — ca și card SEPARAT, nu
    # fuzionat — pentru că, înghesuit într-o a treia coloană îngustă,
    # textul strategiei ("Strategie bazată pe reguli" etc.) se trunchia
    # vizual cu puncte de suspensie. Pe o coloană de lățime dublă (1/2 în
    # loc de 1/3), cardul are destul spațiu să afișeze eticheta întreagă.
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Consum de combustibil înregistrat de arhitectura de "
                 "referință WLTC [L/100km]", f"{base_wltc:.2f}")
        st.metric("Strategie", STRATEGY_LABELS[strat_used].split(" (")[0])
    # "Configurația optimă" și "Consumul înregistrat WLTC" sunt fuzionate
    # într-un singur card (altfel două st.metric() consecutive în aceeași
    # coloană produc două cutii albe separate, suprapuse vizual). Săgeata
    # și culoarea reproduc manual semantica delta_color="inverse" din
    # Streamlit: scădere reală (bun) = verde + săgeată jos; creștere
    # reală (rău) = roșu + săgeată sus.
    is_improvement = pct_vs_ref < 0
    delta_color_hex = "#34C759" if is_improvement else "#FF3B30"
    delta_bg_hex = "#E8F9EE" if is_improvement else "#FFEBEA"
    delta_arrow = "↓" if is_improvement else "↑"
    c2.markdown(
        f'<div data-testid="stMetric" style="display:flex;'
        f'flex-direction:column;gap:10px;">'
        f'<div><label>Configurația optimă</label>'
        f'<div data-testid="stMetricValue">'
        f'{ARCH_LABELS[best_arch].split(" (")[0]}</div></div>'
        f'<div class="fused-metric-divider" style="border-top:0.5px solid '
        f'rgba(60,60,67,.12);padding-top:10px;">'
        f'<label>Consumul înregistrat WLTC [L/100km]</label>'
        f'<div style="display:flex;align-items:baseline;gap:10px;">'
        f'<div data-testid="stMetricValue">{opt_wltc:.2f}</div>'
        f'<div style="background:{delta_bg_hex};color:{delta_color_hex};'
        f'font-weight:600;font-size:.85rem;padding:2px 9px;'
        f'border-radius:8px;">{delta_arrow} {abs(pct_vs_ref):.1f}%</div>'
        f'</div></div></div>', unsafe_allow_html=True)

    rows = []
    for arch in ARCHITECTURES:
        for cyc in cycles:
            r = results[arch][cyc]
            base = results["baseline"][cyc].consumption_L_100km
            rows.append({"Arhitectură": ARCH_LABELS[arch], "Ciclu": cyc,
                         "Consum [L/100km]": r.consumption_L_100km,
                         "CO₂ [g/km]": r.co2_g_km,
                         "Cotă EV [%]": r.ev_share_pct,
                         "Reducere [%]": (round((base - r.consumption_L_100km) / base * 100, 1)
                                          if base and base > 0 else 0.0)})
    df = pd.DataFrame(rows)
    with st.expander("Rezultate detaliate", expanded=False):
        st.dataframe(df, use_container_width=True, hide_index=True, height=420)

    colA, colB = st.columns(2)
    with colA:
        cons_data = {a: {c: results[a][c].consumption_L_100km for c in cycles}
                     for a in ARCHITECTURES}
        # Interpretarea graficului apare la trecerea cursorului peste el
        # (marcaj invizibil + regulă CSS .anchor-cons-chart-q).
        st.markdown('<div class="anchor-cons-chart-q"></div>',
                    unsafe_allow_html=True)
        st.plotly_chart(plot_consumption_bars(cons_data), use_container_width=True)
        st.markdown(
            '<div class="chart-hover-box chart-hover-cons">Figura ilustrează, '
            'într-o manieră comparativă, valorile consumului de combustibil '
            'corespunzătoare celor patru arhitecturi de propulsie evaluate, '
            'pentru fiecare ciclu de testare considerat. Reprezentarea '
            'permite identificarea configurației cu cea mai ridicată '
            'eficiență energetică în funcție de condițiile de exploatare '
            'analizate (urban, extraurban și trasee reale). Bara gri indică '
            'vehiculul convențional de referință, față de care sunt '
            'raportate performanțele celor trei arhitecturi hibride.'
            '</div>', unsafe_allow_html=True)
    with colB:
        st.markdown('<div class="anchor-soc-chart-q"></div>',
                    unsafe_allow_html=True)
        st.plotly_chart(plot_soc_trajectory(
            {a: results[a]["WLTC"] for a in ARCHITECTURES}, p_used),
            use_container_width=True)
        st.markdown(
            '<div class="chart-hover-box chart-hover-soc">Figura prezintă '
            'evoluția temporală a stării de încărcare a bateriei, pentru '
            'fiecare arhitectură, pe parcursul ciclului de testare '
            'considerat. O traiectorie care se menține în vecinătatea '
            'nivelului inițial indică o strategie de gestiune energetică '
            'echilibrată, în care energia electrică consumată este '
            'compensată prin regenerare; o traiectorie cu tendință '
            'descrescătoare constantă către pragul minim admis indică o '
            'arhitectură care recurge într-o măsură mai mare la motorul '
            'termic spre finalul ciclului.</div>', unsafe_allow_html=True)

    with st.expander("Analiză detaliată pe arhitectură", expanded=False):
        sel_arch = st.selectbox("Arhitectura", [a for a in ARCHITECTURES],
                                format_func=lambda a: ARCH_LABELS[a])
        # Marcaj invizibil pus imediat înainte de selectorul "Ciclul" —
        # folosit de CSS ca să identifice exact acest select, fără
        # ambiguitate cu celelalte din pagină.
        st.markdown('<div class="anchor-cycle-q"></div>', unsafe_allow_html=True)
        sel_cyc = st.selectbox("Ciclul", list(cycles.keys()))
        r_sel = results[sel_arch][sel_cyc]

        # --- Ce înseamnă ciclul selectat — totul într-un singur box alb,
        # afișat doar la trecerea cursorului peste selectorul "Ciclul"
        # (fără text mereu vizibil). ---
        if sel_cyc in CYCLE_INFO:
            _cyc_desc_html = _md_bold_to_html(CYCLE_INFO[sel_cyc])
        elif sel_cyc.startswith("Real:"):
            _cs_here = cycle_stats(cycles[sel_cyc])
            _cyc_desc_html = (
                f"<b>Traseu real importat</b> — înregistrare achiziționată "
                f"de utilizator printr-un jurnal OBD-II (aplicația Torque), "
                f"reeșantionată la o frecvență de 1 Hz. Nu constituie un "
                f"ciclu standardizat de omologare, ci o înregistrare "
                f"experimentală proprie: aproximativ {_cs_here['distance_km']:.1f} "
                f"km, {_cs_here['n_stops']} opriri complete, viteză maximă "
                f"{_cs_here['v_max']:.0f} km/h. Util pentru evaluarea "
                f"comparativă a arhitecturilor în condiții proprii de "
                f"conducere, fără valoare de omologare.")
        else:
            _cyc_desc_html = "Nu este disponibilă o descriere pentru acest ciclu."
        cs = cycle_stats(cycles[sel_cyc])
        st.markdown(
            '<div class="cycle-hover-box">'
            '<p style="margin:0 0 10px 0;"><b>Caracteristicile ciclului de testare selectat</b></p>'
            f'<p style="margin:0 0 14px 0;">{_cyc_desc_html}</p>'
            '<p style="margin:0 0 10px 0;color:#666;">Indicatorii de mai jos '
            'sunt calculați pe baza profilului de viteză efectiv '
            'utilizat în cadrul simulării:</p>'
            '<div style="display:flex;gap:18px;flex-wrap:wrap;margin-bottom:10px;">'
            '<div><p style="margin:0;color:#666;font-size:.8rem;">Durată [s]</p>'
            f'<p style="margin:0;font-weight:700;font-size:1.3rem;">{cs["duration_s"]}</p></div>'
            '<div><p style="margin:0;color:#666;font-size:.8rem;">Distanță [km]</p>'
            f'<p style="margin:0;font-weight:700;font-size:1.3rem;">{cs["distance_km"]:.2f}</p></div>'
            '<div><p style="margin:0;color:#666;font-size:.8rem;">Viteză medie / în mers [km/h]</p>'
            f'<p style="margin:0;font-weight:700;font-size:1.3rem;">{cs["v_avg"]:.1f} / {cs["v_avg_moving"]:.1f}</p></div>'
            '<div><p style="margin:0;color:#666;font-size:.8rem;">Viteză maximă [km/h]</p>'
            f'<p style="margin:0;font-weight:700;font-size:1.3rem;">{cs["v_max"]:.1f}</p></div>'
            '</div>'
            f'<p style="margin:0;color:#666;">Durata de staționare reprezintă '
            f'{cs["idle_pct"]:.0f}% din durata totală a ciclului, cu '
            f'{cs["n_stops"]} opriri complete înregistrate.</p>'
            '</div>', unsafe_allow_html=True)

        # Harta traseului real, dacă ciclul selectat are traseu GPS — rămâne
        # mereu vizibilă (e o hartă interactivă, nu doar text).
        _tracks = {**load_bundled_tracks(),
                   **st.session_state.get("gps_tracks", {})}
        if sel_cyc in _tracks:
            deck = build_track_map(_tracks[sel_cyc])
            if deck is not None:
                st.markdown("##### Traseul geografic parcurs")
                st.pydeck_chart(deck, use_container_width=True)
                st.caption("Traseu real, înregistrat prin telemetrie OBD-II. "
                           "Culoarea traiectoriei reflectă viteza instantanee: "
                           "albastru — oprit/viteză redusă, verde-galben — "
                           "viteză medie, roșu — viteză ridicată. Marcajele "
                           "indică punctul de start (verde) și punctul final "
                           "(roșu) al traseului.")

        # --- Derularea LIVE ---
        st.markdown("##### Derularea temporală animată a ciclului")
        _SPEEDS = [1, 5, 10, 15, 20, 25, 30]
        spd_cur = st.session_state.get("live_speed", 1)
        b_l, b_r = st.columns([0.32, 0.68])
        spd_new = b_l.selectbox(
            "Viteza de derulare", _SPEEDS, index=_SPEEDS.index(spd_cur),
            format_func=lambda v: "Redare: timp real (1×)" if v == 1 else f"Redare: {v}×")
        if spd_new != spd_cur:
            st.session_state["live_speed"] = spd_new
            st.rerun()
        # Explicația comenzilor apare doar la trecerea cursorului peste
        # grafic (fără text mereu vizibil sub el) — vezi .anchor-live-q.
        st.markdown('<div class="anchor-live-q"></div>', unsafe_allow_html=True)
        st.plotly_chart(
            plot_cycle_live(r_sel, cycles[sel_cyc], p_used,
                            f"{ARCH_LABELS[sel_arch]} · {sel_cyc}",
                            speed=spd_cur),
            use_container_width=True)
        st.markdown(
            '<div class="chart-hover-box chart-hover-live">Comanda ▶ Redă '
            'inițiază derularea temporală animată a simulării: banda roșie '
            'indică funcționarea motorului termic, banda verde indică '
            'rularea în regim electric, iar triunghiurile marchează '
            'momentele de pornire a motorului termic (MAI). Al doilea rând '
            'al graficului prezintă consumul de combustibil și emisiile de '
            'CO₂ cumulate; al treilea rând prezintă starea de încărcare a '
            'bateriei. Cursorul din partea inferioară permite deplasarea '
            'directă la orice moment al ciclului.</div>', unsafe_allow_html=True)

        # --- Pornirile motorului termic ---
        if sel_arch != "baseline":
            st.markdown("##### Evenimentele de pornire a motorului termic")
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
                    f"Pornirea motorului termic este determinată de două "
                    f"cauze distincte, observabile în reprezentarea grafică: "
                    f"**cererea de tracțiune** (puterea solicitată depășește "
                    f"capacitatea mașinii electrice, generând porniri la "
                    f"viteze ridicate, independent de starea de încărcare) "
                    f"și **necesitatea reîncărcării bateriei** (starea de "
                    f"încărcare sub pragul-țintă de "
                    f"{p_used.SoC_target*100:.0f}%, generând porniri și la "
                    f"viteze reduse). Pe parcursul acestui ciclu, "
                    f"{int(low_soc.sum())} din cele {ign['n']} porniri "
                    f"înregistrate au avut loc cu starea de încărcare sub "
                    f"pragul-țintă; motorul termic a funcționat pe "
                    f"{ign['on_share_pct']:.0f}% din durata totală a "
                    f"ciclului.")
            else:
                st.info("Motorul termic nu a înregistrat nicio pornire pe "
                        "parcursul acestui ciclu.")

        # Interpretarea celor 3 grafice de putere apare la trecerea
        # cursorului peste titlul "Profilul de putere" (fără text mereu
        # vizibil) — vezi .anchor-power-q. Font-ul titlului e potrivit
        # exact cu cel al titlului "Harta consumului specific (BSFC)"
        # (15px), din interiorul graficului BSFC de mai jos.
        st.markdown('<div class="anchor-power-q"></div>', unsafe_allow_html=True)
        st.markdown(
            '<p style="font-size:15px;font-weight:600;margin:1rem 0 .5rem 0;">'
            'Profilul de putere</p>', unsafe_allow_html=True)
        st.plotly_chart(plot_power_profile(r_sel, cycles[sel_cyc]), use_container_width=True)
        st.markdown(
            '<div class="chart-hover-box chart-hover-power">Cele trei '
            'reprezentări grafice descriu, pe întreaga durată a ciclului, '
            'modul de distribuție a efortului de propulsie: reprezentarea '
            'superioară indică viteza de deplasare a vehiculului; '
            'reprezentarea centrală indică contribuția instantanee a '
            'motorului termic în raport cu mașina electrică; reprezentarea '
            'inferioară indică fluxul de putere prin baterie — culoarea '
            'roșie corespunde regimului de descărcare, în sprijinul '
            'propulsiei, iar culoarea verde corespunde regimului de '
            'reîncărcare, prin frânare regenerativă sau prin funcționarea '
            'motorului termic. Interpretate împreună, cele trei '
            'reprezentări evidențiază deciziile adoptate de strategia de '
            'gestiune energetică pe parcursul simulării.</div>',
            unsafe_allow_html=True)

        st.markdown('<div class="anchor-bsfc-q"></div>', unsafe_allow_html=True)
        st.plotly_chart(plot_bsfc_map(p_used, r_sel), use_container_width=True)
        st.markdown(
            '<div class="chart-hover-box chart-hover-bsfc">Reprezentarea '
            'ilustrează consumul specific de combustibil al motorului '
            'termic, exprimat per kilowatt-oră de energie produsă, în '
            'funcție de regimul de sarcină — constituind, în esență, o '
            'hartă a randamentului termic al motorului. Zona evidențiată '
            'în verde marchează punctul de funcționare cu eficiență '
            'maximă; punctele portocalii indică regimurile de funcționare '
            'efectiv parcurse în cadrul simulării. Cu cât aceste puncte '
            'sunt situate mai aproape de zona de eficiență maximă, cu '
            'atât motorul termic a fost exploatat mai eficient.</div>',
            unsafe_allow_html=True)

    with st.expander("Costul total de proprietate", expanded=False):
        tco_data = {}
        for arch in ARCHITECTURES:
            avg = np.mean([results[arch][c].consumption_L_100km for c in cycles])
            tco_data[arch] = compute_tco(p_used.price_EUR * PRICE_MAP[arch], avg,
                                         p_used.residual_frac, econ_used,
                                         is_hev=(arch != "baseline"))
        st.markdown('<div class="anchor-tco-q"></div>', unsafe_allow_html=True)
        st.plotly_chart(plot_tco_breakdown(tco_data), use_container_width=True)
        st.markdown(
            '<div class="chart-hover-box chart-hover-tco">Reprezentarea '
            'grafică descompune costul total de proprietate al vehiculului '
            'pe un orizont de 10 ani de exploatare, în componentele sale: '
            'prețul de achiziție, costul combustibilului și al energiei '
            'electrice consumate, costurile de mentenanță și cele de '
            'asigurare/taxe, din care se deduce valoarea reziduală '
            'estimată la revânzare. Compararea înălțimii totale a barelor '
            'evidențiază arhitectura cu cel mai redus cost pe termen lung, '
            'nu doar la momentul achiziției.</div>',
            unsafe_allow_html=True)
        be = compute_breakeven(p_used.price_EUR * PRICE_MAP["baseline"],
                               p_used.price_EUR,
                               np.mean([results["baseline"][c].consumption_L_100km for c in cycles]),
                               np.mean([results["paralel"][c].consumption_L_100km for c in cycles]),
                               econ_used)
        if be.get("years"):
            st.success(f"**Pragul de rentabilitate hibrid în configurație "
                       f"paralel vs. vehicul de referință:** {be['years']} ani "
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
            st.caption(f"Vehicul selectat din baza de date: **{db_used['marca']} "
                       f"{db_used['model']} {db_used['varianta']}** — comparația "
                       f"se realizează prin raportare la **propria valoare WLTP "
                       f"omologată**, corespunzătoare arhitecturii reale "
                       f"({ARCH_LABELS.get(arch_r, arch_r)}).")
            if db_used["tip"] == "PHEV":
                st.dataframe(pd.DataFrame([{
                    "Mărime": "Consum WLTP oficial (ponderat, baterie plină)",
                    "Valoare": f"{off:.1f} L/100 km"}, {
                    "Mărime": "Consum simulat charge-sustaining · WLTC",
                    "Valoare": f"{sim_w:.3f} L/100 km"}]),
                    use_container_width=True, hide_index=True)
                st.caption(
                    "**PHEV:** valoarea de omologare a consumului de "
                    "combustibil este ponderată prin aplicarea factorului de "
                    "utilitate (Utility Factor – UF), presupunând pornirea cu "
                    "bateria complet încărcată. Prin urmare, aceasta nu este "
                    "direct comparabilă cu rezultatele unei simulări în regim "
                    "charge-sustaining (CS). Consumul simulat corespunde "
                    "funcționării vehiculului după epuizarea energiei "
                    "electrice utilizabile și stabilizarea stării de "
                    "încărcare în jurul valorii-țintă a bateriei, fiind "
                    "echivalent cu „consumul susținut” (charge-sustaining "
                    "fuel consumption) din fișele WLTP, în situațiile în care "
                    "producătorul publică această informație.")
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
                st.caption(f"Abaterea de **{dev:+.1f}%** cuantifică "
                           f"acuratețea modelului de simulare pentru vehiculul "
                           f"selectat, utilizând parametrii din baza de date "
                           f"(câmpuri estimate: "
                           f"{str(db_used['estimari']).replace(';', ', ')}).")
        else:
            sp_wltc = results["serie_paralel"]["WLTC"].consumption_L_100km
            cmpv = compare_with_sources(sp_wltc, "serie_paralel", min_sources=3)
            st.caption(f"Consum simulat pentru arhitectura serie-paralel, ciclul "
                       f"WLTC: **{sp_wltc:.3f} L/100 km** — comparat exclusiv cu "
                       "ciclul de omologare WLTP (WLTC), nu cu media pe cele "
                       "trei cicluri de testare.")
            st.dataframe(pd.DataFrame([{
            "Sursă (vehicul)": c["name"], "WLTP [L/100km]": c["official_L_100km"],
            "Abatere [%]": c["deviation_pct"], "Referință": c["source"]}
            for c in cmpv["comparisons"]]), use_container_width=True, hide_index=True)
            st.caption("Dintre vehiculele enumerate, **doar Dacia Bigster** este "
                       "modelat efectiv în cadrul aplicației — abaterea față de "
                       "acesta cuantifică acuratețea modelului. Symbioz și Corolla "
                       "reprezintă vehicule cu parametri diferiți (masă, motorizare, "
                       "sistem hibrid) și au rol exclusiv orientativ, pentru "
                       "încadrarea rezultatului într-un interval de plauzibilitate "
                       "specific clasei de vehicule full-hybrid, fără valoare de "
                       "validare directă.")

# ----------------------------------------------------------------------
def page_sensibilitate():
    st.markdown("#### Analiza de sensibilitate")
    st.caption("Fiecare parametru de intrare este variat independent cu "
               "**±20%** față de valoarea de referință (interval convențional "
               "de analiză, fixat în aplicație, neconfigurabil din interfață), "
               "fiind cuantificat efectul asupra consumului de combustibil și "
               "asupra costului total de proprietate. Diagrama de tip tornado "
               "ordonează parametrii în funcție de influența exercitată asupra "
               "rezultatului final, parametrii asociați barelor de lungime mai "
               "mare având efectul cel mai pronunțat.")
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
            # Explicația convenției de citire a culorilor (vezi mai jos)
            # apare la trecerea cursorului peste grafic — aceeași tehnică
            # de marcaj invizibil + reguli CSS ca la graficele de consum/SoC,
            # dar cu fundal verde (.chart-hover-sens).
            st.markdown('<div class="anchor-sens-cons-q"></div>',
                        unsafe_allow_html=True)
            st.plotly_chart(plot_sensitivity_tornado(
                sens["consumption"], sens["base_consumption"],
                "Consum [L/100km]"), use_container_width=True)
            st.markdown(
                '<div class="chart-hover-box chart-hover-sens '
                'chart-hover-sens-cons">Codul cromatic indică sensul '
                'variației parametrului analizat, nu o poziție fixă față '
                'de axa centrală: bara albastră corespunde reducerii '
                'parametrului cu 20% față de valoarea de referință, iar '
                'bara portocalie corespunde creșterii acestuia cu 20%. '
                'Direcția în care se extinde fiecare bară reflectă relația '
                'fizică dintre parametrul respectiv și consumul de '
                'combustibil. Pentru parametrii aflați în relație directă '
                'cu consumul (masă, arie frontală, coeficient aerodinamic, '
                'rezistență la rulare), creșterea parametrului determină '
                'creșterea consumului, astfel încât bara portocalie '
                '(+20%) se extinde spre dreapta, iar cea albastră (−20%) '
                'spre stânga. Pentru randamentele funcționale (randamentul '
                'termic al motorului, randamentul transmisiei), relația '
                'este inversă — o creștere a randamentului reduce '
                'consumul —, motiv pentru care, la aceste rânduri, bara '
                'portocalie apare spre stânga, iar cea albastră spre '
                'dreapta, reflectând corect comportamentul fizic al '
                'sistemului.</div>', unsafe_allow_html=True)
        with colR:
            st.markdown('<div class="anchor-sens-tco-q"></div>',
                        unsafe_allow_html=True)
            st.plotly_chart(plot_sensitivity_tornado(
                sens["tco"], sens["base_tco"], "TCO [EUR]"),
                use_container_width=True)
            st.markdown(
                '<div class="chart-hover-box chart-hover-sens '
                'chart-hover-sens-tco">Codul cromatic indică sensul '
                'variației parametrului analizat, nu o poziție fixă față '
                'de axa centrală: bara albastră corespunde reducerii '
                'parametrului cu 20% față de valoarea de referință, iar '
                'bara portocalie corespunde creșterii acestuia cu 20%. '
                'Direcția în care se extinde fiecare bară reflectă relația '
                'fizică dintre parametrul respectiv și costul total de '
                'proprietate. Pentru majoritatea parametrilor (fizici și '
                'economici), creșterea parametrului determină creșterea '
                'costului, astfel încât bara portocalie (+20%) se extinde '
                'spre dreapta, iar cea albastră (−20%) spre stânga. Pentru '
                'randamentele funcționale (randamentul termic al '
                'motorului, randamentul transmisiei), relația este '
                'inversă — o creștere a randamentului reduce consumul de '
                'combustibil și, implicit, costul total de proprietate —, '
                'motiv pentru care, la aceste rânduri, bara portocalie '
                'apare spre stânga, iar cea albastră spre dreapta, '
                'reflectând corect comportamentul fizic al sistemului.'
                '</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------
def page_comparatie():
    st.markdown("#### Comparația vehicul A versus vehicul B")
    st.caption("Se definesc două seturi independente de parametri de vehicul; "
               "aplicația simulează ambele configurații pentru aceeași "
               "arhitectură de propulsie și același ciclu de testare, "
               "evidențiind diferențele obținute.")
    cmp_arch = st.selectbox("Arhitectura", ARCHITECTURES,
                            format_func=lambda a: ARCH_LABELS[a], key="cmp_arch", index=2)
    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Vehicul A**")
        mA = st.number_input("Masă A [kg]", 800.0, 3000.0, 1494.0, 10.0)
        cdA = st.number_input("Cd A", 0.20, 0.50, 0.32, 0.01)
        peA = st.number_input("Putere MAI A [kW]", 40.0, 200.0, 80.0, 1.0)
        batA = st.number_input("Baterie A [kWh]", 0.5, 60.0, 1.4, 0.1)
        prA = st.number_input("Preț A [EUR]", 15000.0, 90000.0, 28590.0, 100.0)
    with colB:
        st.markdown("**Vehicul B**")
        mB = st.number_input("Masă B [kg]", 800.0, 3000.0, 1650.0, 10.0)
        cdB = st.number_input("Cd B", 0.20, 0.50, 0.30, 0.01)
        peB = st.number_input("Putere MAI B [kW]", 40.0, 200.0, 95.0, 1.0)
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
        st.info(f"**Diferența de consum (B − A):** {dcons:+.3f} L/100 km · "
                f"**Diferența costului total de proprietate (B − A):** "
                f"{tB - tA:+,} EUR".replace(",", " "))

# ----------------------------------------------------------------------
def page_validare():
    st.markdown("#### Validarea fizică a rezultatelor simulării")
    st.caption("Verifică respectarea limitelor fizice pentru fiecare simulare "
               "efectuată: încadrarea stării de încărcare a bateriei în "
               "intervalul admisibil, respectarea puterilor maxime instalate, "
               "bilanțul energetic și plauzibilitatea consumului rezultat.")

    # --- Auditul EEA al bazei de date de vehicule (dacă raportul există) ---
    eea_rep = load_eea_report()
    with st.expander("Audit EEA al bazei de date de vehicule", expanded=False):
        if eea_rep is None:
            st.info(
                "Raportul de audit nu a fost generat încă. Este necesară "
                "descărcarea setului de date EEA privind monitorizarea "
                "emisiilor de CO₂ (Regulamentul UE 2019/631) de pe platforma "
                "co2cars.apps.eea.europa.eu — filtrat pentru tipurile de "
                "combustibil petrol/electric și diesel/electric — urmată de "
                "execuția locală a comenzii:\n\n"
                "`python tools/verify_eea.py --eea <fișierul_EEA.csv>`\n\n"
                "Raportul rezultat este scris în "
                "`data/eea_verification_report.csv`; ulterior comiterii în "
                "depozitul de cod, această secțiune afișează automat abaterile "
                "de masă, putere și emisii de CO₂ față de mediana setului EEA, "
                "precum și statusul individual al fiecărui vehicul.")
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
            st.caption("Comparația se realizează cu mediana înregistrărilor "
                       "EEA per model (variantele de echipare specifice nu sunt "
                       "disponibile în setul EEA). Puterea raportată în EEA (ep) "
                       "este comunicată neuniform de către constructori, motiv "
                       "pentru care abaterile de putere trebuie interpretate cu "
                       "prudență. Parametrii Cd, Af, randament și capacitate a "
                       "bateriei, respectiv preț, nu sunt disponibili în setul "
                       "EEA și nu pot fi auditați prin această metodă.")

    st.markdown("##### Rezultatele verificărilor fizice")
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
    st.markdown("#### Exportul raportului PDF")
    st.caption("Generează un raport PDF unitar, incluzând parametrii de intrare, "
               "tabelele de rezultate, reprezentările grafice, validarea fizică, "
               "comparația cu sursele WLTP oficiale și interpretările generate "
               "automat.")
    all_cyc = list(cycles.keys())
    sel_cycles = st.multiselect(
        "Cicluri incluse în secțiunile detaliate (SoC, profiluri de putere, "
        "BSFC, validare, comparație WLTP)", all_cyc,
        default=[c for c in ["WLTC"] if c in all_cyc] or all_cyc[:1])
    if not sel_cycles:
        st.info("Este necesară selectarea a cel puțin un ciclu pentru "
            "generarea secțiunilor detaliate ale raportului.")
    st.caption("Tabelele de sinteză (consum de combustibil, emisii de CO₂, "
               "cotă de rulare electrică, cost total de proprietate) includ, "
               "indiferent de selecție, toate ciclurile simulate; selecția de "
               "mai sus determină exclusiv capitolele cu reprezentări grafice "
               "individuale per ciclu.")
    if any(str(c).startswith("Real") for c in sel_cycles):
        st.caption("Notă metodologică: ciclurile reale cu traseu GPS "
                   "asociat includ identificarea străzilor parcurse printr-un "
                   "serviciu online (OpenStreetMap) — pentru trasee de lungime "
                   "considerabilă, această etapă poate dura până la un minut și "
                   "necesită conexiune activă la internet.")
    if st.button("Generează raportul PDF", type="primary", disabled=not sel_cycles):
        try:
            with st.spinner("Se generează raportul… (poate dura mai mult pentru "
                            "trasee GPS lungi, din cauza identificării străzilor)"):
                def _reduc(a, c):
                    base = results["baseline"][c].consumption_L_100km
                    if not base or base <= 0:
                        return 0.0
                    return round((base - results[a][c].consumption_L_100km) / base * 100, 1)
                rows_pdf = [{"Arhitectură": ARCH_LABELS[a], "Ciclu": c,
                             "Consum [L/100km]": results[a][c].consumption_L_100km,
                             "CO₂ [g/km]": results[a][c].co2_g_km,
                             "Cotă EV [%]": results[a][c].ev_share_pct,
                             "Reducere [%]": _reduc(a, c)}
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
                # Traseele GPS pentru ciclurile reale selectate (hartă în cap. 3)
                _all_tracks = {**load_bundled_tracks(),
                               **st.session_state.get("gps_tracks", {})}
                gps_pdf = {c: _all_tracks[c] for c in sel_cycles if c in _all_tracks}
                out = os.path.join(tempfile.gettempdir(), "raport_simulare_hev.pdf")
                generate_pdf_report(p_used, econ_used, rows_pdf, tco_pdf, checks_pdf,
                                    cmp_pdf, soc_pdf, STRATEGY_LABELS[strat_used], out,
                                    results=results, cycles=cycles, breakeven=be_pdf,
                                    sensitivity=sens_pdf,
                                    sens_arch_label=ARCH_LABELS["serie_paralel"],
                                    eea_audit=eea_audit,
                                    report_cycles=sel_cycles, main_cycle=main_cyc,
                                    gps_tracks=gps_pdf)
            with open(out, "rb") as f:
                import re as _re
                _now = datetime.now().strftime("%d-%m-%y_%H:%M")
                _veh = p_used.name if getattr(p_used, "name", "") else "vehicul"
                _veh = _re.sub(r"[^\w\-]+", "_", _veh).strip("_")
                _fname = f"Simulare_{_now}_{_veh}.pdf"
                st.download_button("Descarcă raportul PDF", f,
                                   file_name=_fname,
                                   mime="application/pdf", type="primary")
            st.success("Raport generat cu succes.")
        except Exception as e:
            st.error(
                "Generarea raportului PDF a eșuat. Cauze posibile: date lipsă "
                "pentru ciclurile selectate, un fișier/traseu importat cu format "
                "neașteptat, sau o problemă temporară la accesul la internet "
                "(dacă traseul include hartă geocodificată). Încercați din nou; "
                "dacă problema persistă, selectați mai puține cicluri sau "
                "reporniți simularea din bara laterală.")
            st.caption(f"Detaliu tehnic (pentru depanare): {type(e).__name__}: {e}")

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
st.caption("Aplicația utilizează un model de simulare cvasi-static de tip "
           "backward-forward și ciclul de conducere WLTC definit de UNECE "
           "GTR No. 15. Codul sursă este distribuit sub licența MIT. © 2026 "
           "A.M. Beldugan, Facultatea de Inginerie Mecanică Industrială și "
           "Maritimă, Universitatea Ovidius din Constanța.")
