# Codebook dei casi documentati

Un **caso** è un account Vinted che ha ricevuto un provvedimento e accetta di raccontarlo con prove.
Un **controllo** è un venditore privato attivo nello stesso periodo, senza provvedimenti,
raccolto con lo stesso questionario e negli stessi canali. Servono entrambi: senza controlli
non si può dire se una caratteristica aumenta il rischio di un provvedimento.

Il foglio si compila con le colonne di `src/casi/modello_casi.csv`. Il file compilato va in
`data/casi/casi.csv` (fuori da GitHub) e si tiene cifrato. Le domande del questionario sono in
`docs/questionario.md`; `src/casi/questionario.py --converti` porta le risposte di Google Moduli nel foglio
con questi codici. Lo analizza `src/casi/analisi_casi.py`, con le regole fissate in
`docs/registro_modifiche.md` ("Regole per H4 e H5").

## Tre tipi di falso positivo

Il tipo dipende dal **motivo dichiarato** da Vinted, e ogni tipo si smentisce con prove diverse.

| Tipo | Vinted sostiene che... | Prove che contraddicono il motivo | Prove che NON bastano |
| --- | --- | --- | --- |
| Merce rubata | l'articolo proviene da un furto | scontrino o ordine intestato, foto datate prima del 17/10, regalo documentato | numero di recensioni, anzianità dell'account |
| Attività commerciale | il privato rivende come un negozio | articoli del proprio guardaroba, regali, pochi doppioni, nessun acquisto all'ingrosso | uno scontrino: molti scontrini di articoli nuovi possono anzi sostenere il motivo |
| Contraffazione | l'articolo è falso | scontrino di un rivenditore autorizzato, certificato, codici verificabili | foto dell'etichetta da sola |

**Quarto tipo: frode o controllo antifrode.** Se Vinted dichiara sospetta frode o truffa (pagamenti, identità, comportamento sull'account), il caso si tiene a parte e non si conta in nessuno dei tre tipi sopra: le prove che lo smentiscono sono diverse (storico delle transazioni, comunicazioni con gli acquirenti) e dopo i saccheggi i controlli di sicurezza possono essere diversi da quelli sulla vendita commerciale. Con pochi casi è solo descrittivo.

## Variabili

**Data di riferimento** per le caratteristiche dell'account e degli annunci: per i casi il giorno del provvedimento (il più recente, se sono più di uno), per i controlli il giorno della risposta.

| Colonna | Cosa contiene | Valori ammessi |
| --- | --- | --- |
| id_caso | Codice progressivo, mai il nome utente | C001... per i casi, K001... per i controlli |
| gruppo | Caso o controllo | caso, controllo |
| data_raccolta | Giorno in cui il questionario è arrivato | AAAA-MM-GG |
| ora_risposta | Data e ora della risposta nel modulo: evita di importare due volte la stessa risposta | AAAA-MM-GG HH:MM:SS |
| canale_raccolta | Da dove arriva. Non è nel questionario: si compila a mano se si usano link diversi per canale | modulo, reddit, gruppo_facebook, altroconsumo, altro |
| consenso | Consenso all'informativa | si (se no: non si registra nulla) |
| paese | Paese del venditore, dichiarato | IT, FR, altro_UE, extra_UE |
| tipo_account | | privato, pro |
| anzianita_mesi | Mesi dall'apertura dell'account, alla data di riferimento | numero |
| annunci_attivi | Annunci visibili alla data di riferimento | numero |
| annunci_nuovi_cartellino | Di questi, quanti "Nuovo con cartellino" | numero |
| quota_nuovi_cartellino | annunci_nuovi_cartellino / annunci_attivi | 0-1 |
| articoli_duplicati | Non è nel questionario; solo se ricavato da altro materiale. Annunci dello stesso articolo oltre il primo | numero |
| pubblicati_ultimi_30_giorni | Non è nel questionario; solo se ricavato da altro materiale. Annunci pubblicati nei 30 giorni prima della data di riferimento | numero |
| vendite_ultimi_3_mesi | Vendite concluse nei 3 mesi prima della data di riferimento (criterio di inclusione: almeno 10) | numero |
| categoria_prevalente | | abbigliamento, scarpe, borse_accessori, cosmetici, elettronica, altro |
| fascia_marchi | Non è nel questionario (non entra nelle analisi registrate); si compila solo se la si ricava da altro materiale | lusso, premium_streetwear, fast_fashion, misti |
| data_provvedimento | Solo casi, se nota (non è nel questionario: si ricava da screenshot o email) | AAAA-MM-GG |
| periodo_provvedimento | Solo casi: provvedimento prima del 17 ottobre 2026 o dal 17 ottobre in poi. Se c'è data_provvedimento, vale la data | prima, dopo |
| tipo_provvedimento | Solo casi | rimozione_annuncio, limitazione_funzioni, sospensione_temporanea, blocco_definitivo, blocco_fondi |
| motivazione_testo | Testo della notifica, senza dati personali. Non è nel questionario: si ricava dallo screenshot | testo |
| motivo_dichiarato | Il motivo scritto da Vinted | merce_rubata, attivita_commerciale, contraffazione, frode, altro, nessuno |
| notifica_disponibile | Screenshot della notifica ufficiale, ricevuto (se la persona lo promette ma non arriva: no) | si, no |
| ricorso | Ricorso interno a Vinted | si, no |
| data_ricorso, data_esito | Solo se note (non sono nel questionario) | AAAA-MM-GG |
| giorni_esito | Giorni tra ricorso e risposta di Vinted, stimati da chi risponde; se mancano si usano le due date | numero |
| esito_ricorso | | revocato, confermato, nessuna_risposta, in_attesa |
| adr | Ricorso a un organismo extragiudiziale certificato (es. ADR Center) | si, no |
| esito_adr | | favorevole, sfavorevole, in_attesa |
| richiesta_gdpr_utente | Richiesta ex art. 15 GDPR inviata dall'utente stesso. Non è nel questionario | si, no |
| risposta_gdpr | Sintesi della risposta ricevuta e condivisa dall'utente. Non è nel questionario | testo |
| prove_disponibili | | scontrino, ordine_online, regalo_documentato, foto_datate, certificato, nessuna (anche più di una) |
| pertinenza_prove | Asse B, vedi sotto | contraddicono_il_motivo, non_pertinenti, insufficienti |
| esito_istituzionale | Asse A, vedi sotto | errore_riconosciuto, revocato_senza_spiegazione, confermato, pendente, mai_contestato |
| classe_caso | Derivata dai due assi | vedi tabella sotto |
| codificatore_1, codificatore_2 | classe_caso assegnata da ciascuno | come classe_caso |
| note | | testo |

## Classificazione dei casi: due assi

**Asse A, cosa è successo dopo.**
- errore_riconosciuto: Vinted o un organismo extragiudiziale dicono esplicitamente che il provvedimento era sbagliato.
- revocato_senza_spiegazione: il provvedimento viene tolto senza ammettere l'errore. Non equivale a un'ammissione.
- confermato: il ricorso è respinto. Non prova che il provvedimento fosse giusto.
- pendente, mai_contestato.

**Asse B, cosa dicono le prove rispetto al motivo dichiarato** (tabella dei tre tipi qui sopra).
- contraddicono_il_motivo: prove pertinenti a quel motivo che lo smentiscono.
- non_pertinenti: prove che riguardano un altro motivo (es. scontrino contro un'accusa di attività commerciale).
- insufficienti: motivo non dichiarato, o prove assenti.

**Classe finale.**

| classe_caso | Regola |
| --- | --- |
| errore_riconosciuto | Asse A = errore_riconosciuto |
| errore_documentato | Asse B = contraddicono_il_motivo, qualunque sia l'asse A |
| ripristino_senza_spiegazione | Asse A = revocato_senza_spiegazione e asse B diverso da contraddicono_il_motivo |
| errore_plausibile | Elementi favorevoli, ma non sufficienti per le classi sopra |
| indeterminato | Tutti gli altri casi |

Si applica la prima regola valida, dall'alto in basso: un caso con errore riconosciuto e prove che contraddicono il motivo è `errore_riconosciuto`.

**Criteri per le prove di robustezza** (sezione 9 della preregistrazione).
- Criterio severo, che coincide con "i soli errori documentati": classi `errore_riconosciuto` ed `errore_documentato`.
- Criterio largo: in più `ripristino_senza_spiegazione` ed `errore_plausibile`.
- `indeterminato` non entra in nessuno dei due.

## Codifica cieca

**Caratteristiche degli annunci** (quota cartellino, duplicati, numero di annunci): le compila chi risponde al questionario, uguale per casi e controlli, quindi non c'è codifica manuale. Se una persona le ricava da screenshot per verifica, lavora su file con codice casuale, senza gruppo (nei limiti del possibile).
**Classificazione dell'errore** (assi A e B): riguarda solo i casi e richiede di conoscere motivazione e prove.

**Due codificatori.** Il kappa di Cohen ha senso solo se due persone classificano gli stessi casi in modo indipendente. Se il secondo codificatore non c'è, non si dichiara alcun kappa: si scrive che la classificazione è di una persona sola e si riportano i casi per classe senza percentuali complessive. Con due codificatori il kappa è pesato se le classi sono ordinabili (asse A), semplice altrimenti.

1. Una persona prepara una copia dei casi senza date, paese, canale e gruppo.
2. Due codificatori assegnano gli assi A e B ognuno per conto suo, seguendo solo questo codebook.
3. Si calcola l'accordo (kappa di Cohen). Sotto 0,6 si rivedono le definizioni e si ricomincia su casi nuovi.
4. I disaccordi si risolvono discutendo; la decisione si annota in `note`.

## Richieste GDPR e organismi extragiudiziali

- Le richieste le presentano gli **utenti stessi** a Vinted, che poi possono condividere la risposta.
- Si chiedono le "informazioni significative sulla logica utilizzata" (art. 15, par. 1, lett. h GDPR; Corte di giustizia UE, C-203/22, 27 febbraio 2025): procedura e principi applicati, non il codice né i pesi.
- L'art. 22 GDPR riguarda solo decisioni **basate unicamente** su trattamenti automatizzati con effetti giuridici o analogamente significativi: non tutte le decisioni di moderazione rientrano.
- ADR Center è certificato da AGCOM come organismo extragiudiziale ai sensi dell'art. 21 DSA (delibera 501/24/CONS). Il suo sito non dice se pubblica decisioni o statistiche per piattaforma: si chiede ai partecipanti di condividere le decisioni ricevute, e ad ADR Center i dati aggregati su Vinted.

## Esclusioni

- Senza consenso: non si registra nulla.
- Casi con indizi di vera ricettazione: esclusi e cancellati, senza conservarne copia.
- Casi fuori dall'UE (per esempio Regno Unito): archivio separato, fuori dalle analisi sul DSA.
- Il questionario non chiede mai nulla che possa autoincriminare.
