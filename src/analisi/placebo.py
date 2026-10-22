"""Distribuzione placebo e test delle ipotesi sul volume e sulla composizione (H1-H3).

Legge SOLO data/processed/qualita/serie_giornaliera.csv (prodotto da qualita.py): pochi secondi.
Non legge il database, quindi non puo' guardare dati non voluti.

Per ogni giorno di inizio possibile si prende una finestra di 15 giorni e una base fatta da tanti giorni validi
quanti ne ha la base registrata (22), e si calcola la stessa statistica che servira' per la finestra dell'evento
(17-31 ottobre 2026). L'insieme di questi valori e' la distribuzione placebo: dice quanto la serie si muove
"normalmente", compresi i cambi nel modo in cui Vinted compila i dati.

Statistiche:
  - conteggi (H1): osservati / attesi, dove atteso = livello della base x fattore del giorno della settimana;
  - quote (H2, H3, categorie): quota nella finestra meno quota nella base, in punti percentuali.

Uso:
    python src/analisi/placebo.py            solo la distribuzione placebo (cosa si puo' rilevare)
    python src/analisi/placebo.py --evento   in piu' la statistica sulla finestra 17-31 ottobre e la sua
                                             posizione nel placebo (serve la modalita' cieca spenta)
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comune import DATI_PROCESSED, REPORTS, a_data, accenti, carica_config, prepara_console  # noqa: E402

# Parametri fissati nella preregistrazione (sezioni 6 e 8). Non si cambiano dopo aver visto l'evento.
# La data di inizio della base e la soglia dei giorni parziali stanno in config/progetto.yaml (base_da,
# soglia_giorno_parziale), cosi' qualita.py e questo script usano gli stessi valori.
FINESTRA = 15                       # giorni della finestra (17 - 31 ottobre 2026)
MIN_VALIDI_FINESTRA = 10            # sotto questa soglia la finestra e' inconcludente
ULTIMO_PRE_EVENTO = dt.date(2026, 10, 16)
INIZIO_EVENTO = dt.date(2026, 10, 17)
BASE_GIORNI = 22                    # ricalcolato in main() dalla config: giorni validi da base_da al 16 ottobre


def giorni_validi(totale: pd.Series, soglia: float) -> pd.Series:
    """Valido = file presente e almeno `soglia` volte la mediana dei 29 giorni attorno (stessa regola di qualita.py)."""
    vicini = totale.rolling(29, center=True, min_periods=7).median()
    return (totale > 0) & ~(totale < soglia * vicini)


# nome, colonna numeratore, colonna denominatore (None = conteggio), a due code, ipotesi
STATISTICHE = [
    ("H1 Dichiarazioni totali (osservate/attese)", "totale", None, False, "H1"),
    ("Chiusure definitive (oss./att.), descrittiva", "chiusure", None, False, "descrittiva"),
    ("H2a Rilevamento automatico tra restrizioni account (pt)", "ra_rilevamento_auto", "ra_n", False, "H2a"),
    ("H2b Decisione automatica tra restrizioni account (pt)", "ra_decisione_auto", "ra_n", False, "H2b"),
    ("H3 Altra segnalazione tra restrizioni account (pt, due code)", "ra_altra_segnalazione", "ra_n", True, "H3"),
    ("H2a' Rilevamento automatico tra le sole chiusure (pt)", "chi_rilevamento_auto", "chi_n", False, "robustezza"),
    ("H2b' Decisione automatica tra le sole chiusure (pt)", "chi_decisione_auto", "chi_n", False, "robustezza"),
    ("H3' Altra segnalazione tra le sole chiusure (pt, due code)", "chi_altra_segnalazione", "chi_n", True, "robustezza"),
]
CATEGORIE = {
    "n categoria: STATEMENT_CATEGORY_OTHER_VIOLATION_TC": "Altre violazioni delle regole",
    "n categoria: STATEMENT_CATEGORY_INTELLECTUAL_PROPERTY_INFRINGEMENTS": "Proprieta' intellettuale",
    "n categoria: STATEMENT_CATEGORY_SCAMS_AND_FRAUD": "Truffe e frodi",
    "n categoria: STATEMENT_CATEGORY_UNSAFE_AND_PROHIBITED_PRODUCTS": "Prodotti non sicuri o vietati",
}
for _col, _nome in CATEGORIE.items():
    STATISTICHE.append((f"Esplorativa: quota {_nome} (pt, due code)", _col, "totale", True, "esplorativa"))


def fattori_giorno(x: pd.Series, validi: pd.Series) -> np.ndarray:
    """Fattore moltiplicativo per giorno della settimana: giorno / media mobile centrata di 7 giorni."""
    v = x.where(validi)
    media = v.rolling(7, center=True, min_periods=7).mean()
    r = (v / media).replace([np.inf, -np.inf], np.nan).dropna()
    f = r.groupby(pd.DatetimeIndex(r.index).dayofweek).mean().reindex(range(7)).fillna(1.0).to_numpy()
    return f / f.mean()


def statistica(g: pd.DataFrame, validi: pd.Series, num: str, den: str | None, inizio: pd.Timestamp,
               fattori: np.ndarray) -> float:
    """Valore della statistica per la finestra che comincia in `inizio`; NaN se non calcolabile."""
    fine = inizio + pd.Timedelta(days=FINESTRA - 1)
    win = g.loc[inizio:fine]
    win = win[validi.loc[win.index]]
    if len(win) < MIN_VALIDI_FINESTRA:
        return float("nan")
    prima = g.loc[:inizio - pd.Timedelta(days=1)]
    prima = prima[validi.loc[prima.index]].tail(BASE_GIORNI)
    if len(prima) < BASE_GIORNI:
        return float("nan")
    if den is None:
        f_b = fattori[pd.DatetimeIndex(prima.index).dayofweek]
        f_w = fattori[pd.DatetimeIndex(win.index).dayofweek]
        livello = float((prima[num] / f_b).mean())
        atteso = float((livello * f_w).sum())
        return float(win[num].sum() / atteso) if atteso > 0 else float("nan")
    dw, db = win[den].sum(), prima[den].sum()
    if dw <= 0 or db <= 0:
        return float("nan")
    return float((win[num].sum() / dw - prima[num].sum() / db) * 100)


def main() -> None:
    prepara_console()
    parser = argparse.ArgumentParser(description="Distribuzione placebo per H1-H3")
    parser.add_argument("--evento", action="store_true", help="calcola anche la finestra 17-31 ottobre")
    args = parser.parse_args()

    percorso = DATI_PROCESSED / "qualita" / "serie_giornaliera.csv"
    if not percorso.exists():
        sys.exit("Manca serie_giornaliera.csv: esegui prima python src/tdb/qualita.py")
    g = pd.read_csv(percorso, parse_dates=["giorno"]).set_index("giorno").sort_index()
    richieste = {x for riga in STATISTICHE for x in (riga[1], riga[2]) if x}
    mancanti = [c for c in richieste if c not in g.columns]
    if mancanti:
        sys.exit(f"Nel file mancano colonne ({sorted(set(mancanti))[:4]}...): rieseguire qualita.py aggiornato.")
    global BASE_GIORNI
    cfg = carica_config()
    soglia = float(cfg.get("soglia_giorno_parziale") or 0.6)
    base_da = a_data(cfg["base_da"])
    pre = g.loc[:pd.Timestamp(ULTIMO_PRE_EVENTO)]
    # I giorni prima dell'evento si giudicano solo con dati prima dell'evento: il placebo non cambia dopo.
    validi_pre = giorni_validi(pre["totale"], soglia)
    validi = giorni_validi(g["totale"], soglia)
    validi.loc[validi_pre.index] = validi_pre
    esclusi = [d.date() for d in g.index if not validi[d]]
    BASE_GIORNI = int(validi_pre.loc[pd.Timestamp(base_da):].sum())

    ultimo_inizio = pd.Timestamp(ULTIMO_PRE_EVENTO) - pd.Timedelta(days=FINESTRA - 1)
    inizi = [d for d in pre.index if d <= ultimo_inizio]
    righe = []
    risultati = []
    for nome, num, den, due_code, ipotesi in STATISTICHE:
        fatt = fattori_giorno(pre[num], validi_pre) if den is None else None
        valori = np.array([statistica(pre, validi_pre, num, den, d, fatt) for d in inizi])
        ok = ~np.isnan(valori)
        for d, v in zip(inizi, valori):
            if not np.isnan(v):
                righe.append((nome, d.date().isoformat(), v))
        v = valori[ok]
        riga = dict(nome=nome, ipotesi=ipotesi, due_code=due_code, n=int(ok.sum()),
                    q=np.quantile(v, [0.025, 0.05, 0.5, 0.95, 0.975]) if len(v) else [np.nan] * 5,
                    den=den, num=num, fatt=fatt, valori=v)
        if args.evento:
            ev_g = g
            fatt_ev = fattori_giorno(pre[num], validi_pre) if den is None else None
            val = statistica(ev_g, validi, num, den, pd.Timestamp(INIZIO_EVENTO), fatt_ev)
            riga["evento"] = val
            if not np.isnan(val) and len(v):
                riga["rango_alto"] = float((v >= val).mean())
                riga["rango_basso"] = float((v <= val).mean())
                riga["p"] = min(1.0, 2 * min(riga["rango_alto"], riga["rango_basso"])) if due_code else riga["rango_alto"]
        risultati.append(riga)

    uscita = DATI_PROCESSED / "placebo"
    uscita.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(righe, columns=["statistica", "inizio_finestra", "valore"]).to_csv(
        uscita / "placebo.csv", index=False, float_format="%.5f")

    def fmt(r, v):
        return f"{(v - 1) * 100:+.1f}%" if r["den"] is None else f"{v:+.1f} pt"

    md = ["# Distribuzione placebo\n\n",
          f"Finestra di {FINESTRA} giorni, base di {BASE_GIORNI} giorni validi che la precedono. "
          f"Finestre con inizio dal {min(r[1] for r in righe)} al {max(r[1] for r in righe)} "
          f"(le prime date non hanno ancora una base completa), fino al {ULTIMO_PRE_EVENTO}. "
          f"Base registrata: dal {base_da} al {ULTIMO_PRE_EVENTO}, {BASE_GIORNI} giorni validi. "
          f"Giorni esclusi (file assente o sotto il {soglia:.0%} della mediana dei 29 giorni attorno): "
          f"{', '.join(d.isoformat() for d in esclusi)}. "
          "Le finestre vicine si sovrappongono: i valori non sono indipendenti, "
          f"il numero di finestre indipendenti e' circa {len(inizi) // FINESTRA}.\n\n",
          "| Statistica | Finestre | 2,5% | 5% | Mediana | 95% | 97,5% |\n| --- | --- | --- | --- | --- | --- | --- |\n"]
    for r in risultati:
        q = r["q"]
        md.append(f"| {r['nome']} | {r['n']} | " + " | ".join(fmt(r, x) if not np.isnan(x) else "-" for x in q) + " |\n")
    if args.evento:
        md.append(f"\n## Finestra dell'evento ({INIZIO_EVENTO} e i {FINESTRA - 1} giorni dopo)\n\n"
                  "| Statistica | Valore | Quota placebo >= | Quota placebo <= | p (placebo; due code se indicato) |\n| --- | --- | --- | --- | --- |\n")
        for r in risultati:
            if np.isnan(r.get("evento", np.nan)):
                md.append(f"| {r['nome']} | non calcolabile (dati insufficienti) | - | - | - |\n")
            else:
                md.append(f"| {r['nome']} | {fmt(r, r['evento'])} | {r.get('rango_alto', float('nan')):.3f} | "
                          f"{r.get('rango_basso', float('nan')):.3f} | {r.get('p', float('nan')):.3f} |\n")
    REPORTS.mkdir(parents=True, exist_ok=True)
    testo = accenti("".join(md))
    (REPORTS / "placebo.md").write_text(testo, encoding="utf-8")
    print(testo)
    print(f"Scritto: {REPORTS / 'placebo.md'}")


if __name__ == "__main__":
    main()
