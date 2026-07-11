# Modificări v41 → v42

Două corecturi punctuale, semnalate direct de utilizator după testarea v41.

## Ce s-a schimbat

1. **Denumirile celor 3 strategii** din dropdown au fost aliniate exact la
   formularea cerută, fără paranteze suplimentare:
   - „Bazată pe reguli (Rule-Based)" → **„Strategie bazată pe reguli"**
   - „ECMS (minimizarea consumului echi…)" → **„Minimizarea consumului
     echivalent"**
   - „Programare dinamică (benchmark optim)" → **„Programare dinamică"**

2. **Panoul de explicații (popover) depășea marginea de sus a ferestrei**
   atunci când declanșatorul „?" era aproape de vârful paginii (de exemplu
   lângă „Strategia de management energetic"), afișându-se tăiat. Panoul e
   acum poziționat fix, mai jos (≈16% din înălțimea ferestrei) și centrat
   pe orizontală, cu înălțime maximă și scroll intern dacă textul e lung —
   nu mai depinde de poziția declanșatorului pe pagină.

## Notă tehnică

Poziționarea s-a corectat prin CSS țintit pe `div[data-testid="stPopoverBody"]`
(identificat direct în bundle-ul JS al Streamlit 1.59, testid-ul intern al
panoului de conținut al `st.popover`), cu `position: fixed` și `!important`
— acesta are prioritate față de stilul inline calculat automat de
biblioteca de poziționare a Streamlit, care altfel plasează panoul deasupra
declanșatorului când nu are loc dedesubt.
