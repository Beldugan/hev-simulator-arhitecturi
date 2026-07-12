# CHANGELOG v48

## 1. Fix real (verificat live) al golului din bara laterală
v47 folosea `display: contents` pentru a scoate din calculul de layout containerele care înfășoară marcajele invizibile și box-urile de hover — teoretic corect, dar verificarea LIVE pe aplicația publicată (inspecție DOM directă, cu Chrome conectat, pe simhev.streamlit.app, după deploy-ul v47) a arătat că fix-ul nu funcționa: golul de ~64px persista.

Root cause real, descoperit prin măsurători directe în browser: Chrome tot inserează gap-ul de flexbox (16px) în jurul unui container `display:contents`, chiar dacă acesta nu generează nicio cutie vizibilă — comportament diferit de ce ar sugera specificația CSS. În plus, un container `display:contents` nu poate primi `margin` (nu există nicio cutie căreia să i se aplice), deci nu putea fi nici măcar compensat.

Soluția implementată și verificată live: containerul rămâne o cutie normală (`display:block`), de înălțime 0, iar gap-ul din jurul lui este anulat cu margine negativă simetrică (`margin: -0.5rem 0`, adică −8px sus + −8px jos = −16px per container). Matematic, pentru N containere-fantomă înlănțuite între două elemente reale: (N+1) goluri de 16px, minus N containere × 16px anulați, rămâne exact 16px — un singur gol normal, indiferent dacă e vorba de 1 container (Variantă) sau 5 (Meniu).

S-a mai descoperit, tot prin inspecție live, că Streamlit reinserează periodic propriul `<style>` (din `st.markdown`) mai jos în `<head>` la fiecare rerun — la specificitate CSS egală, ultima regulă din DOM câștigă, deci regula originală (display:none/none pe boxuri) redevenea câștigătoare intermitent. Rezolvat prin dublarea selectorului de atribut (`[data-testid=...][data-testid=...]`), care crește specificitatea suficient cât regula proprie să câștige indiferent de ordinea de inserare.

Verificat live, cu Chrome conectat direct la aplicația publicată: gol redus de la ~64px la exact 16px (identic cu spațiul normal dintre oricare alte două widget-uri), iar box-urile de hover (testat pe "Strategie bazată pe reguli") continuă să apară corect la trecerea cursorului peste opțiune.

## 2. Cardul "Strategie" separat de cardul de consum, dar mutat sub el
Layout-ul paginii de simulare a fost restructurat de la 3 coloane la 2: prima coloană conține acum, STACKED vertical (ca 2 carduri separate, nu fuzionate), cardul de consum al arhitecturii de referință și, direct sub el, cardul cu strategia de management energetic folosită. A doua coloană rămâne cardul fuzionat "Configurația optimă". Motivul: în layout-ul pe 3 coloane, textul strategiei ("Strategie bazată pe reguli" etc.) se trunchia vizual cu puncte de suspensie din cauza lățimii insuficiente a coloanei; pe o coloană de lățime dublă, eticheta completă încape.

## Verificare
- `py_compile` — OK.
- Suită completă de teste: `60 passed, 3 subtests passed`.
- Verificare LIVE pe simhev.streamlit.app (Chrome conectat): gol eliminat (64px → 16px) și funcționalitatea de hover confirmată vizual prin captură de ecran.
