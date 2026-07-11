"""
test_tco_model.py — Teste unitare pentru modelul TCO și comparația WLTP
=========================================================================
Acoperă tco_model.py: compute_tco(), compute_breakeven(),
load_wltp_references(), compare_with_sources().

Rulare: pytest tests/  sau  python3 tests/test_tco_model.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from tco_model import (EconomicParams, compute_tco, compute_breakeven,
                       load_wltp_references, compare_with_sources)


class TestComputeTCO(unittest.TestCase):
    def setUp(self):
        self.econ = EconomicParams()

    def test_returns_expected_keys(self):
        t = compute_tco(28590.0, 4.5, 0.20, self.econ, is_hev=True)
        for key in ("price", "residual", "cost_fuel", "cost_energy",
                    "maintenance", "insurance", "subsidy", "tco_total", "total_km"):
            self.assertIn(key, t)

    def test_tco_positive_and_reasonable(self):
        t = compute_tco(28590.0, 4.5, 0.20, self.econ, is_hev=True)
        self.assertGreater(t["tco_total"], t["price"])  # combustibil+mentenanță > 0
        self.assertEqual(t["total_km"], int(self.econ.km_per_year * self.econ.years))

    def test_higher_consumption_raises_tco(self):
        t_low = compute_tco(28590.0, 4.0, 0.20, self.econ, is_hev=True)
        t_high = compute_tco(28590.0, 6.0, 0.20, self.econ, is_hev=True)
        self.assertGreater(t_high["tco_total"], t_low["tco_total"])

    def test_hev_maintenance_differs_from_ice(self):
        t_hev = compute_tco(28590.0, 4.5, 0.20, self.econ, is_hev=True)
        t_ice = compute_tco(28590.0, 4.5, 0.20, self.econ, is_hev=False)
        self.assertNotEqual(t_hev["maintenance"], t_ice["maintenance"])

    def test_subsidy_reduces_tco(self):
        econ_sub = EconomicParams(rabla_plus_EUR=3000.0)
        t_no_sub = compute_tco(28590.0, 4.5, 0.20, self.econ, is_hev=True)
        t_sub = compute_tco(28590.0, 4.5, 0.20, econ_sub, is_hev=True)
        self.assertLess(t_sub["tco_total"], t_no_sub["tco_total"])


class TestBreakeven(unittest.TestCase):
    def setUp(self):
        self.econ = EconomicParams()

    def test_breakeven_when_hev_saves_fuel(self):
        be = compute_breakeven(24500.0, 27500.0, 6.0, 4.5, self.econ)
        self.assertIsNotNone(be["years"])
        self.assertGreater(be["years"], 0)
        self.assertGreater(be["annual_saving"], 0)

    def test_no_breakeven_when_no_saving(self):
        """Dacă HEV nu economisește combustibil, nu există break-even (years=None)."""
        be = compute_breakeven(24500.0, 27500.0, 4.5, 4.5, self.econ)
        self.assertIsNone(be["years"])
        self.assertIn("note", be)


class TestWLTPReferences(unittest.TestCase):
    def test_load_default_references(self):
        """Fișierul de referință livrat cu aplicația se încarcă fără erori."""
        refs = load_wltp_references()
        self.assertIn("vehicles", refs)
        self.assertGreater(len(refs["vehicles"]), 0)

    def test_load_missing_path_raises_clear_error(self):
        """O cale explicită inexistentă trebuie să ridice FileNotFoundError
        cu un mesaj clar, nu un TypeError obscur (fix aplicat)."""
        with self.assertRaises(FileNotFoundError):
            load_wltp_references("/cale/care/nu/exista/wltp_references.json")

    def test_compare_with_sources_structure(self):
        cmp_ = compare_with_sources(4.6, "serie_paralel", min_sources=3)
        self.assertIn("comparisons", cmp_)
        self.assertGreaterEqual(cmp_["n_sources"], 1)
        for c in cmp_["comparisons"]:
            self.assertIn("deviation_pct", c)
            self.assertIn("official_L_100km", c)


if __name__ == "__main__":
    unittest.main(verbosity=2)
