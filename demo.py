"""
demo.py — Demonstrație a motorului de simulare (linie de comandă)
=================================================================

Rulează toate cele patru arhitecturi cu strategia Rule-Based pe ciclul WLTC
și afișează un tabel comparativ. Util pentru verificarea rapidă că motorul
funcționează, fără interfața web.

Rulare:
    python demo.py
    python demo.py --strategy ecms
    python demo.py --all-strategies
"""
import sys
import os
import argparse
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from vehicle_model import VehicleParams
from ems_strategies import simulate, ARCHITECTURES, ARCH_LABELS, STRATEGY_LABELS


def load_cycle(name: str = "wltc_class3b_reference.csv"):
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "data", name)
    return pd.read_csv(path)["speed_kmh"].values


def main():
    parser = argparse.ArgumentParser(description="Simulator arhitecturi hibride — demo CLI")
    parser.add_argument("--strategy", default="rule_based",
                        choices=["rule_based", "ecms", "dp"],
                        help="Strategia EMS (implicit: rule_based)")
    parser.add_argument("--all-strategies", action="store_true",
                        help="Rulează toate strategiile pentru arhitectura paralel")
    args = parser.parse_args()

    p = VehicleParams()
    wltc = load_cycle()

    print("=" * 70)
    print("  SIMULATOR ARHITECTURI HIBRIDE — Demonstrație")
    print("  Vehicul:", p.name, f"({p.mass_kg:.0f} kg)")
    print("=" * 70)

    if args.all_strategies:
        print(f"\nArhitectura PARALEL pe WLTC, toate strategiile:\n")
        print(f"{'Strategie':<45}{'Consum':>12}{'CO2':>10}")
        print("-" * 67)
        for strat in ["rule_based", "ecms", "dp"]:
            r = simulate("paralel", p, wltc, "WLTC", strategy=strat)
            print(f"{STRATEGY_LABELS[strat]:<45}{r.consumption_L_100km:>9.3f} L{r.co2_g_km:>8.1f} g")
    else:
        strat = args.strategy
        print(f"\nStrategie: {STRATEGY_LABELS[strat]}")
        print(f"Ciclu: WLTC clasa 3b\n")
        print(f"{'Arhitectură':<28}{'Consum':>12}{'CO2':>10}{'EV':>8}{'Reducere':>10}")
        print("-" * 68)
        base_cons = None
        for arch in ARCHITECTURES:
            r = simulate(arch, p, wltc, "WLTC", strategy=strat)
            if arch == "baseline":
                base_cons = r.consumption_L_100km
            red = (base_cons - r.consumption_L_100km) / base_cons * 100 if base_cons else 0
            print(f"{ARCH_LABELS[arch]:<28}{r.consumption_L_100km:>9.3f} L"
                  f"{r.co2_g_km:>8.1f} g{r.ev_share_pct:>6.0f}%{red:>9.1f}%")

    print("\n" + "=" * 70)
    print("  Pentru interfața web completă: streamlit run app.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
