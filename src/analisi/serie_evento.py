"""Serie giornaliera delle restrizioni account attorno all'evento: tabella descrittiva, non un test.

Scritto il 27 novembre 2026, DOPO l'analisi registrata di H1-H3 (registro delle modifiche, note dopo l'analisi).
Serve a rendere verificabili i numeri giornalieri citati nelle presentazioni: per ogni giorno dal 23 settembre 2026,
quante restrizioni account ci sono e quante dichiarano rilevamento automatico, decisione tutta automatica e altra
segnalazione. I periodi del riepilogo sono scelti guardando i dati, per descrivere il salto del 30 ottobre e il
rientro successivo: non sono ipotesi e non hanno soglie. I verdetti restano quelli di `placebo.py`.

Legge data/processed/qualita/serie_giornaliera.csv (prodotto da qualita.py) e usa la stessa regola di validita'
dei giorni di placebo.py, senza modificarlo.

Uso:
    python src/analisi/serie_evento.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import placebo as P  # noqa: E402  (aggiunge src/ al percorso)
from comune import DATI_PROCESSED, REPORTS, carica_config, prepara_console  # noqa: E402

INIZIO_TABELLA = "2026-09-23"
# Periodi descrittivi (scelti dopo aver visto i dati). L'ultimo arriva fino all'ultimo giorno disponibile.
PERIODI = [
    ("Base registrata", "2026-09-23", "2026-10-16"),
    ("17-29 ottobre", "2026-10-17", "2026-10-29"),
    ("30 ottobre (giorno del cambio)", "2026-10-30", "2026-10-30"),
    ("31 ottobre - 5 novembre", "2026-10-31", "2026-11-05"),
    ("6-17 novembre", "2026-11-06", "2026-11-17"),
    ("18 novembre", "2026-11-18", "2026-11-18"),
    ("19-23 novembre", "2026-11-19", "2026-11-23"),
    ("Dal 24 novembre", "2026-11-24", None),
]


def num(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def perc(a: float, b: float) -> str:
    return f"{100 * a / b:.1f}".replace(".", ",") if b else "-"


def main() -> None:
    prepara_console()
    percorso = DATI_PROCESSED / "qualita" / "serie_giornaliera.csv"
    if not percorso.exists():
        sys.exit("Manca serie_giornaliera.csv: esegui prima python src/tdb/qualita.py")
    g = pd.read_csv(percorso, parse_dates=["giorno"]).set_index("giorno").sort_index()
    soglia = float(carica_config().get("soglia_giorno_parziale") or 0.6)
    validi = P.giorni_validi(g["totale"], soglia)
    ultimo = g.index.max()

    md = ["# Serie giornaliera attorno all'evento (descrittiva)\n\n",
          "**Non è un test.** I verdetti su H1-H3 sono quelli della finestra registrata (17-31 ottobre) in "
          "`placebo.md`; le prove di robustezza sono in `robustezza.md`. Questa tabella rende verificabili i numeri "
          "giornalieri. I periodi del riepilogo sono stati scelti dopo aver visto i dati (registro delle modifiche, "
          "note dopo l'analisi).\n\n",
          "Restrizioni account = dichiarazioni con una restrizione sull'account (chiusura o sospensione). Le quote "
          "sono calcolate sulle restrizioni account, come H2a, H2b e H3, sommando i giorni validi. Giorni esclusi: "
          "stessa regola di `placebo.py` (file assente o sotto il 60% della mediana dei 29 giorni attorno). "
          f"Dati fino al {ultimo.date()}.\n\n",
          "## Riepilogo per periodo\n\n",
          "| Periodo | Giorni validi | Dichiarazioni al giorno | Restrizioni account al giorno | "
          "Rilevamento automatico (%) | Decisione tutta automatica (%) | Altra segnalazione (%) |\n",
          "| --- | --- | --- | --- | --- | --- | --- |\n"]
    for nome, da, a in PERIODI:
        s = g.loc[pd.Timestamp(da):(pd.Timestamp(a) if a else ultimo)]
        s = s[validi.loc[s.index]]
        if s.empty:
            continue
        md.append(f"| {nome} | {len(s)} | {num(s['totale'].mean())} | {num(s['ra_n'].mean())} | "
                  f"{perc(s['ra_rilevamento_auto'].sum(), s['ra_n'].sum())} | "
                  f"{perc(s['ra_decisione_auto'].sum(), s['ra_n'].sum())} | "
                  f"{perc(s['ra_altra_segnalazione'].sum(), s['ra_n'].sum())} |\n")

    md += ["\n## Giorno per giorno\n\n",
           "| Giorno | Dichiarazioni | Restrizioni account | Rilevamento automatico | Decisione tutta automatica | "
           "Rilevamento automatico (%) | Decisione tutta automatica (%) | Altra segnalazione (%) | Valido |\n",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"]
    for d, r in g.loc[pd.Timestamp(INIZIO_TABELLA):].iterrows():
        md.append(f"| {d.date()} | {num(r['totale'])} | {num(r['ra_n'])} | {num(r['ra_rilevamento_auto'])} | "
                  f"{num(r['ra_decisione_auto'])} | {perc(r['ra_rilevamento_auto'], r['ra_n'])} | "
                  f"{perc(r['ra_decisione_auto'], r['ra_n'])} | {perc(r['ra_altra_segnalazione'], r['ra_n'])} | "
                  f"{'sì' if validi[d] else 'escluso'} |\n")

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "serie_evento.md").write_text("".join(md), encoding="utf-8")
    print("".join(md[:16]))
    print(f"Scritto: {REPORTS / 'serie_evento.md'}")


if __name__ == "__main__":
    main()
