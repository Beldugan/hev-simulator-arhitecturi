# Modificări v38 → v39

Versiune de corecții, pe baza unui review de cod. Nu schimbă logica de
simulare (rezultatele fizice rămân identice) — doar robustețea, securitatea
și claritatea mesajelor din interfață.

## Corecții de cod

1. **Teste noi** pentru `analysis.py`, `tco_model.py`, `obd_import.py`,
   `pdf_export.py`, `visualizations.py` (înainte, doar `vehicle_model.py`/
   `ems_strategies.py` erau acoperite). Suita completă: 54 de teste.
2. **Export PDF**: generarea raportului este acum încadrată în `try/except`
   în `app.py` — la eroare, utilizatorul vede un mesaj clar în loc de un
   traceback Python brut.
3. **Securitate (SSRF)**: `load_external_params()` din `app.py` validează
   URL-ul introdus de utilizator (doar http/https, blochează adrese
   private/loopback/link-local) înainte de a-l accesa.
4. **Nominatim (geocodare trasee GPS)**: `_reverse_geocode()` din
   `pdf_export.py` respectă acum limita de 1 cerere/secundă a OpenStreetMap
   (throttling) și memorează rezultatele deja cerute (cache).
5. **`ems_strategies.simulate()`**: gardă explicită pentru cicluri cu mai
   puțin de 2 eșantioane — ridică o eroare clară în loc de o excepție
   internă neclară (împărțire la zero / `np.gradient` eșuat).
6. **Docstring corectat** în `vehicle_model.py` (nu mai pretinde greșit că
   modulul conține `simulate()` — funcția e în `ems_strategies.py`).
7. **Timpii DP reconciliați**: măsurați empiric (~1-2 s per combinație
   arhitectură-ciclu, ~10-20 s pentru o rulare completă) și actualizați
   consecvent în `app.py` și `ems_strategies.py`.
8. **`load_wltp_references()`**: ridică acum `FileNotFoundError` cu mesaj
   explicit dacă fișierul de referință lipsește, în loc de un `TypeError`
   neclar.
9. **`pdf_export.py`**: erorile la înregistrarea fonturilor / desenarea
   logo-ului nu mai sunt înghițite silențios — se loghează un avertisment
   (`logging.warning`), fără să oprească generarea raportului.

## Claritate a mesajelor pentru utilizator

- Caseta de informare pentru strategia DP explică pe scurt metoda (fără
  jargon „PMP-shooting" neexplicat) și avertizează că se recalculează
  TOATE arhitecturile/ciclurile.
- Explicația termenului „charge-sustaining" e completă la prima apariție
  (caption PHEV din bara laterală).
- Secțiunea „Despre ciclul selectat" nu mai apare goală pentru trasee GPS
  importate de utilizator — are acum o descriere generică, cu statistici.
- Mesajele de eroare la fișier/URL/log neinterpretabil sunt reformulate în
  română, prietenos, cu detaliul tehnic brut păstrat ca linie secundară.
- Captions PHEV/MHEV încep cu o concluzie pe scurt, îngroșată, urmată de
  detaliul tehnic.
- Caption-ul de sensibilitate precizează că ±20% e un interval fix,
  neconfigurabil din interfață.
