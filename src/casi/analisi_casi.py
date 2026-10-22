"""Analisi dei casi documentati e dei controlli (H4, H5 e descrittive dei casi).

Legge il foglio compilato secondo docs/codebook_casi.md (di default data/casi/casi.csv, fuori da GitHub).
Le regole sono quelle della preregistrazione (sezione 7, H4 e H5) e delle precisazioni del 22 ottobre 2026
in docs/registro_modifiche.md. Scritto e pubblicato prima di raccogliere qualsiasi risposta.

Due passi, in quest'ordine:

    python src/casi/analisi_casi.py --numerosita
        Legge SOLO i controlli e usa i primi 30 validi per fissare la numerosita' di H5.
        Carica il foglio e scarta subito le righe dei casi: nessun loro valore e' usato o mostrato.
        Scrive reports/casi_numerosita.md.
        Il numero si copia in config/progetto.yaml (h5_numerosita_per_gruppo) e si registra,
        con data, in docs/registro_modifiche.md, prima di lanciare il passo successivo.

    python src/casi/analisi_casi.py
        H4, H5 e tabelle descrittive. Scrive reports/casi.md.
        Si rifiuta di partire se la numerosita' non e' registrata in config/progetto.yaml,
        perche' il piano vuole che sia fissata prima di guardare i casi. Se non si arriva mai
        a 30 controlli validi, si lancia con --senza-numerosita: H5 diventa solo esplorativa.

Opzione comune: --file percorso.csv per leggere un foglio diverso da data/casi/casi.csv.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comune import RADICE, REPORTS, carica_config, prepara_console  # noqa: E402

# Parametri fissati prima di aprire il questionario (preregistrazione, sezione 7; registro, 22 ottobre 2026).
DATA_EVENTO = dt.date(2026, 10, 17)
SOGLIA_ESPOSTO = 0.5                # esposto = almeno il 50% degli annunci "nuovo con cartellino"
MIN_GRUPPO_H4 = 15                  # sotto, H4 e' solo descrittiva
ALFA = 0.05
OR_OBIETTIVO = 2.0
POTENZA = 0.80
CONTROLLI_PILOTA = 30               # controlli usati per stimare la quota di esposti
LIVELLO_WILSON = 0.80
TETTO_PER_GRUPPO = 300
CHIUSURA_RECLUTAMENTO = dt.date(2027, 1, 31)
MIN_VENDITE = 10                    # vendite negli ultimi 3 mesi, criterio di inclusione di H5
PAESI_UE = {"IT", "FR", "altro_UE"}
MIN_PER_CATEGORIA = 10              # categorie con meno risposte nel campione di H5 confluiscono in "altro"
CATEGORIA_RIFERIMENTO = "abbigliamento"
MIN_DOPPIA_CODIFICA = 10            # casi codificati da due persone necessari per riportare il kappa

FILE_DEFAULT = RADICE / "data" / "casi" / "casi.csv"

VALORI = {
    "gruppo": {"caso", "controllo"},
    "consenso": {"si"},
    "paese": {"IT", "FR", "altro_UE", "extra_UE"},
    "tipo_account": {"privato", "pro"},
    "categoria_prevalente": {"abbigliamento", "scarpe", "borse_accessori", "cosmetici", "elettronica", "altro"},
    "motivo_dichiarato": {"merce_rubata", "attivita_commerciale", "contraffazione", "frode", "altro", "nessuno"},
    "notifica_disponibile": {"si", "no"},
    "esito_ricorso": {"revocato", "confermato", "nessuna_risposta", "in_attesa"},
    "canale_raccolta": {"modulo", "reddit", "gruppo_facebook", "altroconsumo", "altro"},
    "fascia_marchi": {"lusso", "premium_streetwear", "fast_fashion", "misti"},
    "tipo_provvedimento": {"rimozione_annuncio", "limitazione_funzioni", "sospensione_temporanea", "blocco_definitivo",
                           "blocco_fondi"},
    "ricorso": {"si", "no"},
    "adr": {"si", "no"},
    "esito_adr": {"favorevole", "sfavorevole", "in_attesa"},
    "richiesta_gdpr_utente": {"si", "no"},
    "pertinenza_prove": {"contraddicono_il_motivo", "non_pertinenti", "insufficienti"},
    "esito_istituzionale": {"errore_riconosciuto", "revocato_senza_spiegazione", "confermato", "pendente", "mai_contestato"},
    "classe_caso": {"errore_riconosciuto", "errore_documentato", "ripristino_senza_spiegazione",
                    "errore_plausibile", "indeterminato"},
}
CLASSI_SEVERO = {"errore_riconosciuto", "errore_documentato"}
CLASSI_LARGO = CLASSI_SEVERO | {"ripristino_senza_spiegazione", "errore_plausibile"}
NUMERICHE = ["anzianita_mesi", "annunci_attivi", "annunci_nuovi_cartellino", "quota_nuovi_cartellino",
             "vendite_ultimi_3_mesi"]
DATE = ["data_raccolta", "data_provvedimento", "data_ricorso", "data_esito"]


# ---------------------------------------------------------------- lettura e controlli

def leggi(percorso: Path, solo_controlli: bool) -> pd.DataFrame:
    if not percorso.exists():
        sys.exit(f"Manca il foglio dei casi: {percorso}")
    df = pd.read_csv(percorso, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    attese = pd.read_csv(Path(__file__).with_name("modello_casi.csv"), nrows=0).columns
    mancanti = [c for c in attese if c not in df.columns]
    if mancanti:
        sys.exit(f"Nel foglio mancano colonne del modello: {mancanti}")
    df = df.apply(lambda s: s.str.strip())
    if solo_controlli:
        # Per la numerosita' si tengono solo i controlli: le righe dei casi si scartano qui, prima di qualsiasi calcolo.
        df = df[df["gruppo"] == "controllo"].copy()
    for c in NUMERICHE:
        df[c] = pd.to_numeric(df[c].str.replace(",", ".", regex=False), errors="coerce")
    for c in DATE:
        scritte_male = df[(df[c] != "") & pd.to_datetime(df[c], format="%Y-%m-%d", errors="coerce").isna()]
        for i in scritte_male["id_caso"]:
            print(f"Attenzione: {i}, {c} non è nel formato AAAA-MM-GG: trattata come mancante")
    for c in DATE:
        giorni = pd.to_datetime(df[c], format="%Y-%m-%d", errors="coerce")
        df[c] = [g.date() if pd.notna(g) else None for g in giorni]   # data mancante o scritta male = None
    return df


def e_data(d) -> bool:
    return isinstance(d, dt.date)


def controlla(df: pd.DataFrame) -> list[str]:
    """Valori fuori dal codebook e incoerenze. Non cambia i dati: elenca i problemi da correggere a mano."""
    avvisi = []
    for col, ammessi in VALORI.items():
        if col not in df:
            continue
        sbagliati = df[(df[col] != "") & ~df[col].isin(ammessi)]
        for _, r in sbagliati.iterrows():
            avvisi.append(f"{r['id_caso']}: {col} = '{r[col]}' non previsto dal codebook")
    prove = {"scontrino", "ordine_online", "regalo_documentato", "foto_datate", "certificato", "nessuna"}
    for _, r in df[df["prove_disponibili"] != ""].iterrows():
        sbagliate = [p for p in re.split(r"[;,]\s*", r["prove_disponibili"]) if p and p not in prove]
        if sbagliate:
            avvisi.append(f"{r['id_caso']}: prove_disponibili contiene valori non previsti: {sbagliate}")
    doppi = df["id_caso"][df["id_caso"].duplicated()].unique()
    avvisi += [f"{i}: id_caso ripetuto" for i in doppi]
    q = df["annunci_nuovi_cartellino"] / df["annunci_attivi"]
    dichiarata = df["quota_nuovi_cartellino"]
    diversa = dichiarata.notna() & q.notna() & ((dichiarata - q).abs() > 0.01)
    avvisi += [f"{i}: quota_nuovi_cartellino diversa da nuovi/attivi (si usa nuovi/attivi)"
               for i in df.loc[diversa, "id_caso"]]
    troppi = df["annunci_nuovi_cartellino"] > df["annunci_attivi"]
    avvisi += [f"{i}: più annunci con cartellino che annunci attivi (quota non calcolabile)"
               for i in df.loc[troppi, "id_caso"]]
    senza_data = (df["gruppo"] == "caso") & df["data_provvedimento"].isna()
    avvisi += [f"{i}: caso senza data_provvedimento valida (escluso da H4 e H5)" for i in df.loc[senza_data, "id_caso"]]
    if "classe_caso" in df:
        casi = df[df["gruppo"] == "caso"]
        regola = casi["esito_istituzionale"].eq("errore_riconosciuto") & casi["classe_caso"].ne("errore_riconosciuto")
        avvisi += [f"{i}: esito errore_riconosciuto ma classe diversa (regola di precedenza del codebook)"
                   for i in casi.loc[regola, "id_caso"]]
        regola = (casi["pertinenza_prove"].eq("contraddicono_il_motivo")
                  & ~casi["classe_caso"].isin(CLASSI_SEVERO) & casi["classe_caso"].ne(""))
        avvisi += [f"{i}: prove che contraddicono il motivo ma classe non tra gli errori documentati"
                   for i in casi.loc[regola, "id_caso"]]
    return avvisi


def quota_valida(df: pd.DataFrame) -> pd.Series:
    """Quota cartellino = nuovi con cartellino / annunci attivi; NaN se i due numeri non sono utilizzabili."""
    a, n = df["annunci_attivi"], df["annunci_nuovi_cartellino"]
    ok = a.notna() & n.notna() & (a > 0) & (n >= 0) & (n <= a)
    return (n / a).where(ok)


def base_h5(df: pd.DataFrame) -> tuple[pd.DataFrame, list[tuple[str, int]]]:
    """Criteri di inclusione di H5, uguali per casi e controlli. Restituisce le righe incluse e il flusso."""
    flusso = [("Righe nel foglio", len(df))]
    passi = [
        ("Consenso", df["consenso"] == "si"),
        ("Account privato", df["tipo_account"] == "privato"),
        ("Paese UE", df["paese"].isin(PAESI_UE)),
        (f"Almeno {MIN_VENDITE} vendite negli ultimi 3 mesi", df["vendite_ultimi_3_mesi"] >= MIN_VENDITE),
        (f"Raccolto entro il {CHIUSURA_RECLUTAMENTO}", df["data_raccolta"].map(
            lambda d: e_data(d) and d <= CHIUSURA_RECLUTAMENTO)),
        ("Quota cartellino calcolabile", df["quota"].notna()),
    ]
    tieni = pd.Series(True, index=df.index)
    for nome, cond in passi:
        tieni &= cond.fillna(False).astype(bool)
        flusso.append((nome, int(tieni.sum())))
    return df[tieni].copy(), flusso


# ---------------------------------------------------------------- numerosita' (solo controlli)

def n_per_gruppo(p0: float) -> float:
    """Numerosita' per gruppo, formula della sezione 7 (due proporzioni, alfa a due code, 1:1)."""
    from scipy.stats import norm
    p1 = OR_OBIETTIVO * p0 / (1 - p0 + OR_OBIETTIVO * p0)
    if not 0 < p0 < 1 or p1 == p0:
        return math.inf
    pm = (p0 + p1) / 2
    za, zb = norm.ppf(1 - ALFA / 2), norm.ppf(POTENZA)
    n = (za * math.sqrt(2 * pm * (1 - pm)) + zb * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2 / (p1 - p0) ** 2
    return float(math.ceil(n - 1e-9))


def wilson(k: int, n: int, livello: float) -> tuple[float, float]:
    from scipy.stats import norm
    z = norm.ppf(1 - (1 - livello) / 2)
    p = k / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    mezzo = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centro - mezzo), min(1.0, centro + mezzo)


def numerosita(percorso: Path) -> None:
    df = leggi(percorso, solo_controlli=True)
    df["quota"] = quota_valida(df)
    inclusi, _ = base_h5(df)
    inclusi = inclusi.sort_values(["data_raccolta", "id_caso"], key=lambda s: s.astype(str))
    if len(inclusi) < CONTROLLI_PILOTA:
        sys.exit(f"Controlli validi finora: {len(inclusi)} su {CONTROLLI_PILOTA}. Riprova quando sono {CONTROLLI_PILOTA}.")
    pilota = inclusi.head(CONTROLLI_PILOTA)
    k = int((pilota["quota"] >= SOGLIA_ESPOSTO).sum())
    p0 = k / CONTROLLI_PILOTA
    basso, alto = wilson(k, CONTROLLI_PILOTA, LIVELLO_WILSON)
    n_basso, n_alto, n_stima = n_per_gruppo(basso), n_per_gruppo(alto), n_per_gruppo(p0)
    n_fissato = int(min(max(n_basso, n_alto), TETTO_PER_GRUPPO))

    def f(n):
        return "non finita" if math.isinf(n) else f"{int(n)}"

    testo = (
        "# Numerosità di H5\n\n"
        f"Calcolata il {dt.date.today().isoformat()} sui primi {CONTROLLI_PILOTA} controlli validi, "
        "senza usare né mostrare i dati dei casi (preregistrazione, sezione 7, punti 1-4).\n\n"
        f"- Controlli usati (in ordine di arrivo): {', '.join(pilota['id_caso'])}\n"
        f"- Esposti (almeno il {pct(SOGLIA_ESPOSTO, 0)} degli annunci nuovi con cartellino): {k} su {CONTROLLI_PILOTA}, "
        f"quota {pct(p0)}\n"
        f"- Intervallo di Wilson all'{pct(LIVELLO_WILSON, 0)}: {pct(basso)} - {pct(alto)}\n"
        f"- Casi per gruppo per OR {num(OR_OBIETTIVO, 0)}, alfa {num(ALFA)} a due code, potenza {pct(POTENZA, 0)}: "
        f"{f(n_basso)} all'estremo basso, {f(n_alto)} all'estremo alto, {f(n_stima)} alla stima puntuale\n"
        f"- **Numerosità fissata: {n_fissato} casi e {n_fissato} controlli** "
        f"(il maggiore dei due estremi, con tetto {TETTO_PER_GRUPPO}; reclutamento chiuso comunque il "
        f"{CHIUSURA_RECLUTAMENTO})\n\n"
        f"I {CONTROLLI_PILOTA} controlli restano nel campione finale.\n"
    )
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "casi_numerosita.md").write_text(testo, encoding="utf-8")
    print(testo)
    print(f"Scritto: {REPORTS / 'casi_numerosita.md'}")
    print(f"\nOra scrivi in config/progetto.yaml:  h5_numerosita_per_gruppo: {n_fissato}\n"
          "e aggiungi una riga con la data in docs/registro_modifiche.md, prima di lanciare l'analisi.")


# ---------------------------------------------------------------- H4

def hodges_lehmann(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Spostamento di Hodges-Lehmann (mediana delle differenze x - y tra tutte le coppie) con intervallo al 95%
    ricavato dalla distribuzione di Mann-Whitney (approssimazione normale): e' la stima che accompagna il test."""
    from scipy.stats import norm
    d = np.sort(np.subtract.outer(x, y).ravel())
    n1, n2 = len(x), len(y)
    k = int(math.floor(n1 * n2 / 2 - norm.ppf(0.975) * math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)))
    k = min(max(k, 0), len(d) - 1)
    return float(np.median(d)), float(d[k]), float(d[len(d) - 1 - k])


def h4(casi: pd.DataFrame) -> dict:
    """Quota cartellino nei casi con provvedimento dal 17 ottobre contro quelli precedenti (Mann-Whitney, una coda)."""
    from scipy.stats import mannwhitneyu
    dopo = casi.loc[casi["dopo"], "quota"].to_numpy()
    prima = casi.loc[~casi["dopo"], "quota"].to_numpy()
    r = dict(n_dopo=len(dopo), n_prima=len(prima))
    if len(dopo) == 0 or len(prima) == 0:
        r["esito"] = "non calcolabile: un gruppo è vuoto"
        return r
    r.update(med_dopo=np.median(dopo), med_prima=np.median(prima),
             iqr_dopo=np.percentile(dopo, [25, 75]), iqr_prima=np.percentile(prima, [25, 75]))
    r["diff"], *r["ci"] = hodges_lehmann(dopo, prima)
    u = mannwhitneyu(dopo, prima, alternative="greater")
    r["superiorita"] = u.statistic / (len(dopo) * len(prima))   # P(dopo > prima) + 0,5 P(pari)
    if min(len(dopo), len(prima)) < MIN_GRUPPO_H4:
        r["esito"] = f"solo descrittiva: un gruppo ha meno di {MIN_GRUPPO_H4} casi"
    else:
        r["p"] = u.pvalue
        r["esito"] = ("sostenuta" if u.pvalue < ALFA else "non sostenuta: nessuna differenza rilevata con questo campione")
    return r


# ---------------------------------------------------------------- H5

def or_grezzo(d: pd.DataFrame) -> tuple[float, float, float, list[int]]:
    """OR della tabella 2x2 con intervallo di Woolf; aggiunge 0,5 a ogni cella se una e' vuota."""
    a = int(((d["y"] == 1) & (d["esposto"] == 1)).sum())
    b = int(((d["y"] == 1) & (d["esposto"] == 0)).sum())
    c = int(((d["y"] == 0) & (d["esposto"] == 1)).sum())
    e = int(((d["y"] == 0) & (d["esposto"] == 0)).sum())
    celle = [a, b, c, e]
    x = [v + 0.5 for v in celle] if 0 in celle else celle
    lor = math.log(x[0] * x[3] / (x[1] * x[2]))
    se = math.sqrt(sum(1 / v for v in x))
    return math.exp(lor), math.exp(lor - 1.96 * se), math.exp(lor + 1.96 * se), celle


def modello(d: pd.DataFrame, esposizione: str) -> dict:
    """provvedimento ~ esposizione + log(annunci) + anzianita' in anni + categoria prevalente."""
    import warnings

    import statsmodels.formula.api as smf
    from statsmodels.tools.sm_exceptions import ConvergenceWarning, PerfectSeparationWarning
    categorie = d["categoria"].nunique()
    formula = (f"y ~ {esposizione} + np.log(annunci_attivi) + anni"
               + (f" + C(categoria, Treatment(reference='{d.attrs['riferimento']}'))" if categorie > 1 else ""))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            warnings.simplefilter("error", PerfectSeparationWarning)
            warnings.simplefilter("error", RuntimeWarning)
            fit = smf.logit(formula, data=d).fit(disp=0, maxiter=200)
        b, se = fit.params[esposizione], fit.bse[esposizione]
        if not fit.mle_retvals.get("converged", True) or not np.isfinite(se) or se > 10:
            raise ValueError("stima instabile, probabile separazione")
        return dict(or_=math.exp(b), basso=math.exp(b - 1.96 * se), alto=math.exp(b + 1.96 * se),
                    p=float(fit.pvalues[esposizione]), n=int(fit.nobs))
    except Exception as e:  # noqa: BLE001
        motivo = {"PerfectSeparationWarning": "separazione perfetta tra i gruppi",
                  "ConvergenceWarning": "la stima non converge"}.get(type(e).__name__, str(e))
        return dict(errore=f"modello non stimabile ({motivo})")


def prepara_h5(base: pd.DataFrame, casi_ammessi: pd.Series | None = None) -> pd.DataFrame:
    """Casi con provvedimento dal 17 ottobre (o il sottoinsieme indicato) e tutti i controlli inclusi."""
    controlli = base[base["gruppo"] == "controllo"]
    casi = base[(base["gruppo"] == "caso") & base["dopo"]] if casi_ammessi is None else base[casi_ammessi]
    d = pd.concat([casi, controlli])
    d = d[d["annunci_attivi"].notna() & d["anzianita_mesi"].notna() & d["categoria_prevalente"].ne("")].copy()
    d["y"] = (d["gruppo"] == "caso").astype(int)
    d["esposto"] = (d["quota"] >= SOGLIA_ESPOSTO).astype(int)
    d["quota10"] = d["quota"] * 10           # OR per 10 punti percentuali di quota
    d["anni"] = d["anzianita_mesi"] / 12
    conta = d["categoria_prevalente"].value_counts()
    rare = set(conta[conta < MIN_PER_CATEGORIA].index)
    d["categoria"] = d["categoria_prevalente"].where(~d["categoria_prevalente"].isin(rare), "altro")
    conta = d["categoria"].value_counts()
    d.attrs["riferimento"] = CATEGORIA_RIFERIMENTO if conta.get(CATEGORIA_RIFERIMENTO, 0) > 0 else (
        conta.index[0] if len(conta) else CATEGORIA_RIFERIMENTO)
    return d


def esito_h5(m: dict, n_registrato: int | None, n_casi: int, n_controlli: int) -> str:
    if n_registrato is None:
        return "esplorativa: numerosità non registrata, nessun verdetto"
    if min(n_casi, n_controlli) < n_registrato:
        return f"esplorativa: numerosità non raggiunta ({n_casi} casi e {n_controlli} controlli su {n_registrato}), nessun verdetto"
    if "errore" in m:
        return "non valutabile: " + m["errore"]
    if m["basso"] > 1:
        return "sostenuta"
    if m["alto"] < 1:
        return "associazione in direzione opposta"
    return "non sostenuta: l'intervallo comprende OR = 1"


# ---------------------------------------------------------------- descrittive dei casi

def kappa(a: pd.Series, b: pd.Series) -> float:
    etichette = sorted(set(a) | set(b))
    t = pd.crosstab(a, b).reindex(index=etichette, columns=etichette, fill_value=0).to_numpy()
    n = t.sum()
    po = np.trace(t) / n
    pe = (t.sum(0) * t.sum(1)).sum() / n ** 2
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


# ---------------------------------------------------------------- rapporto

def num(x: float, cifre: int = 2) -> str:
    return f"{x:.{cifre}f}".replace(".", ",")


def pct(x: float, cifre: int = 1) -> str:
    return f"{x * 100:.{cifre}f}%".replace(".", ",")


def valore_p(p: float) -> str:
    return "< 0,001" if p < 0.001 else num(p, 3)


def analisi(percorso: Path, n_registrato: int | None) -> None:
    tutte = leggi(percorso, solo_controlli=False)
    avvisi = controlla(tutte)
    tutte["quota"] = quota_valida(tutte)
    tutte["dopo"] = tutte["data_provvedimento"].map(lambda d: e_data(d) and d >= DATA_EVENTO)
    tutte["doc_completa"] = (tutte["notifica_disponibile"].eq("si") & tutte["prove_disponibili"].ne("")
                             & tutte["prove_disponibili"].ne("nessuna"))
    df = tutte[tutte["consenso"] == "si"].copy()
    md = ["# Casi documentati e controlli\n\n",
          f"Foglio: `{percorso.name}`, letto il {dt.date.today().isoformat()}. "
          f"Soglia di esposizione: almeno il {SOGLIA_ESPOSTO:.0%} degli annunci \"nuovo con cartellino\". "
          "Regole: preregistrazione (sezione 7) e `docs/registro_modifiche.md`.\n\n"]

    if avvisi:
        md.append(f"## Da correggere nel foglio ({len(avvisi)})\n\n" + "".join(f"- {a}\n" for a in avvisi) + "\n")

    # ---- H4
    casi = df[(df["gruppo"] == "caso") & df["paese"].isin(PAESI_UE) & df["quota"].notna()
              & df["data_provvedimento"].map(e_data)].copy()
    scenari_h4 = [
        ("Principale: tutti i casi UE", casi),
        ("Senza documentazione incompleta", casi[casi["doc_completa"]]),
        ("Criterio severo (soli errori documentati)", casi[casi["classe_caso"].isin(CLASSI_SEVERO)]),
        ("Criterio largo", casi[casi["classe_caso"].isin(CLASSI_LARGO)]),
    ]
    md.append("## H4. Quota cartellino nei casi, dal 17 ottobre contro prima\n\n"
              f"Casi UE con data del provvedimento e quota calcolabile. Mann-Whitney a una coda: verifica se le quote dei casi "
              f"dal 17 ottobre tendono a essere più alte (spostamento della distribuzione), non solo la mediana; "
              f"alfa {num(ALFA)}; solo descrittiva se un gruppo ha meno di {MIN_GRUPPO_H4} casi. Spostamento = stima di "
              "Hodges-Lehmann (mediana delle differenze tra tutte le coppie di casi), con intervallo al 95% a due code "
              "calcolato con l'approssimazione normale senza correzione per i valori pari (il test è a una coda: l'intervallo "
              "può comprendere 0 anche con p sotto 0,05); probabilità "
              "di superiorità = probabilità che un caso dal 17 ottobre abbia una quota più alta di un caso precedente "
              "(0,5 = nessuna differenza).\n\n")
    md.append("| Campione | Casi dal 17/10 | Casi prima | Mediana dal 17/10 (IQR) | Mediana prima (IQR) | "
              "Spostamento (IC 95%) | Prob. superiorità | p | Esito |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
    for nome, d in scenari_h4:
        r = h4(d)
        if "diff" not in r:
            md.append(f"| {nome} | {r['n_dopo']} | {r['n_prima']} | - | - | - | - | - | {r['esito']} |\n")
            continue
        md.append(
            f"| {nome} | {r['n_dopo']} | {r['n_prima']} | {pct(r['med_dopo'])} ({pct(r['iqr_dopo'][0])}-{pct(r['iqr_dopo'][1])}) | "
            f"{pct(r['med_prima'])} ({pct(r['iqr_prima'][0])}-{pct(r['iqr_prima'][1])}) | "
            f"{r['diff'] * 100:+.1f} pt ({r['ci'][0] * 100:+.1f}; {r['ci'][1] * 100:+.1f})".replace(".", ",") + " | "
            f"{num(r['superiorita'])} | {valore_p(r['p']) if 'p' in r else '-'} | {r['esito']} |\n")
    md.append("\nH4 dice se è cambiato il profilo dei venditori colpiti, non se il cartellino aumenta il rischio di blocco.\n\n")

    # ---- H5
    base, flusso = base_h5(tutte)
    md.append("## H5. Casi e controlli\n\n### Criteri di inclusione\n\n| Passo | Righe rimaste |\n| --- | --- |\n")
    md += [f"| {n} | {v} |\n" for n, v in flusso]
    principale = prepara_h5(base)
    n_casi, n_contr = int(principale["y"].sum()), int((principale["y"] == 0).sum())
    md.append(f"\nCampione principale: {n_casi} casi con provvedimento dal 17 ottobre 2026 e {n_contr} controlli, "
              "con covariate complete. "
              + (f"Numerosità registrata: {n_registrato} per gruppo.\n\n" if n_registrato else
                 "Numerosità non registrata.\n\n"))

    m = modello(principale, "esposto") if n_casi and n_contr else dict(errore="un gruppo è vuoto")
    esito = esito_h5(m, n_registrato, n_casi, n_contr)
    verdetto = esito in ("sostenuta", "associazione in direzione opposta") or esito.startswith("non sostenuta")
    if n_casi and n_contr:
        o, lo, hi, celle = or_grezzo(principale)
        md.append("| | Esposti | Non esposti |\n| --- | --- | --- |\n"
                  f"| Casi | {celle[0]} | {celle[1]} |\n| Controlli | {celle[2]} | {celle[3]} |\n\n")
        md.append(f"- OR grezzo (tabella 2x2): {num(o)} (IC 95% {num(lo)} - {num(hi)})"
                  + (", con 0,5 aggiunto a ogni cella perché una è vuota" if 0 in celle else "") + "\n")
    if "errore" in m:
        md.append(f"- OR aggiustato: {m['errore']}\n")
    else:
        md.append(f"- **OR aggiustato (modello registrato): {num(m['or_'])} (IC 95% {num(m['basso'])} - {num(m['alto'])})**"
                  + (f", p {valore_p(m['p'])}" if verdetto else "") + "\n")
    md.append(f"- **Esito H5: {esito}**\n")
    mc = modello(principale, "quota10") if n_casi and n_contr else dict(errore="un gruppo è vuoto")
    md.append("- Secondaria, quota come numero (OR per 10 punti di quota): "
              + (mc["errore"] if "errore" in mc else f"{num(mc['or_'])} (IC 95% {num(mc['basso'])} - {num(mc['alto'])})")
              + "\n\nModello: provvedimento ~ esposto + log(annunci attivi) + anzianità in anni + categoria prevalente "
              f"(riferimento: {principale.attrs.get('riferimento', CATEGORIA_RIFERIMENTO)}; categorie con meno di "
              f"{MIN_PER_CATEGORIA} risposte unite ad \"altro\"). Intervalli di Wald.\n\n")

    md.append("### Robustezza (casi diversi, stessi controlli)\n\n| Casi | Casi | Controlli | OR aggiustato (IC 95%) |\n"
              "| --- | --- | --- | --- |\n")
    caso_dopo = (base["gruppo"] == "caso") & base["dopo"]
    scenari_h5 = [
        ("Senza documentazione incompleta", caso_dopo & base["doc_completa"]),
        ("Criterio severo (soli errori documentati)", caso_dopo & base["classe_caso"].isin(CLASSI_SEVERO)),
        ("Criterio largo", caso_dopo & base["classe_caso"].isin(CLASSI_LARGO)),
        ("Tutti i casi, anche prima del 17 ottobre", base["gruppo"] == "caso"),
    ]
    for nome, cond in scenari_h5:
        d = prepara_h5(base, cond)
        nc, nk = int(d["y"].sum()), int((d["y"] == 0).sum())
        r = modello(d, "esposto") if nc and nk else dict(errore="un gruppo è vuoto")
        md.append(f"| {nome} | {nc} | {nk} | "
                  + (r["errore"] if "errore" in r else f"{num(r['or_'])} ({num(r['basso'])} - {num(r['alto'])})") + " |\n")
    md.append("\nIl reclutamento è volontario: sono associazioni nel campione raccolto, non la quota di venditori Vinted "
              "bloccati ingiustamente.\n\n")

    # ---- descrittive dei casi (domande 2 e 3)
    tutti = df[(df["gruppo"] == "caso") & df["paese"].isin(PAESI_UE)]
    md.append(f"## Casi per classe e motivo dichiarato (descrittiva, {len(tutti)} casi UE)\n\n")
    if len(tutti):
        t = pd.crosstab(tutti["classe_caso"].replace("", "non codificato"),
                        tutti["motivo_dichiarato"].replace("", "non indicato"), margins=True, margins_name="Totale")
        md.append("| Classe | " + " | ".join(t.columns) + " |\n| --- |" + " --- |" * len(t.columns) + "\n")
        md += [f"| {i} | " + " | ".join(str(v) for v in row) + " |\n" for i, row in t.iterrows()]
        doppi = tutti[tutti["codificatore_1"].ne("") & tutti["codificatore_2"].ne("")]
        if len(doppi) >= MIN_DOPPIA_CODIFICA:
            md.append(f"\nKappa di Cohen sulla classe ({len(doppi)} casi codificati da due persone): "
                      f"{num(kappa(doppi['codificatore_1'], doppi['codificatore_2']))}\n")
        else:
            md.append("\nClassificazione di una persona sola: nessun kappa.\n")
        ric = tutti[tutti["ricorso"] == "si"].copy()
        md.append(f"\n## Ricorsi interni (descrittiva, {len(ric)} casi)\n\n")
        if len(ric):
            ric["giorni"] = [(e - r).days if e_data(e) and e_data(r) else np.nan
                             for e, r in zip(ric["data_esito"], ric["data_ricorso"])]
            md.append("| Esito | Casi | Giorni fino all'esito (mediana) |\n| --- | --- | --- |\n")
            for esito_r, g in ric.groupby(ric["esito_ricorso"].replace("", "non indicato")):
                gg = g["giorni"].dropna()
                md.append(f"| {esito_r} | {len(g)} | {num(gg.median(), 0) if len(gg) else '-'} |\n")
        adr = tutti[tutti["adr"] == "si"]
        md.append(f"\nRicorsi a un organismo extragiudiziale: {len(adr)}"
                  + (" (" + ", ".join(f"{k}: {v}" for k, v in adr["esito_adr"].replace("", "non indicato")
                                      .value_counts().items()) + ")" if len(adr) else "") + ".\n")

    REPORTS.mkdir(parents=True, exist_ok=True)
    testo = "".join(md)
    (REPORTS / "casi.md").write_text(testo, encoding="utf-8")
    print(testo)
    print(f"Scritto: {REPORTS / 'casi.md'}")


def main() -> None:
    prepara_console()
    parser = argparse.ArgumentParser(description="Analisi dei casi e dei controlli (H4, H5)")
    parser.add_argument("--file", type=Path, default=FILE_DEFAULT, help="foglio compilato (default data/casi/casi.csv)")
    parser.add_argument("--numerosita", action="store_true", help="fissa la numerosita' di H5 leggendo solo i controlli")
    parser.add_argument("--senza-numerosita", action="store_true",
                        help="analisi senza numerosita' registrata (H5 solo esplorativa)")
    args = parser.parse_args()
    if args.numerosita:
        numerosita(args.file)
        return
    n = carica_config().get("h5_numerosita_per_gruppo")
    if not n and not args.senza_numerosita:
        sys.exit("La numerosita' di H5 non e' registrata in config/progetto.yaml (h5_numerosita_per_gruppo).\n"
                 "Prima lancia: python src/casi/analisi_casi.py --numerosita\n"
                 "Se i controlli validi non arriveranno mai a 30, usa --senza-numerosita (H5 solo esplorativa).")
    analisi(args.file, int(n) if n else None)


if __name__ == "__main__":
    main()
