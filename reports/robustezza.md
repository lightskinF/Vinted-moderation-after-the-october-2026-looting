# Prove di robustezza di H1-H3 (finestre diverse)

Preregistrazione, sezione 9, punto 3. Stesso codice di `placebo.py`, con finestra, base e minimo di giorni validi cambiati per ogni scenario; minimo di giorni validi = due terzi della finestra, arrotondati per eccesso. Base registrata: 22 giorni validi dal 2026-09-23 al 2026-10-16. Dati fino al 2026-11-24. Una conclusione che regge solo in uno scenario si riporta come fragile.

## Registrato: finestra 15 giorni, base registrata

Finestra di 15 giorni (evento: 2026-10-17 - 2026-10-31), base di 22 giorni validi, almeno 10 giorni validi nella finestra. 459 finestre placebo.

| Statistica | Finestre | 2,5% | 5% | 95% | 97,5% | Evento | Esito |
| --- | --- | --- | --- | --- | --- | --- | --- |
| H1 Dichiarazioni totali (osservate/attese) | 436 | -20.2% | -14.8% | +14.5% | +17.1% | +11.2% | sotto la soglia |
| H2a Rilevamento automatico tra restrizioni account (pt) | 436 | -13.0 pt | -10.7 pt | +9.6 pt | +12.3 pt | +13.1 pt | sopra la soglia |
| H2b Decisione automatica tra restrizioni account (pt) | 436 | -8.4 pt | -6.7 pt | +7.4 pt | +8.8 pt | +15.4 pt | sopra la soglia |
| H3 Altra segnalazione tra restrizioni account (pt, due code) | 436 | -22.0 pt | -11.7 pt | +5.7 pt | +40.9 pt | -13.3 pt | entro le soglie |

## Finestra 7 giorni

Finestra di 7 giorni (evento: 2026-10-17 - 2026-10-23), base di 22 giorni validi, almeno 5 giorni validi nella finestra. 467 finestre placebo.

| Statistica | Finestre | 2,5% | 5% | 95% | 97,5% | Evento | Esito |
| --- | --- | --- | --- | --- | --- | --- | --- |
| H1 Dichiarazioni totali (osservate/attese) | 444 | -17.4% | -12.4% | +13.6% | +16.7% | +4.9% | sotto la soglia |
| H2a Rilevamento automatico tra restrizioni account (pt) | 444 | -12.6 pt | -10.4 pt | +10.4 pt | +12.6 pt | +5.2 pt | sotto la soglia |
| H2b Decisione automatica tra restrizioni account (pt) | 444 | -8.2 pt | -6.3 pt | +6.3 pt | +7.8 pt | -2.4 pt | sotto la soglia |
| H3 Altra segnalazione tra restrizioni account (pt, due code) | 444 | -17.1 pt | -11.4 pt | +11.9 pt | +43.4 pt | -5.8 pt | entro le soglie |

## Finestra 21 giorni

Finestra di 21 giorni (evento: 2026-10-17 - 2026-11-06), base di 22 giorni validi, almeno 14 giorni validi nella finestra. 453 finestre placebo.

| Statistica | Finestre | 2,5% | 5% | 95% | 97,5% | Evento | Esito |
| --- | --- | --- | --- | --- | --- | --- | --- |
| H1 Dichiarazioni totali (osservate/attese) | 430 | -20.6% | -15.0% | +14.7% | +17.4% | +27.8% | sopra la soglia |
| H2a Rilevamento automatico tra restrizioni account (pt) | 430 | -14.0 pt | -11.1 pt | +10.5 pt | +11.8 pt | +27.3 pt | sopra la soglia |
| H2b Decisione automatica tra restrizioni account (pt) | 430 | -8.3 pt | -7.0 pt | +8.6 pt | +9.4 pt | +42.0 pt | sopra la soglia |
| H3 Altra segnalazione tra restrizioni account (pt, due code) | 430 | -23.9 pt | -11.9 pt | +4.3 pt | +22.6 pt | -26.8 pt | sotto la soglia bassa |

## Base 14 giorni validi

Finestra di 15 giorni (evento: 2026-10-17 - 2026-10-31), base di 14 giorni validi, almeno 10 giorni validi nella finestra. 459 finestre placebo.

| Statistica | Finestre | 2,5% | 5% | 95% | 97,5% | Evento | Esito |
| --- | --- | --- | --- | --- | --- | --- | --- |
| H1 Dichiarazioni totali (osservate/attese) | 444 | -16.9% | -12.3% | +13.7% | +16.9% | +11.7% | sotto la soglia |
| H2a Rilevamento automatico tra restrizioni account (pt) | 444 | -12.1 pt | -10.1 pt | +9.9 pt | +12.5 pt | +13.7 pt | sopra la soglia |
| H2b Decisione automatica tra restrizioni account (pt) | 444 | -7.6 pt | -6.2 pt | +6.2 pt | +7.8 pt | +17.6 pt | sopra la soglia |
| H3 Altra segnalazione tra restrizioni account (pt, due code) | 444 | -19.4 pt | -11.8 pt | +5.1 pt | +32.5 pt | -13.8 pt | entro le soglie |

## Giorni esclusi nella finestra dell'evento (2026-10-17 - 2026-11-06)

Nessun giorno escluso.
