# ⚡ HEV Architecture Simulator

Aplicație open-source pentru analiza comparativă a configurațiilor de propulsie
hibridă (**serie**, **paralel**, **serie-paralel**) pe o platformă comună de
vehicul C-SUV: consum de combustibil, emisii CO₂, cost total de proprietate (TCO),
analiză de sensibilitate, validare fizică și audit al datelor față de sursele
oficiale UE.

Însoțește lucrarea de disertație:
> **Analiza comparativă a configurațiilor de propulsie hibridă (serie, paralel,
> serie-paralel) pentru un vehicul de clasă C-SUV**
> Adrian Mircea Beldugan — FIMIM, Universitatea Ovidius din Constanța, 2026.
> Studiu de caz: **Dacia Bigster Hybrid 155**.

---

## Funcționalități

- **Simulare** pe 4 arhitecturi (baseline · serie · paralel · serie-paralel) ×
  5 cicluri, cu 3 strategii de management energetic: **Rule-Based**, **ECMS** și
  **benchmark optim PMP/DP**.
- **Cicluri de conducere**: WLTC (omologare UE) și UDDS · HWFET (proceduri EPA,
  cicluri oficiale NREL/FASTSim), plus **două trasee reale** înregistrate prin
  OBD-II în zona Constanța–Năvodari (urban și mixt). Se pot importa trasee proprii
  din loguri Torque.
- **Bază de date de 250 de vehicule** electrificate de pe piața UE (HEV/PHEV/MHEV,
  31 de mărci), selectabile după marcă → model → variantă, cu topologia reală și
  valorile oficiale WLTP.
- **Grafice interactive** (Plotly): consum comparativ, traiectorii SoC, profiluri
  de putere MCI/EM/baterie, hărți BSFC cu puncte de operare, **derulare LIVE
  animată** a ciclului (timp real → 30×) și **hartă a traseului** real (tip
  Google Maps) colorată după viteză.
- **Analiză de sensibilitate completă**: 8 parametri fizici + 4 economici,
  variație ±20%, diagrame tornado pe consum și TCO.
- **Comparație vehicul-la-vehicul (A/B)** pe aceleași condiții.
- **Validare fizică automată**: verificări per simulare (SoC în fereastră, puteri
  sub limite, bilanț energetic, plauzibilitatea consumului).
- **Audit al bazei de date** față de setul EEA de monitorizare CO₂ (Reg. UE
  2019/631): abateri de masă/putere/CO₂ față de mediana oficială, cu status
  per vehicul.
- **Export PDF complet**: selectezi ciclurile incluse; tabele + grafice per ciclu
  (SoC, putere, BSFC) + hărți de traseu + validare + audit EEA + interpretări
  automate, fiecare capitol pe pagină nouă.
- **Temă luminoasă / întunecată** (stil iOS), comutabilă din colțul dreapta-sus.
- **Patru moduri de intrare**: preset Bigster · bază de date (marcă → model) ·
  introducere manuală · fișier/URL.

## Instalare și pornire

```bash
pip install -r requirements.txt
streamlit run app.py          # interfața web completă
python demo.py                # verificare rapidă în linie de comandă
```

Ghidul complet de utilizare (PDF, cu capturi de ecran):
[`docs/Ghid_utilizare.pdf`](docs/Ghid_utilizare.pdf) (și `.docx` editabil).

## Structura proiectului

```
hev_app_v2/
├── app.py                      # aplicația web (Streamlit, temă light/dark iOS)
├── demo.py                     # demonstrație CLI
├── requirements.txt · LICENSE · README.md
├── src/
│   ├── vehicle_model.py        # model fizic (Type Hints + docstrings complete)
│   ├── ems_strategies.py       # Rule-Based + ECMS + PMP/DP shooting
│   ├── tco_model.py            # TCO, break-even, comparație WLTP
│   ├── analysis.py             # sensibilitate + validare fizică
│   ├── visualizations.py       # grafice Plotly + derulare LIVE + hartă traseu
│   ├── obd_import.py           # import trasee reale OBD-II/Torque (1 Hz, hartă)
│   └── pdf_export.py           # raport PDF complet (reportlab)
├── data/
│   ├── wltc_class3b_reference.csv   # WLTC oficial (rezervă; primar: biblioteca wltp)
│   ├── udds.csv · hwfet.csv         # cicluri EPA oficiale (NREL/FASTSim)
│   ├── real_urban_constanta.csv     # traseu real urban (OBD-II) + _track.json
│   ├── real_mixt_constanta.csv      # traseu real mixt (OBD-II) + _track.json
│   ├── vehicles_db.csv              # 250 vehicule electrificate UE
│   ├── eea_verification_report.csv  # raportul de audit EEA (generat local)
│   └── wltp_references.json          # valori WLTP citate (editabil)
├── tools/
│   └── verify_eea.py           # audit al bazei de date contra setului EEA
├── tests/
│   ├── test_engine.py          # teste unitare — model fizic + simulare
│   ├── test_analysis.py        # sensibilitate + validare fizică
│   ├── test_tco_model.py       # TCO, break-even, referințe WLTP
│   ├── test_obd_import.py      # import loguri Torque (OBD-II)
│   ├── test_visualizations.py  # statistici de ciclu, CYCLE_INFO, grafice
│   ├── test_pdf_export.py      # generare raport PDF (test de fum, cap-coadă)
│   └── test_app_ui.py          # interfața (AppTest) — popover-uri, etichete
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
(randament ≈0,86) la viteze mari, iar **seria** este penalizată de dubla conversie.

Valorile absolute de consum depind de calibrarea parametrilor (masă, aerodinamică,
randamente — unele estimate); comparația **relativă** între arhitecturi este însă
robustă, deoarece toate folosesc aceleași date de intrare.

## Baza de date de vehicule (`data/vehicles_db.csv`)

250 de vehicule electrificate de pe piața UE (84 HEV, 120 PHEV, 46 MHEV; 31 de
mărci), selectabile în aplicație din **Sursa datelor → Bază de date
(marcă → model)**. Câmpuri: masă în ordine de mers, Cd, Af, puteri MCI/EM,
capacitate baterie, preț de listă orientativ, CO₂ și consum WLTP oficiale,
topologia reală (serie / paralel / serie-paralel) și sursa per vehicul.

Valorile provin din fișele tehnice ale constructorilor; câmpurile care nu se
publică oficial (Cd·Af la unele modele, randamentul termic, CO₂ ponderat la unele
PHEV) sunt estimări de segment, marcate explicit în coloana `estimari`.

## Auditul EEA (`tools/verify_eea.py`)

Baza de date poate fi încrucișată cu setul oficial EEA de monitorizare a
emisiilor CO₂ (Regulamentul UE 2019/631), care raportează masa în ordine de mers,
puterea și CO₂ WLTP pentru vehiculele înmatriculate în UE.

```bash
# 1) descarcă setul EEA (filtrat pe Ft = petrol/electric, diesel/electric) de la
#    https://co2cars.apps.eea.europa.eu/
# 2) (opțional) inspectează coloanele:
python tools/verify_eea.py --eea <fișier_EEA.csv> --inspect
# 3) rulează auditul:
python tools/verify_eea.py --eea <fișier_EEA.csv>
```

Raportul se scrie în `data/eea_verification_report.csv` (abateri de masă/putere/CO₂
față de mediana EEA, cu status OK / de verificat / negăsit) și este afișat automat
în aplicație (pagina *Validare* și badge sub vehiculul selectat) și în raportul PDF
(secțiunea 7.3). Setul EEA are milioane de rânduri; scriptul îl citește pe bucăți,
detectează separatorul și denumirile de coloane automat și separă HEV de PHEV.

## Trasee reale (OBD-II / Torque)

Pe lângă ciclurile standard, aplicația include două trasee reale înregistrate prin
OBD-II în zona Constanța–Năvodari cu aplicația Torque: `Real urban (Constanța)`
(~13 km, regim urban) și `Real mixt (Constanța)` (~17 km, periurban). Sunt
reeșantionate la 1 Hz, cu staționările și pauzele de înregistrare decupate
(`src/obd_import.py`), iar traseul GPS se afișează pe hartă colorată după viteză.

Poți importa trasee proprii din bara laterală → „Traseu real (OBD-II / Torque)":
încarci logul CSV exportat din Torque, iar aplicația îl transformă în ciclu
selectabil și, dacă logul conține MAF, estimează și consumul real măsurat al
vehiculului — util pentru validarea configurației baseline a modelului. Traseele
importate ad-hoc sunt valabile doar în sesiunea curentă; cele două incluse sunt
permanente.

## Datele de comparație WLTP

Pentru presetul Bigster, valorile oficiale de referință se află în
`data/wltp_references.json`, fiecare cu sursă și dată de accesare. Pentru un
vehicul din baza de date, comparația se face automat cu propria valoare WLTP
oficială. Editarea fișierului JSON nu necesită modificarea codului.

## Testare

```bash
pip install pytest
pytest tests/            # rulează toate suitele (60 de teste)
# sau, fișier cu fișier, fără pytest:
cd tests && python3 test_engine.py
```

## Licență

[MIT](LICENSE) — © 2026 Adrian Mircea Beldugan.
