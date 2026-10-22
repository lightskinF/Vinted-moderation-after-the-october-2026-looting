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
| Preregistrazione | Sezione 4, giorni esclusi | "Nei giorni vicini le dichiarazioni sono circa 160.000" | Vale per il 3 e il 4 ottobre 2026. Per il 2 luglio 2025 la mediana dei giorni vicini è 110.598, per il 22 agosto 2026 è 148.007 (tabella del rapporto di qualità) |

## 22 ottobre 2026: precisazioni sull'esecuzione, prima di scaricare i dati dal 17 ottobre

Sono scritte prima di vedere la finestra dell'evento. Chiariscono come si applica il piano; non cambiano ipotesi, statistiche, soglie o regole di decisione.

1. **Righe con `uuid` ripetuto.** La sezione 3 della preregistrazione definisce la dichiarazione "senza duplicati per `uuid`", ma il codice registrato (`qualita.py`, `placebo.py`) conta tutte le righe caricate. Nello storico le righe ripetute sono 168 su 66.713.658 (0,0003%). Le statistiche si calcolano con il codice registrato. Per la finestra dell'evento si riporta il numero di righe ripetute; se supera lo 0,1% delle righe della finestra, si riportano anche le statistiche senza duplicati.
2. **Decisioni inviate il giorno dopo.** Alcune decisioni arrivano al database il giorno successivo. Per questo la finestra 17-31 ottobre si calcola con i file fino al 1 novembre 2026 compreso, e il file del 17 ottobre può aggiungere qualche riga al 16 ottobre, ultimo giorno della base. Se la distribuzione placebo ricalcolata dopo il caricamento differisce da quella registrata, fanno fede le soglie della sezione 5 della preregistrazione; i valori ricalcolati si riportano accanto.
3. **Prove di robustezza con finestre diverse** (sezione 9, punto 3). `placebo.py` registrato usa la finestra di 15 giorni. Le finestre di 7 e 21 giorni e la base di 14 giorni validi si calcolano con uno script separato che riusa le funzioni di `placebo.py` senza modificarlo.
4. **Rapporto di qualità rilanciato dopo l'evento.** Con i dati dal 17 ottobre caricati, la sezione 5 di `qualita_tdb.md` indica come fine della base l'ultimo giorno caricato. È solo testo descrittivo: la base usata dalle statistiche resta 23 settembre - 16 ottobre 2026, fissata in `placebo.py`.
