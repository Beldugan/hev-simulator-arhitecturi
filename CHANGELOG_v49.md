# CHANGELOG v49

## 1. Legendă mutată deasupra graficului — "Consum pe arhitecturi și cicluri"
Root cause real (descoperit prin inspecție directă a `fig.layout` după construcție): funcția helper comună `_grid()`, apelată la finalul FIECĂREI funcții de grafic (`return _grid(fig)`), suprascrie necondiționat legenda și marginile figurii, fixând-o SUB grafic (`y=-0.16`) — orice setare de legendă făcută ÎNAINTE de acest apel era complet ignorată. De-aia încercarea anterioară de a muta legenda deasupra (din v46) nu avusese niciun efect vizibil.

Corectat prin reordonare: `_grid(fig)` este acum apelat ÎNTÂI, iar poziționarea explicită a legendei (deasupra graficului, `yanchor="bottom", y=1.08`, ancorată de marginea ei de jos ca să nu alunece spre etichetele înclinate ale axei X) este aplicată DUPĂ, ca ultimă suprascriere. Mărită și înălțimea totală a graficului (480px) și marginea de sus, ca titlul + legenda să aibă loc separat de grafic.

## 2. Legendă mutată deasupra graficului — redarea LIVE a ciclului
Aceeași cerere, grafic diferit (`plot_cycle_live`): legenda era poziționată explicit SUB grafic (`y=-0.40`), sub eticheta axei X „Timp [s]" — exact suprapunerea din captura primită. Mutată deasupra, imediat sub titlu, ancorată de marginea ei de SUS (`yanchor="top", y=0.93`), între titlu (`y=0.98`) și zona de plotare — verificat structural (fără să se suprapună nici cu titlul, nici cu graficul).

## 3. Logo aplicație (înlocuiește titlul text din bara laterală)
Textul „Simulator al arhitecturilor de propulsie hibridă" a fost înlocuit cu logo-ul aplicației (`assets/logo_hybrid.png`), afișat cu `st.image(..., use_container_width=True)` în capul barei laterale.

Notă privind proveniența fișierului: imaginea logo-ului trimisă în conversație nu a putut fi extrasă ca fișier binar (mediul de chat nu a livrat-o ca atașament accesibil pe disc, doar ca imagine inline vizibilă). Logo-ul a fost recreat ca vector SVG, cât mai fidel imaginii originale (siluetă mașină + pictogramă baterie-conector-motor-roată pe linia de forță + wordmark „HYBRID / POWERTRAIN SIMULATOR", aceeași paletă navy/verde/albastru), apoi convertit în PNG cu fundal transparent. Dacă fișierul original e disponibil ca atașament real într-o conversație viitoare, poate înlocui direct `assets/logo_hybrid.png` (păstrând numele fișierului, restul codului nu necesită nicio modificare).

## 4. Logo aplicație și în raportul PDF, sub logo-ul AR
Pe prima pagină a raportului PDF, `assets/logo_hybrid.png` este desenat imediat sub logo-ul AR existent, cu aceeași lățime (3 cm, identică cu logo-ul AR) și un gap mic (0,2 cm) între ele.

Bug găsit și corectat în timpul verificării: forțarea logo-ului (care e lat, nu pătrat ca cel AR) într-o cutie pătrată 3×3 cm cu `preserveAspectRatio=True` producea un „letterboxing" — ReportLab îl scala după lățime și lăsa un gol vertical mult mai mare decât gap-ul dorit în cutie (confirmat exact prin generarea unui PDF real și măsurarea poziției imaginii cu `pdfplumber`: gol de facto ~1 cm în loc de 0,2 cm). Corectat calculând înălțimea reală din raportul de aspect al fișierului (lățime = 3 cm, ca logo-ul AR; înălțimea rezultă din proporțiile logo-ului) și poziționând manual imaginea, fără cutie irosită.

Paragraful introductiv de pe prima pagină („Acest raport a fost generat automat...") avea anterior lățime completă (fără rezervă pentru cele două logo-uri stivuite) — i s-a adăugat un stil dedicat cu `rightIndent` (aceeași rezervă orizontală ca titlul/subtitlul), ca nicio linie să nu ajungă sub zona logo-urilor.

## Verificare
- `py_compile` — OK.
- Suită completă de teste: `60 passed, 3 subtests passed` (inclusiv cele 2 teste de generare PDF).
- Verificare structurală directă a `fig.layout.legend`/`margin`/`height` pentru ambele grafice corectate — confirmă poziționarea corectă.
- Generat un PDF real (independent de teste) și inspectat cu `pdfplumber`: poziția exactă a celor 2 imagini + a tuturor liniilor de text de pe prima pagină confirmă zero suprapunere (gap orizontal de minim 23pt/0,8cm între text și logo-uri, gap vertical între cele 2 logo-uri de 5,7pt ≈ 0,2cm, exact cât s-a cerut).
