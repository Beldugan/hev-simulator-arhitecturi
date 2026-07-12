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
