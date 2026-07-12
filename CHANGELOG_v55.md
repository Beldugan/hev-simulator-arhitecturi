# Changelog — v55

## Rezolvat

- **Simplificat radical poziționarea TUTUROR casetelor de interpretare.**
  Rundele anterioare (v54 și cele dinainte) au încercat variante din ce
  în ce mai elaborate — ancorare pe rândul cu 2 coloane, poziționare
  laterală față de propriul grafic, flux normal sub grafic — fiecare
  rezolvând un caz, dar introducând altul (box tăiat pe ferestre mai
  mici, suprapunere peste conținutul de dedesubt etc.). Conform cerinței
  explicite, s-a renunțat la toate aceste calcule relative la grafic: **
  toate** casetele (strategie, vehicul, meniu, traseu OBD, ciclu, consum,
  SoC, redare live, profil de putere, hartă BSFC, TCO, cele 2 de la
  analiza de sensibilitate) folosesc acum aceeași poziționare fixă,
  centrată pe ecran (`position:fixed`, centrată orizontal, la 16% din
  înălțimea ferestrei, cu înălțime maximă 70% din fereastră și scroll
  intern dacă textul e mai lung) — identică celei deja folosite și
  verificate pentru strategie/vehicul/meniu. Nu mai contează ce anume
  acoperă din pagină; singura garanție urmărită, respectată în toate
  cazurile, e că boxul apare mereu **complet vizibil** pe ecran.

## Verificare

- `python3 -m py_compile app.py` — OK.
- `pytest tests/` — 60 passed, 3 subtests passed.
- Verificare live pe aplicația deployată: pentru fiecare casetă (inclusiv
  cele aflate în interiorul unor secțiuni expandabile — Analiză detaliată
  pe arhitectură, Costul total de proprietate), s-a confirmat prin
  măsurare directă `getBoundingClientRect()` că boxul rămâne complet
  în interiorul ferestrei (top ≥ 0, bottom ≤ înălțimea ferestrei, stânga
  ≥ 0, dreapta ≤ lățimea ferestrei) — inclusiv cazul, verificat separat,
  al unei casete aflate într-o secțiune expandabilă deschisă.
