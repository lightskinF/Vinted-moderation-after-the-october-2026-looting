# Questionario per casi e controlli

Testo delle domande del questionario su Google Moduli, pubblicato prima di aprirlo. Lo genera `src/casi/questionario.py --testo`, dalle stesse definizioni che creano il modulo e convertono le risposte nel foglio del codebook (`docs/codebook_casi.md`). Il modulo si apre con l'informativa sul trattamento dei dati.

Percorso: chi risponde "No" al consenso finisce lì. Chi non ha mai ricevuto provvedimenti (controllo) risponde al profilo e agli annunci di oggi. Chi ha ricevuto un provvedimento (caso) risponde agli annunci al momento del provvedimento e poi alle domande su provvedimento, ricorsi e prove. Le colonne del codebook non presenti qui le compila chi analizza: `id_caso`, `data_raccolta` e `ora_risposta` (dalla data e ora della risposta), `quota_nuovi_cartellino` (calcolata) e la classificazione dei casi.

## Consenso

| Domanda | Tipo | Risposte → codice | Colonna |
| --- | --- | --- | --- |
| Hai almeno 18 anni e acconsenti al trattamento dei dati descritto nell'informativa qui sopra? | una risposta | Sì, ho almeno 18 anni e acconsento → `si`<br>No → `no` | `consenso` |

## Il tuo profilo

| Domanda | Tipo | Risposte → codice | Colonna |
| --- | --- | --- | --- |
| In quale paese vendi su Vinted? | una risposta | Italia → `IT`<br>Francia → `FR`<br>Un altro paese dell'Unione europea → `altro_UE`<br>Un paese fuori dall'Unione europea (per esempio Regno Unito o Svizzera) → `extra_UE` | `paese` |
| Che tipo di account Vinted hai?<br>*Se hai ricevuto un provvedimento, l'account che avevi in quel momento.* | una risposta | Privato → `privato`<br>Professionale (Vinted Pro) → `pro` | `tipo_account` |
| Che cosa vendi di più? | una risposta | Abbigliamento → `abbigliamento`<br>Scarpe → `scarpe`<br>Borse e accessori → `borse_accessori`<br>Cosmetici e profumi → `cosmetici`<br>Elettronica → `elettronica`<br>Altro → `altro` | `categoria_prevalente` |
| Di che marchi sono soprattutto i tuoi articoli? | una risposta | Lusso (per esempio Gucci, Prada, Louis Vuitton) → `lusso`<br>Premium o streetwear (per esempio Nike, Ralph Lauren, Stone Island) → `premium_streetwear`<br>Fast fashion (per esempio Zara, H&M, Shein) → `fast_fashion`<br>Misti → `misti` | `fascia_marchi` |
| Dove hai trovato questo questionario? | una risposta | Reddit → `reddit`<br>Un gruppo Facebook → `gruppo_facebook`<br>Altroconsumo → `altroconsumo`<br>Altro (passaparola, altri social, link diretto) → `altro` | `canale_raccolta` |
| Vinted ha mai preso un provvedimento sul tuo account o sui tuoi annunci?<br>*Per esempio: rimozione di annunci, limitazione di alcune funzioni, sospensione o blocco dell'account, blocco dei fondi.* | una risposta | Sì → `caso`<br>No → `controllo` | `gruppo` |

## I tuoi annunci oggi

Solo controlli. Dopo questa pagina il modulo si invia.

| Domanda | Tipo | Risposte → codice | Colonna |
| --- | --- | --- | --- |
| Da quanti mesi hai l'account Vinted?<br>*Una stima va bene: 1 anno = 12 mesi.* | numero intero | - | `anzianita_mesi` |
| Quanti annunci hai attivi oggi?<br>*Gli annunci visibili sul profilo, esclusi quelli già venduti. Una stima va bene.* | numero intero | - | `annunci_attivi` |
| Quanti di questi annunci sono nella condizione "Nuovo con cartellino"?<br>*È la condizione che scegli quando pubblichi l'annuncio. Scrivi 0 se nessuno.* | numero intero | - | `annunci_nuovi_cartellino` |
| Quanti di questi annunci sono doppioni dello stesso articolo?<br>*Conta solo le copie oltre la prima: 3 annunci dello stesso articolo = 2 doppioni. Scrivi 0 se nessuno.* | numero intero | - | `articoli_duplicati` |
| Quanti annunci hai pubblicato negli ultimi 30 giorni? | numero intero | - | `pubblicati_ultimi_30_giorni` |
| Quante vendite hai concluso negli ultimi 3 mesi? | numero intero | - | `vendite_ultimi_3_mesi` |

## I tuoi annunci prima del provvedimento

Solo casi. Se i provvedimenti sono più di uno, in tutto il questionario rispondi pensando al più recente.

| Domanda | Tipo | Risposte → codice | Colonna |
| --- | --- | --- | --- |
| Da quanti mesi avevi l'account Vinted quando hai ricevuto il provvedimento?<br>*Una stima va bene: 1 anno = 12 mesi.* | numero intero | - | `anzianita_mesi` |
| Quanti annunci avevi attivi quando hai ricevuto il provvedimento?<br>*Gli annunci visibili sul profilo, esclusi quelli già venduti. Una stima va bene.* | numero intero | - | `annunci_attivi` |
| Quanti di quegli annunci erano nella condizione "Nuovo con cartellino"?<br>*È la condizione che scegli quando pubblichi l'annuncio. Scrivi 0 se nessuno.* | numero intero | - | `annunci_nuovi_cartellino` |
| Quanti di quegli annunci erano doppioni dello stesso articolo?<br>*Conta solo le copie oltre la prima: 3 annunci dello stesso articolo = 2 doppioni. Scrivi 0 se nessuno.* | numero intero | - | `articoli_duplicati` |
| Quanti annunci avevi pubblicato nei 30 giorni prima del provvedimento? | numero intero | - | `pubblicati_ultimi_30_giorni` |
| Quante vendite avevi concluso nei 3 mesi prima del provvedimento? | numero intero | - | `vendite_ultimi_3_mesi` |

## Il provvedimento

Solo casi. 

| Domanda | Tipo | Risposte → codice | Colonna |
| --- | --- | --- | --- |
| In che giorno Vinted ha preso il provvedimento? | data | - | `data_provvedimento` |
| Che provvedimento era?<br>*Se erano più cose insieme, scegli la più grave.* | una risposta | Rimozione di uno o più annunci → `rimozione_annuncio`<br>Limitazione di alcune funzioni → `limitazione_funzioni`<br>Sospensione temporanea dell'account → `sospensione_temporanea`<br>Blocco definitivo dell'account → `blocco_definitivo`<br>Blocco dei fondi nel borsellino → `blocco_fondi` | `tipo_provvedimento` |
| Quale motivo ha indicato Vinted? | una risposta | Merce rubata o di provenienza illecita → `merce_rubata`<br>Attività commerciale (vendere come un negozio senza account Pro) → `attivita_commerciale`<br>Articolo contraffatto → `contraffazione`<br>Frode, truffa o sicurezza dell'account → `frode`<br>Un altro motivo → `altro`<br>Nessun motivo → `nessuno` | `motivo_dichiarato` |
| Copia qui il testo della notifica di Vinted (facoltativa)<br>*Togli nome utente, nome, email, numeri d'ordine e ogni altro dato personale.* | testo lungo | - | `motivazione_testo` |
| Puoi inviare uno screenshot della notifica di Vinted, con i dati personali oscurati? | una risposta | Sì → `si`<br>No → `no` | `notifica_disponibile` |

## Ricorsi e richieste

Solo casi. 

| Domanda | Tipo | Risposte → codice | Colonna |
| --- | --- | --- | --- |
| Hai chiesto a Vinted di rivedere il provvedimento (ricorso interno)?<br>*Per esempio tramite l'assistenza o il modulo di reclamo.* | una risposta | Sì → `si`<br>No → `no` | `ricorso` |
| Se sì, in che giorno hai fatto il ricorso? (facoltativa) | data | - | `data_ricorso` |
| Se sì, com'è andato il ricorso? (facoltativa) | una risposta | Il provvedimento è stato revocato → `revocato`<br>Il provvedimento è stato confermato → `confermato`<br>Nessuna risposta da più di un mese → `nessuna_risposta`<br>Aspetto una risposta da meno di un mese → `in_attesa` | `esito_ricorso` |
| Se Vinted ha risposto al ricorso, in che giorno? (facoltativa) | data | - | `data_esito` |
| Ti sei rivolto a un organismo di risoluzione extragiudiziale certificato (per esempio ADR Center)? | una risposta | Sì → `si`<br>No → `no` | `adr` |
| Se sì, com'è andata con l'organismo extragiudiziale? (facoltativa) | una risposta | A mio favore → `favorevole`<br>Contro di me → `sfavorevole`<br>In attesa → `in_attesa` | `esito_adr` |
| Hai chiesto a Vinted i tuoi dati personali con una richiesta di accesso (art. 15 GDPR)? | una risposta | Sì → `si`<br>No → `no` | `richiesta_gdpr_utente` |
| Se Vinted ha risposto alla richiesta di accesso, che cosa dice sul motivo e su come è stata presa la decisione? (facoltativa) | testo lungo | - | `risposta_gdpr` |

## Prove di acquisto

Solo casi. 

| Domanda | Tipo | Risposte → codice | Colonna |
| --- | --- | --- | --- |
| Quali prove hai sugli articoli contestati?<br>*Puoi sceglierne più di una. Non inviarle qui.* | più risposte | Scontrino o fattura → `scontrino`<br>Conferma d'ordine online → `ordine_online`<br>Prova che era un regalo → `regalo_documentato`<br>Foto con data precedente al provvedimento → `foto_datate`<br>Certificato di autenticità → `certificato`<br>Nessuna → `nessuna` | `prove_disponibili` |
| Parola di riferimento per l'email (facoltativa)<br>*Se invii screenshot, inventa una parola (per esempio girasole42), scrivila qui e mettila nell'oggetto dell'email con gli screenshot oscurati, all'indirizzo indicato nell'informativa.* | testo breve | - | in `note` |
| Vuoi aggiungere qualcosa? (facoltativa) | testo lungo | - | `note` |

