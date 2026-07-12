# Changelog — v51

## Rezolvat

### Suprapunere titlu/legendă pe grafice Plotly (bug structural, root-cause)

Toate funcțiile din `src/visualizations.py` care setau `legend=dict(...)` ÎNAINTE de
apelul `return _grid(fig)` aveau acea setare complet ignorată: `_grid()` suprascrie
necondiționat `legend` și `margin` la finalul fiecărei figuri (fixându-le sub grafic,
`y=-0.16`). Acest bug fusese identificat și corectat parțial într-o versiune anterioară
doar pentru graficul de consum (`plot_consumption_bars`); în v51 a fost corectat
consecvent pe toate graficele afectate, plus recalibrată poziția exactă a legendei
(verificată live, pixel cu pixel, pe aplicația deployată) astfel încât să nu se mai
suprapună cu titlul:

- **`plot_consumption_bars`** — "Consum pe arhitecturi și cicluri": legenda muta
  deasupra graficului, dar la o distanță insuficientă de titlu (se suprapuneau parțial).
  Recalibrat la `legend.y=1.17, yanchor="top", margin.t=90` — gol curat de ~9px între
  titlu și legendă.
- **`plot_soc_trajectory`** — "Evoluția stării de încărcare (SoC)": legenda era încă sub
  grafic (bug-ul nu fusese corectat până acum pentru acest grafic). Mutată deasupra
  graficului, cu aceeași reordonare `_grid()` → override legendă/margine.
- **`plot_bsfc_map`** — "Harta consumului specific (BSFC)": aceeași corecție.
- **`plot_tco_breakdown`** — "Defalcarea costului total de proprietate": aceeași corecție.
- **`plot_sensitivity_tornado`** — "Analiza de sensibilitate": aceeași corecție.
- **`plot_vehicle_comparison`** — "Comparație vehicul A vs vehicul B": aceeași corecție.

Tipar aplicat consecvent: `fig = _grid(fig)` este apelat ÎNTÂI, apoi `legend`/`margin`
sunt suprascrise explicit DUPĂ, astfel încât override-ul să nu mai fie anulat.

## Verificare

- `python3 -m py_compile src/visualizations.py` — OK.
- `pytest tests/` — 60 passed, 3 subtests passed.
- Verificare live pe aplicația deployată (simhev.streamlit.app), prin manipulare directă
  a obiectului Plotly (`Plotly.relayout`) și măsurare `getBoundingClientRect()` pentru
  titlu și legendă — confirmat fără suprapunere pe graficele de consum și SoC.
