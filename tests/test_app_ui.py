"""
test_app_ui.py — Teste de fum pentru interfața app.py, folosind
streamlit.testing.v1.AppTest (rulează scriptul într-un mediu simulat, fără
browser real).

Acoperă comportamentul introdus în v40: redenumirea meniului de strategie,
popover-urile de explicații (strategie EMS, detalii vehicul, pagini) și
faptul că nu ridică excepții pentru niciun tip de vehicul din baza de date
(HEV/PHEV/MHEV).

Rulare: pytest tests/  sau  python3 tests/test_app_ui.py
"""
import os
import sys
import unittest

from streamlit.testing.v1 import AppTest

APP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py")


class TestSidebarLabels(unittest.TestCase):
    def test_strategy_label_renamed(self):
        """Meniul de strategie nu mai poartă acronimul EMS în etichetă."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.assertEqual(at.exception, [])
        labels = [s.label for s in at.sidebar.selectbox]
        self.assertIn("Strategia de management energetic", labels)
        self.assertNotIn("Strategie EMS", labels)

    def test_strategy_options_have_no_bare_acronyms(self):
        """Etichetele afișate pentru cele 3 strategii nu (mai) conțin
        acronimele brute (Rule-Based / ECMS) — cerință explicită a
        utilizatorului."""
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
        from ems_strategies import STRATEGY_LABELS
        joined = " ".join(STRATEGY_LABELS.values())
        self.assertNotIn("Rule-Based", joined)
        self.assertNotIn("ECMS", joined)


class TestPopoversRenderWithoutErrors(unittest.TestCase):
    def test_ems_explanation_popover_present(self):
        """Cele 3 explicații de strategie sunt randate (ascunse, arătate la
        hover pe opțiune — fără niciun buton „?")."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.assertEqual(at.exception, [])
        text = " ".join(m.value for m in at.sidebar.markdown)
        self.assertIn("Strategie bazată pe reguli", text)
        self.assertIn("Minimizarea consumului echivalent", text)
        self.assertIn("Programare dinamică", text)
        self.assertIn("strategy-hover-0", text)
        self.assertIn("strategy-hover-1", text)
        self.assertIn("strategy-hover-2", text)

    def test_menu_pages_popover_present(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        text = " ".join(m.value for m in at.sidebar.markdown)
        for page in ["Simulare", "Sensibilitate", "Comparație A/B", "Validare", "Export PDF"]:
            self.assertIn(page, text)

    def test_vehicle_popover_all_types(self):
        """Popover-ul de audit + tip vehicul se randează fără erori pentru
        fiecare tip din baza de date (HEV, PHEV, MHEV)."""
        cases = [
            ("Toyota", "Yaris", "1.5 Hybrid 116", "HEV", "Hibrid complet"),
            ("Toyota", "C-HR", "2.0 PHEV 223", "PHEV", "nu corespund regimului uzual"),
            ("Ford", "Puma", "1.0 EcoBoost mHEV 125", "MHEV", "Electrificare ușoară"),
        ]
        for marca, model, varianta, tip, expected_snippet in cases:
            with self.subTest(tip=tip):
                at = AppTest.from_file(APP_PATH, default_timeout=30)
                at.run()
                at.sidebar.selectbox[0].set_value("Bază de date (marcă → model)").run()
                at.sidebar.selectbox[2].set_value(marca).run()
                at.sidebar.selectbox[3].set_value(model).run()
                at.sidebar.selectbox[4].set_value(varianta).run()
                self.assertEqual(at.exception, [], f"Excepție la {tip} {marca} {model}")
                text = " ".join(m.value for m in at.sidebar.markdown)
                self.assertIn(expected_snippet, text)

    def test_vehicle_summary_in_hover_box(self):
        """Descrierea scurtă (tip/arhitectură/CO2/sursă) nu mai e mereu
        vizibilă separat — e inclusă, împreună cu auditul EEA și tipul de
        electrificare, în box-ul arătat la hover pe „Variantă" (fără niciun
        buton „?")."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        at.sidebar.selectbox[0].set_value("Bază de date (marcă → model)").run()
        text = " ".join(m.value for m in at.sidebar.markdown)
        self.assertIn("arhitectura reală", text)
        self.assertIn("CO₂ WLTP oficial", text)
        self.assertIn("Sursă:", text)
        self.assertIn("vehicle-hover-box", text)
        captions = " ".join(c.value for c in at.sidebar.caption)
        self.assertNotIn("arhitectura reală", captions)


if __name__ == "__main__":
    unittest.main(verbosity=2)
