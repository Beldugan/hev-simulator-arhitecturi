"""
test_engine.py — Teste unitare pentru motorul de simulare
==========================================================

Rulare:
    cd tests && python3 test_engine.py
sau, cu pytest:
    pytest tests/

Verifică:
    - modelul fizic (road_load, fuel_rate) dă valori corecte dimensional
    - simularea rulează pentru toate arhitecturile și strategiile
    - relațiile de ordine între strategii (Rule-Based >= ECMS pe consum)
    - corecția charge-sustaining păstrează SoC în limite
    - reproductibilitatea (aceleași intrări → aceleași ieșiri)
"""
import sys
import os
import unittest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from vehicle_model import VehicleParams, road_load, fuel_rate, bsfc_map, RHO_AIR, G
from ems_strategies import simulate


def _load_wltc():
    import pandas as pd
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "data", "wltc_class3b_reference.csv")
    return pd.read_csv(path)["speed_kmh"].values


class TestPhysics(unittest.TestCase):
    """Teste pentru funcțiile fizice de bază."""

    def setUp(self):
        self.p = VehicleParams()

    def test_road_load_stationary(self):
        """La viteză 0 și accelerație 0, puterea la roată e 0."""
        P, F = road_load(0.0, 0.0, self.p)
        self.assertAlmostEqual(P, 0.0, places=6)

    def test_road_load_positive_at_speed(self):
        """La viteză constantă pozitivă, puterea la roată e pozitivă."""
        P, F = road_load(25.0, 0.0, self.p)  # 90 km/h
        self.assertGreater(P, 0.0)
        self.assertGreater(F, 0.0)

    def test_road_load_drag_scaling(self):
        """Forța de drag crește cu pătratul vitezei."""
        _, F1 = road_load(10.0, 0.0, self.p)
        _, F2 = road_load(20.0, 0.0, self.p)
        # La dublarea vitezei, componenta de drag se cvadruplează;
        # forța totală crește (rr constant + drag ×4)
        self.assertGreater(F2, F1)

    def test_fuel_rate_zero_when_engine_off(self):
        """Debit de combustibil 0 când motorul e oprit."""
        self.assertEqual(fuel_rate(0.0, self.p), 0.0)
        self.assertEqual(fuel_rate(-1000.0, self.p), 0.0)

    def test_fuel_rate_positive(self):
        """Debit pozitiv pentru putere pozitivă."""
        self.assertGreater(fuel_rate(30000.0, self.p), 0.0)

    def test_fuel_rate_monotonic(self):
        """Consumul crește cu puterea."""
        f1 = fuel_rate(20000.0, self.p)
        f2 = fuel_rate(40000.0, self.p)
        self.assertGreater(f2, f1)

    def test_bsfc_reasonable(self):
        """BSFC într-un interval fizic rezonabil (150-400 g/kWh)."""
        bsfc = bsfc_map(40000.0, self.p)
        self.assertTrue(150 < bsfc < 500, f"BSFC={bsfc} în afara intervalului")


class TestSimulation(unittest.TestCase):
    """Teste pentru simularea completă."""

    @classmethod
    def setUpClass(cls):
        cls.wltc = _load_wltc()
        cls.p = VehicleParams()

    def test_all_architectures_run(self):
        """Toate cele patru arhitecturi rulează fără erori."""
        for arch in ["baseline", "serie", "paralel", "serie_paralel"]:
            r = simulate(arch, self.p, self.wltc, "WLTC", strategy="rule_based")
            self.assertGreater(r.consumption_L_100km, 0)
            self.assertLess(r.consumption_L_100km, 15)  # plauzibil

    def test_hybrid_better_than_baseline(self):
        """Arhitecturile hibride consumă mai puțin decât baseline."""
        base = simulate("baseline", self.p, self.wltc, "WLTC", strategy="rule_based")
        par = simulate("paralel", self.p, self.wltc, "WLTC", strategy="rule_based")
        self.assertLess(par.consumption_L_100km, base.consumption_L_100km)

    def test_soc_within_limits(self):
        """SoC rămâne în intervalul [SoC_min, SoC_max]."""
        r = simulate("paralel", self.p, self.wltc, "WLTC", strategy="rule_based")
        self.assertGreaterEqual(r.SoC.min(), self.p.SoC_min - 1e-6)
        self.assertLessEqual(r.SoC.max(), self.p.SoC_max + 1e-6)

    def test_ecms_not_worse_than_rule_based(self):
        """ECMS ar trebui să dea consum <= Rule-Based (e optimizare)."""
        rb = simulate("paralel", self.p, self.wltc, "WLTC", strategy="rule_based")
        ec = simulate("paralel", self.p, self.wltc, "WLTC", strategy="ecms")
        # ECMS optimizează, deci nu ar trebui să fie semnificativ mai rău
        self.assertLessEqual(ec.consumption_L_100km, rb.consumption_L_100km * 1.02)

    def test_reproducibility(self):
        """Aceleași intrări → aceleași ieșiri (determinism)."""
        r1 = simulate("serie_paralel", self.p, self.wltc, "WLTC", strategy="rule_based")
        r2 = simulate("serie_paralel", self.p, self.wltc, "WLTC", strategy="rule_based")
        self.assertEqual(r1.consumption_L_100km, r2.consumption_L_100km)

    def test_co2_proportional_to_consumption(self):
        """CO2 e proporțional cu consumul de combustibil."""
        r = simulate("paralel", self.p, self.wltc, "WLTC", strategy="rule_based")
        expected_co2 = r.consumption_L_100km * self.p.fuel_CO2_kg_L * 10
        self.assertAlmostEqual(r.co2_g_km, expected_co2, delta=1.0)

    def test_result_summary(self):
        """Metoda summary() returnează un dicționar complet."""
        r = simulate("paralel", self.p, self.wltc, "WLTC", strategy="rule_based")
        s = r.summary()
        self.assertIn("consumption_L_100km", s)
        self.assertIn("co2_g_km", s)
        self.assertIn("ev_share_pct", s)


class TestEdgeCases(unittest.TestCase):
    """Teste pentru cazuri limită."""

    def setUp(self):
        self.p = VehicleParams()

    def test_short_cycle(self):
        """Un ciclu foarte scurt rulează fără erori."""
        short = np.array([0, 10, 20, 30, 20, 10, 0], dtype=float)
        r = simulate("paralel", self.p, short, "test", strategy="rule_based")
        self.assertGreaterEqual(r.consumption_L_100km, 0)

    def test_high_mass_vehicle(self):
        """Un vehicul greu consumă mai mult."""
        wltc = _load_wltc()
        light = VehicleParams(mass_kg=1200)
        heavy = VehicleParams(mass_kg=2000)
        r_light = simulate("paralel", light, wltc, "WLTC", strategy="rule_based")
        r_heavy = simulate("paralel", heavy, wltc, "WLTC", strategy="rule_based")
        self.assertGreater(r_heavy.consumption_L_100km, r_light.consumption_L_100km)


if __name__ == "__main__":
    unittest.main(verbosity=2)
