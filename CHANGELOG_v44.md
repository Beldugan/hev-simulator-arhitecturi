# Modificări v43 → v44

Corectare bug + o schimbare cerută explicit de utilizator.

## Ce s-a schimbat

1. **Bug fix: box-ul de la „Variantă" nu apărea niciodată.** Cauza: marcajul
   invizibil folosit pentru identificarea selectorului era plasat cu un
   nivel mai adânc în structura internă a Streamlit decât presupusesem
   (`stElementContainer > stMarkdownContainer > (div fără atribut) >
   stMarkdown > marcaj`, nu direct `stElementContainer > marcaj`), așa că
   regula CSS bazată pe frați adiacenți nu găsea niciodată o potrivire.
   Corectat folosind `:has()` cu combinator descendent (nu copil direct)
   pentru localizarea containerului corect — verificat live, cu hover
   real, direct pe aplicația publicată, nu doar presupus.

2. **Meniu — eliminat butonul „?".** La fel ca la strategie: descrierea
   fiecărei pagini (Simulare, Sensibilitate, Comparație A/B, Validare,
   Export PDF) apare acum DOAR pentru pagina aflată sub cursor, în momentul
   în care dropdown-ul „Meniu" e deschis — nu mai există panou unic cu
   toate cele 5 descrieri și niciun buton de declanșare.

## Notă tehnică

Ambele funcționalități au fost verificate prin injectare temporară a
regulilor CSS corectate direct în pagina publicată (simhev.streamlit.app)
și hover real cu mouse-ul, cu captură de ecran de confirmare — nu doar
verificare structurală (`querySelectorAll`) fără interacțiune reală, care
s-a dovedit insuficientă la v43 (a ratat exact bug-ul de mai sus).
