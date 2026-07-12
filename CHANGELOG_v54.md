# Changelog — v54

## Adăugat

- Casetă verde de interpretare (aceeași tehnică hover ca la celelalte
  grafice) pentru cele două diagrame tornado din secțiunea „Analiza de
  sensibilitate" (Consum și TCO), care apare la trecerea cursorului peste
  fiecare grafic și explică de ce culoarea barei (albastru = parametru
  −20%, portocaliu = parametru +20%) nu corespunde întotdeauna aceleiași
  părți a axei — pentru randamentul termic al motorului și randamentul
  transmisiei, relația e inversă (creșterea randamentului reduce
  consumul/costul), motiv pentru care barele lor apar „în oglindă" față
  de ceilalți parametri.

## Rezolvat

- Eticheta de la selectorul vitezei de derulare a animației (grafic
  „Derularea temporală animată") a fost eliminată împreună cu semnul
  „?" aferent (tooltip help), textul explicativ redundant de sub selector.
- **Poziționarea casetelor de interpretare de la grafice — corecție
  structurală.** Casetele de la graficele de Consum și SoC (2 coloane)
  apăreau, pe ferestre mai puțin înalte, mult sub grafic, suprapunându-se
  peste conținutul de dedesubt (expanderele următoare) și ieșind parțial
  din zona vizibilă. Cauza: erau ancorate la centrul întregului rând
  (2 coloane), poziționare moștenită dintr-o corecție anterioară.
  Rezolvat prin reancorare pe granița dintre cele două coloane — caseta
  graficului din stânga (Consum) se extinde spre dreapta, cea din
  dreapta (SoC) spre stânga — astfel încât fiecare casetă nu mai acoperă
  NICIODATĂ propriul grafic, rămânând complet vizibilă indiferent de
  înălțimea ferestrei. Aceeași corecție a fost aplicată și celor două
  casete verzi noi de la analiza de sensibilitate.
- Casetele de interpretare de la graficele pe o singură coloană (redare
  live, profil de putere, hartă BSFC, defalcare TCO) foloseau aceeași
  poziționare suprapusă peste grafic (deasupra, centrată), acoperind o
  parte semnificativă a graficului explicat. Nemaiavând coloană alăturată
  în care să se „reverse" lateral, au fost mutate în flux normal, IMEDIAT
  SUB grafic, astfel încât graficul rămâne mereu complet vizibil, iar
  textul apare imediat lângă el, fără suprapunere.

## Verificare

- `python3 -m py_compile app.py` — OK.
- `pytest tests/` — 60 passed, 3 subtests passed.
- Poziționare verificată live pe aplicația deployată (simhev.streamlit.app),
  prin injectare temporară a noilor reguli CSS și măsurare
  `getBoundingClientRect()` pentru grafic vs. casetă — confirmat: nicio
  casetă nu se mai suprapune peste propriul grafic, toate rămân în
  interiorul ferestrei vizibile.
