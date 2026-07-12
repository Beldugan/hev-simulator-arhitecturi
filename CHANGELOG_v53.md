# Changelog — v53

## Rezolvat

- Casetele de selecție (`selectbox`) din conținutul principal al paginilor
  (ex. „Arhitectura analizată” din secțiunea Sensibilitate) nu aveau fundal
  alb explicit definit, ci doar din bara laterală — în conținutul principal
  se confundau vizual cu fundalul gri-deschis al paginii, devenind aproape
  invizibile. Regula CSS pentru fundal alb + bordură (deja folosită în bara
  laterală, ex. „Preset: Bigster (lucrare)”) a fost extinsă la toate
  casetele de selecție din aplicație, indiferent de secțiune.
