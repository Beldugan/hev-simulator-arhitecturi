"""
test_pdf_export.py — Test de fum (smoke test) pentru pdf_export.py.

Nu verifică aspectul vizual al PDF-ului (nefezabil într-un test automat),
ci faptul că generate_pdf_report() rulează cap-coadă, fără excepții, pe date
realiste, și produce un fișier PDF valid nevid. Acoperă indirect majoritatea
funcțiilor interne ale modulului (tabele, grafice matplotlib, interpretări
generate din date, validare fizică, comparație WLTP, breakeven, sensibilitate).

Traseele GPS (geocodare via Nominatim) sunt EXCLUSE intenționat din acest
test, ca să nu necesite acces la internet la rulare (vezi gps_tracks={}).

Rulare: pytest tests/  sau  python3 tests/test_pdf_export.py
"""
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from vehicle_model import VehicleParams
from ems_strategies import simulate, ARCHITECTURES, ARCH_LABELS, STRATEGY_LABELS
from tco_model import EconomicParams, compute_tco, compute_breakeven, compare_with_sources
from analysis import sensitivity_analysis, physical_validation
from pdf_export import generate_pdf_report

PRICE_MAP = {"baseline": 0.84, "serie": 0.98, "paralel": 1.00, "serie_paralel": 1.04}


def _load_cycles():
    here = os.path.dirname(os.path.abspath(__file__))
    dd = os.path.join(here, "..", "data")
    out = {}
    for label, fname in [("WLTC", "wltc_class3b_reference.csv"),
                         ("UDDS", "udds.csv")]:
        out[label] = pd.read_csv(os.path.join(dd, fname))["speed_kmh"].values
    return out


class TestGeneratePdfReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cycles = _load_cycles()
        cls.p = VehicleParams()
        cls.econ = EconomicParams()
        cls.results = {a: {c: simulate(a, cls.p, spd, c, strategy="rule_based")
                           for c, spd in cls.cycles.items()}
                      for a in ARCHITECTURES}

    def _build_common_args(self):
        results, cycles, p, econ = self.results, self.cycles, self.p, self.econ

        def _reduc(a, c):
            base = results["baseline"][c].consumption_L_100km
            return round((base - results[a][c].consumption_L_100km) / base * 100, 1) if base > 0 else 0.0

        rows_pdf = [{"Arhitectură": ARCH_LABELS[a], "Ciclu": c,
                     "Consum [L/100km]": results[a][c].consumption_L_100km,
                     "CO₂ [g/km]": results[a][c].co2_g_km,
                     "Cotă EV [%]": results[a][c].ev_share_pct,
                     "Reducere [%]": _reduc(a, c)}
                    for a in ARCHITECTURES for c in cycles]

        tco_pdf = []
        for a in ARCHITECTURES:
            avg = np.mean([results[a][c].consumption_L_100km for c in cycles])
            t = compute_tco(p.price_EUR * PRICE_MAP[a], avg, p.residual_frac,
                            econ, is_hev=(a != "baseline"))
            tco_pdf.append({"Arhitectură": ARCH_LABELS[a], "Achiziție": t["price"],
                            "Energie": t["cost_energy"], "Mentenanță": t["maintenance"],
                            "Asigurare": t["insurance"], "Rezidual": t["residual"],
                            "TCO total": t["tco_total"]})

        be_pdf = compute_breakeven(
            p.price_EUR * PRICE_MAP["baseline"], p.price_EUR,
            np.mean([results["baseline"][c].consumption_L_100km for c in cycles]),
            np.mean([results["paralel"][c].consumption_L_100km for c in cycles]), econ)

        checks_pdf = physical_validation(results["paralel"]["WLTC"], p)
        sp_wltc = results["serie_paralel"]["WLTC"].consumption_L_100km
        cmp_pdf = compare_with_sources(sp_wltc, "serie_paralel", min_sources=3)
        soc_pdf = {c: {a: results[a][c].SoC for a in ARCHITECTURES if a != "baseline"}
                  for c in cycles}
        sens_pdf = sensitivity_analysis("serie_paralel", p, econ,
                                        cycles["WLTC"], "WLTC")

        return dict(p=p, econ=econ, rows_pdf=rows_pdf, tco_pdf=tco_pdf,
                   checks_pdf=checks_pdf, cmp_pdf=cmp_pdf, soc_pdf=soc_pdf,
                   be_pdf=be_pdf, sens_pdf=sens_pdf)

    def test_full_report_generates_valid_pdf(self):
        a = self._build_common_args()
        out_path = os.path.join(tempfile.gettempdir(), "test_raport_hev.pdf")
        result_path = generate_pdf_report(
            a["p"], a["econ"], a["rows_pdf"], a["tco_pdf"], a["checks_pdf"],
            a["cmp_pdf"], a["soc_pdf"], STRATEGY_LABELS["rule_based"], out_path,
            results=self.results, cycles=self.cycles, breakeven=a["be_pdf"],
            sensitivity=a["sens_pdf"], sens_arch_label=ARCH_LABELS["serie_paralel"],
            eea_audit=None, report_cycles=list(self.cycles.keys()),
            main_cycle="WLTC", gps_tracks={})
        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(os.path.getsize(out_path), 5000)  # PDF real, nu gol
        with open(out_path, "rb") as f:
            header = f.read(5)
        self.assertEqual(header, b"%PDF-")
        os.remove(out_path)

    def test_report_without_optional_sections(self):
        """Raportul trebuie să se genereze și fără date opționale (breakeven,
        sensibilitate, comparație WLTP, audit EEA) — cazul unui vehicul
        introdus manual, fără corespondent în baza de date."""
        a = self._build_common_args()
        out_path = os.path.join(tempfile.gettempdir(), "test_raport_hev_minimal.pdf")
        generate_pdf_report(
            a["p"], a["econ"], a["rows_pdf"], a["tco_pdf"], a["checks_pdf"],
            None, a["soc_pdf"], STRATEGY_LABELS["rule_based"], out_path,
            results=self.results, cycles=self.cycles, breakeven=None,
            sensitivity=None, sens_arch_label="", eea_audit=None,
            report_cycles=["WLTC"], main_cycle="WLTC", gps_tracks={})
        self.assertTrue(os.path.exists(out_path))
        with open(out_path, "rb") as f:
            header = f.read(5)
        self.assertEqual(header, b"%PDF-")
        os.remove(out_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
