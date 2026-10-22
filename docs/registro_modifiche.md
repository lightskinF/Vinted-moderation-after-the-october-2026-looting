# Registro delle modifiche e delle note alla preregistrazione

Preregistrazione: https://osf.io/4grmp (OSF, modello Open-Ended, 22 ottobre 2026; DOI 10.17605/OSF.IO/4GRMP).

Qui si elencano, con data e motivo, le deviazioni dal piano registrato, le precisazioni su come si applica e le imprecisioni note nei file allegati. Tutte le voci sono scritte prima di scaricare o analizzare i dati dal 17 ottobre 2026. Nessuna cambia ipotesi, statistiche, soglie o regole di decisione.

Lo stato completo del codice al momento della registrazione è il tag `prereg-v1` di questo repository. I tre file con impronta SHA-256 nella preregistrazione (`placebo.py`, `qualita.py`, `comune.py`) non sono cambiati. Dopo il tag sono cambiati solo commenti, messaggi a schermo, la stima dello spazio su disco e le date di download predefinite in `config/progetto.yaml`, `carica.py`, `scarica_diretto.py`, `scarica.py` e `tasso_base.py`, e si è aggiunta una colonna al modello del foglio dei casi; la storia dei commit mostra ogni riga modificata.

## Deviazioni dal piano

1. **Righe con `uuid` ripetuto** (22 ottobre 2026). La sezione 3 della preregistrazione definisce la dichiarazione "senza duplicati per `uuid`", ma il codice registrato (`qualita.py`, `placebo.py`) conta tutte le righe caricate. Nello storico le righe ripetute sono 168 su 66.713.658 (0,0003%). Le statistiche si calcolano con il codice registrato. Per la finestra dell'evento si riporta il numero di righe ripetute; se supera lo 0,1% delle righe della finestra, si riportano anche le statistiche senza duplicati.

## Precisazioni su come si applica il piano (22 ottobre 2026)

1. **Quando si fa l'analisi definitiva.** Un giorno è valido se ha almeno il 60% della mediana dei 29 giorni attorno, calcolata dal codice registrato con una finestra centrata. Per il 31 ottobre servono quindi i dati fino al 14 novembre, e per le decisioni inviate il giorno dopo i file fino al 15 novembre. L'analisi definitiva della finestra 17-31 ottobre si fa con i file fino al 15 novembre 2026 compreso, quindi dal 16 novembre. Dal 2 novembre i dati si possono scaricare e guardare in forma descrittiva, senza verdetti su H1-H3.
2. **Righe arrivate il giorno dopo nella base.** Il file del 17 ottobre può aggiungere qualche riga al 16 ottobre, ultimo giorno della base. Se la distribuzione placebo ricalcolata dopo il caricamento differisce da quella registrata, fanno fede le soglie della sezione 5 della preregistrazione; i valori ricalcolati si riportano accanto.
3. **Restrizione dell'account o del servizio.** La definizione registrata unisce `decision_account` (stato dell'account) e `decision_provision` (sospensione o cessazione della fornitura del servizio). Nello storico `decision_provision` è vuoto nel 100% delle dichiarazioni, quindi la misura coincide con `decision_account`. Se nella finestra dell'evento `decision_provision` compare, le statistiche H2-H3 si riportano anche separate per i due campi, e la comparsa si tratta come un cambio nel modo di compilare.
4. **Prove di robustezza con finestre diverse** (sezione 9, punto 3). `placebo.py` registrato usa la finestra di 15 giorni. Le finestre di 7 e 21 giorni e la base di 14 giorni validi si calcolano con uno script separato che riusa le funzioni di `placebo.py` senza modificarlo.
5. **Ritardo di invio dopo l'evento** (sezione 4). La sezione 2 del rapporto di qualità misura il ritardo solo sulle decisioni applicate almeno 30 giorni prima dell'ultimo invio, quindi non copre la finestra dell'evento. Per quei giorni il ritardo si controlla confrontando, giorno per giorno, le dichiarazioni per data di applicazione con quelle contenute nel file del giorno (`controllo_caricamento.csv` e `serie_giornaliera.csv`).
6. **Classificazione dei casi per le prove di robustezza** (sezione 9, punti 2 e 5). I criteri severo e largo sono definiti nel codebook (`docs/codebook_casi.md`, "Criteri per le prove di robustezza"): il severo coincide con "i soli errori documentati".
7. **Rapporto di qualità rilanciato dopo l'evento.** Con i dati dal 17 ottobre caricati, la sezione 5 di `qualita_tdb.md` indica come fine della base l'ultimo giorno caricato. È solo testo descrittivo: la base usata dalle statistiche resta 23 settembre - 16 ottobre 2026, fissata in `placebo.py`.

## Da fissare prima di aprire il questionario (H5)

Si registrano qui, con data, prima di raccogliere risposte:

- la soglia di "quota cartellino alta" che definisce gli esposti;
- se nel modello logistico la quota entra in forma dicotomica (come nel calcolo della numerosità) o continua.

Gli script per H4 e H5 si scrivono e si pubblicano prima di guardare i casi.

## Imprecisioni note nei file allegati (22 ottobre 2026)

Sono imprecisioni di testo nella preregistrazione e nei file generati dal codice registrato. Non si correggono nei file, per non cambiare il documento registrato e le impronte SHA-256.

| File | Dove | Cosa dice | Cosa vale |
| --- | --- | --- | --- |
| Preregistrazione e `placebo.md` | Sezione 5 / testo introduttivo | Le 436 finestre placebo sono "circa 30 indipendenti" | Il conto divide i giorni per la sola finestra di 15 giorni. Ogni valore usa però 37 giorni consecutivi (22 di base e 15 di finestra): i blocchi senza giorni in comune sono circa 13. Le soglie restano quelle registrate; i percentili estremi sono più incerti di quanto suggerisca "30", e lo si dichiara come limite insieme ai risultati |
| Preregistrazione | Sezione 4, giorni esclusi | "Nei giorni vicini le dichiarazioni sono circa 160.000" | Vale per il 3 e il 4 ottobre 2026. Per il 2 luglio 2025 la mediana dei giorni vicini è 110.598, per il 22 agosto 2026 è 148.007 (tabella del rapporto di qualità) |
| `qualita_tdb.md` | Sezione 1, tabella "Copertura" | "Giorni con dati mancanti o parziali (sotto metà dei giorni vicini)" | La regola applicata è quella registrata: sotto il 60% della mediana dei 29 giorni attorno. I 4 giorni elencati sono calcolati con il 60% |
| `qualita_tdb.md` | Sezione 1, tabella "Copertura" e tabella dei giorni parziali | "Giorni senza alcuna dichiarazione: 0" e 22 agosto 2026 con 5 dichiarazioni | Il file del 22 agosto manca; le 5 dichiarazioni con quella data di applicazione sono arrivate nei file di altri giorni |
| `qualita_tdb.md` | Sezione 2 | "almeno 1 giorni" | almeno 1 giorno |
| `qualita_tdb.md` | Sezioni "Da guardare per primo" e 9 | "vendita commerciale" | Stesso significato di "attività commerciale" nella preregistrazione |
| `qualita_tdb.md` | "Da guardare per primo" | "Estensione vuota o pari a tutta l'UE in oltre il 90% dei casi" | Il valore misurato è 100% (sezione 8 del rapporto) |
| `qualita_tdb.md`, `placebo.md` | Tutte le tabelle | Decimali con il punto (32.6%, +14.5%) e migliaia con il punto (66.713.658) | Stessi valori della preregistrazione, che usa la virgola per i decimali (+14,5%) |
| `src/analisi/placebo.py` | Commento in cima al file | Rimanda alle "sezioni 6 e 8" | Nella versione registrata quei contenuti sono nelle sezioni 4, 5 e 6. Solo un commento: non tocca i calcoli |
