# CHANGELOG v50

## 1. Logo simplificat — doar text, centrat
Logo-ul din bara laterală a fost simplificat: eliminat desenul (siluetă mașină + pictogramă baterie-conector-motor-roată), rămâne doar wordmark-ul „HYBRID" (bleumarin, bold) / „POWERTRAIN" (verde) „SIMULATOR" (bleumarin), aceeași paletă de culori, centrat.

## 2. Suprapunere box explicativ SoC peste graficul de redare live
Root cause real, confirmat prin inspecție live pe aplicația publicată: `.chart-hover-box`/`.cycle-hover-box` foloseau `position: fixed`, ceea ce le poziționează relativ la FEREASTRĂ, nu la PAGINĂ. Pe o pagină lungă, cu mai multe grafice răsfirate pe verticală (consum, SoC, redare live, putere, BSFC, TCO), asta înseamnă că boxul apărea mereu la aceeași poziție din ecran, indiferent unde era derulată pagina în momentul hover-ului — dacă utilizatorul deschidea explicația SoC în timp ce avea graficul de redare live vizibil pe ecran (fiindcă derulase mai jos), boxul SoC apărea peste graficul de redare live, nu peste propriul grafic.

Corectat prin trecerea la `position: absolute`, ancorat local:
- pentru graficele de consum/SoC (aflate în 2 coloane), ancora e rândul întreg (`stHorizontalBlock`, făcut `position: relative`), ca boxul să rămână centrat pe tot rândul;
- pentru celelalte (ciclu, redare live, putere, BSFC, TCO — layout pe o coloană), ancora e propriul container al fiecărui marcaj/box.

Astfel boxul scrolează natural, împreună cu restul conținutului, și apare mereu lângă propriul grafic, nu la o poziție fixă din fereastră. Verificat live, cu Chrome conectat direct la aplicația publicată: am rulat o simulare reală, am derulat la graficul SoC și am declanșat hover-ul — boxul apare acum exact peste rândul cu cele două grafice (consum + SoC), nu mai departe pe pagină.

## 3. Legendă deasupra graficului (verificare, nu modificare nouă)
Fix-ul din v49 (legenda „Consum pe arhitecturi și cicluri" și cea de la redarea live, mutate deasupra graficului) a fost reconfirmat ca funcțional, direct pe aplicația publicată — legenda apare corect deasupra, fără suprapunere cu etichetele axei X.

## 4. Raport PDF: logo eliminat, titlu înlocuit cu grafica din logo
La cerere, logo-ul aplicației (adăugat în v49 sub logo-ul AR) a fost eliminat din raportul PDF — rămâne doar logo-ul AR, ca înainte de v49.

Titlul de pe prima pagină, „Raport de simulare — Arhitecturi de propulsie hibridă", a fost înlocuit cu exact grafica textului din logo: „HYBRID" (bleumarin, bold, font mare) urmat de „POWERTRAIN" (verde) „SIMULATOR" (bleumarin), aceleași două tonuri ca în logo.

## Verificare
- `py_compile` — OK.
- Suită completă de teste: `60 passed, 3 subtests passed`.
- PDF generat real și inspectat cu `pdfplumber`: confirmat un singur logo pe prima pagină (AR) și titlul nou, cu textul „HYBRID" / „POWERTRAIN SIMULATOR" pe cele două linii așteptate.
- Fix-ul de poziționare a boxului SoC verificat LIVE, cu Chrome conectat la aplicația publicată, cu simulare reală rulată: box-ul apare corect lângă propriul grafic, indiferent de poziția de derulare a paginii.
