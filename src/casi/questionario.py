"""Questionario per casi e controlli: domande, modulo Google e conversione delle risposte.

Le domande stanno solo qui (DOMANDE). Da qui escono, sempre coerenti tra loro:

    python src/casi/questionario.py --testo
        docs/questionario.md: il testo pubblico delle domande, con i codici del codebook.

    python src/casi/questionario.py --modulo
        data/casi/crea_modulo.gs: script per Google Apps Script che crea il modulo su Google Moduli,
        con l'informativa presa da docs/privacy.md. Sta in data/, quindi fuori da GitHub.

    python src/casi/questionario.py --converti risposte.csv
        Converte il CSV scaricato da Google Moduli nel foglio del codebook (data/casi/casi.csv).
        Aggiunge solo le risposte nuove: le righe gia' presenti nel foglio, anche se corrette a mano,
        non si toccano. Le risposte senza consenso non si registrano.

Se cambi il titolo di una domanda nel modulo, cambialo anche qui: la conversione riconosce le domande dal titolo.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comune import RADICE, prepara_console  # noqa: E402

TITOLO_MODULO = "VintedScope: audit black box dei sistemi antifrode di Vinted"
CONFERMA = ("Grazie per aver partecipato. Le risposte si usano solo in forma aggregata e anonima. "
            "Se ti va, fai girare il questionario anche a chi vende su Vinted e non ha mai avuto problemi: "
            "senza di loro il confronto non si può fare.")
FOGLIO = RADICE / "data" / "casi" / "casi.csv"
MODELLO = Path(__file__).with_name("modello_casi.csv")
SI_NO = [("Sì", "si"), ("No", "no")]


PAROLA = r"[A-Za-z0-9]{3,30}"       # parola di riferimento: solo lettere e cifre, niente simboli
MAX_TESTO = 300                      # lunghezza massima di un testo libero tenuto nel foglio


def d(colonna, titolo, tipo, scelte=None, obbligatoria=True, aiuto="", schema=None):
    return dict(colonna=colonna, titolo=titolo, tipo=tipo, scelte=scelte or [], obbligatoria=obbligatoria, aiuto=aiuto,
                schema=schema)


def numero(colonna, titolo, aiuto=""):
    return d(colonna, titolo, "numero", aiuto=aiuto)


# Domande che dipendono dal momento: per i controlli si risponde pensando a oggi,
# per i casi al momento del provvedimento (codebook). Titoli diversi, stessa colonna.
# Solo le variabili che servono a H4, H5 e ai ricorsi: un questionario breve si compila fino in fondo.
def annunci(caso: bool) -> list[dict]:
    if caso:
        return [
            numero("anzianita_mesi", "Da quanti mesi avevi l'account Vinted quando hai ricevuto il provvedimento?",
                   "Una stima va bene: 1 anno = 12 mesi."),
            numero("annunci_attivi", "Quanti annunci avevi attivi quando hai ricevuto il provvedimento?",
                   "Gli annunci visibili sul profilo, esclusi quelli già venduti. Una stima va bene."),
            numero("annunci_nuovi_cartellino", 'Quanti di quegli annunci erano nella condizione "Nuovo con cartellino"?',
                   "È la condizione che scegli quando pubblichi l'annuncio. Scrivi 0 se nessuno."),
            numero("vendite_ultimi_3_mesi", "Quante vendite avevi concluso nei 3 mesi prima del provvedimento?",
                   "Una stima va bene."),
        ]
    return [
        numero("anzianita_mesi", "Da quanti mesi hai l'account Vinted?", "Una stima va bene: 1 anno = 12 mesi."),
        numero("annunci_attivi", "Quanti annunci hai attivi oggi?",
               "Gli annunci visibili sul profilo, esclusi quelli già venduti. Una stima va bene."),
        numero("annunci_nuovi_cartellino", 'Quanti di questi annunci sono nella condizione "Nuovo con cartellino"?',
               "È la condizione che scegli quando pubblichi l'annuncio. Scrivi 0 se nessuno."),
        numero("vendite_ultimi_3_mesi", "Quante vendite hai concluso negli ultimi 3 mesi?", "Una stima va bene."),
    ]


CONSENSO = d("consenso", "Hai almeno 18 anni e acconsenti al trattamento dei dati descritto qui sopra?",
             "scelta", [("Sì, ho almeno 18 anni e acconsento", "si"), ("No", "no")])
GRUPPO = d("gruppo", "Vinted ha mai preso un provvedimento sul tuo account o sui tuoi annunci?", "scelta",
           [("Sì", "caso"), ("No", "controllo")],
           aiuto="Per esempio: rimozione di annunci, limitazione di alcune funzioni, sospensione o blocco dell'account, "
                 "blocco dei fondi.")

# Pagine nell'ordine del modulo. "fine": dopo questa pagina il modulo si invia (i controlli finiscono qui).
PAGINE = [
    dict(id="consenso", titolo="", aiuto="", domande=[CONSENSO]),
    dict(id="profilo", titolo="Il tuo profilo", aiuto="", domande=[
        d("paese", "In quale paese vendi su Vinted?", "scelta", [
            ("Italia", "IT"), ("Francia", "FR"), ("Un altro paese dell'Unione europea", "altro_UE"),
            ("Un paese fuori dall'Unione europea (per esempio Regno Unito o Svizzera)", "extra_UE")]),
        d("tipo_account", "Che tipo di account Vinted hai?", "scelta",
          [("Privato", "privato"), ("Professionale (Vinted Pro)", "pro")],
          aiuto="Se hai ricevuto un provvedimento, l'account che avevi in quel momento."),
        d("categoria_prevalente", "Che cosa vendi di più?", "scelta", [
            ("Abbigliamento", "abbigliamento"), ("Scarpe", "scarpe"), ("Borse e accessori", "borse_accessori"),
            ("Cosmetici e profumi", "cosmetici"), ("Elettronica", "elettronica"), ("Altro", "altro")]),
        GRUPPO,
    ]),
    dict(id="controlli", titolo="I tuoi annunci oggi", aiuto="", fine=True, domande=annunci(caso=False)),
    dict(id="casi", titolo="I tuoi annunci prima del provvedimento",
         aiuto="Se i provvedimenti sono più di uno, in tutto il questionario rispondi pensando al più recente.",
         domande=annunci(caso=True)),
    dict(id="provvedimento", titolo="Il provvedimento", aiuto="", domande=[
        d("periodo_provvedimento", "Quando Vinted ha preso il provvedimento?", "scelta", [
            ("Prima del 17 ottobre 2026", "prima"), ("Dal 17 ottobre 2026 in poi", "dopo")],
          aiuto="Il 17 ottobre 2026 è il giorno dei saccheggi."),
        d("tipo_provvedimento", "Che provvedimento era?", "scelta", [
            ("Rimozione di uno o più annunci", "rimozione_annuncio"),
            ("Limitazione di alcune funzioni", "limitazione_funzioni"),
            ("Sospensione temporanea dell'account", "sospensione_temporanea"),
            ("Blocco definitivo dell'account", "blocco_definitivo"),
            ("Blocco dei fondi nel borsellino", "blocco_fondi")],
          aiuto="Se erano più cose insieme, scegli la più grave."),
        d("motivo_dichiarato", "Quale motivo ha indicato Vinted?", "scelta", [
            ("Merce rubata o di provenienza illecita", "merce_rubata"),
            ("Attività commerciale (vendere come un negozio senza account Pro)", "attivita_commerciale"),
            ("Articolo contraffatto", "contraffazione"),
            ("Frode, truffa o sicurezza dell'account", "frode"),
            ("Un altro motivo", "altro"),
            ("Nessun motivo", "nessuno")]),
        d("notifica_disponibile", "Puoi inviare uno screenshot della notifica di Vinted, con i dati personali oscurati?",
          "scelta", SI_NO, aiuto="Si invia per email, vedi l'ultima pagina."),
    ]),
    dict(id="ricorsi", titolo="Ricorsi", aiuto="", domande=[
        d("ricorso", "Hai chiesto a Vinted di rivedere il provvedimento (ricorso interno)?", "scelta", SI_NO,
          aiuto="Per esempio tramite l'assistenza o il modulo di reclamo."),
        d("esito_ricorso", "Se sì, com'è andato il ricorso?", "scelta", [
            ("Il provvedimento è stato revocato", "revocato"),
            ("Il provvedimento è stato confermato", "confermato"),
            ("Nessuna risposta da più di un mese", "nessuna_risposta"),
            ("Aspetto una risposta da meno di un mese", "in_attesa")], obbligatoria=False),
        d("giorni_esito", "Se Vinted ha risposto, dopo quanti giorni circa?", "numero", obbligatoria=False,
          aiuto="Una stima va bene: 1 settimana = 7 giorni."),
        d("adr", "Ti sei rivolto a un organismo di risoluzione extragiudiziale certificato (per esempio ADR Center)?",
          "scelta", SI_NO),
        d("esito_adr", "Se sì, com'è andata con l'organismo extragiudiziale?", "scelta", [
            ("A mio favore", "favorevole"), ("Contro di me", "sfavorevole"), ("In attesa", "in_attesa")],
          obbligatoria=False),
    ]),
    dict(id="prove", titolo="Prove di acquisto", aiuto="", domande=[
        d("prove_disponibili", "Quali prove hai sugli articoli contestati?", "caselle", [
            ("Scontrino o fattura", "scontrino"), ("Conferma d'ordine online", "ordine_online"),
            ("Prova che era un regalo", "regalo_documentato"), ("Foto con data precedente al provvedimento", "foto_datate"),
            ("Certificato di autenticità", "certificato"), ("Nessuna", "nessuna")],
          aiuto="Puoi sceglierne più di una. Non inviarle qui."),
        d(None, "Parola di riferimento per l'email", "testo", obbligatoria=False, schema=PAROLA,
          aiuto="Solo se invii screenshot: inventa una parola (per esempio girasole42), scrivila qui e mettila nell'oggetto "
                "dell'email con gli screenshot oscurati, all'indirizzo indicato nell'informativa."),
    ]),
]
DOMANDE = [q for p in PAGINE for q in p["domande"]]


def controlla_definizioni() -> None:
    titoli = [q["titolo"] for q in DOMANDE]
    doppi = {t for t in titoli if titoli.count(t) > 1}
    assert not doppi, f"Titoli ripetuti: {doppi}"
    for q in DOMANDE:
        if q["tipo"] == "caselle":
            # Google Moduli separa le caselle scelte con ", ": nessuna etichetta deve contenere una virgola.
            assert all("," not in e for e, _ in q["scelte"]), q["titolo"]
    colonne = set(pd.read_csv(MODELLO, nrows=0).columns)
    fuori = {q["colonna"] for q in DOMANDE if q["colonna"]} - colonne
    assert not fuori, f"Colonne non nel modello: {fuori}"


# ---------------------------------------------------------------- testo pubblico

TIPI = {"scelta": "una risposta", "caselle": "più risposte", "numero": "numero intero", "data": "data",
        "testo": "testo breve", "paragrafo": "testo lungo"}


def testo() -> None:
    righe = [
        "# Questionario per casi e controlli\n\n",
        "Testo delle domande del questionario su Google Moduli, pubblicato prima di aprirlo. Lo genera "
        "`src/casi/questionario.py --testo`, dalle stesse definizioni che creano il modulo e convertono le risposte "
        "nel foglio del codebook (`docs/codebook_casi.md`). Il modulo si apre con l'informativa sul trattamento "
        "dei dati.\n\n",
        "Percorso: chi risponde \"No\" al consenso finisce lì. Chi non ha mai ricevuto provvedimenti (controllo) "
        "risponde al profilo e agli annunci di oggi. Chi ha ricevuto un provvedimento (caso) risponde agli annunci "
        "al momento del provvedimento e poi alle domande su provvedimento, ricorsi e prove. "
        "Le colonne del codebook non presenti qui le compila chi analizza: `id_caso`, `data_raccolta` e "
        "`ora_risposta` (dalla data e ora della risposta), `quota_nuovi_cartellino` (calcolata) e la classificazione "
        "dei casi.\n\n",
    ]
    for p in PAGINE:
        titolo = p["titolo"] or "Consenso"
        righe.append(f"## {titolo}\n\n")
        if p["id"] == "controlli":
            righe.append("Solo controlli. Dopo questa pagina il modulo si invia.\n\n")
        if p["id"] in ("casi", "provvedimento", "ricorsi", "prove"):
            righe.append("Solo casi. " + (p["aiuto"] + "\n\n" if p["aiuto"] else "\n\n"))
        righe.append("| Domanda | Tipo | Risposte → codice | Colonna |\n| --- | --- | --- | --- |\n")
        for q in p["domande"]:
            dom = q["titolo"] + ("" if q["obbligatoria"] else " (facoltativa)")
            if q["aiuto"]:
                dom += f"<br>*{q['aiuto']}*"
            risposte = "<br>".join(f"{e} → `{c}`" for e, c in q["scelte"]) or "-"
            col = f"`{q['colonna']}`" if q["colonna"] else "in `note`"
            righe.append(f"| {dom} | {TIPI[q['tipo']]} | {risposte} | {col} |\n")
        righe.append("\n")
    uscita = RADICE / "docs" / "questionario.md"
    uscita.write_text("".join(righe), encoding="utf-8")
    print(f"Scritto: {uscita}")


# ---------------------------------------------------------------- modulo Google

def informativa() -> str:
    percorso = RADICE / "docs" / "privacy.md"
    if not percorso.exists():
        sys.exit(f"Manca {percorso}: serve per il testo dell'informativa.")
    parti = re.split(r"^---\s*$", percorso.read_text(encoding="utf-8"), flags=re.M)
    if len(parti) < 3:
        sys.exit("In docs/privacy.md l'informativa deve stare tra due righe '---'.")
    t = parti[1].strip()
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    return re.sub(r"\n{3,}", "\n\n", t)


def modulo() -> None:
    def js(x) -> str:
        return json.dumps(x, ensure_ascii=False)

    righe = [
        "// Crea il questionario su Google Moduli. Generato da src/casi/questionario.py --modulo: non modificarlo a mano.",
        "// Uso: script.google.com > Nuovo progetto > incolla tutto > Salva > scegli creaModulo > Esegui.",
        "function creaModulo() {",
        f"  var form = FormApp.create({js(TITOLO_MODULO)});",
        f"  form.setDescription({js(informativa())});",
        f"  form.setConfirmationMessage({js(CONFERMA)});",
        "  form.setProgressBar(true);",
        "  form.setAllowResponseEdits(false);",
        "  var numero = FormApp.createTextValidation().setHelpText('Scrivi un numero intero, senza punti né lettere.')",
        "      .requireWholeNumber().build();",
        "  var pagine = {};",
        "  var domande = {};",
        "  var item;",
    ]
    for p in PAGINE:
        if p["id"] != "consenso":
            righe.append(f"  pagine[{js(p['id'])}] = form.addPageBreakItem().setTitle({js(p['titolo'])})"
                         + (f".setHelpText({js(p['aiuto'])})" if p["aiuto"] else "") + ";")
        for q in p["domande"]:
            metodo = {"scelta": "addMultipleChoiceItem", "caselle": "addCheckboxItem", "numero": "addTextItem",
                      "data": "addDateItem", "testo": "addTextItem", "paragrafo": "addParagraphTextItem"}[q["tipo"]]
            riga = f"  item = form.{metodo}().setTitle({js(q['titolo'])}).setRequired({js(q['obbligatoria'])})"
            if q["aiuto"]:
                riga += f".setHelpText({js(q['aiuto'])})"
            if q["tipo"] in ("scelta", "caselle"):
                riga += f".setChoiceValues({js([e for e, _ in q['scelte']])})"
            if q["tipo"] == "numero":
                riga += ".setValidation(numero)"
            if q["schema"]:
                riga += (".setValidation(FormApp.createTextValidation().setHelpText('Da 3 a 30 tra lettere e cifre, senza spazi "
                         "né simboli.').requireTextMatchesPattern(" + js("^" + q["schema"] + "$") + ").build())")
            if q["tipo"] == "data":
                riga += ".setIncludesYear(true)"
            righe.append(riga + ";")
            if q["colonna"] in ("consenso", "gruppo"):
                righe.append(f"  domande[{js(q['colonna'])}] = item;")
    # Percorsi: consenso no -> invio; gruppo si -> pagina dei casi, no -> pagina dei controlli;
    # alla fine della pagina dei controlli -> invio (si imposta sulla pagina che la segue).
    si_c, no_c = CONSENSO["scelte"][0][0], CONSENSO["scelte"][1][0]
    si_g, no_g = GRUPPO["scelte"][0][0], GRUPPO["scelte"][1][0]
    righe += [
        "  var c = domande['consenso'];",
        f"  c.setChoices([c.createChoice({js(si_c)}, FormApp.PageNavigationType.CONTINUE),",
        f"                c.createChoice({js(no_c)}, FormApp.PageNavigationType.SUBMIT)]);",
        "  var g = domande['gruppo'];",
        f"  g.setChoices([g.createChoice({js(si_g)}, pagine['casi']), g.createChoice({js(no_g)}, pagine['controlli'])]);",
    ]
    for i, p in enumerate(PAGINE):
        if p.get("fine"):
            righe.append(f"  pagine[{js(PAGINE[i + 1]['id'])}].setGoToPage(FormApp.PageNavigationType.SUBMIT);")
    righe += [
        "  // Resta chiuso finché non lo controlli e premi Pubblica nell'editor.",
        "  try { form.setPublished(false); } catch (e) { Logger.log('Nota: ' + e); }",
        "  Logger.log('Modulo creato. Per controllarlo e pubblicarlo: ' + form.getEditUrl());",
        "}",
        "",
    ]
    uscita = RADICE / "data" / "casi" / "crea_modulo.gs"
    uscita.parent.mkdir(parents=True, exist_ok=True)
    uscita.write_text("\n".join(righe), encoding="utf-8")
    print(f"Scritto: {uscita}\nIncollalo in un nuovo progetto su script.google.com ed esegui creaModulo.")


# ---------------------------------------------------------------- conversione delle risposte

def ora(testo_ora: str) -> str | None:
    """Data e ora della risposta in AAAA-MM-GG HH:MM:SS, dai formati usati da Google (anche 'PM', '23.21.05')."""
    t = testo_ora.strip()
    m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", t)
    if m:
        a, me, g = m.groups()
    else:
        m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", t)
        if not m:
            return None
        g, me, a = m.groups()
    h = re.search(r"(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?\s*([AaPp][Mm])?", t[m.end():])
    hh, mm, ss = (int(h.group(1)), int(h.group(2)), int(h.group(3) or 0)) if h else (0, 0, 0)
    if h and h.group(4):
        hh = hh % 12 + (12 if h.group(4).lower() == "pm" else 0)
    try:
        return dt.datetime(int(a), int(me), int(g), hh, mm, ss).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:   # per esempio mese 17: data scritta in un formato non previsto
        return None


def giorno(testo_data: str) -> str:
    t = testo_data.strip()
    if not t:
        return ""
    o = ora(t)
    return o[:10] if o else "?" + t


def pulisci(v: str, massimo: int = MAX_TESTO) -> str:
    """Toglie i caratteri di controllo, riduce gli spazi e accorcia: quello che arriva dal modulo e' solo dato."""
    v = re.sub(r"[\x00-\x1f\x7f]+", " ", v)
    return re.sub(r"\s+", " ", v).strip()[:massimo]


def neutralizza(v: str) -> str:
    """Un testo che inizia con = + - @ sarebbe una formula se il CSV si apre in Excel o Fogli Google: si prefissa con '."""
    return "'" + v if v[:1] in ("=", "+", "-", "@") else v


def breve(v: str, massimo: int = 40) -> str:
    """Per i messaggi a schermo: nessun testo libero intero."""
    return re.sub(r"[^\w .,'-]", "?", v)[:massimo]


def converti(percorso: Path) -> None:
    risposte = pd.read_csv(percorso, dtype=str, keep_default_na=False)
    colonne = list(pd.read_csv(MODELLO, nrows=0).columns)
    per_titolo = {q["titolo"]: q for q in DOMANDE}
    presenti = [c for c in risposte.columns[1:] if c.strip() in per_titolo]
    ignote = [c for c in risposte.columns[1:] if c.strip() not in per_titolo]
    mancanti = [t for t in per_titolo if t not in {c.strip() for c in risposte.columns}]
    avvisi = [f"Colonna del CSV non riconosciuta (titolo cambiato?): {c}" for c in ignote]
    avvisi += [f"Domanda non trovata nel CSV: {t}" for t in mancanti]

    esistente = pd.read_csv(FOGLIO, dtype=str, keep_default_na=False) if FOGLIO.exists() else pd.DataFrame(columns=colonne)
    for c in colonne:
        if c not in esistente:
            esistente[c] = ""
    gia = set(esistente["ora_risposta"])
    prossimo = {}
    for pref in ("C", "K"):
        numeri = [int(i[1:]) for i in esistente["id_caso"] if re.fullmatch(pref + r"\d+", i)]
        prossimo[pref] = max(numeri, default=0) + 1

    nuove, senza_consenso, doppie = [], 0, 0
    righe = []
    for _, r in risposte.iterrows():
        o = ora(r.iloc[0])
        if o is None:
            avvisi.append(f"Riga con data e ora non leggibili, saltata: {r.iloc[0]!r}")
            continue
        righe.append((o, r))
    for o, r in sorted(righe, key=lambda x: x[0]):
        if o in gia:
            doppie += 1
            continue
        riga = {c: "" for c in colonne}
        riferimento = ""
        for col_csv in presenti:
            q = per_titolo[col_csv.strip()]
            v = pulisci(r[col_csv])
            if not v:
                continue
            if q["colonna"] is None:
                if not re.fullmatch(PAROLA, v):
                    avvisi.append(f"Risposta {o}: parola di riferimento non valida, scartata ({breve(v)})")
                    continue
                riferimento = v
                continue
            if q["tipo"] == "numero" and not re.fullmatch(r"\d{1,6}", v):
                avvisi.append(f"Risposta {o}: numero non valido in \"{q['titolo']}\", lasciato vuoto ({breve(v)})")
                continue
            if q["tipo"] == "scelta":
                codice = dict(q["scelte"]).get(v)
                if codice is None:
                    avvisi.append(f"Risposta {o}: '{breve(v)}' non è tra le scelte di \"{q['titolo']}\"")
                    continue
                v = codice
            elif q["tipo"] == "caselle":
                mappa = dict(q["scelte"])
                parti = [p.strip() for p in v.split(", ")]
                sbagliate = [p for p in parti if p not in mappa]
                if sbagliate:
                    avvisi.append(f"Risposta {o}: scelte non riconosciute in \"{q['titolo']}\": "
                                  f"{[breve(x) for x in sbagliate]}")
                v = "; ".join(mappa[p] for p in parti if p in mappa)
            elif q["tipo"] == "data":
                v = giorno(v)
                if v.startswith("?"):
                    avvisi.append(f"Risposta {o}: data non leggibile in \"{q['titolo']}\": {breve(v[1:])}")
                    v = ""
            if riga[q["colonna"]] and riga[q["colonna"]] != v:
                avvisi.append(f"Risposta {o}: due valori per {q['colonna']}")
            riga[q["colonna"]] = v
        if riga["consenso"] != "si":
            senza_consenso += 1
            continue
        pref = "C" if riga["gruppo"] == "caso" else "K"
        riga["id_caso"] = f"{pref}{prossimo[pref]:03d}"
        prossimo[pref] += 1
        riga["ora_risposta"], riga["data_raccolta"] = o, o[:10]
        for c in ("data_provvedimento", "data_ricorso", "data_esito"):
            if riga[c] and riga[c] > riga["data_raccolta"]:
                avvisi.append(f"{riga['id_caso']}: {c} ({riga[c]}) è dopo la data della risposta: da verificare")
        try:
            a, n = float(riga["annunci_attivi"]), float(riga["annunci_nuovi_cartellino"])
            riga["quota_nuovi_cartellino"] = f"{n / a:.3f}" if a > 0 and 0 <= n <= a else ""
        except ValueError:
            pass
        promemoria = []
        if riga["notifica_disponibile"] == "si":
            promemoria.append("screenshot promesso: notifica_disponibile resta si solo se arriva")
        if riferimento:
            promemoria.append(f"riferimento email: {riferimento}")
        riga["note"] = " | ".join(promemoria + ([riga["note"]] if riga["note"] else []))
        nuove.append({k: neutralizza(x) for k, x in riga.items()})

    tutto = pd.concat([esistente[colonne], pd.DataFrame(nuove, columns=colonne)], ignore_index=True)
    FOGLIO.parent.mkdir(parents=True, exist_ok=True)
    tutto.to_csv(FOGLIO, index=False, encoding="utf-8")
    casi = sum(1 for x in nuove if x["gruppo"] == "caso")
    print(f"Risposte nel CSV: {len(risposte)}. Nuove aggiunte: {len(nuove)} ({casi} casi, {len(nuove) - casi} controlli). "
          f"Già nel foglio: {doppie}. Senza consenso, non registrate: {senza_consenso}.")
    if senza_consenso:
        print("Cancella dal modulo le risposte senza consenso.")
    for a in avvisi:
        print("Attenzione:", a)
    print(f"Scritto: {FOGLIO}")


def main() -> None:
    prepara_console()
    controlla_definizioni()
    parser = argparse.ArgumentParser(description="Questionario: testo, modulo Google, conversione delle risposte")
    gruppo = parser.add_mutually_exclusive_group(required=True)
    gruppo.add_argument("--testo", action="store_true", help="scrive docs/questionario.md")
    gruppo.add_argument("--modulo", action="store_true", help="scrive data/casi/crea_modulo.gs")
    gruppo.add_argument("--converti", type=Path, metavar="RISPOSTE.csv", help="aggiunge le risposte nuove a data/casi/casi.csv")
    args = parser.parse_args()
    if args.testo:
        testo()
    elif args.modulo:
        modulo()
    else:
        converti(args.converti)


if __name__ == "__main__":
    main()
