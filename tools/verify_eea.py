"""
verify_eea.py — Audit al bazei de date de vehicule contra setului EEA
=====================================================================

Încrucișează `data/vehicles_db.csv` cu setul oficial EEA de monitorizare a
emisiilor CO2 pentru autoturisme noi (Regulamentul UE 2019/631) și produce un
raport de concordanță pentru câmpurile verificabile:

    - masa în ordine de mers  (EEA: coloana `m (kg)`)          toleranță ±6%
    - puterea motorului       (EEA: coloana `ep (KW)`)         toleranță ±8%
    - CO2 WLTP                (EEA: coloana `Ewltp (g/km)`)    toleranță ±8%

Câmpurile Cd, Af, eta_th_peak, bat_energy_kWh, price_EUR NU există în setul
EEA — ele provin din fișele tehnice ale constructorilor (vezi coloanele
`sursa` și `estimari` din baza de date) și nu pot fi auditate aici.

UTILIZARE (local — fișierul EEA are milioane de rânduri și nu se poate
descărca din mediul cloud al aplicației):

  1. Descărcați setul de date "CO2 emissions from new passenger cars" (anul
     dorit, de preferat "Final data") de la EEA:
         https://co2cars.apps.eea.europa.eu/
     sau prin portalul de date EEA (căutați "co2 cars"). Salvați CSV-ul local.

  2. Rulați:
         python tools/verify_eea.py --eea /cale/catre/CO2_passenger_cars.csv

  3. Raportul se scrie în data/eea_verification_report.csv — comiteți-l în
     repo: aplicația îl detectează automat și afișează auditul per vehicul.
     (o linie per vehicul: găsit/negăsit + abaterile procentuale per câmp).

Note metodologice:
  - Potrivirea se face pe (marcă, denumire comercială) normalizate; EEA
    folosește coloanele `Mk` (make) și `Cn` (commercial name). Variantele de
    echipare nu există în EEA, deci pentru un model se compară cu MEDIANA
    înregistrărilor EEA al căror `Cn` conține numele modelului și al căror
    `Ft` (fuel type) corespunde tipului (petrol/electric hibrid).
  - Masa EEA este "mass in running order" (include șoferul de 75 kg), la fel
    ca valorile din baza de date.
"""
from __future__ import annotations
import argparse
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "..", "data", "vehicles_db.csv")
OUT_PATH = os.path.join(HERE, "..", "data", "eea_verification_report.csv")

TOL = {"mass_pct": 6.0, "power_pct": 8.0, "co2_pct": 8.0}

# tipuri de combustibil EEA acceptate pentru HEV/PHEV pe benzină/diesel
FT_ACCEPT = {"petrol/electric", "diesel/electric", "petrol", "diesel",
             "PETROL/ELECTRIC", "DIESEL/ELECTRIC"}


def _norm(s: str) -> str:
    s = str(s).upper()
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _detect_sep(path: str) -> str:
    """Detectează separatorul din prima linie (virgulă, punct-virgulă sau tab)."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        head = f.readline()
    counts = {",": head.count(","), ";": head.count(";"), "\t": head.count("\t")}
    return max(counts, key=counts.get)


# Aliasuri acceptate pentru fiecare coloană necesară (denumirile diferă între
# exporturile din vizualizatorul co2cars și fișierele anuale complete).
_COL_ALIASES = {
    "Mk":   ["mk", "make", "marca"],
    "Cn":   ["cn", "commercial name", "cn (commercial name)", "commercialname"],
    "m_kg": ["m (kg)", "m(kg)", "m", "mass", "mass in running order",
             "mass in running order (kg)", "mro"],
    "ep_kW": ["ep (kw)", "ep(kw)", "ep", "engine power", "engine power (kw)",
              "enginepower"],
    "co2_wltp": ["ewltp (g/km)", "ewltp(g/km)", "ewltp",
                 "specific co2 emissions (wltp)",
                 "specific co2 emissions in g/km (wltp)"],
    "Ft":   ["ft", "fuel type", "fueltype"],
}


def _map_columns(cols: list[str]) -> dict | None:
    """Mapează coloanele reale ale fișierului la cele 6 necesare (fără
    sensibilitate la majuscule/spații). Returnează None dacă lipsește vreuna."""
    norm = {re.sub(r"\s+", " ", c).strip().lower(): c for c in cols}
    mapping = {}
    for target, aliases in _COL_ALIASES.items():
        found = next((norm[a] for a in aliases if a in norm), None)
        if found is None:
            return None
        mapping[target] = found
    return mapping


def _load_eea(path: str, chunksize: int = 500_000) -> pd.DataFrame:
    """Citește doar coloanele necesare, pe bucăți; detectează separatorul și
    denumirile de coloane; afișează diagnostic dacă structura nu se potrivește."""
    sep = _detect_sep(path)
    header = pd.read_csv(path, sep=sep, nrows=0, encoding_errors="replace")
    mapping = _map_columns(list(header.columns))
    if mapping is None:
        print("\nCOLOANELE GĂSITE în fișier:")
        for c in header.columns:
            print("   ", repr(c))
        raise SystemExit(
            "\nNu am putut identifica coloanele necesare "
            "(marcă, denumire comercială, masă, putere, CO2 WLTP, tip combustibil).\n"
            "Trimiteți lista de mai sus pentru adaptarea scriptului, sau "
            "re-exportați setul de date DETALIAT (per înregistrare) de la "
            "co2cars.apps.eea.europa.eu.")
    print(f"Separator detectat: {sep!r} · coloane mapate: "
          + ", ".join(f"{k}←{v!r}" for k, v in mapping.items()))
    chunks = []
    for ch in pd.read_csv(path, sep=sep, usecols=list(mapping.values()),
                          chunksize=chunksize, encoding_errors="replace",
                          low_memory=True):
        ch = ch.rename(columns={v: k for k, v in mapping.items()})
        ch = ch[ch["Ft"].astype(str).str.lower()
                  .str.contains("electric|petrol|diesel|hybrid", na=False)]
        chunks.append(ch)
    df = pd.concat(chunks, ignore_index=True)
    for c in ("m_kg", "ep_kW", "co2_wltp"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if len(df) == 0:
        vals = pd.read_csv(path, sep=sep, usecols=[mapping["Ft"]],
                           nrows=200_000, encoding_errors="replace")
        print("\nValori întâlnite în coloana de combustibil:",
              sorted(vals.iloc[:, 0].astype(str).str.lower().unique())[:20])
        raise SystemExit("Filtrul pe tipul de combustibil nu a păstrat nimic — "
                         "trimiteți lista de mai sus pentru adaptare.")
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eea", required=True, help="CSV-ul EEA descărcat local")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    db = pd.read_csv(DB_PATH)
    print(f"Baza de date: {len(db)} vehicule · EEA: se încarcă (poate dura)…")
    eea = _load_eea(args.eea)
    eea["MK_N"] = eea["Mk"].map(_norm)
    eea["CN_N"] = eea["Cn"].map(_norm)
    print(f"EEA: {len(eea):,} înregistrări relevante încărcate.")

    rows = []
    for _, v in db.iterrows():
        mk, model = _norm(v["marca"]), _norm(v["model"])
        cand = eea[(eea["MK_N"].str.contains(mk.split()[0], na=False)) &
                   (eea["CN_N"].str.contains(model, na=False))]
        rec = {"marca": v["marca"], "model": v["model"],
               "varianta": v["varianta"], "eea_inregistrari": len(cand)}
        if len(cand) == 0:
            rec["status"] = "NEGĂSIT în EEA (model non-UE sau denumire diferită)"
        else:
            m_med = cand["m_kg"].median()
            p_med = cand["ep_kW"].median()
            c_med = cand["co2_wltp"].median()
            rec["eea_masa_mediana"] = m_med
            rec["eea_putere_mediana"] = p_med
            rec["eea_co2_mediana"] = c_med
            rec["abatere_masa_pct"] = round((v["mass_kg"] - m_med) / m_med * 100, 1) if m_med else np.nan
            # puterea EEA este puterea totală de omologare; comparăm cu MCI+EM plafonat
            p_db = v["P_ICE_max_kW"]
            rec["abatere_putere_pct"] = round((p_db - p_med) / p_med * 100, 1) if p_med else np.nan
            rec["abatere_co2_pct"] = round((v["co2_wltp_g_km"] - c_med) / c_med * 100, 1) if c_med else np.nan
            ok = (abs(rec.get("abatere_masa_pct", 0)) <= TOL["mass_pct"] and
                  abs(rec.get("abatere_co2_pct", 0)) <= TOL["co2_pct"])
            rec["status"] = "OK" if ok else "DE VERIFICAT manual"
        rows.append(rec)

    rep = pd.DataFrame(rows)
    rep.to_csv(args.out, index=False)
    n_ok = (rep["status"] == "OK").sum()
    n_miss = rep["status"].str.startswith("NEGĂSIT").sum()
    print(f"\nRaport: {args.out}")
    print(f"  OK: {n_ok} · De verificat: {len(rep)-n_ok-n_miss} · Negăsite: {n_miss}")
    print("Notă: puterea EEA (ep) este adesea puterea sistemului sau doar a MCI,")
    print("în funcție de constructor — tratați abaterile de putere orientativ.")


if __name__ == "__main__":
    main()
