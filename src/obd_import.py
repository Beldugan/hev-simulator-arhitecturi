"""
obd_import.py — Import de trasee reale înregistrate cu OBD-II (aplicația Torque)
================================================================================

Transformă un log Torque (CSV, cu antet) într-un profil de viteză utilizabil ca
ciclu de conducere în simulator, echivalent cu WLTC/UDDS/HWFET.

Prelucrări aplicate:
  1. detectarea coloanelor relevante (viteză OBD, timp, MAF) indiferent de
     ordinea/denumirea exactă din exportul Torque;
  2. reeșantionarea la 1 Hz (Torque logează neregulat, ~1-2 s) prin
     interpolare pe o axă de timp uniformă;
  3. decuparea pauzelor de înregistrare (goluri mari de timp — motorul lăsat
     pornit între segmente) și a staționărilor lungi de la început/sfârșit;
  4. curățarea vârfurilor nefizice de viteză;
  5. (opțional) estimarea consumului real de combustibil din debitul masic de
     aer (MAF), pentru validarea configurației baseline.

Formatul de ieșire e identic cu al ciclurilor standard: un vector de viteză în
km/h, eșantionat la 1 Hz.

Licență: MIT
"""
from __future__ import annotations
import io
import os
import re

import numpy as np
import pandas as pd

# Raportul stoichiometric aer/combustibil pentru benzină și densitatea ei.
_AFR_STOICH = 14.7            # kg aer / kg benzină
_FUEL_DENSITY_G_L = 745.0     # g/L


def _find_col(cols: list[str], *patterns: str) -> str | None:
    """Prima coloană al cărei nume normalizat conține unul dintre pattern-uri."""
    norm = {re.sub(r"\s+", " ", c).strip().lower(): c for c in cols}
    for pat in patterns:
        for key, orig in norm.items():
            if pat in key:
                return orig
    return None


def parse_torque_log(source, *, max_gap_s: float = 10.0,
                     trim_idle: bool = True) -> dict:
    """
    Parsează un log Torque și returnează un ciclu la 1 Hz.

    Parameters
    ----------
    source : cale (str) sau obiect fișier / buffer cu CSV-ul Torque.
    max_gap_s : pauzele de înregistrare mai mari de atât [s] sunt decupate
        (nu se interpolează peste ele — ar crea staționări fictive).
    trim_idle : elimină staționarea (v<1 km/h) de la începutul și sfârșitul
        traseului (pornirea motorului, parcarea).

    Returns
    -------
    dict cu: speed_kmh (np.ndarray, 1 Hz), duration_s, distance_km, v_max,
        v_avg_moving, n_stops, fuel_L (consum real estimat din MAF sau None),
        consumption_L_100km (real, sau None), warnings (list[str]).
    """
    if isinstance(source, (str, os.PathLike)):
        raw = open(source, "r", encoding="utf-8", errors="replace").read()
    elif isinstance(source, bytes):
        raw = source.decode("utf-8", errors="replace")
    elif hasattr(source, "read"):
        data = source.read()
        raw = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    else:
        raise TypeError("source trebuie să fie cale, bytes sau obiect fișier.")

    warnings: list[str] = []
    df = pd.read_csv(io.StringIO(raw), encoding_errors="replace")
    df.columns = [c.strip() for c in df.columns]

    spd_col = _find_col(list(df.columns), "speed (obd)", "obd)(km/h)", "speed (gps)")
    if spd_col is None:
        raise ValueError("Nu am găsit o coloană de viteză (OBD sau GPS) în log.")
    if "obd" not in spd_col.lower():
        warnings.append("Viteza OBD lipsește; se folosește viteza GPS (mai puțin "
                        "precisă la viteze mici).")

    time_col = _find_col(list(df.columns), "device time", "gps time")
    maf_col = _find_col(list(df.columns), "mass air flow", "maf")
    # coordonate GPS de precizie completă (coloanele Longitude/Latitude brute,
    # nu cele rotunjite „GPS Longitude(°)")
    lat_col = _find_col(list(df.columns), "latitude")
    lon_col = _find_col(list(df.columns), "longitude")

    v = pd.to_numeric(df[spd_col], errors="coerce").to_numpy(dtype=float)

    # Axă de timp în secunde de la start
    if time_col is not None:
        t = pd.to_datetime(df[time_col], errors="coerce", dayfirst=True)
        t_s = (t - t.iloc[0]).dt.total_seconds().to_numpy(dtype=float)
        if np.isnan(t_s).all():
            t_s = np.arange(len(v), dtype=float)
            warnings.append("Timpul nu a putut fi interpretat; se presupune 1 Hz.")
    else:
        t_s = np.arange(len(v), dtype=float)
        warnings.append("Fără coloană de timp; se presupune 1 Hz.")

    maf = (pd.to_numeric(df[maf_col], errors="coerce").to_numpy(dtype=float)
           if maf_col is not None else None)
    lat = (pd.to_numeric(df[lat_col], errors="coerce").to_numpy(dtype=float)
           if lat_col is not None else None)
    lon = (pd.to_numeric(df[lon_col], errors="coerce").to_numpy(dtype=float)
           if lon_col is not None else None)

    # Elimină rândurile fără timp sau fără viteză
    ok = ~np.isnan(t_s) & ~np.isnan(v)
    t_s, v = t_s[ok], np.clip(v[ok], 0, None)
    if maf is not None:
        maf = maf[ok]
    if lat is not None:
        lat = lat[ok]
    if lon is not None:
        lon = lon[ok]
    if len(v) < 5:
        raise ValueError("Prea puține puncte valide în log.")

    # Curăță vârfuri nefizice (accelerații > 4 m/s^2 între probe adiacente)
    dt = np.diff(t_s, prepend=t_s[0])
    dt[dt <= 0] = np.median(dt[dt > 0]) if np.any(dt > 0) else 1.0
    dv = np.abs(np.diff(v, prepend=v[0])) / 3.6
    spike = dv / np.maximum(dt, 0.1) > 4.0
    if spike.sum():
        v[spike] = np.nan
        v = pd.Series(v).interpolate(limit_direction="both").to_numpy()
        warnings.append(f"{int(spike.sum())} vârfuri de viteză nefizice au fost netezite.")

    # Segmentează pe golurile mari de timp și reeșantionează fiecare segment la 1 Hz
    gaps = np.where(np.diff(t_s) > max_gap_s)[0]
    bounds = np.concatenate([[0], gaps + 1, [len(t_s)]])
    n_cuts = len(gaps)
    if n_cuts:
        warnings.append(f"{n_cuts} pauze de înregistrare (>{max_gap_s:.0f}s) au fost decupate.")

    segments = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b - a < 2:
            continue
        seg_t = t_s[a:b] - t_s[a]
        seg_v = v[a:b]
        grid = np.arange(0, np.floor(seg_t[-1]) + 1, 1.0)
        seg_v_1hz = np.interp(grid, seg_t, seg_v)
        segments.append(seg_v_1hz)

    if not segments:
        raise ValueError("Niciun segment continuu utilizabil după decupare.")
    speed = np.concatenate(segments)

    # Decupează staționarea de la capete
    if trim_idle:
        moving = np.where(speed > 1.0)[0]
        if len(moving):
            speed = speed[moving[0]:moving[-1] + 1]

    # Statistici
    dist_km = float(np.sum(speed / 3.6)) / 1000.0
    if dist_km < 0.3 or (speed > 1.0).sum() < 10:
        raise ValueError(
            "Traseul nu conține deplasare utilă (distanță < 0,3 km sau vehicul "
            "quasi-staționar). Verifică dacă înregistrarea Torque conține "
            "viteză OBD nenulă — un log făcut cu motorul pornit dar mașina "
            "oprită nu poate fi folosit ca ciclu de conducere.")
    moving = speed > 1.0
    n_stops = int(np.sum((~moving[1:]) & moving[:-1]))

    # Consum real din MAF (dacă există): m_fuel = MAF / AFR
    # Integrarea folosește DOAR intervalele de timp păstrate (exclude golurile
    # mari de înregistrare, care altfel ar umfla consumul).
    fuel_L = cons = None
    if maf is not None and np.isfinite(maf).sum() > len(maf) * 0.5:
        maf_clean = pd.Series(np.clip(maf, 0, None)).interpolate(
            limit_direction="both").to_numpy()
        dt_kept = dt.copy()
        dt_kept[dt_kept > max_gap_s] = 0.0        # nu integra peste pauze
        fuel_g = np.sum(maf_clean * dt_kept) / _AFR_STOICH
        fuel_L = float(fuel_g / _FUEL_DENSITY_G_L)
        if dist_km > 0.1:
            cons = float(fuel_L / dist_km * 100.0)

    # Traseul GPS pentru hartă (coordonate valide + viteza asociată)
    gps_track = None
    if lat is not None and lon is not None:
        gok = (~np.isnan(lat) & ~np.isnan(lon) &
               (np.abs(lat) > 1) & (np.abs(lon) > 1))
        if gok.sum() >= 5:
            gla, glo, gv = lat[gok], lon[gok], v[gok]
            gps_track = {
                "lat": gla.round(6).tolist(),
                "lon": glo.round(6).tolist(),
                "speed": np.clip(gv, 0, None).round(1).tolist(),
            }
        else:
            warnings.append("Coordonate GPS insuficiente pentru hartă.")

    return dict(
        speed_kmh=speed,
        duration_s=int(len(speed)),
        distance_km=dist_km,
        v_max=float(speed.max()),
        v_avg_moving=float(speed[moving].mean()) if moving.any() else 0.0,
        n_stops=n_stops,
        fuel_L=fuel_L,
        consumption_L_100km=cons,
        gps_track=gps_track,
        warnings=warnings,
    )


def cycle_to_csv(speed_kmh: np.ndarray) -> str:
    """Serializează un vector de viteză în formatul CSV al ciclurilor din app
    (coloane: time_s, speed_kmh)."""
    n = len(speed_kmh)
    out = pd.DataFrame({"time_s": np.arange(n, dtype=int),
                        "speed_kmh": np.round(speed_kmh, 2)})
    return out.to_csv(index=False)


def _speed_color(v: float, v_max: float = 80.0) -> list[int]:
    """Culoare RGB pe gradientul albastru→verde→galben→roșu după viteză."""
    t = min(max(v / v_max, 0.0), 1.0)
    stops = [(24, 95, 165), (29, 158, 117), (239, 159, 39), (226, 75, 74)]
    seg = t * 3
    i = min(int(seg), 2)
    f = seg - i
    a, b = stops[i], stops[i + 1]
    return [int(a[k] + (b[k] - a[k]) * f) for k in range(3)]


def build_track_map(gps_track: dict):
    """Construiește un pydeck.Deck cu traseul GPS colorat după viteză, pe dale
    de hartă tip stradal (CARTO). Returnează None dacă pydeck lipsește."""
    try:
        import pydeck as pdk
    except ImportError:
        return None
    lat, lon, spd = gps_track["lat"], gps_track["lon"], gps_track["speed"]
    v_max = max(spd) if spd else 80.0
    segments = []
    for i in range(len(lat) - 1):
        if lat[i] == lat[i + 1] and lon[i] == lon[i + 1]:
            continue
        segments.append({
            "from": [lon[i], lat[i]], "to": [lon[i + 1], lat[i + 1]],
            "color": _speed_color((spd[i] + spd[i + 1]) / 2, v_max),
            "speed": round((spd[i] + spd[i + 1]) / 2, 1),
        })
    endpoints = [
        {"pos": [lon[0], lat[0]], "color": [29, 158, 117], "name": "Start"},
        {"pos": [lon[-1], lat[-1]], "color": [226, 75, 74], "name": "Sfârșit"},
    ]
    line_layer = pdk.Layer(
        "LineLayer", data=segments, get_source_position="from",
        get_target_position="to", get_color="color", get_width=4,
        pickable=True, width_min_pixels=3)
    point_layer = pdk.Layer(
        "ScatterplotLayer", data=endpoints, get_position="pos",
        get_fill_color="color", get_radius=40, radius_min_pixels=6,
        pickable=True)
    view = pdk.ViewState(latitude=sum(lat) / len(lat),
                         longitude=sum(lon) / len(lon), zoom=12)
    return pdk.Deck(
        layers=[line_layer, point_layer], initial_view_state=view,
        map_provider="carto", map_style="light",
        tooltip={"text": "{name}{speed} km/h"})
