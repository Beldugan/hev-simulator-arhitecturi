# ⚡ HEV Architecture Simulator

Aplicație open-source pentru analiza comparativă a configurațiilor de propulsie
hibridă (**serie**, **paralel**, **serie-paralel**) pe o platformă comună de
vehicul C-SUV: consum de combustibil, emisii CO₂, cost total de proprietate (TCO),
analiză de sensibilitate și validare fizică.

Însoțește lucrarea de disertație:
> **Analiza comparativă a configurațiilor de propulsie hibridă (serie, paralel,
> serie-paralel) pentru un vehicul de clasă C-SUV**
> Adrian Mircea Beldugan — FIMIM, Universitatea Ovidius din Constanța, 2026.

---

## Funcționalități

- **Simulare** pe 4 arhitecturi × 3 cicluri (WLTC · UDDS · HWFET), cu 3 strategii
  de management energetic: **Rule-Based**, **ECMS** și **benchmark optim PMP/DP**
- **Grafice interactive** (Plotly): consum comparativ, traiectorii SoC, profiluri
  de putere MCI/EM/baterie, hărți BSFC cu puncte de operare
- **Analiză de sensibilitate completă**: 8 parametri fizici + 4 economici,
  variație ±20%, diagrame tornado pe consum și TCO
- **Comparație vehicul-la-vehicul (A/B)** pe aceleași condiții
- **Validare fizică automată**: 7 verificări per simulare (SoC, puteri, bilanț)
- **Export PDF complet**: tabele + grafice + validare + interpretări automate
- **Două moduri de intrare**: preset Bigster (parametrii lucrării) sau
  introducere manuală a parametrilor

## Instalare și pornire

```bash
pip install -r requirements.txt
streamlit run app.py          # interfața web completă
python demo.py                # verificare rapidă în linie de comandă
```

Ghidul complet de utilizare (PDF, cu capturi de ecran): [`docs/Ghid_utilizare.pdf (și .docx editabil)`](docs/Ghid_utilizare.pdf)

## Structura proiectului

```
hev_app_v2/
├── app.py                      # aplicația web (Streamlit, 5 module, design iOS light)
├── demo.py                     # demonstrație CLI
├── requirements.txt · LICENSE · README.md
├── src/
│   ├── vehicle_model.py        # model fizic (Type Hints + docstrings complete)
│   ├── ems_strategies.py       # Rule-Based + ECMS + PMP/DP shooting
│   ├── tco_model.py            # TCO, break-even, comparație WLTP
│   ├── analysis.py             # sensibilitate + validare fizică
│   ├── visualizations.py       # grafice Plotly profesionale
│   └── pdf_export.py           # raport PDF complet (reportlab)
├── data/
│   ├── wltc_class3b_reference.csv   # WLTC oficial (rezervă; primar: biblioteca wltp)
│   ├── udds.csv · hwfet.csv
│   └── wltp_references.json    # valori WLTP citate (editabil de utilizator)
├── tests/
│   └── test_engine.py          # 16 teste unitare
└── docs/
    ├── Ghid_utilizare.pdf      # ghid utilizator (docx + pdf, capturi reale)
    └── screenshots/
```

## Metodologie (pe scurt)

Model cvasi-static de tip *backward-forward* cu modelul liniei Willans pentru
consum. Strategia Rule-Based folosește reguli ierarhice cu histerezis; ECMS
minimizează consumul echivalent instantaneu cu factor adaptiv; benchmark-ul optim
folosește metoda **PMP-shooting** (căutare binară a factorului de echivalență
constant care închide bilanțul SoC — echivalent cu soluția Dynamic Programming
conform Principiului de Minim al lui Pontriaghin, dar numeric robust și rapid).

Ierarhia rezultatelor este consecventă cu literatura și cu lucrarea: arhitectura
**paralel** câștigă pe cicluri mixte prin cuplaj mecanic direct (randament ≈0,95),
în timp ce **serie-paralel** plătește pierderile buclei electrice MG1→baterie→MG2
(randament ≈0,86) la viteze mari.

## Testare

```bash
cd tests && python3 test_engine.py    # 16/16 PASS
```

## Datele de comparație WLTP

Valorile oficiale se află în `data/wltp_references.json`, fiecare cu sursă și
dată de accesare. Editați fișierul pentru a adăuga vehicule noi — nu e nevoie
de modificarea codului.

## Licență

[MIT](LICENSE) — © 2026 Adrian Mircea Beldugan.
