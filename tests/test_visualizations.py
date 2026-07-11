"""
test_visualizations.py — Teste unitare pentru visualizations.py:
statistici de ciclu, evenimente de aprindere, conținutul CYCLE_INFO și
funcțiile de grafic (smoke test — verifică doar că produc o figură validă,
nu aspectul vizual).

Rulare: pytest tests/  sau  python3 tests/test_visualizations.py
"""
import os
import sys
import unittest

import numpy as np
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from vehicle_model import VehicleParams
from ems_strategies import simulate, ARCHITECTURES
from visualizations import (cycle_stats, ignition_events, CYCLE_INFO,
                            plot_soc_trajectory, plot_power_profile,
                            plot_bsfc_map, plot_consumption_bars,
                            plot_sensitivity_tornado, plot_cycle_live,
                            plot_ignition_scatter)

# Etichetele ciclurilor livrate cu aplicația (vezi load_cycles() în app.py) —
# fiecare trebuie să aibă o descriere în CYCLE_INFO, altfel secțiunea "Despre
# ciclul selectat" apare goală în interfață.
BUNDLED_CYCLE_LABELS = ["WLTC", "UDDS", "HWFET",
                        "Real urban (Constanța)", "Real mixt (Constanța)"]


def _load_wltc():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "data", "wltc_class3b_reference.csv")
    return pd.read_csv(path)["speed_kmh"].values


class TestCycleInfoCompleteness(unittest.TestCase):
    def test_all_bundled_cycles_have_description(self):
        for label in BUNDLED_CYCLE_LABELS:
            self.assertIn(label, CYCLE_INFO, f"Lipsește descrierea pentru '{label}'")
            self.assertGreater(len(CYCLE_INFO[label]), 20)


class TestCycleStats(unittest.TestCase):
    def test_wltc_stats_plausible(self):
        wltc = _load_wltc()
        cs = cycle_stats(wltc)
        self.assertEqual(cs["duration_s"], 1800)
        self.assertAlmostEqual(cs["distance_km"], 23.27, delta=0.5)
        self.assertGreater(cs["v_max"], 100)
        self.assertGreaterEqual(cs["n_stops"], 1)

    def test_constant_speed_has_no_stops(self):
        v = np.full(100, 50.0)
        cs = cycle_stats(v)
        self.assertEqual(cs["n_stops"], 0)
        self.assertEqual(cs["idle_pct"], 0.0)


class TestIgnitionEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wltc = _load_wltc()
        cls.p = VehicleParams()

    def test_hybrid_has_ignition_events_on_wltc(self):
        r = simulate("paralel", self.p, self.wltc, "WLTC", strategy="rule_based")
        ign = ignition_events(r, self.wltc)
        self.assertIn("n", ign)
        self.assertGreater(ign["n"], 0)
        self.assertEqual(len(ign["t"]), ign["n"])
        self.assertEqual(len(ign["speed"]), ign["n"])
        self.assertEqual(len(ign["soc"]), ign["n"])


class TestPlotSmoke(unittest.TestCase):
    """Verifică doar că funcțiile de grafic rulează fără erori și întorc un
    plotly.graph_objects.Figure — nu validează aspectul vizual."""

    @classmethod
    def setUpClass(cls):
        cls.wltc = _load_wltc()
        cls.p = VehicleParams()
        cls.results = {a: simulate(a, cls.p, cls.wltc, "WLTC", strategy="rule_based")
                       for a in ARCHITECTURES}

    def test_plot_soc_trajectory(self):
        fig = plot_soc_trajectory(self.results, self.p)
        self.assertIsInstance(fig, go.Figure)

    def test_plot_power_profile(self):
        fig = plot_power_profile(self.results["paralel"], self.wltc)
        self.assertIsInstance(fig, go.Figure)

    def test_plot_bsfc_map(self):
        fig = plot_bsfc_map(self.p, self.results["paralel"])
        self.assertIsInstance(fig, go.Figure)

    def test_plot_consumption_bars(self):
        data = {a: {"WLTC": self.results[a].consumption_L_100km} for a in ARCHITECTURES}
        fig = plot_consumption_bars(data)
        self.assertIsInstance(fig, go.Figure)

    def test_plot_sensitivity_tornado(self):
        effects = [{"label": "Masă vehicul", "low": 4.0, "high": 5.0}]
        fig = plot_sensitivity_tornado(effects, 4.5, "Consum [L/100km]")
        self.assertIsInstance(fig, go.Figure)

    def test_plot_cycle_live(self):
        fig = plot_cycle_live(self.results["paralel"], self.wltc, self.p, "Test")
        self.assertIsInstance(fig, go.Figure)

    def test_plot_ignition_scatter(self):
        fig = plot_ignition_scatter(self.results["paralel"], self.wltc)
        self.assertIsInstance(fig, go.Figure)


if __name__ == "__main__":
    unittest.main(verbosity=2)
