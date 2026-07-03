"""
analysis.py — Analiza de sensibilitate și validarea fizică
===========================================================

- sensitivity_analysis() : variază fiecare parametru cu ±20% și măsoară
  efectul asupra consumului și TCO (analiză completă, toți parametrii).
- physical_validation() : verifică respectarea limitelor fizice într-o
  simulare (SoC, puteri, bilanț energetic).

Licență: MIT
"""
from __future__ import annotations
from dataclasses import replace
from typing import Callable
import numpy as np

from vehicle_model import VehicleParams, SimulationResult
from ems_strategies import simulate
from tco_model import EconomicParams, compute_tco


# Parametrii fizici analizați în sensibilitate (nume atribut, etichetă UI)
SENS_VEHICLE_PARAMS: list[tuple[str, str]] = [
    ("mass_kg", "Masă vehicul"),
    ("Cd", "Coeficient aerodinamic Cd"),
    ("Af", "Arie frontală"),
    ("f_rr", "Rezistență la rulare"),
    ("eta_th_peak", "Randament termic motor"),
    ("P_EM_max_kW", "Putere mașină electrică"),
    ("bat_energy_kWh", "Capacitate baterie"),
    ("eta_tr", "Randament transmisie"),
]

SENS_ECON_PARAMS: list[tuple[str, str]] = [
    ("fuel_price_EUR_L", "Preț combustibil"),
    ("km_per_year", "Kilometraj anual"),
    ("elec_price_EUR_kWh", "Preț electricitate"),
    ("maintenance_EUR_year_HEV", "Mentenanță anuală"),
]


def sensitivity_analysis(arch: str, p: VehicleParams, econ: EconomicParams,
                         cycle_kmh: np.ndarray, cycle_name: str = "WLTC",
                         variation: float = 0.20,
                         progress_cb: Callable[[float], None] | None = None) -> dict:
    """
    Analiză de sensibilitate completă: fiecare parametru variat ±variation.

    Returns
    -------
    dict cu chei:
        'consumption' : list[dict(label, low, high)] — efect pe consum
        'tco'         : list[dict(label, low, high)] — efect pe TCO
        'base_consumption', 'base_tco' : valorile de referință
    """
    r_base = simulate(arch, p, cycle_kmh, cycle_name, strategy="rule_based")
    base_cons = r_base.consumption_L_100km
    tco_base = compute_tco(p.price_EUR, base_cons, p.residual_frac, econ,
                           is_hev=(arch != "baseline"))["tco_total"]

    cons_effects, tco_effects = [], []
    total = len(SENS_VEHICLE_PARAMS) + len(SENS_ECON_PARAMS)
    done = 0

    # Parametrii vehiculului: efect pe consum ȘI pe TCO
    for attr, label in SENS_VEHICLE_PARAMS:
        vals = {}
        for sign, mult in [("low", 1 - variation), ("high", 1 + variation)]:
            p_mod = replace(p, **{attr: getattr(p, attr) * mult})
            r = simulate(arch, p_mod, cycle_kmh, cycle_name, strategy="rule_based")
            vals[sign] = r.consumption_L_100km
        cons_effects.append(dict(label=label, low=vals["low"], high=vals["high"]))
        tco_effects.append(dict(
            label=label,
            low=compute_tco(p.price_EUR, vals["low"], p.residual_frac, econ,
                            is_hev=(arch != "baseline"))["tco_total"],
            high=compute_tco(p.price_EUR, vals["high"], p.residual_frac, econ,
                             is_hev=(arch != "baseline"))["tco_total"],
        ))
        done += 1
        if progress_cb:
            progress_cb(done / total)

    # Parametrii economici: efect doar pe TCO (consumul e fix)
    for attr, label in SENS_ECON_PARAMS:
        vals = {}
        for sign, mult in [("low", 1 - variation), ("high", 1 + variation)]:
            e_mod = replace(econ, **{attr: getattr(econ, attr) * mult})
            vals[sign] = compute_tco(p.price_EUR, base_cons, p.residual_frac,
                                     e_mod, is_hev=(arch != "baseline"))["tco_total"]
        tco_effects.append(dict(label=label, low=vals["low"], high=vals["high"]))
        done += 1
        if progress_cb:
            progress_cb(done / total)

    return dict(consumption=cons_effects, tco=tco_effects,
                base_consumption=base_cons, base_tco=tco_base)


def physical_validation(r: SimulationResult, p: VehicleParams) -> list[dict]:
    """
    Verifică respectarea limitelor fizice într-o simulare.

    Returns
    -------
    list[dict(check, status, detail)] — o listă de verificări PASS/FAIL.
    """
    checks = []

    def _add(name: str, ok: bool, detail: str):
        checks.append(dict(check=name, status="PASS" if ok else "FAIL", detail=detail))

    # 1. SoC în limite
    soc_ok = (r.SoC.min() >= p.SoC_min - 1e-6) and (r.SoC.max() <= p.SoC_max + 1e-6)
    _add("SoC în intervalul de protecție",
         soc_ok, f"min={r.SoC.min()*100:.1f}%, max={r.SoC.max()*100:.1f}% "
                 f"(limite: {p.SoC_min*100:.0f}–{p.SoC_max*100:.0f}%)")

    # 2. Puterea motorului termic ≤ maxim
    pe_max = r.P_engine_W.max() / 1000
    _add("Putere motor termic ≤ maxim",
         pe_max <= p.P_ICE_max_kW * 1.001,
         f"vârf={pe_max:.1f} kW (max: {p.P_ICE_max_kW:.0f} kW)")

    # 3. Puterea mașinii electrice ≤ maxim
    pem_max = np.abs(r.P_EM_W).max() / 1000
    _add("Putere mașină electrică ≤ maxim",
         pem_max <= p.P_EM_max_kW * 1.001,
         f"vârf={pem_max:.1f} kW (max: {p.P_EM_max_kW:.0f} kW)")

    # 4. Puterea bateriei ≤ maxim
    pb_max = np.abs(r.P_bat_W).max() / 1000
    _add("Putere baterie ≤ maxim",
         pb_max <= p.P_bat_max_kW * 1.05,
         f"vârf={pb_max:.1f} kW (max: {p.P_bat_max_kW:.0f} kW)")

    # 5. Neutralitate energetică (charge-sustaining)
    dSoC = abs(r.SoC[-1] - p.SoC_init)
    _add("Neutralitate energetică (|ΔSoC| < 10%)",
         dSoC < 0.10,
         f"SoC inițial={p.SoC_init*100:.0f}%, final={r.SoC[-1]*100:.1f}% (Δ={dSoC*100:.1f} p.p.)")

    # 6. Consum plauzibil
    _add("Consum în interval plauzibil (2–15 L/100km)",
         2.0 <= r.consumption_L_100km <= 15.0,
         f"consum={r.consumption_L_100km:.2f} L/100km")

    # 7. Consum nenegativ instantaneu
    _add("Debit de combustibil nenegativ",
         bool((r.fuel_rate_g_s >= 0).all()),
         f"min={r.fuel_rate_g_s.min():.4f} g/s")

    return checks
