"""
test_analysis.py — Teste unitare pentru analiza de sensibilitate și
validarea fizică (analysis.py).

Rulare: pytest tests/  sau  python3 tests/test_analysis.py
"""
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from vehicle_model import VehicleParams
from ems_strategies import simulate
from tco_model import EconomicParams
from analysis import (sensitivity_analysis, physical_validation,
                      SENS_VEHICLE_PARAMS, SENS_ECON_PARAMS)


def _load_wltc():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "data", "wltc_class3b_reference.csv")
    return pd.read_csv(path)["speed_kmh"].values


class TestPhysicalValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wltc = _load_wltc()
        cls.p = VehicleParams()

    def test_all_checks_have_status_and_detail(self):
        r = simulate("paralel", self.p, self.wltc, "WLTC", strategy="rule_based")
        checks = physical_validation(r, self.p)
        self.assertGreater(len(checks), 0)
        for c in checks:
            self.assertIn(c["status"], ("PASS", "FAIL"))
            self.assertTrue(c["detail"])

    def test_hard_physical_limits_always_pass(self):
        """Limitele fizice stricte (SoC în interval, puteri sub maxime, debit
        de combustibil nenegativ) sunt garantate prin construcție (clipping)
        în ems_strategies.py — trebuie să treacă indiferent de strategie.
        (Notă: neutralitatea energetică e o verificare de calitate a
        strategiei, nu o limită fizică strictă, și poate eșua legitim la
        Rule-Based — nu e inclusă aici.)"""
        r = simulate("paralel", self.p, self.wltc, "WLTC", strategy="rule_based")
        checks = {c["check"]: c["status"] for c in physical_validation(r, self.p)}
        for name in ("SoC în intervalul de protecție",
                     "Putere motor termic ≤ maxim",
                     "Putere mașină electrică ≤ maxim",
                     "Debit de combustibil nenegativ"):
            self.assertEqual(checks[name], "PASS", f"{name} a eșuat neașteptat")


class TestSensitivityAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wltc = _load_wltc()
        cls.p = VehicleParams()
        cls.econ = EconomicParams()

    def test_returns_expected_structure(self):
        sens = sensitivity_analysis("paralel", self.p, self.econ, self.wltc, "WLTC")
        for key in ("consumption", "tco", "base_consumption", "base_tco"):
            self.assertIn(key, sens)
        # consum: doar parametrii vehiculului; TCO: vehicul + economici
        self.assertEqual(len(sens["consumption"]), len(SENS_VEHICLE_PARAMS))
        self.assertEqual(len(sens["tco"]),
                         len(SENS_VEHICLE_PARAMS) + len(SENS_ECON_PARAMS))

    def test_each_effect_has_low_high(self):
        sens = sensitivity_analysis("paralel", self.p, self.econ, self.wltc, "WLTC")
        for eff in sens["consumption"]:
            self.assertIn("low", eff)
            self.assertIn("high", eff)
            self.assertIn("label", eff)

    def test_mass_increases_consumption(self):
        """Masa mai mare (high) trebuie să dea consum >= masă mai mică (low) —
        sanity check fizic minim pentru rezultatul de sensibilitate."""
        sens = sensitivity_analysis("paralel", self.p, self.econ, self.wltc, "WLTC")
        mass_eff = next(e for e in sens["consumption"] if e["label"] == "Masă vehicul")
        self.assertGreaterEqual(mass_eff["high"], mass_eff["low"])

    def test_progress_callback_reaches_one(self):
        progress_values = []
        sensitivity_analysis("paralel", self.p, self.econ, self.wltc, "WLTC",
                             progress_cb=progress_values.append)
        self.assertTrue(progress_values)
        self.assertAlmostEqual(progress_values[-1], 1.0, places=6)
        # monoton crescător
        self.assertEqual(progress_values, sorted(progress_values))


if __name__ == "__main__":
    unittest.main(verbosity=2)
