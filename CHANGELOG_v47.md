# CHANGELOG v46

## 1. Carduri metrici (pagina Simulare)
- Cardul 1 redenumit: "Consum de combustibil înregistrat de arhitectura de referință WLTC [L/100km]".
- Cardul 2 (Paralel · WLTC) eliminat; layout trecut de la 4 la 3 coloane egale.
- Cardul "Configurația optimă" a primit un al doilea metric: "Consumul înregistrat WLTC [L/100km]".
- Fix real: arhitectura optimă era hardcodată la "paralel"; acum se calculează dinamic (`min` peste toate arhitecturile, exclusiv referința).
- Fix real: săgeata de variație procentuală folosea un semn minus Unicode decorativ (mereu interpretat ca pozitiv de Streamlit → săgeată sus, verde, indiferent de sens). Acum se calculează un procent semnat real, formatat cu semn ASCII (`f"{pct:+.1f}%"`) + `delta_color="inverse"` → jos/verde pentru scădere reală, sus/roșu pentru creștere reală.

## 2. Hover-uri explicative pe titlurile de grafice
- "Consum pe arhitecturi și cicluri" și "Evoluția stării de încărcare (SoC)": box centrat, text cursiv fără acronime, apare la hover pe titlu.

## 3. Redenumire globală
- „Baseline" → „Referință" peste tot (sursă centrală: `ARCH_LABELS` din `ems_strategies.py`, propagat automat în sidebar, PDF, comparații, sensibilitate, validare).
- „MCI" → „MAI" peste tot în UI, grafice și export PDF.
- Bug auto-descoperit și corectat: filtrul din `pdf_export.py` verifica `"Baseline" not in ...`; după redenumire ar fi rămas mereu adevărat și ar fi inclus greșit rândul de referință. Corectat la `"Referință" not in ...`.
- Bug auto-descoperit și corectat: `plot_consumption_bars` și `plot_soc_trajectory` din `visualizations.py` generau eticheta din legendă direct din cheia internă (`arch.replace("_","-").title()`), ocolind `ARCH_LABELS` — „Baseline" ar fi rămas vizibil în grafice. Corectat să folosească `ARCH_LABELS`.
- Bug suplimentar găsit la verificarea finală (nu fusese semnalat): `plot_tco_breakdown` avea exact aceeași problemă pe axa X (etichetele arhitecturilor în graficul TCO) — corectat identic.

## 4. Box informații ciclu selectat
- Tot conținutul din "Despre ciclul selectat" (descriere + 4 metrici + linia de staționare) mutat într-un box cu fundal alb, afișat central la hover pe selectorul "Ciclul". Harta GPS a traseului rămâne mereu vizibilă (element interactiv, nu text static).

## 5. Control viteză redare
- Convertit din buton click-to-cycle într-un meniu dropdown; explicația la hover a rămas neschimbată.

## 6. Box explicativ redare live
- Caption-ul permanent de sub graficul de redare eliminat; apare acum doar la hover pe butonul Play, într-un box alb, cu text nou:
  "Apăsați ▶ Redă pentru derularea în timp: banda roșie = motorul termic pornit, banda verde = rulare electrică; triunghiurile marchează pornirile MAI. Rândul 2: consumul de combustibil și CO₂ cumulate; rândul 3: starea de încărcare a bateriei. Cursorul de jos permite saltul la orice moment."

## 7. Secțiune putere/BSFC
- Titlul "Profilul de putere și harta BSFC" redenumit "Profilul de putere", scris cu același font-size ca "Harta consumului specific (BSFC)".
- Hover pe "Profilul de putere": interpretare pe scurt a celor 3 grafice, cu titluri actualizate — "Profil de viteză" → "Viteza de deplasare", "Putere MCI și mașina electrică" → "Putere MAI și motor electric", "Flux de putere prin baterie" (neschimbat).

## 8. Hartă BSFC
- Hover pe "Harta consumului specific (BSFC)": box alb cu interpretarea graficului.

## 9. TCO
- Hover pe "Defalcarea costului total de proprietate (10 ani)": box cu interpretare.
- Textul break-even schimbat din "Break-even Paralel vs Baseline: ..." în "Pragul de rentabilitate hibrid în configurație paralel vs. vehicul de referință: ..." (cifrele calculate dinamic rămân).

## 10. Notă PHEV
- Text înlocuit cu varianta nouă, mai detaliată, care menționează explicit Utility Factor (UF) și regimul charge-sustaining (CS).

## 11. Footer
- Text nou: "Aplicația utilizează un model de simulare cvasi-static de tip backward-forward și ciclul de conducere WLTC definit de UNECE GTR No. 15. Codul sursă este distribuit sub licența MIT. © 2026 A.M. Beldugan, Facultatea de Inginerie Mecanică Industrială și Maritimă, Universitatea Ovidius din Constanța."

## Fix-uri suplimentare cerute în aceeași sesiune
- Suprapunerea etichetelor de pe axa X din graficul de consum ("Real urban" / "Real mixt") rezolvată prin înclinarea etichetelor (`tickangle=-25`) și mărirea marginii de jos.
- Expander-ul "Traseul real (OBD II/Torque)" mutat imediat sub "Parametrii economici" în sidebar.

## Metodologie de verificare
- `py_compile` pe toate fișierele modificate.
- Suită completă de teste: `60 passed, 3 subtests passed`.
- Apeluri directe (unit-level) ale funcțiilor de grafic pentru a confirma titluri/legende corecte, inclusiv verificarea explicită că "Baseline" nu mai apare în niciun grafic (consum, SoC, TCO).
- Audit de auto-consistență marker/regulă CSS/clasă țintă pentru toate cele 9 box-uri noi de hover (perechi unice confirmate prin grep).
- Notă onestă: spre deosebire de v43–v45, box-urile noi de hover din acest batch NU au fost verificate live într-un browser real (Chrome DevTools) pe aplicația deployată, deoarece site-ul live nu reflectă încă aceste modificări și volumul de schimbări a depășit timpul disponibil pentru reproducere sintetică completă. Tehnica CSS de hover în sine a fost însă validată live, repetat, în rundele anterioare din această sesiune.
- Segfault-ul cunoscut la `AppTest` pentru "Rulează simularea" este o limitare preexistentă a mediului sandbox (reprodusă identic și pe versiunea v43 nemodificată), nu o regresie introdusă în acest batch.

---

# CHANGELOG v47 (adăugiri peste v46)

## 1. Fuzionare carduri "Configurația optimă" / "Consumul înregistrat WLTC"
- Cele două `st.metric()` din a doua coloană produceau două cutii albe separate, suprapuse vizual. Înlocuite cu un singur card HTML custom, cu ambele informații în interior (etichetă+valoare pentru configurație, apoi o linie despărțitoare subțire, apoi etichetă+valoare+pastilă de variație procentuală).
- Cardul reutilizează exact hook-urile CSS existente (`data-testid="stMetric"` / `data-testid="stMetricValue"`) ca să rămână identic vizual cu restul cardurilor și compatibil automat cu tema întunecată (fără culori de text hardcodate care s-ar fi pierdut în modul dark).
- Pastila de variație procentuală (verde+săgeată jos pentru scădere reală, roșu+săgeată sus pentru creștere reală) e construită manual din numărul semnat real, păstrând exact aceeași semantică `delta_color="inverse"` stabilită anterior.

## 2. Eliminare spațiu gol în bara laterală (între Strategie și Parametrii vehiculului)
- Cauza reală: fiecare box de hover și fiecare marcaj invizibil (`.anchor-*-q`) este randat de Streamlit într-un container propriu, iar Streamlit aplică un "gap" de layout între containere indiferent dacă interiorul lor e vizibil (display:none) sau poziționat fix — de-aia cele 3 box-uri de explicație ale strategiilor lăsau un gol vizibil deasupra "Parametrii vehiculului", deși ele nu se văd niciodată acolo.
- Fix: toate containerele care înfășoară exclusiv un asemenea marcaj/box invizibil au fost scoase complet din calculul de layout cu `display:contents`, tehnică ce nu afectează deloc funcționarea hover-urilor (elementele poziționate fix ies oricum din flux) și nu strică regulile CSS bazate pe frați (`+`/`~`), care depind de structura DOM, nu de randare.
- Aceeași corecție elimină golurile similare de sub toate celelalte 8 marcaje/box-uri de hover din aplicație (Variantă, OBD, Ciclu, cele 2 grafice de consum/SoC, redare live, putere/BSFC, TCO), nu doar cazul semnalat explicit.

## 3. Sweep final MCI → MAI
- Ultimele 2 apariții rămase (comentarii interne în `tools/verify_eea.py`, instrument de verificare tehnică, neafișat în UI) au fost și ele înlocuite, la cererea explicită de a acoperi absolut toate aparițiile din cod. Confirmat prin grep: zero apariții „MCI" în tot repository-ul.

## Verificare
- `py_compile` pe toate fișierele modificate — OK.
- Suită completă de teste: `60 passed, 3 subtests passed`.
- `grep -rn "MCI"` pe tot proiectul — niciun rezultat.

## 4. Suprapunere box explicativ peste graficele de consum/SoC (la retragerea meniului)
- Cauza reală: `.chart-hover-box` (folosit de box-urile de la "Consum pe arhitecturi și cicluri" și "Evoluția SoC") se centrează la 50% din LĂȚIMEA FERESTREI, nu din conținutul principal. Cele două grafice stau unul lângă altul, în două coloane. Cu bara laterală deschisă, cele două coloane sunt împinse spre dreapta și centrul ferestrei cade în afara lor — dar la retragerea barei laterale, conținutul principal ocupă toată fereastra, iar centrul acesteia ajunge exact pe granița dintre cele două coloane; boxul, fiind mai îngust decât rândul întreg, acoperea doar parțial fiecare grafic, lăsând marginile lor vizibile în jurul lui (exact suprapunerea din captura primită).
- Fix: `.chart-hover-box` a fost lățit (de la 560px la ~1100px/96vw) ca să acopere mereu, complet, tot rândul cu cele două grafice, indiferent de starea barei laterale — nu mai rămân porțiuni de grafic vizibile pe lângă box.

## 4. Rescriere academică a textelor din aplicație
La cerere, toate textele explicative din aplicație (descrierile celor 3 strategii EMS, descrierea vehiculului/tipului de electrificare din boxul „Variantă", cele 5 descrieri din meniul de navigare, caption-ul de upload OBD-II și mesajele de succes/avertizare aferente, descrierea ciclului selectat, interpretările celor 6 grafice — consum, SoC, redare live, putere, BSFC, TCO —, secțiunile Sensibilitate/Comparație A-B/Validare/Export PDF și mesajele lor) au fost rescrise într-un registru academic, impersonal, adecvat unei lucrări de disertație sau unui articol științific (construcții de tipul „Figura ilustrează...", „Reprezentarea permite identificarea...", evitând formulările colocviale de tip „arată", „ca să se vadă dintr-o privire", persoana a II-a).

Etichetele scurte, funcționale ale interfeței — nume de butoane, opțiuni de dropdown, capete de coloană cu unități de măsură, denumiri de pagini din meniu — au fost păstrate concise, conform convenției standard pentru tabele și formulare într-o lucrare științifică (transformarea lor în propoziții complete ar fi afectat lizibilitatea interfeței). Titlurile de secțiune au fost, acolo unde a fost cazul, ușor reformulate într-un registru mai formal.

Textul din boxul de interpretare a graficului de consum a fost înlocuit cu formularea exactă furnizată.

S-a corectat și un test din suita existentă (`test_vehicle_popover_all_types`) care verifica un fragment literal din vechiul text al notei PHEV, actualizat să reflecte noua formulare academică.

## 5. Verificare finală MCI → MAI
Confirmat, printr-o nouă căutare exhaustivă, că nu mai există nicio apariție a acronimului „MCI" în tot codul sursă (app.py, src/, tools/).

## Verificare
- `py_compile` pe toate fișierele — OK.
- Suită completă de teste: `60 passed, 3 subtests passed`.
