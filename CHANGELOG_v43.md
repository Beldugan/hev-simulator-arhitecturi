# Modificări v42 → v43

Eliminarea completă a butoanelor „?" pentru strategie și vehicul, înlocuite
cu afișare pe hover (fără niciun clic), plus eliminarea unui mesaj
redundant pentru „Programare dinamică".

## Ce s-a schimbat

1. **Strategia de management energetic** — nu mai există niciun buton „?"
   lângă dropdown. Explicația apare acum DOAR pentru strategia aflată sub
   cursor, în momentul în care dropdown-ul e deschis și utilizatorul trece
   cu mouse-ul peste una din cele 3 opțiuni — exact comportamentul cerut
   inițial, dar implementat robust (vezi nota tehnică).

2. **Variantă** (bază de date vehicule) — nu mai există niciun buton „?".
   Descrierea scurtă (tip/arhitectură/CO₂/sursă), auditul EEA și descrierea
   tipului de electrificare (PHEV/MHEV/HEV) au fost unificate într-un
   singur box verde, afișat la trecerea cursorului peste selectorul
   „Variantă" — nimic nu mai rămâne afișat implicit în bara laterală.
   Funcționează identic pentru toate vehiculele din bază.

3. S-a eliminat mesajul informativ care apărea sub dropdown când era
   selectată „Programare dinamică" ("...durează aproximativ 10-20 secunde
   în total...") — informația relevantă rămâne disponibilă în panoul de
   explicație al strategiei.

Panoul „Meniu" își păstrează butonul „?" (neschimbat, nu a fost menționat
de utilizator).

## Notă tehnică — de ce nu e simplu CSS „oricine ar scrie"

Am testat live pe aplicația publicată (simhev.streamlit.app) înainte de a
implementa, ca să evit o soluție care pare corectă dar nu funcționează
robust:

- Identificatorii generați automat de bibliotecă pentru opțiunile din
  dropdown (`id="bui17val-0"` etc.) **nu sunt stabili** — la o simplă
  reîncărcare a paginii, fără nicio schimbare de cod, id-ul s-a schimbat în
  `bui14val-0`. O regulă CSS bazată pe aceste id-uri s-ar fi stricat
  aleatoriu, uneori chiar de la prima încărcare a paginii.
- Soluția robustă pentru strategie: fiecare opțiune e identificată după
  POZIȚIE (1/2/3) în dropdown-ul deschis, dar condiționat explicit de
  faptul că strategia e cea deschisă în acel moment (verificat prin
  eticheta ei, stabilă: „Strategia de management energetic" cu
  `aria-expanded="true"`) — asta elimină riscul ca hover-ul pe alt dropdown
  (Marcă, Model, Meniu etc.) să afișeze greșit explicația de strategie, caz
  testat explicit și confirmat corect într-un browser real.
- Pentru „Variantă" regula de mai sus nu se aplică (nu are stare
  deschis/închis relevantă) — CSS nu permite un `:has()` imbricat în alt
  `:has()`, deci am folosit un marcaj invizibil pus chiar înaintea
  selectorului și combinatori de frați (`+`/`~`) pentru a lega hover-ul de
  box-ul corect, fără ambiguitate cu celelalte selectoare din bară.

Ambele soluții au fost verificate direct într-un browser real (Chrome),
simulând structura exactă găsită live, inclusiv testul explicit „hover pe
alt dropdown cu aceleași poziții de opțiuni NU declanșează greșit box-ul" —
nu doar presupuse teoretic.
