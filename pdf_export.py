"""
vehicle_model.py — Modelul fizic al vehiculului hibrid
========================================================

Implementează modelul cvasi-static de tip backward-forward pentru simularea
consumului de combustibil al vehiculelor hibride electrice pe cicluri de
testare standardizate.

Modelul reproduce identic rezultatele din lucrarea de disertație:
"Analiza comparativă a configurațiilor de propulsie hibridă (serie, paralel,
serie-paralel) pentru un vehicul de clasă C-SUV"
Adrian Mircea Beldugan, FIMIM, Universitatea Ovidius din Constanța, 2026.

Modulul expune:
    - VehicleParams : structura parametrilor fizici ai vehiculului
    - SimulationResult : structura rezultatului unei simulări
    - road_load(), fuel_rate() : funcții fizice de bază
    - simulate() : simularea unui vehicul pe un ciclu

Licență: MIT
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional
import numpy as np
from numpy.typing import NDArray

# ======================================================================
#  Constante fizice
# ======================================================================
RHO_AIR: float = 1.20   # kg/m^3, densitatea aerului la 20°C, 1 atm
G: float = 9.81         # m/s^2, accelerația gravitațională
DELTA: float = 1.05     # factor de masă rotativă echivalentă (adim.)

Architecture = Literal["baseline", "serie", "paralel", "serie_paralel"]
EMSStrategy = Literal["rule_based", "ecms", "dp"]


# ======================================================================
#  Structuri de date
# ======================================================================
@dataclass
class VehicleParams:
    """
    Parametrii fizici ai autovehiculului.

    Valorile implicite corespund platformei Dacia Bigster Hybrid 155
    (calibrare din Capitolul 3 al lucrării).

    Attributes
    ----------
    name : str
        Denumirea vehiculului (folosită în rapoarte).
    mass_kg : float
        Masa proprie a vehiculului + 1 ocupant [kg].
    Cd : float
        Coeficient aerodinamic al drag-ului [adim.].
    Af : float
        Aria frontală a vehiculului [m^2].
    f_rr : float
        Coeficient de rezistență la rulare [adim.].
    r_wheel : float
        Raza dinamică a roții [m].
    eta_tr : float
        Randamentul mecanic al transmisiei [adim., 0..1].
    P_aux_W : float
        Puterea consumatorilor auxiliari (climatizare, iluminat) [W].

    P_ICE_max_kW : float
        Puterea maximă a motorului termic [kW].
    eta_th_peak : float
        Randamentul termic de vârf al motorului [adim., 0..1].
    P_loss_frac : float
        Fracția de pierderi mecanice interne relative la puterea max [adim.].
    P_ICE_min_kW : float
        Puterea minimă de funcționare a motorului termic [kW].
    P_ICE_opt_kW : float
        Puterea la punctul de eficiență optimă a motorului termic [kW].

    P_EM_max_kW : float
        Puterea maximă a mașinii electrice principale de tracțiune [kW].
    P_bat_max_kW : float
        Puterea maximă de descărcare/încărcare a bateriei [kW].
    bat_energy_kWh : float
        Capacitatea utilă a bateriei de tracțiune [kWh].
    eta_em : float
        Randamentul mașinii electrice [adim., 0..1].
    eta_inv : float
        Randamentul invertorului electric [adim., 0..1].
    eta_bat : float
        Randamentul bateriei [adim., 0..1].
    eta_regen : float
        Randamentul global al frânării regenerative [adim., 0..1].

    SoC_init : float
        Starea inițială de încărcare a bateriei [adim., 0..1].
    SoC_target : float
        Starea de încărcare țintă (charge-sustaining) [adim., 0..1].
    SoC_min : float
        Limita inferioară a stării de încărcare (protecție baterie) [adim.].
    SoC_max : float
        Limita superioară a stării de încărcare [adim.].

    is_phev : bool
        Dacă vehiculul este plug-in hybrid (baterie mare, încărcare rețea).
    AER_km : float
        Autonomia pur electrică (numai relevantă pentru PHEV) [km].

    fuel_LHV_MJ_kg : float
        Puterea calorică inferioară a combustibilului [MJ/kg].
    fuel_density_kg_L : float
        Densitatea combustibilului [kg/L].
    fuel_CO2_kg_L : float
        Factorul de emisie CO2 al combustibilului [kg CO2 / L].

    price_EUR : float
        Prețul de listă al vehiculului nou [EUR].
    residual_frac : float
        Fracția din preț ca valoare reziduală la 10 ani [adim., 0..1].
    """
    # Identificare
    name: str = "Bigster Hybrid 155"

    # Masă și aerodinamică
    mass_kg: float = 1494.0
    Cd: float = 0.32
    Af: float = 2.65
    # f_rr și P_aux sunt calibrate la CONDIȚIILE DE OMOLOGARE WLTP: coast-down
    # cu pneuri de clasă energetică superioară (f_rr ≈ 0,009) și consumatorii
    # auxiliari opriți pe durata testului (~300 W sarcină electrică de bord).
    # Pentru scenarii de conducere reală se recomandă f_rr ≈ 0,011 și ~500 W.
    f_rr: float = 0.009
    r_wheel: float = 0.336
    eta_tr: float = 0.95
    P_aux_W: float = 300.0

    # Motor termic
    P_ICE_max_kW: float = 80.0
    eta_th_peak: float = 0.41
    P_loss_frac: float = 0.06
    P_ICE_min_kW: float = 8.0
    P_ICE_opt_kW: float = 45.0

    # Mașină electrică / baterie
    P_EM_max_kW: float = 37.0
    P_bat_max_kW: float = 40.0
    bat_energy_kWh: float = 1.4
    eta_em: float = 0.93
    eta_inv: float = 0.97
    eta_bat: float = 0.96
    eta_regen: float = 0.70

    # Stare de încărcare (SoC)
    SoC_init: float = 0.55
    SoC_target: float = 0.55
    SoC_min: float = 0.40
    SoC_max: float = 0.70

    # PHEV
    is_phev: bool = False
    AER_km: float = 0.0

    # Combustibil
    fuel_LHV_MJ_kg: float = 43.5
    fuel_density_kg_L: float = 0.745
    fuel_CO2_kg_L: float = 2.31

    # Economic
    price_EUR: float = 28590.0
    residual_frac: float = 0.20


@dataclass
class SimulationResult:
    """
    Rezultatul complet al unei simulări (un vehicul, o arhitectură, un ciclu).

    Attributes
    ----------
    architecture : Architecture
        Arhitectura simulată.
    strategy : EMSStrategy
        Strategia de management energetic aplicată.
    cycle_name : str
        Numele ciclului (ex. "WLTC", "UDDS").
    consumption_L_100km : float
        Consum de combustibil corectat charge-sustaining [L/100 km].
    consumption_raw_L_100km : float
        Consum brut, fără corecție (dacă e diferit) [L/100 km].
    co2_g_km : float
        Emisii CO2 tank-to-wheel [g/km].
    distance_km : float
        Distanța parcursă în ciclu [km].
    duration_s : int
        Durata ciclului [s].
    SoC : NDArray[np.float64]
        Traiectoria SoC pe parcursul ciclului [adim., 0..1].
    P_engine_W : NDArray[np.float64]
        Puterea motorului termic pe parcursul ciclului [W].
    P_EM_W : NDArray[np.float64]
        Puterea mașinii electrice principale [W].
    P_bat_W : NDArray[np.float64]
        Puterea prin baterie (pozitiv = descărcare) [W].
    P_wheel_W : NDArray[np.float64]
        Puterea la roată [W].
    fuel_rate_g_s : NDArray[np.float64]
        Debitul instantaneu de combustibil [g/s].
    ev_share_pct : float
        Fracția distanței parcursă în regim pur electric [%].
    """
    architecture: Architecture
    strategy: EMSStrategy
    cycle_name: str
    consumption_L_100km: float
    consumption_raw_L_100km: float
    co2_g_km: float
    distance_km: float
    duration_s: int
    SoC: NDArray[np.float64] = field(repr=False)
    P_engine_W: NDArray[np.float64] = field(repr=False)
    P_EM_W: NDArray[np.float64] = field(repr=False)
    P_bat_W: NDArray[np.float64] = field(repr=False)
    P_wheel_W: NDArray[np.float64] = field(repr=False)
    fuel_rate_g_s: NDArray[np.float64] = field(repr=False)
    ev_share_pct: float = 0.0

    def summary(self) -> dict:
        """Returnează un dicționar cu valorile scalare (fără traiectorii)."""
        return dict(
            architecture=self.architecture,
            strategy=self.strategy,
            cycle_name=self.cycle_name,
            consumption_L_100km=round(self.consumption_L_100km, 3),
            co2_g_km=round(self.co2_g_km, 1),
            distance_km=round(self.distance_km, 2),
            duration_s=self.duration_s,
            ev_share_pct=round(self.ev_share_pct, 1),
        )


# ======================================================================
#  Funcții fizice
# ======================================================================
def road_load(v_ms: float, a_ms2: float, p: VehicleParams) -> tuple[float, float]:
    """
    Calculează puterea și forța la roată necesare pentru urmărirea ciclului.

    Model de dinamică longitudinală: rezistență la rulare + drag aerodinamic +
    forța de inerție. Folosit în modelarea backward-looking (de la roată
    spre sursă).

    Parameters
    ----------
    v_ms : float
        Viteza instantanee [m/s].
    a_ms2 : float
        Accelerația instantanee [m/s^2].
    p : VehicleParams
        Parametrii vehiculului.

    Returns
    -------
    P_wheel_W : float
        Puterea instantanee la roată [W] (pozitivă când vehiculul cere putere,
        negativă când vehiculul disipă / poate recupera energie).
    F_wheel_N : float
        Forța de tracțiune la roată [N].
    """
    F_rr = p.mass_kg * G * p.f_rr
    F_drag = 0.5 * RHO_AIR * p.Cd * p.Af * v_ms ** 2
    F_acc = p.mass_kg * DELTA * a_ms2
    F = F_rr + F_drag + F_acc
    return F * v_ms, F


def fuel_rate(P_eng_W: float, p: VehicleParams) -> float:
    """
    Calculează debitul de combustibil pe baza modelului liniei Willans.

    Modelul: consumul e liniar în raport cu puterea (P_fuel = a + b·P_eng),
    unde `a` reprezintă pierderile constante (frecare, ralanti) și `b` este
    inversul randamentului termic. Este modelul standard folosit în lucrare.

    Parameters
    ----------
    P_eng_W : float
        Puterea cerută la arborele motorului termic [W].
    p : VehicleParams
        Parametrii vehiculului.

    Returns
    -------
    m_dot_g_s : float
        Debitul instantaneu de combustibil [g/s]. Returnează 0 pentru
        P_eng <= 0 (motor oprit sau în regim inactiv).
    """
    if P_eng_W <= 0:
        return 0.0
    P_max_W = p.P_ICE_max_kW * 1000.0
    P_loss0 = p.P_loss_frac * P_max_W
    P_fuel = (P_eng_W + P_loss0) / p.eta_th_peak
    P_fuel = min(P_fuel, P_max_W / p.eta_th_peak * 1.5)
    return P_fuel / (p.fuel_LHV_MJ_kg * 1e6) * 1000.0


def bsfc_map(P_eng_W: float, p: VehicleParams) -> float:
    """
    Estimează consumul specific efectiv de combustibil (BSFC) [g/kWh].

    Formulă: BSFC = m_dot [g/s] / P_eng [kW] * 3600. Returnează 0 la P=0.

    Parameters
    ----------
    P_eng_W : float
        Puterea motorului [W].
    p : VehicleParams
        Parametrii vehiculului.

    Returns
    -------
    bsfc_g_kWh : float
        BSFC [g/kWh].
    """
    if P_eng_W <= 100:
        return 0.0
    m_dot_g_s = fuel_rate(P_eng_W, p)
    P_kW = P_eng_W / 1000.0
    return m_dot_g_s / P_kW * 3600.0
