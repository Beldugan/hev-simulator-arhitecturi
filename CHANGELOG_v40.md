# Modificări v39 → v40

Versiune de UX pe bara laterală: mutarea explicațiilor lungi din text mereu
vizibil în panouri afișate la cerere (click), plus redenumirea meniului de
strategie fără acronime.

## Ce s-a schimbat

1. **"Strategie EMS" → "Strategia de management energetic"** — eticheta
   dropdown-ului nu mai folosește acronimul.

2. **Explicațiile celor 3 strategii** (Bazată pe reguli / Minimizarea
   consumului echivalent / Programare dinamică) nu mai apar tot timpul —
   sunt acum într-un panou „Ce înseamnă fiecare strategie?", afișat la
   click, cu text redactat cursiv, fără acronime (SoC, EMS etc. înlocuite cu
   formulări în limbaj comun).

3. **Descrierea vehiculului selectat** (bază de date) a fost simplificată:
   rămân mereu vizibile doar cele două linii scurte (tip/arhitectură/CO₂ și
   sursă/câmpuri estimate). Auditul EEA și descrierea de tip (PHEV/MHEV/HEV)
   au fost mutate într-un panou „Detalii și audit pentru acest vehicul",
   afișat la click, cu fundal verde — valabil pentru toate cele 250 de
   vehicule din bază, nu doar pentru cazurile PHEV/MHEV (s-a adăugat și o
   descriere pentru HEV, care înainte nu avea niciuna).

4. **Meniul de navigare** are acum un panou „Ce conține fiecare pagină?",
   afișat la click, cu o descriere scurtă pentru fiecare din cele 5 pagini
   (Simulare, Sensibilitate, Comparație A/B, Validare, Export PDF).

## Notă tehnică: de ce click și nu hover

Cerința inițială a fost afișarea acestor panouri la simpla trecere a
cursorului peste o opțiune din dropdown, înainte de a o selecta. Streamlit
nu oferă acest mecanism nativ, iar o soluție bazată pe CSS/JavaScript ar fi
fost fragilă — mai ales cu mai multe dropdown-uri similare pe aceeași
pagină (riscul era ca hover-ul pe un dropdown să declanșeze eronat panoul
altui dropdown, din cauza structurii identice a listelor derulante). S-a
ales `st.popover()`, componenta nativă Streamlit: un click în loc de hover,
dar identic ca aspect (panouri colorate) și 100% fiabil.

## Teste noi

`tests/test_app_ui.py` — 6 teste (folosind `streamlit.testing.v1.AppTest`)
care verifică: eticheta redenumită, absența acronimelor brute din
`STRATEGY_LABELS`, prezența conținutului corect în toate cele 3 panouri, și
faptul că niciunul din cele 3 tipuri de vehicul (HEV/PHEV/MHEV) nu produce
erori la afișare. Suita completă: 60 de teste.
