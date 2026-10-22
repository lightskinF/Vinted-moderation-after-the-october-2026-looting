# Registro delle modifiche e delle note alla preregistrazione

Preregistrazione: https://osf.io/4grmp (OSF, modello Open-Ended, 22 ottobre 2026; DOI 10.17605/OSF.IO/4GRMP).

Qui si elencano, con data e motivo, le modifiche al piano registrato e le imprecisioni note nei file allegati. Nessuna voce qui sotto cambia ipotesi, statistiche, soglie o regole di decisione.

## 22 ottobre 2026: imprecisioni note nei file allegati

Sono imprecisioni di testo nei file generati dal codice registrato. Non si correggono nei file, per non cambiare le impronte SHA-256 registrate.

| File | Dove | Cosa dice | Cosa vale |
| --- | --- | --- | --- |
| `qualita_tdb.md` | Sezione 1, tabella "Copertura" | "Giorni con dati mancanti o parziali (sotto metà dei giorni vicini)" | La regola applicata è quella registrata: sotto il 60% della mediana dei 29 giorni attorno. I 4 giorni elencati sono calcolati con il 60% |
| `qualita_tdb.md` | Sezione 1, tabella "Copertura" e tabella dei giorni parziali | "Giorni senza alcuna dichiarazione: 0" e 22 agosto 2026 con 5 dichiarazioni | Il file del 22 agosto manca; le 5 dichiarazioni con quella data di applicazione sono arrivate nei file di altri giorni |
| `qualita_tdb.md` | Sezione 2 | "almeno 1 giorni" | almeno 1 giorno |
| `qualita_tdb.md` | Sezioni "Da guardare per primo" e 9 | "vendita commerciale" | Stesso significato di "attività commerciale" nella preregistrazione |
| `qualita_tdb.md` | "Da guardare per primo" | "Estensione vuota o pari a tutta l'UE in oltre il 90% dei casi" | Il valore misurato è 100% (sezione 8 del rapporto) |
| `qualita_tdb.md`, `placebo.md` | Tutte le tabelle | Decimali con il punto (32.6%, +14.5%) e migliaia con il punto (66.713.658) | Stessi valori della preregistrazione, che usa la virgola per i decimali (+14,5%) |
| `src/analisi/placebo.py` | Commento in cima al file | Rimanda alle "sezioni 6 e 8" | Nella versione registrata quei contenuti sono nelle sezioni 4, 5 e 6. Solo un commento: non tocca i calcoli |
