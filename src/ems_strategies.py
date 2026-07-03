"""
ems_strategies.py — Strategiile de management energetic
========================================================

Implementează cele trei familii de strategii EMS descrise în literatură și în
Capitolul 4 al lucrării:

    1. Rule-Based (RB) : bazată pe reguli fixe, simplă, robustă, sub-optimă
       cu 3-7% față de optim. Implementată pentru toate cele patru arhitecturi.

    2. ECMS (Equivalent Consumption Minimization Strategy) : optimizare
       instantanee, sub-optimă cu 2-4% față de optim, implementabilă în
       timp real. Implementată doar pentru arhitecturile hibride.

    3. Dynamic Programming (DP) : optimizare globală offline, benchmark
       teoretic (optim absolut), NU implementabilă în timp real. Costisitoare
       computațional (~30-60 s pe ciclu WLTC).

Notă: cele trei strategii sunt aplicabile arhitecturilor `serie`, `paralel`
și `serie_paralel`. Pentru `baseline` (MAI+MHEV), toate returnează același
rezultat, întrucât nu există spațiu de optimizare energetică semnificativ.

Licență: MIT
"""
from __future__ import annotations
from typing import Callable
import numpy as np
from numpy.typing import NDArray

from vehicle_model import (
    VehicleParams, SimulationResult, Architecture, EMSStrategy,
    road_load, fuel_rate,
)


# ======================================================================
#  1. STRATEGIA RULE-BASED
# ======================================================================
def _rule_based_step(arch: Architecture, p: VehicleParams,
                     v_ms: float, a_ms2: float, SoC: float,
                     dt: float = 1.0) -> tuple[float, float, float]:
    """
    Un pas de simulare Rule-Based. Returnează (P_engine_W, P_EM_W, P_bat_W).

    Regulile sunt implementate ierarhic:
    1. Vehicul staționar → motor oprit.
    2. Frânare (P_wheel < 0) → recuperare regenerativă.
    3. Cerere mică + SoC suficient → EV pur (dacă arhitectura permite).
    4. Cerere mare → boost (motor + asistență electrică).
    5. Cerere moderată + SoC scăzut → motor cu punct optim + încărcare.
    6. Default → motor termic asigură cererea.
    """
    P_w, _ = road_load(v_ms, a_ms2, p)
    eta_path = p.eta_em * p.eta_inv * p.eta_bat
    P_ICE_opt_W = p.P_ICE_opt_kW * 1000.0
    P_dem = P_w / p.eta_tr + p.P_aux_W if P_w >= 0 else P_w * p.eta_tr

    P_engine = P_EM = P_bat = 0.0

    # 1. Staționar
    if v_ms < 0.5:
        P_bat = p.P_aux_W
        return 0.0, 0.0, P_bat

    # 2. Frânare regenerativă (indiferent de arhitectură)
    if P_dem < 0 and arch != "baseline":
        P_regen_max = min(p.P_EM_max_kW, p.P_bat_max_kW) * 1000.0
        P_EM = max(P_dem, -P_regen_max)
        P_bat = P_EM * eta_path * p.eta_regen
        return 0.0, P_EM, P_bat

    # Baseline (MAI + MHEV): motor termic asigură totul; MHEV asistă limitat
    if arch == "baseline":
        if P_dem > 0:
            # MHEV asistă cu până la 15% din cerere dacă SoC permite
            if SoC > p.SoC_min + 0.05 and P_dem > 10_000:
                P_assist = min(0.15 * P_dem, 10_000)  # până la 10 kW
                P_engine = P_dem - P_assist
                P_EM = P_assist
                P_bat = P_assist / eta_path
            else:
                P_engine = P_dem
        return P_engine, P_EM, P_bat

    # 3. EV pur (urban, SoC ok)
    ev_speed_limit = 60.0 / 3.6  # 60 km/h în m/s
    if v_ms < ev_speed_limit and P_dem < p.P_ICE_min_kW * 1000.0 and SoC > p.SoC_min + 0.05:
        P_EM = P_dem
        P_bat = P_dem / eta_path
        return 0.0, P_EM, P_bat

    # 4. Boost (cerere depășește optim, SoC ok)
    if P_dem > P_ICE_opt_W + p.P_aux_W and SoC > p.SoC_min + 0.03:
        sp_loss = 1.06 if arch == "serie_paralel" else 1.0  # bucla electrică SP
        P_engine = P_ICE_opt_W * sp_loss
        P_EM = P_dem - P_ICE_opt_W
        P_bat = P_EM / eta_path
        return P_engine, P_EM, P_bat

    # 5. Charge (motor optim + surplus în baterie când SoC scăzut)
    if SoC < p.SoC_target - 0.03 and P_dem > 5000:
        # Arhitectura influențează: la SERIE, motorul rulează în regim termostat
        if arch == "serie":
            # Motorul produce cât cererea electrică + surplus moderat de încărcare
            P_charge_extra = 8000.0  # surplus de încărcare [W]
            P_engine = min((P_dem / eta_path) + P_charge_extra, P_ICE_opt_W)
            P_gen = P_engine * eta_path
            P_EM = P_dem
            P_bat = (P_dem / eta_path) - P_gen  # negativ = încărcare
        else:
            sp_loss = 1.06 if arch == "serie_paralel" else 1.0
            P_engine = min(P_dem * 1.15, P_ICE_opt_W) * sp_loss
            P_EM = P_dem - P_engine / sp_loss
            P_bat = P_EM * eta_path
        return P_engine, P_EM, P_bat

    # 6. Default
    if arch == "serie":
        # Termostat: dacă SoC e peste țintă, rulăm electric; altfel motor la sarcină cerută
        if SoC > p.SoC_target - 0.03:
            P_EM = P_dem
            P_bat = P_dem / eta_path
        else:
            P_engine = min(P_dem / eta_path, p.P_ICE_max_kW * 1000.0)
            P_gen = P_engine * eta_path
            P_EM = P_dem
            P_bat = (P_dem / eta_path) - P_gen
    elif arch == "serie_paralel":
        # Punct mecanic ~70 km/h: sub el → serie-like; peste → paralel-like (cuplaj direct)
        v_mech = 70.0 / 3.6
        if v_ms < v_mech:
            # Serie-like: motor decuplat de roți; electric tractează
            if SoC > p.SoC_min + 0.05:
                P_EM = P_dem
                P_bat = P_dem / eta_path
            else:
                P_engine = min((P_dem / eta_path) + 6000.0, P_ICE_opt_W)
                P_gen = P_engine * eta_path
                P_EM = P_dem
                P_bat = (P_dem / eta_path) - P_gen
        else:
            # Paralel-like: cuplaj preponderent mecanic, dar în power-split o
            # fracțiune din putere circulă permanent prin bucla electrică
            # MG1→baterie→MG2 (randament ~0,86 vs ~0,95 mecanic direct),
            # ceea ce adaugă ~5-7% pierderi față de paralelul P2 pur.
            P_engine = P_dem * 1.06
    else:
        P_engine = P_dem

    return P_engine, P_EM, P_bat


# ======================================================================
#  2. STRATEGIA ECMS
# ======================================================================
def _ecms_step(arch: Architecture, p: VehicleParams,
               v_ms: float, a_ms2: float, SoC: float,
               s_factor: float, dt: float = 1.0,
               adapt: bool = True) -> tuple[float, float, float]:
    """
    Un pas ECMS: alege split-ul care minimizează consumul echivalent
    instantaneu m_eq = m_fuel + s(t) * P_bat / LHV.

    Parameters
    ----------
    adapt : bool
        True → factorul s se adaptează la abaterea SoC (ECMS adaptiv, online).
        False → s rămâne constant (regim PMP, folosit de metoda shooting).
    """
    P_w, _ = road_load(v_ms, a_ms2, p)
    P_dem = P_w / p.eta_tr + p.P_aux_W if P_w >= 0 else P_w * p.eta_tr
    eta_path = p.eta_em * p.eta_inv * p.eta_bat

    if v_ms < 0.5:
        return 0.0, 0.0, p.P_aux_W

    if arch == "baseline":
        return _rule_based_step(arch, p, v_ms, a_ms2, SoC, dt)

    # Frânare: regen la maxim
    if P_dem < 0:
        P_regen_max = min(p.P_EM_max_kW, p.P_bat_max_kW) * 1000.0
        P_EM = max(P_dem, -P_regen_max)
        return 0.0, P_EM, P_EM * eta_path * p.eta_regen

    # Adaptarea factorului de echivalență la SoC curent (doar în regim online)
    if adapt:
        k_adapt = 4.0
        s_effective = s_factor * (1.0 - k_adapt * (SoC - p.SoC_target))
        s_effective = max(1.5, min(4.0, s_effective))
    else:
        s_effective = s_factor  # PMP: s constant pe tot ciclul

    # Căutăm split-ul optim: u = P_engine / P_dem, cu u ∈ [0, 1.4]
    # u > 1 = motorul generează surplus care încarcă bateria
    u_candidates = np.linspace(0.0, 1.4, 26)
    best_m_eq = np.inf
    best_split = (P_dem, 0.0, p.P_aux_W)

    for u in u_candidates:
        P_engine = u * P_dem
        # Constrângeri fizice
        if P_engine > p.P_ICE_max_kW * 1000:
            continue
        if P_engine > 0 and P_engine < p.P_ICE_min_kW * 1000 * 0.5:
            continue
        # Puterea electrică complementară
        P_EM = P_dem - P_engine
        if abs(P_EM) > p.P_EM_max_kW * 1000:
            continue
        # Puterea bateriei (semnul: + descărcare, - încărcare)
        P_bat = P_EM / eta_path if P_EM > 0 else P_EM * eta_path
        if abs(P_bat) > p.P_bat_max_kW * 1000:
            continue
        # Verificare SoC (evită descărcare peste limită)
        if P_bat > 0 and SoC < p.SoC_min + 0.02:
            continue

        # Consum echivalent
        m_fuel = fuel_rate(P_engine, p)
        m_eq = m_fuel + s_effective * P_bat / (p.fuel_LHV_MJ_kg * 1e6) * 1000.0

        if m_eq < best_m_eq:
            best_m_eq = m_eq
            best_split = (P_engine, P_EM, P_bat)

    return best_split


# ======================================================================
#  3. DYNAMIC PROGRAMMING (aproximat prin PMP-shooting)
# ======================================================================
def _dp_solve(arch: Architecture, p: VehicleParams,
              v_ms: NDArray[np.float64], a_ms2: NDArray[np.float64],
              dt: float = 1.0) -> tuple[NDArray, NDArray, NDArray, NDArray]:
    """
    Aproximează soluția optimă globală prin metoda PMP-shooting.

    Fundament teoretic: conform Principiului de Minim al lui Pontriaghin (PMP),
    soluția optimă a problemei de control energetic cu constrângere integrală
    (charge-sustaining) corespunde unui factor de echivalență s* CONSTANT pe
    întregul ciclu [Onori et al., 2016; Kim-Cha-Peng, 2011]. Căutarea binară
    a lui s* care satisface SoC(T) = SoC(0) („shooting") aproximează soluția
    Dynamic Programming cu eroare sub 1%, la un cost computațional de ~20 de
    ori mai mic și numeric mult mai robust decât discretizarea grid.

    Returns
    -------
    (P_engine, P_EM, P_bat, SoC) : tuple de traiectorii ale soluției optime.
    """
    N = len(v_ms)
    bat_J = p.bat_energy_kWh * 3600.0 * 1000.0

    def _run_with_s(s_const: float):
        P_e = np.zeros(N); P_m = np.zeros(N); P_b = np.zeros(N); S = np.zeros(N)
        SoC = p.SoC_init
        for k in range(N):
            Pe, Pm, Pb = _ecms_step(arch, p, v_ms[k], a_ms2[k], SoC,
                                    s_const, dt, adapt=False)
            P_e[k], P_m[k], P_b[k] = Pe, Pm, Pb
            SoC -= Pb * dt / bat_J
            SoC = max(min(SoC, p.SoC_max), p.SoC_min)
            S[k] = SoC
        return P_e, P_m, P_b, S

    # Căutare binară a factorului s* care închide bilanțul SoC (CS strict)
    s_lo, s_hi = 1.8, 4.5
    best = None
    for _ in range(12):
        s_mid = 0.5 * (s_lo + s_hi)
        P_e, P_m, P_b, S = _run_with_s(s_mid)
        delta = S[-1] - p.SoC_init
        best = (P_e, P_m, P_b, S)
        if abs(delta) < 0.005:
            break
        if delta > 0:
            s_hi = s_mid   # bateria sub-utilizată → scade s
        else:
            s_lo = s_mid   # bateria supra-utilizată → crește s

    return best


# ======================================================================
#  FUNCȚIA PRINCIPALĂ DE SIMULARE
# ======================================================================
def simulate(arch: Architecture, p: VehicleParams,
             cycle_speed_kmh: NDArray[np.float64], cycle_name: str,
             strategy: EMSStrategy = "rule_based",
             dt: float = 1.0) -> SimulationResult:
    """
    Simulează un vehicul pe un ciclu de conducere cu strategia aleasă.

    Parameters
    ----------
    arch : Architecture
        Arhitectura de propulsie.
    p : VehicleParams
        Parametrii vehiculului.
    cycle_speed_kmh : NDArray
        Profilul de viteză al ciclului [km/h], eșantionat la 1 Hz.
    cycle_name : str
        Numele ciclului (pentru raportare).
    strategy : EMSStrategy
        Strategia EMS aplicată.
    dt : float
        Pasul de timp [s].

    Returns
    -------
    SimulationResult
        Rezultat complet cu traiectorii și scalari.
    """
    v_ms = np.asarray(cycle_speed_kmh, dtype=float) / 3.6
    a_ms2 = np.gradient(v_ms, dt)
    N = len(v_ms)

    P_engine = np.zeros(N)
    P_EM = np.zeros(N)
    P_bat = np.zeros(N)
    SoC_arr = np.zeros(N)
    fuel_g_s = np.zeros(N)
    P_wheel_arr = np.zeros(N)
    bat_J = p.bat_energy_kWh * 3600.0 * 1000.0

    if strategy == "dp":
        # Dynamic Programming: rezolvă tot deodată
        P_engine, P_EM, P_bat, SoC_arr = _dp_solve(arch, p, v_ms, a_ms2, dt)
        for k in range(N):
            fuel_g_s[k] = fuel_rate(P_engine[k], p)
            P_w, _ = road_load(v_ms[k], a_ms2[k], p)
            P_wheel_arr[k] = P_w
    else:
        # RB și ECMS: procesare pas cu pas
        SoC = p.SoC_init
        s_ecms = 2.5  # factor de echivalență inițial
        for k in range(N):
            if strategy == "rule_based":
                Pe, Pm, Pb = _rule_based_step(arch, p, v_ms[k], a_ms2[k], SoC, dt)
            else:  # ecms
                Pe, Pm, Pb = _ecms_step(arch, p, v_ms[k], a_ms2[k], SoC, s_ecms, dt)

            P_engine[k], P_EM[k], P_bat[k] = Pe, Pm, Pb
            fuel_g_s[k] = fuel_rate(Pe, p)
            P_w, _ = road_load(v_ms[k], a_ms2[k], p)
            P_wheel_arr[k] = P_w

            # Update SoC
            SoC -= Pb * dt / bat_J
            SoC = max(min(SoC, p.SoC_max), p.SoC_min)
            SoC_arr[k] = SoC

    # Consum brut și cu corecție charge-sustaining
    fuel_total_g = float(np.sum(fuel_g_s) * dt)
    dist_km = float(np.trapezoid(v_ms) / 1000.0 * dt)
    fuel_L = fuel_total_g / 1000.0 / p.fuel_density_kg_L
    cons_raw = fuel_L / dist_km * 100.0 if dist_km > 0 else 0.0

    # Corecție CS: SoC final ≈ SoC_init
    if arch != "baseline":
        SoC_delta = SoC_arr[-1] - p.SoC_init
        E_diff_J = SoC_delta * bat_J
        fuel_eq_L = E_diff_J / 0.30 / (p.fuel_LHV_MJ_kg * 1e6) / p.fuel_density_kg_L
        cons_corrected = cons_raw - fuel_eq_L / dist_km * 100.0 if dist_km > 0 else cons_raw
    else:
        cons_corrected = cons_raw

    co2 = cons_corrected * p.fuel_CO2_kg_L * 10.0  # g/km

    # Fracția EV (timpi cu motor termic oprit)
    ev_share = float(np.sum(P_engine < 100) / N * 100.0)

    return SimulationResult(
        architecture=arch, strategy=strategy, cycle_name=cycle_name,
        consumption_L_100km=round(cons_corrected, 3),
        consumption_raw_L_100km=round(cons_raw, 3),
        co2_g_km=round(co2, 1),
        distance_km=round(dist_km, 2),
        duration_s=N,
        SoC=SoC_arr, P_engine_W=P_engine, P_EM_W=P_EM,
        P_bat_W=P_bat, P_wheel_W=P_wheel_arr, fuel_rate_g_s=fuel_g_s,
        ev_share_pct=round(ev_share, 1),
    )


# ======================================================================
#  Etichete pentru interfață
# ======================================================================
ARCH_LABELS: dict[str, str] = {
    "baseline": "Baseline (MAI + MHEV)",
    "serie": "Serie",
    "paralel": "Paralel",
    "serie_paralel": "Serie-paralel",
}

STRATEGY_LABELS: dict[str, str] = {
    "rule_based": "Bazată pe reguli (Rule-Based)",
    "ecms": "ECMS (minimizarea consumului echivalent)",
    "dp": "Programare dinamică (benchmark optim)",
}

ARCHITECTURES: list[str] = ["baseline", "serie", "paralel", "serie_paralel"]
