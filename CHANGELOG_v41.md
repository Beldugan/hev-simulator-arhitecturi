# Modificări v40 → v41

Retușare vizuală a celor 3 panouri de explicații introduse în v40: butonul
de declanșare nu mai e o bară cu text pe toată lățimea, ci un simplu semn
de întrebare albastru, circular, așezat direct lângă eticheta la care se
referă.

## Ce s-a schimbat

1. **"Strategia de management energetic"** — semnul „?" apare lângă
   dropdown, nu mai există bară „Ce înseamnă fiecare strategie?" dedesubt.

2. **"Variantă"** (bază de date vehicule) — semnul „?" apare lângă
   dropdown-ul de variantă; conținutul panoului (audit EEA + descriere
   PHEV/MHEV/HEV) e neschimbat față de v40.

3. **"Meniu"** — semnul „?" apare lângă titlul „Meniu", deasupra
   dropdown-ului de navigare; conținutul (descrierea celor 5 pagini) e
   neschimbat.

Conținutul panourilor (textele explicative) nu s-a schimbat — doar
declanșatorul (trigger-ul) e diferit vizual: cerc albastru mic, fără text,
în loc de buton lat cu etichetă.

## Notă tehnică

Streamlit nu permite restilizarea directă a componentei `st.popover` prin
parametri — s-a folosit CSS țintit pe `div[data-testid="stPopover"] >
button` pentru a-l transforma într-un cerc de 1.6rem, fără chenar, cu
textul „?" colorat albastru (inclusiv variantă pentru modul întunecat).
Poziționarea alăturată etichetei s-a obținut cu `st.columns()`.

Nu a fost posibilă o verificare vizuală în browser real (sandbox-ul nu are
acces la Chrome/Playwright) — verificarea s-a făcut prin compilare
(`py_compile`), suita completă de teste (`pytest`, 60/60 treceri) și teste
`AppTest` dedicate care simulează randarea sidebar-ului pentru toate
tipurile de vehicule și confirmă absența excepțiilor.
