"""
tco_model.py — Model TCO și comparație cu surse WLTP
=====================================================

Implementează:
    - EconomicParams : structura parametrilor economici
    - compute_tco() : calculul TCO pe orizont configurabil
    - compute_breakeven() : punctul de break-even vs baseline
    - load_wltp_references() / compare_with_sources() : validare externă

Licență: MIT
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import json
import os


@dataclass
class EconomicParams:
    """
    Parametrii economici pentru calculul TCO (calibrare piața românească).

    Attributes
    ----------
    years : int
        Orizontul de analiză [ani].
    km_per_year : float
        Kilometrajul anual mediu [km/an].
    fuel_price_EUR_L : float
        Prețul de listă al benzinei [EUR/L].
    elec_price_EUR_kWh : float
        Prețul electricității casnice [EUR/kWh].
    maintenance_EUR_year_ICE : float
        Mentenanța anuală pentru vehicule ICE [EUR/an].
    maintenance_EUR_year_HEV : float
        Mentenanța anuală pentru vehicule HEV [EUR/an].
    insurance_tax_EUR_year : float
        Asigurare + taxe anuale [EUR/an].
    rabla_plus_EUR : float
        Subvenție Rabla Plus [EUR] (0 dacă nu se aplică).
    """
    years: int = 10
    km_per_year: float = 15000.0
    fuel_price_EUR_L: float = 1.83
    elec_price_EUR_kWh: float = 0.28
    maintenance_EUR_year_ICE: float = 850.0
    maintenance_EUR_year_HEV: float = 700.0
    insurance_tax_EUR_year: float = 260.0
    rabla_plus_EUR: float = 0.0


def compute_tco(price_EUR: float, consumption_L_100km: float,
                residual_frac: float, econ: EconomicParams,
                is_hev: bool = True,
                elec_kWh_100km: float = 0.0) -> dict:
    """
    Calculează Costul Total de Proprietate pe orizontul dat.

    Formula: TCO = achiziție − reziduală + energie + mentenanță + asigurare − subvenție.

    Parameters
    ----------
    price_EUR : float
        Prețul de listă al vehiculului nou.
    consumption_L_100km : float
        Consumul mediu de combustibil pe orizont.
    residual_frac : float
        Fracția de valoare reziduală (ex. 0.20 = 20%).
    econ : EconomicParams
        Parametrii economici.
    is_hev : bool
        True pentru vehicule hibride (mentenanță mai mică).
    elec_kWh_100km : float
        Consumul mediu de electricitate din rețea (pentru PHEV).

    Returns
    -------
    dict cu defalcarea completă TCO.
    """
    total_km = econ.km_per_year * econ.years
    fuel_L = consumption_L_100km / 100.0 * total_km
    cost_fuel = fuel_L * econ.fuel_price_EUR_L
    cost_elec = elec_kWh_100km / 100.0 * total_km * econ.elec_price_EUR_kWh
    cost_energy = cost_fuel + cost_elec
    maint = (econ.maintenance_EUR_year_HEV if is_hev
             else econ.maintenance_EUR_year_ICE) * econ.years
    insurance = econ.insurance_tax_EUR_year * econ.years
    residual = price_EUR * residual_frac
    subsidy = econ.rabla_plus_EUR
    tco = price_EUR - residual + cost_energy + maint + insurance - subsidy
    return dict(
        price=round(price_EUR),
        residual=round(residual),
        cost_fuel=round(cost_fuel),
        cost_elec=round(cost_elec),
        cost_energy=round(cost_energy),
        maintenance=round(maint),
        insurance=round(insurance),
        subsidy=round(subsidy),
        tco_total=round(tco),
        total_km=int(total_km),
    )


def compute_breakeven(price_baseline: float, price_hev: float,
                      cons_baseline: float, cons_hev: float,
                      econ: EconomicParams) -> dict:
    """
    Calculează punctul de break-even (recuperarea costului suplimentar).

    Break-even = anii/km necesari pentru ca economia de combustibil să
    compenseze diferența de preț de achiziție.
    """
    extra_cost = price_hev - price_baseline
    fuel_saved_L_per_km = (cons_baseline - cons_hev) / 100.0
    annual_saving = fuel_saved_L_per_km * econ.km_per_year * econ.fuel_price_EUR_L
    if annual_saving <= 0:
        return dict(extra_cost=round(extra_cost), annual_saving=round(annual_saving, 1),
                    years=None, km=None, note="Fără economie netă — break-even inexistent")
    years = extra_cost / annual_saving
    return dict(
        extra_cost=round(extra_cost),
        annual_saving=round(annual_saving, 1),
        years=round(years, 1),
        km=round(years * econ.km_per_year),
    )


def load_wltp_references(path: Optional[str] = None) -> dict:
    """Încarcă valorile WLTP oficiale din fișierul JSON citat."""
    candidates: list[str] = []
    if path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates = [os.path.join(here, "..", "data", "wltp_references.json"),
                     os.path.join(here, "data", "wltp_references.json"),
                     "wltp_references.json"]
        for cand in candidates:
            if os.path.exists(cand):
                path = cand
                break
        else:
            raise FileNotFoundError(
                "Fișierul de referință 'wltp_references.json' (valorile "
                "WLTP oficiale folosite pentru comparație) nu a fost găsit. "
                "Căile verificate au fost:\n  - " + "\n  - ".join(candidates) +
                "\nVerificați instalarea aplicației — fișierul trebuie să "
                "existe în folderul 'data/'.")
    elif not os.path.exists(path):
        raise FileNotFoundError(
            f"Fișierul de referință indicat nu există: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compare_with_sources(simulated_L_100km: float,
                         architecture: str,
                         refs: Optional[dict] = None,
                         min_sources: int = 3) -> dict:
    """Compară consumul simulat cu valorile WLTP oficiale din surse externe."""
    if refs is None:
        refs = load_wltp_references()
    matches = [v for v in refs["vehicles"]
               if v["architecture"] == architecture or architecture == "any"]
    if len(matches) < min_sources and architecture != "baseline":
        extra = [v for v in refs["vehicles"]
                 if v["architecture"] != "baseline" and v not in matches]
        matches += extra
    comparisons = []
    for v in matches:
        official = v["consumption_wltp_L_100km"]
        deviation = (simulated_L_100km - official) / official * 100.0
        comparisons.append(dict(
            name=v["name"], official_L_100km=official,
            deviation_pct=round(deviation, 1),
            source=v["source"], accessed=v["accessed"],
        ))
    n = len(comparisons)
    avg_official = sum(c["official_L_100km"] for c in comparisons) / n if n else None
    avg_dev = sum(c["deviation_pct"] for c in comparisons) / n if n else None
    return dict(
        simulated_L_100km=round(simulated_L_100km, 2),
        n_sources=n,
        sufficient=n >= min_sources,
        comparisons=comparisons,
        avg_official_L_100km=round(avg_official, 2) if avg_official else None,
        avg_deviation_pct=round(avg_dev, 1) if avg_dev else None,
    )
