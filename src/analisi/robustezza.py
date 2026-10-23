"""Prove di robustezza di H1-H3 con finestre diverse (preregistrazione, sezione 9, punto 3) e giorni esclusi.

Riusa le funzioni di placebo.py SENZA modificarlo (registro delle modifiche, precisazione 4): cambia solo, per
ogni scenario, la lunghezza della finestra, i giorni della base e il minimo di giorni validi, poi ricalcola la
distribuzione placebo e la statistica dell'evento con lo stesso codice registrato.
Scritto e pubblicato il 23 ottobre 2026, prima di scaricare i dati dal 17 ottobre.

Scenari (sezione 9, punto 3):
  - finestra di 7 giorni (17-23 ottobre), base registrata;
  - finestra di 21 giorni (17 ottobre - 6 novembre), base registrata;
  - finestra di 15 giorni, base di 14 giorni validi.
Minimo di giorni validi nella finestra: due terzi, arrotondati per eccesso, come 10 su 15 nel codice registrato
(5 su 7, 14 su 21).

Soglie: stessa regola della sezione 5, applicata alla distribuzione placebo di ogni scenario (95 percentile nella
direzione prevista; per H3 2,5 e 97,5 percentile).

Il rapporto elenca anche i giorni esclusi nella finestra dell'evento con il loro valore (sezione 4).

Uso:
    python src/analisi/robustezza.py            solo le distribuzioni placebo degli scenari
    python src/analisi/robustezza.py --evento   in piu' la finestra dell'evento in ogni scenario
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import placebo as P  # noqa: E402  (aggiunge src/ al percorso e porta con se' comune.py)
from comune import DATI_PROCESSED, REPORTS, a_data, accenti, carica_config, prepara_console  # noqa: E402

GIORNI_MEDIANA = 14        # meta' della finestra centrata di 29 giorni usata per giudicare un giorno
RITARDO_INVIO = 1          # giorni: le decisioni possono arrivare al database il giorno dopo


def minimo_validi(finestra: int) -> int:
    return math.ceil(finestra * 2 / 3)


# nome, giorni della finestra, giorni validi della base (None = base registrata)
SCENARI = [
    ("Registrato: finestra 15 giorni, base registrata", 15, None),
    ("Finestra 7 giorni", 7, None),
    ("Finestra 21 giorni", 21, None),
    ("Base 14 giorni validi", 15, 14),
]
IPOTESI = [s for s in P.STATISTICHE if s[4] in ("H1", "H2a", "H2b", "H3")]


def esito(valore: float, q: np.ndarray, due_code: bool) -> str:
    """Regola della sezione 5 applicata al placebo dello scenario. q = percentili 2,5 / 5 / 50 / 95 / 97,5."""
    if np.isnan(valore) or np.isnan(q).any():
        return "non calcolabile"
    if due_code:
        if valore > q[4]:
            return "sopra la soglia alta"
        if valore < q[0]:
            return "sotto la soglia bassa"
        return "entro le soglie"
    if valore > q[3]:
        return "sopra la soglia"
    if valore < q[1]:
        return "direzione opposta"
    return "sotto la soglia"


def main() -> None:
    prepara_console()
    parser = argparse.ArgumentParser(description="Prove di robustezza di H1-H3 con finestre diverse")
    parser.add_argument("--evento", action="store_true", help="calcola anche la finestra dell'evento")
    args = parser.parse_args()

    percorso = DATI_PROCESSED / "qualita" / "serie_giornaliera.csv"
    if not percorso.exists():
        sys.exit("Manca serie_giornaliera.csv: esegui prima python src/tdb/qualita.py")
    g = pd.read_csv(percorso, parse_dates=["giorno"]).set_index("giorno").sort_index()
    cfg = carica_config()
    soglia = float(cfg.get("soglia_giorno_parziale") or 0.6)
    base_da = a_data(cfg["base_da"])

    # Validita' dei giorni: stessa costruzione di placebo.py.
    pre = g.loc[:pd.Timestamp(P.ULTIMO_PRE_EVENTO)]
    validi_pre = P.giorni_validi(pre["totale"], soglia)
    validi = P.giorni_validi(g["totale"], soglia)
    validi.loc[validi_pre.index] = validi_pre
    base_registrata = int(validi_pre.loc[pd.Timestamp(base_da):].sum())
    ultimo_file = g.index.max().date()
    inizio_evento = pd.Timestamp(P.INIZIO_EVENTO)

    md = ["# Prove di robustezza di H1-H3 (finestre diverse)\n\n",
          "Preregistrazione, sezione 9, punto 3. Stesso codice di `placebo.py`, con finestra, base e minimo di giorni "
          "validi cambiati per ogni scenario; minimo di giorni validi = due terzi della finestra, arrotondati per "
          f"eccesso. Base registrata: {base_registrata} giorni validi dal {base_da} al {P.ULTIMO_PRE_EVENTO}. "
          f"Dati fino al {ultimo_file}. Una conclusione che regge solo in uno scenario si riporta come fragile.\n\n"]

    for nome_sc, finestra, base in SCENARI:
        P.FINESTRA = finestra
        P.BASE_GIORNI = base or base_registrata
        P.MIN_VALIDI_FINESTRA = minimo_validi(finestra)
        fine_evento = P.INIZIO_EVENTO + dt.timedelta(days=finestra - 1)
        servono = fine_evento + dt.timedelta(days=GIORNI_MEDIANA + RITARDO_INVIO)
        ultimo_inizio = pd.Timestamp(P.ULTIMO_PRE_EVENTO) - pd.Timedelta(days=finestra - 1)
        inizi = [d for d in pre.index if d <= ultimo_inizio]

        md.append(f"## {nome_sc}\n\n"
                  f"Finestra di {finestra} giorni (evento: {P.INIZIO_EVENTO} - {fine_evento}), base di "
                  f"{P.BASE_GIORNI} giorni validi, almeno {P.MIN_VALIDI_FINESTRA} giorni validi nella finestra. "
                  f"{len(inizi)} finestre placebo.")
        if args.evento and ultimo_file < servono:
            md.append(f" **Provvisorio:** per giudicare tutti i giorni della finestra servono i file fino al {servono}.")
        md.append("\n\n| Statistica | Finestre | 2,5% | 5% | 95% | 97,5% |"
                  + (" Evento | Esito |" if args.evento else "") + "\n"
                  + "| --- " * (6 + (2 if args.evento else 0)) + "|\n")

        for nome, num, den, due_code, _ in IPOTESI:
            fatt = P.fattori_giorno(pre[num], validi_pre) if den is None else None
            valori = np.array([P.statistica(pre, validi_pre, num, den, d, fatt) for d in inizi])
            v = valori[~np.isnan(valori)]
            q = np.quantile(v, [0.025, 0.05, 0.5, 0.95, 0.975]) if len(v) else np.full(5, np.nan)

            def fmt(x):
                if np.isnan(x):
                    return "-"
                return f"{(x - 1) * 100:+.1f}%" if den is None else f"{x:+.1f} pt"

            riga = f"| {nome} | {len(v)} | {fmt(q[0])} | {fmt(q[1])} | {fmt(q[3])} | {fmt(q[4])} |"
            if args.evento:
                val = P.statistica(g, validi, num, den, inizio_evento, fatt)
                riga += f" {fmt(val)} | {esito(val, q, due_code)} |"
            md.append(riga + "\n")
        md.append("\n")

    if args.evento:
        # Giorni esclusi nella finestra piu' lunga (contiene le altre), con il loro valore (sezione 4).
        fine = P.INIZIO_EVENTO + dt.timedelta(days=max(s[1] for s in SCENARI) - 1)
        vicini = g["totale"].rolling(29, center=True, min_periods=7).median()
        tratto = g.loc[inizio_evento:pd.Timestamp(fine)]
        esclusi = [d for d in tratto.index if not validi[d]]
        md.append(f"## Giorni esclusi nella finestra dell'evento ({P.INIZIO_EVENTO} - {fine})\n\n")
        if esclusi:
            md.append("| Giorno | Dichiarazioni | Mediana dei 29 giorni attorno | Rapporto |\n| --- | --- | --- | --- |\n")
            for d in esclusi:
                tot, med = g.at[d, "totale"], vicini.get(d, np.nan)
                rapp = f"{tot / med:.2f}" if med and not np.isnan(med) else "-"
                md.append(f"| {d.date()} | {int(tot):,} | {med:,.0f} | {rapp} |\n".replace(",", "."))
            md.append("\nI giorni esclusi possono contenere un calo reale dovuto all'evento: si riportano sempre, con "
                      "il loro valore, accanto ai risultati.\n")
        else:
            md.append("Nessun giorno escluso.\n")

    testo = accenti("".join(md))
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "robustezza.md").write_text(testo, encoding="utf-8")
    print(testo)
    print(f"Scritto: {REPORTS / 'robustezza.md'}")


if __name__ == "__main__":
    main()
