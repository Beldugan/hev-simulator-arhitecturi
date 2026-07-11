"""
test_obd_import.py — Teste unitare pentru importul de trasee reale OBD-II
(Torque) din obd_import.py.

Rulare: pytest tests/  sau  python3 tests/test_obd_import.py
"""
import io
import os
import sys
import unittest
from datetime import datetime, timedelta

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from obd_import import parse_torque_log, cycle_to_csv, build_track_map


def _make_torque_csv(n=200, with_gps=True, with_maf=True, start_lat=44.18,
                     start_lon=28.63) -> str:
    """Construiește un CSV sintetic, cu coloane și format asemănătoare unui
    export real din aplicația Torque (vezi header-ul fișierelor din
    'Ciclu testare CT_MAMAIA_NAVODARI/trackLog-*.csv')."""
    t0 = datetime(2026, 4, 2, 11, 0, 0)
    rows = []
    speed = 0.0
    for i in range(n):
        # profil simplu: accelerare, croazieră, o oprire la mijloc, decelerare
        if i < 20:
            speed = min(speed + 2.0, 50.0)
        elif 90 <= i < 100:
            speed = max(speed - 5.0, 0.0)
        elif i >= n - 15:
            speed = max(speed - 4.0, 0.0)
        else:
            speed = min(speed + 0.5, 60.0)
        ts = (t0 + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
        lat = start_lat + i * 0.0001 if with_gps else ""
        lon = start_lon + i * 0.0001 if with_gps else ""
        maf = round(2.0 + speed / 10.0, 2) if with_maf else ""
        rows.append(f"{ts},{ts},{lon},{lat},{speed:.1f},{maf}")
    header = "GPS Time, Device Time, Longitude, Latitude,Speed (OBD)(km/h),Mass Air Flow Rate(g/s)"
    return header + "\n" + "\n".join(rows) + "\n"


class TestParseTorqueLog(unittest.TestCase):
    def test_basic_parse_returns_expected_keys(self):
        csv_text = _make_torque_csv()
        res = parse_torque_log(io.StringIO(csv_text))
        for key in ("speed_kmh", "duration_s", "distance_km", "v_max",
                    "v_avg_moving", "n_stops", "consumption_L_100km",
                    "gps_track", "warnings"):
            self.assertIn(key, res)

    def test_speed_resampled_at_1hz_and_plausible(self):
        csv_text = _make_torque_csv()
        res = parse_torque_log(io.StringIO(csv_text))
        self.assertGreater(len(res["speed_kmh"]), 50)
        self.assertLessEqual(res["v_max"], 61.0)
        self.assertGreater(res["distance_km"], 0)

    def test_gps_track_present_when_coordinates_given(self):
        csv_text = _make_torque_csv(with_gps=True)
        res = parse_torque_log(io.StringIO(csv_text))
        self.assertIsNotNone(res["gps_track"])
        self.assertIn("lat", res["gps_track"])
        self.assertIn("lon", res["gps_track"])

    def test_consumption_estimated_from_maf(self):
        csv_text = _make_torque_csv(with_maf=True)
        res = parse_torque_log(io.StringIO(csv_text))
        self.assertIsNotNone(res["consumption_L_100km"])
        self.assertGreater(res["consumption_L_100km"], 0)

    def test_missing_speed_column_raises_clear_error(self):
        bad_csv = "GPS Time, Device Time, Latitude, Longitude\n" + \
                  "\n".join(f"t{i},t{i},44.{i},28.{i}" for i in range(10))
        with self.assertRaises(ValueError):
            parse_torque_log(io.StringIO(bad_csv))

    def test_too_short_log_raises_clear_error(self):
        csv_text = _make_torque_csv(n=3)
        with self.assertRaises(ValueError):
            parse_torque_log(io.StringIO(csv_text))

    def test_stationary_log_raises_clear_error(self):
        """Un log cu motorul pornit dar mașina oprită (viteză ~0 tot timpul)
        nu poate fi folosit ca ciclu de conducere — trebuie semnalat clar."""
        t0 = datetime(2026, 4, 2, 11, 0, 0)
        rows = []
        for i in range(60):
            ts = (t0 + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
            rows.append(f"{ts},{ts},28.63,44.18,0.0,2.0")
        header = "GPS Time, Device Time, Longitude, Latitude,Speed (OBD)(km/h),Mass Air Flow Rate(g/s)"
        csv_text = header + "\n" + "\n".join(rows) + "\n"
        with self.assertRaises(ValueError):
            parse_torque_log(io.StringIO(csv_text))


class TestCycleToCsv(unittest.TestCase):
    def test_roundtrip_columns(self):
        speed = np.array([0, 10, 20, 30, 20, 10, 0], dtype=float)
        csv_text = cycle_to_csv(speed)
        self.assertIn("time_s", csv_text)
        self.assertIn("speed_kmh", csv_text)
        self.assertEqual(csv_text.strip().count("\n"), len(speed))  # antet + N-1 rânduri interne + 1


class TestBuildTrackMap(unittest.TestCase):
    def test_returns_deck_or_none_without_crashing(self):
        track = {"lat": [44.18, 44.181, 44.182],
                "lon": [28.63, 28.631, 28.632],
                "speed": [10.0, 20.0, 15.0]}
        deck = build_track_map(track)  # None dacă pydeck lipsește, altfel un Deck
        self.assertTrue(deck is None or hasattr(deck, "to_json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
