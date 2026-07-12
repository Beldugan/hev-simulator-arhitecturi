# Changelog — v56

## Rezolvat

- **Suprapunere titlu/legendă în raportul PDF generat — 4 grafice
  corectate.** Graficele matplotlib din raportul PDF (complet separate,
  ca implementare, de graficele Plotly din aplicația web — nu foloseau
  aceeași funcție și nu beneficiaseră de corecțiile aplicate anterior
  interfeței web) aveau legenda poziționată prea aproape de titlu,
  suprapunându-se parțial peste el:
  - „Consumul pe arhitecturi și cicluri"
  - „Emisiile de CO₂ pe arhitecturi și cicluri"
  - „Fracțiunea de timp cu motorul termic oprit"

  Toate trei folosesc aceeași funcție internă (`_bars_chart`), la care
  titlul și legenda au fost repoziționate explicit (titlu la y=1.22,
  legendă la y=1.09, în coordonate relative la grafic), verificat
  programatic (măsurarea directă a dreptunghiurilor de randare
  matplotlib) că nu se mai suprapun, la orice combinație realistă de
  arhitecturi/cicluri.

  - „Defalcarea costului total de proprietate" folosea o legendă cu
    poziție AUTOMATĂ („cea mai bună" poziție liberă, aleasă de
    matplotlib) — instabilă pe date reale, ajungând uneori peste bare
    sau peste etichetele axei X. Repoziționată explicit, deasupra
    graficului (aceeași tehnică), pe un singur rând (5 coloane), fără
    să se mai suprapună nici cu titlul, nici cu etichetele de sumă
    totală (€) afișate deasupra fiecărei bare.

- **Verificare completă a întregului raport PDF.** S-au verificat
  programatic (nu doar vizual) TOATE graficele matplotlib generate în
  raport — traiectoriile SoC, profilul de putere, harta BSFC, diagrama
  tornado (analiza de sensibilitate), derularea finală (3 panouri),
  harta traseului GPS — pentru suprapuneri între titlu/legendă/sub-titluri
  ale sub-graficelor. Niciunul dintre celelalte grafice nu prezenta
  suprapuneri.

## Verificare

- `python3 -m py_compile src/pdf_export.py` — OK.
- `pytest tests/` — 60 passed, 3 subtests passed (inclusiv
  `test_pdf_export.py`).
- Verificare programatică suplimentară: pentru fiecare funcție de grafic
  din `pdf_export.py`, s-au extras dreptunghiurile de randare reale
  (matplotlib `get_window_extent()`) pentru titlu, legendă, sub-titluri
  și bare/etichete, verificând absența oricărei suprapuneri — rulat cu
  date provenite dintr-o simulare reală (nu doar valori sintetice), pe
  toate cele 4 arhitecturi și 5 cicluri de testare.
- Verificare vizuală: graficele corectate au fost regenerate ca imagini
  PNG independente și inspectate direct — titlul și legenda apar acum
  clar separate, pe rânduri distincte, fără nicio suprapunere de text.
