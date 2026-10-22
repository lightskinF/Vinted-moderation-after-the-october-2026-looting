"""Analisi di sensibilita' del tasso base: in quali condizioni una regola di segnalazione
produce soprattutto falsi allarmi.

Se l'illecito e' raro nella popolazione controllata, anche una regola precisa segnala
soprattutto innocenti. Ogni risultato e' CONDIZIONALE: "se la prevalenza fosse p e la
regola avesse sensibilita' r e specificita' s, allora...".
Con p = quota di ricettatori nella popolazione a cui la regola viene applicata,
     r = sensibilita' (quota di ricettatori che la regola prende),
     s = specificita' (quota di onesti che la regola lascia stare):

    onesti tra i segnalati = (1 - s)(1 - p) / ((1 - s)(1 - p) + r p)

Uso:
    python src/sim/tasso_base.py                         griglia completa, grafico e CSV
    python src/sim/tasso_base.py --p 0.005 --r 0.9 --s 0.95   un solo caso, spiegato

I numeri sono IPOTETICI: nessuno dei tre parametri e' noto per Vinted. Lo script mostra
un meccanismo possibile, non misura quello reale.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comune import DATI_PROCESSED, REPORTS, prepara_console  # noqa: E402

SUPERFICIE, TESTO, TESTO_2, GRIGLIA = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

# Tre regole ipotetiche, dalla piu' grossolana alla piu' precisa.
REGOLE = [
    ("Regola grossolana (sensibilità 80%, specificità 90%)", 0.80, 0.90, "#2a78d6"),
    ("Regola buona (90%, 95%)", 0.90, 0.95, "#eb6834"),
    ("Regola ottima (95%, 99%)", 0.95, 0.99, "#1baf7a"),
]


def onesti_tra_segnalati(p: float, r: float, s: float) -> float:
    falsi = (1 - s) * (1 - p)
    veri = r * p
    return falsi / (falsi + veri)


def spiega(p: float, r: float, s: float, venditori: int = 10_000) -> None:
    ricettatori = venditori * p
    presi = ricettatori * r
    onesti_segnalati = (venditori - ricettatori) * (1 - s)
    quota = onesti_tra_segnalati(p, r, s)
    print(f"Scenario ipotetico. Su {venditori:,} venditori controllati:".replace(",", "."))
    print(f"  ricettatori: {ricettatori:,.0f}, di cui presi dalla regola: {presi:,.0f}")
    print(f"  onesti segnalati per errore: {onesti_segnalati:,.0f}")
    print(f"  => su 100 profili segnalati, {quota * 100:.0f} sono onesti.")


def griglia() -> list[tuple[float, str, float, float, float]]:
    passi = 60
    prevalenze = [10 ** (-3 + 2 * i / (passi - 1)) for i in range(passi)]  # da 0,1% a 10%
    righe = []
    for nome, r, s, _ in REGOLE:
        for p in prevalenze:
            righe.append((p, nome, r, s, onesti_tra_segnalati(p, r, s)))
    return righe


def grafico(righe, percorso: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.6), facecolor=SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)
    for nome, r, s, colore in REGOLE:
        xs = [x[0] * 100 for x in righe if x[1] == nome]
        ys = [x[4] * 100 for x in righe if x[1] == nome]
        ax.plot(xs, ys, color=colore, linewidth=2, label=nome, solid_capstyle="round")
        ax.annotate(nome.split(" (")[0], (xs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=9, color=TESTO)
    # Il caso di esempio mostrato nel grafico (p = 0,5%, r = 90%, s = 95%).
    p, r, s = 0.005, 0.90, 0.95
    y = onesti_tra_segnalati(p, r, s) * 100
    ax.plot([p * 100], [y], marker="o", markersize=8, color="#eb6834",
            markeredgecolor=SUPERFICIE, markeredgewidth=2, zorder=5)
    ax.annotate(f"Se 1 controllato su 200\nfosse un ricettatore:\n{y:.0f} segnalati su 100 onesti",
                (p * 100, y), xytext=(1.3, 61), textcoords="data", fontsize=9, color=TESTO,
                ha="left", va="top",
                arrowprops=dict(arrowstyle="-", color=TESTO_2, linewidth=0.8, shrinkA=0, shrinkB=5))
    ax.set_xscale("log")
    ax.set_xlim(0.1, 10)
    ax.set_ylim(0, 100)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}%".replace(".", ",")))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlabel("Quota di ricettatori nella popolazione controllata (scala logaritmica)",
                  fontsize=9.5, color=TESTO_2)
    ax.set_ylabel("Onesti tra i profili segnalati", fontsize=9.5, color=TESTO_2)
    ax.grid(color=GRIGLIA, linewidth=0.8)
    ax.tick_params(colors=TESTO_2, labelsize=9, length=0)
    for lato in ("top", "right", "left", "bottom"):
        ax.spines[lato].set_visible(False)
    legenda = ax.legend(loc="lower left", frameon=False, fontsize=9)
    for t in legenda.get_texts():
        t.set_color(TESTO)
    fig.suptitle("Se l'illecito è raro, anche una regola precisa segnala soprattutto onesti",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=TESTO)
    fig.text(0.01, 0.01, "Scenari ipotetici: prevalenza e prestazioni di Vinted non sono note. "
             "Formula: (1-s)(1-p) / ((1-s)(1-p) + r·p).", fontsize=8.5, color=TESTO_2)
    fig.tight_layout(rect=(0, 0.03, 0.9, 0.95))
    fig.savefig(percorso, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


def main() -> None:
    prepara_console()
    parser = argparse.ArgumentParser(description="Analisi di sensibilita' del tasso base")
    parser.add_argument("--p", type=float, help="quota di ricettatori (es. 0.005 = 1 su 200)")
    parser.add_argument("--r", type=float, help="sensibilita' della regola (es. 0.9)")
    parser.add_argument("--s", type=float, help="specificita' della regola (es. 0.95)")
    args = parser.parse_args()

    if args.p is not None:
        if args.r is None or args.s is None:
            sys.exit("Indica anche --r e --s.")
        spiega(args.p, args.r, args.s)
        return

    righe = griglia()
    uscita_csv = DATI_PROCESSED / "sim" / "tasso_base_griglia.csv"
    uscita_csv.parent.mkdir(parents=True, exist_ok=True)
    with uscita_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["prevalenza", "regola", "sensibilita", "specificita", "onesti_tra_segnalati"])
        w.writerows((f"{p:.6f}", n, r, s, f"{q:.4f}") for p, n, r, s, q in righe)
    REPORTS.mkdir(parents=True, exist_ok=True)
    uscita_png = REPORTS / "tasso_base.png"
    grafico(righe, uscita_png)
    print(f"Grafico: {uscita_png}\nTabella: {uscita_csv}\n")
    spiega(0.005, 0.90, 0.95)


if __name__ == "__main__":
    main()
