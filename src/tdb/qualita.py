"""Rapporto di qualita' e di stabilita' sui dati che Vinted invia al database UE.

Legge data/interim/vinted.duckdb (creato da carica.py) e scrive:
  reports/qualita_tdb.md                 il rapporto da leggere
  reports/qualita_tdb_serie.png          serie giornaliere con i cambi strutturali
  reports/qualita_tdb_categorie.png      composizione per categoria, settimana per settimana
  data/processed/qualita/*.csv           le tabelle usate nel rapporto

Risponde alle domande da chiudere prima di registrare le ipotesi:
  1. Quante dichiarazioni ci sono, e i file sono completi?
  2. I campi distinguono annunci/account, automazione, origine?
  3. Le motivazioni distinguono i casi (merce rubata, contraffazione, vendita commerciale)?
  4. Quanto spesso Vinted cambia il modo di segnalare (cambi strutturali)?
  5. Quanto varia normalmente la serie in due settimane (distribuzione placebo)?
  6. Quale finestra di base usare prima dell'evento?

Unita' di conto: la DICHIARAZIONE DI MOTIVAZIONE (statement of reasons), non l'account
e non la persona. Una dichiarazione puo' contenere piu' restrizioni.

Il database (decine di milioni di righe) viene letto poche volte: un'aggregazione per giorno
e qualche conteggio, poi tutto il resto si calcola su tabelle piccole.

Uso:  python src/tdb/qualita.py
"""
from __future__ import annotations

import datetime as dt
import math
import re
import sys
import time
from pathlib import Path

import duckdb
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comune import DATI_PROCESSED, DATI_RAW_TDB, DB_PATH, REPORTS, a_data as comune_a_data, accenti, carica_config, descrivi_modalita, prepara_console  # noqa: E402

USCITA_CSV = DATI_PROCESSED / "qualita"
PAESI_UE = 27
FINESTRA_RITARDO = 30   # giorni: il ritardo si misura solo su decisioni piu' vecchie di cosi'
W = 14                  # giorni validi prima e dopo, per misurare un cambio
SOGLIA_QUOTA = 10.0     # punti percentuali: cambio di composizione da segnalare
SOGLIA_LIVELLO = 1.5    # rapporto: cambio di volume da segnalare (x1,5 o /1,5)
GIORNO_ANOMALO = 0.6    # predefinito: un giorno sotto il 60% della mediana dei 29 giorni attorno e' un'interruzione

# Palette di riferimento (tema chiaro), ordine fisso delle serie.
SUPERFICIE, TESTO, TESTO_2, GRIGLIA = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]

ETICHETTE = {
    "STATEMENT_CATEGORY_OTHER_VIOLATION_TC": "Altre violazioni delle regole",
    "STATEMENT_CATEGORY_INTELLECTUAL_PROPERTY_INFRINGEMENTS": "Proprietà intellettuale",
    "STATEMENT_CATEGORY_SCAMS_AND_FRAUD": "Truffe e frodi",
    "STATEMENT_CATEGORY_UNSAFE_AND_PROHIBITED_PRODUCTS": "Prodotti non sicuri o vietati",
    "STATEMENT_CATEGORY_ILLEGAL_OR_HARMFUL_SPEECH": "Discorsi illegali o dannosi",
    "SOURCE_VOLUNTARY": "iniziativa propria",
    "SOURCE_TYPE_OTHER_NOTIFICATION": "altra segnalazione",
    "SOURCE_ARTICLE_16": "segnalazione art. 16",
    "SOURCE_TRUSTED_FLAGGER": "segnalatore attendibile",
}

CAMPI_ENUM = ["category", "decision_ground", "decision_account", "decision_provision", "decision_monetary",
              "account_type", "automated_detection", "automated_decision", "source_type"]
CAMPI_LISTA = ["decision_visibility", "content_type", "category_specification"]
CAMPI_CHIAVE = ["automated_detection", "automated_decision", "source_type", "territorial_scope",
                "decision_facts", "category", "decision_account"]

RESTRIZIONE_ACCOUNT = "(decision_account IS NOT NULL OR decision_provision IS NOT NULL)"
RESTRIZIONE_CONTENUTO = "(COALESCE(LEN(decision_visibility), 0) > 0)"

# Ricerca di controllo nei testi distinti delle motivazioni (inglese, francese, italiano).
GRUPPI_MOTIVO = {
    "Merce rubata": r"stolen|theft|thief|loot|vol[ée]s?\b|pillage|recel|rubat|furto|saccheg|ricettaz",
    "Contraffazione": r"counterfeit|fake|replica|imitation|contrefa|contraff",
    "Vendita commerciale": r"business|commercial|professional|resell|resale|wholesale|bulk|revente|professionnel|rivendit|ingrosso",
    "Nuovo con cartellino": r"new with tags|with tags|neuf avec [ée]tiquette|nuovo con cartellino|brand new",
}


def etichetta(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "(vuoto)"
    return ETICHETTE.get(str(v), str(v))


def numero(v) -> str:
    return f"{v:,.0f}".replace(",", ".")


def tabella_md(righe: list[tuple], intestazioni: list[str]) -> str:
    def cella(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "(vuoto)"
        if isinstance(v, bool):
            return str(v)
        if isinstance(v, float):
            return f"{v:.1f}"
        if isinstance(v, int):
            return numero(v)
        if isinstance(v, dt.date):
            return v.isoformat()
        return str(v).replace("|", "/").replace("\n", " ")
    testa = "| " + " | ".join(intestazioni) + " |\n| " + " | ".join("---" for _ in intestazioni) + " |\n"
    return testa + "".join("| " + " | ".join(cella(v) for v in r) + " |\n" for r in righe)


def stile_asse(ax) -> None:
    ax.set_facecolor(SUPERFICIE)
    ax.grid(axis="y", color=GRIGLIA, linewidth=0.8)
    ax.tick_params(colors=TESTO_2, labelsize=9, length=0)
    for lato in ("top", "right", "left"):
        ax.spines[lato].set_visible(False)
    ax.spines["bottom"].set_color(GRIGLIA)


# ---------------------------------------------------------------- serie e cambi strutturali

def misura_cambi(valori: pd.Series, tipo: str) -> pd.DataFrame:
    """Per ogni giorno valido: media dei W giorni validi prima e dei W giorni validi da quel giorno in poi
    (la media, a differenza della mediana, ha il massimo esattamente sul giorno del cambio).
    tipo 'quota' -> variazione in punti percentuali; tipo 'livello' -> rapporto dopo/prima."""
    v = valori.to_numpy(dtype=float)
    righe = []
    for i in range(W, len(v) - W + 1):
        prima = float(v[i - W:i].mean())
        dopo = float(v[i:i + W].mean())
        if tipo == "quota":
            variazione = dopo - prima
            punteggio = abs(variazione) / SOGLIA_QUOTA
        else:
            variazione = (dopo + 1) / (prima + 1)
            punteggio = abs(math.log(variazione)) / math.log(SOGLIA_LIVELLO)
        righe.append((valori.index[i], prima, dopo, variazione, punteggio))
    return pd.DataFrame(righe, columns=["giorno", "prima", "dopo", "variazione", "punteggio"])


def trova_rotture(cambi: pd.DataFrame) -> list[int]:
    """Picchi del punteggio sopra la soglia (punteggio >= 1), distanti almeno W giorni validi."""
    if cambi.empty:
        return []
    punteggi = cambi["punteggio"].to_numpy().copy()
    scelti = []
    while True:
        i = int(punteggi.argmax())
        if punteggi[i] < 1:
            break
        scelti.append(i)
        punteggi[max(0, i - W + 1):i + W] = -1
    return sorted(scelti)


def grafico_serie(giornaliero: pd.DataFrame, anomali: list[dt.date], eventi: list[dt.date],
                  fonti: list[str], percorso: Path) -> None:
    giorni = pd.to_datetime(giornaliero.index)
    fig, assi = plt.subplots(3, 1, figsize=(11, 8.6), sharex=True, facecolor=SUPERFICIE)

    ax = assi[0]
    ax.plot(giorni, giornaliero["totale"], color=SERIE[0], linewidth=1.6, solid_capstyle="round")
    if anomali:
        x = pd.to_datetime(anomali)
        ax.scatter(x, giornaliero.loc[anomali, "totale"], s=40, color=SUPERFICIE, edgecolors=TESTO_2,
                   linewidths=1.5, zorder=3, label="giorni con dati mancanti o parziali")
        ax.legend(loc="lower right", bbox_to_anchor=(1, 1), frameon=False, fontsize=8.5, labelcolor=TESTO_2)
    ax.set_title("Dichiarazioni al giorno", loc="left", fontsize=11, color=TESTO, pad=6)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: numero(v)))

    pulito = giornaliero.copy()
    pulito.loc[anomali] = float("nan")  # nei pannelli 2 e 3 i giorni con dati mancanti restano vuoti
    ax = assi[1]
    ax.plot(giorni, pulito["sospensioni"], color=SERIE[0], linewidth=1.6, label="sospensioni")
    ax.plot(giorni, pulito["chiusure"], color=SERIE[1], linewidth=1.6, label="chiusure definitive")
    ax.set_title("Restrizioni sugli account al giorno", loc="left", fontsize=11, color=TESTO, pad=6)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: numero(v)))
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1), frameon=False, fontsize=8.5, labelcolor=TESTO_2, ncol=2)

    ax = assi[2]
    for n, f in enumerate(fonti[:3]):
        ax.plot(giorni, pulito[f"fonte: {f}"], color=SERIE[n], linewidth=1.6, label=etichetta(f))
    ax.set_title("Origine della decisione (quota sul totale del giorno)", loc="left", fontsize=11, color=TESTO, pad=6)
    ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
    ax.set_ylim(0, 100)
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1), frameon=False, fontsize=8.5, labelcolor=TESTO_2, ncol=3)

    for ax in assi:
        stile_asse(ax)
        if ax is not assi[2]:
            ax.set_ylim(bottom=0)
        for e in eventi:
            ax.axvline(pd.Timestamp(e), color=TESTO_2, linewidth=1, linestyle=(0, (3, 3)), alpha=0.7)
    for n, e in enumerate(eventi, 1):
        assi[0].text(pd.Timestamp(e), assi[0].get_ylim()[1], f" {n}", fontsize=8.5, fontweight="bold",
                     color=TESTO_2, va="top", ha="left")
    assi[2].xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    fig.suptitle("Vinted nel database UE: volumi e cambi strutturali", x=0.01, ha="left",
                 fontsize=13, fontweight="bold", color=TESTO)
    fig.text(0.01, 0.005, "Fonte: DSA Transparency Database, data di applicazione. Linee tratteggiate numerate: "
             "cambi strutturali (elenco nel rapporto).", fontsize=8.5, color=TESTO_2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(percorso, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


def grafico_categorie(settimanale: pd.DataFrame, eventi: list[dt.date], percorso: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.2), facecolor=SUPERFICIE)
    x = pd.to_datetime(settimanale.index)
    for n, c in enumerate(settimanale.columns[:5]):
        ax.plot(x, settimanale[c], color=SERIE[n], linewidth=1.8, label=etichetta(c))
    for n, e in enumerate(eventi, 1):
        ax.axvline(pd.Timestamp(e), color=TESTO_2, linewidth=1, linestyle=(0, (3, 3)), alpha=0.5)
        ax.text(pd.Timestamp(e), ax.get_ylim()[1], f" {n}", fontsize=8.5, fontweight="bold", color=TESTO_2,
                va="top", ha="left")
    stile_asse(ax)
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), frameon=False, fontsize=8.5,
              labelcolor=TESTO_2, ncol=min(5, len(settimanale.columns)))
    ax.set_title("Quota di ogni categoria sulle dichiarazioni della settimana", loc="left",
                 fontsize=12, fontweight="bold", color=TESTO, pad=8)
    fig.tight_layout()
    fig.savefig(percorso, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


# ---------------------------------------------------------------- rapporto

def main() -> None:
    prepara_console()
    avvio = time.time()
    cfg = carica_config()
    if not DB_PATH.exists():
        sys.exit("Non trovo il database. Esegui prima: python src/tdb/carica.py")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    meta = dict(con.execute("SELECT * FROM meta").fetchall())
    USCITA_CSV.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    def passo(testo: str) -> None:
        print(f"  [{(time.time() - avvio) / 60:4.1f} min] {testo}")

    # --- Lettura 1: aggregazione per giorno e per combinazione di campi (la sola lettura pesante)
    passo("Aggregazione per giorno...")
    con.execute(f"""
        CREATE TEMP TABLE agg AS
        SELECT application_date AS giorno, category, source_type, decision_account, decision_provision,
               decision_monetary, decision_ground, account_type, automated_detection, automated_decision,
               {RESTRIZIONE_CONTENUTO} AS contenuto, COUNT(*) AS n
        FROM sor GROUP BY ALL""")
    a = con.execute("SELECT * FROM agg").df()
    totale = int(a["n"].sum())
    if not totale:
        sys.exit("La tabella sor e' vuota: controlla filtro piattaforma e date in config.")
    primo, ultimo = a["giorno"].min(), a["giorno"].max()
    primo = primo.date() if hasattr(primo, "date") else primo
    ultimo = ultimo.date() if hasattr(ultimo, "date") else ultimo
    a["giorno"] = pd.to_datetime(a["giorno"]).dt.date
    tutti = [primo + dt.timedelta(days=i) for i in range((ultimo - primo).days + 1)]

    def per_giorno(maschera) -> pd.Series:
        return a.loc[maschera].groupby("giorno")["n"].sum().reindex(tutti, fill_value=0)

    g = pd.DataFrame(index=pd.Index(tutti, name="giorno"))
    g["totale"] = per_giorno(slice(None))
    g["con_restrizione_contenuto"] = per_giorno(a["contenuto"])
    g["con_restrizione_account"] = per_giorno(a["decision_account"].notna() | a["decision_provision"].notna())
    g["sospensioni"] = per_giorno(a["decision_account"] == "DECISION_ACCOUNT_SUSPENDED")
    g["chiusure"] = per_giorno(a["decision_account"] == "DECISION_ACCOUNT_TERMINATED")
    g["rilevamento_automatico"] = per_giorno(a["automated_detection"] == True)  # noqa: E712
    g["decisione_tutta_automatica"] = per_giorno(a["automated_decision"] == "AUTOMATED_DECISION_FULLY")
    # Sottoinsiemi usati dalle ipotesi: dichiarazioni con restrizione account, e solo chiusure definitive.
    in_auto = a["automated_detection"] == True  # noqa: E712
    dec_auto = a["automated_decision"] == "AUTOMATED_DECISION_FULLY"
    altra = a["source_type"] == "SOURCE_TYPE_OTHER_NOTIFICATION"
    propria = a["source_type"] == "SOURCE_VOLUNTARY"
    for nome, m in (("ra", a["decision_account"].notna() | a["decision_provision"].notna()),
                    ("chi", a["decision_account"] == "DECISION_ACCOUNT_TERMINATED")):
        g[f"{nome}_n"] = per_giorno(m)
        g[f"{nome}_rilevamento_auto"] = per_giorno(m & in_auto)
        g[f"{nome}_decisione_auto"] = per_giorno(m & dec_auto)
        g[f"{nome}_altra_segnalazione"] = per_giorno(m & altra)
        g[f"{nome}_iniziativa_propria"] = per_giorno(m & propria)
    fonti = a.groupby("source_type", dropna=False)["n"].sum().sort_values(ascending=False)
    fonti = [f for f in fonti.index if isinstance(f, str) and fonti[f] / totale >= 0.001]
    for f in fonti:
        g[f"n fonte: {f}"] = per_giorno(a["source_type"] == f)
    categorie = a.groupby("category", dropna=False)["n"].sum().sort_values(ascending=False)
    categorie = [c for c in categorie.index if isinstance(c, str)]
    for c in categorie:
        g[f"n categoria: {c}"] = per_giorno(a["category"] == c)

    def quota(col: str) -> pd.Series:
        return (g[col] * 100 / g["totale"].where(g["totale"] > 0)).astype(float)

    g["quota account"] = quota("con_restrizione_account")
    g["quota rilevamento automatico"] = quota("rilevamento_automatico")
    g["quota decisione automatica"] = quota("decisione_tutta_automatica")
    for f in fonti:
        g[f"fonte: {f}"] = quota(f"n fonte: {f}")
    for c in categorie:
        g[f"categoria: {c}"] = quota(f"n categoria: {c}")
    g.to_csv(USCITA_CSV / "serie_giornaliera.csv", encoding="utf-8", float_format="%.3f")

    # --- Giorni anomali (interruzioni): molto sotto la mediana dei giorni vicini
    vicini = g["totale"].rolling(29, center=True, min_periods=7).median()
    soglia_parziale = float(cfg.get("soglia_giorno_parziale") or GIORNO_ANOMALO)
    anomali = [d for d in tutti if g.at[d, "totale"] == 0 or g.at[d, "totale"] < soglia_parziale * vicini[d]]
    validi = g.drop(index=anomali)

    # --- Cambi strutturali
    passo("Cerco i cambi strutturali...")
    metriche = [("totale", "livello", "Dichiarazioni al giorno"),
                ("sospensioni", "livello", "Sospensioni di account"),
                ("chiusure", "livello", "Chiusure definitive di account"),
                ("quota account", "quota", "Quota con restrizione sull'account (%)"),
                ("quota rilevamento automatico", "quota", "Quota con rilevamento automatico (%)"),
                ("quota decisione automatica", "quota", "Quota con decisione tutta automatica (%)")]
    metriche += [(f"fonte: {f}", "quota", f"Quota da {etichetta(f)} (%)") for f in fonti]
    metriche += [(f"categoria: {c}", "quota", f"Quota {etichetta(c)} (%)") for c in categorie
                 if g[f"categoria: {c}"].max() >= 2]
    rotture = []
    placebo = []
    for col, tipo, nome in metriche:
        cambi = misura_cambi(validi[col].fillna(0), tipo)
        if cambi.empty:
            continue
        scelti = trova_rotture(cambi)
        for i in scelti:
            r = cambi.iloc[i]
            rotture.append((r["giorno"], nome, tipo, r["prima"], r["dopo"], r["variazione"]))
        vicino_rottura = pd.Series(False, index=cambi.index)
        for i in scelti:
            vicino_rottura.iloc[max(0, i - W + 1):i + W] = True
        cambi["metrica"] = nome
        cambi["tipo"] = tipo
        cambi["vicino_a_cambio_strutturale"] = vicino_rottura
        placebo.append(cambi)
    placebo_df = pd.concat(placebo) if placebo else pd.DataFrame()
    if not placebo_df.empty:
        placebo_df.to_csv(USCITA_CSV / "variazioni_14_giorni.csv", index=False, encoding="utf-8", float_format="%.4f")

    # Raggruppa le rotture vicine (entro 7 giorni) in un solo evento
    rotture.sort(key=lambda r: r[0])
    eventi: list[list] = []
    for r in rotture:
        if eventi and (r[0] - eventi[-1][0][0]).days <= 7:
            eventi[-1].append(r)
        else:
            eventi.append([r])
    date_eventi = [ev[0][0] for ev in eventi]
    pd.DataFrame(rotture, columns=["giorno", "metrica", "tipo", "prima", "dopo", "variazione"]).to_csv(
        USCITA_CSV / "cambi_strutturali.csv", index=False, encoding="utf-8", float_format="%.3f")

    # --- Finestra di base suggerita: dall'ultimo cambio strutturale al limite, senza giorni anomali
    proposta_base = date_eventi[-1] if date_eventi else primo
    base_registrata = comune_a_data(cfg["base_da"]) if cfg.get("base_da") else None
    inizio_base = base_registrata or proposta_base
    base = [d for d in tutti if d >= inizio_base and d not in anomali]

    # --- Grafici
    passo("Grafici...")
    grafico = REPORTS / "qualita_tdb_serie.png"
    grafico_serie(g, anomali, date_eventi, fonti, grafico)
    sett = g[[f"n categoria: {c}" for c in categorie] + ["totale"]].copy()
    sett.index = pd.to_datetime(sett.index)
    sett = sett.drop(index=pd.to_datetime(anomali)).resample("W-MON", label="left", closed="left").sum()
    sett = sett[sett["totale"] > 0]
    quote_sett = pd.DataFrame({c: sett[f"n categoria: {c}"] * 100 / sett["totale"] for c in categorie
                               if (sett[f"n categoria: {c}"].sum() / totale) >= 0.01})
    grafico_cat = REPORTS / "qualita_tdb_categorie.png"
    if not quote_sett.empty:
        grafico_categorie(quote_sett, date_eventi, grafico_cat)

    # --- Lettura 2: ritardo tra decisione e invio
    passo("Ritardo di invio...")
    ultimo_invio = con.execute("SELECT MAX(CAST(created_at AS DATE)) FROM sor").fetchone()[0]
    ritardo = None
    inizio_incompleto = None
    if ultimo_invio:
        soglia = ultimo_invio - dt.timedelta(days=FINESTRA_RITARDO)
        isto = con.execute(f"""
            SELECT DATE_DIFF('day', application_date, CAST(created_at AS DATE)) AS r, COUNT(*) AS n
            FROM sor WHERE created_at IS NOT NULL AND application_date <= DATE '{soglia}'
            GROUP BY 1 ORDER BY 1""").fetchall()
        n_r = sum(n for _, n in isto)
        if n_r:
            def quantile(q: float) -> int:
                cum = 0
                for r, n in isto:
                    cum += n
                    if cum >= q * n_r:
                        return int(r)
                return int(isto[-1][0])
            oltre7 = sum(n for r, n in isto if r > 7) * 100 / n_r
            ritardo = (n_r, quantile(0.5), quantile(0.9), quantile(0.99), int(isto[-1][0]), oltre7,
                       sum(n for r, n in isto if r < 0))
            inizio_incompleto = ultimo_invio - dt.timedelta(days=ritardo[2])

    # --- Lettura 3: campi vuoti, mese per mese (un'unica lettura per tutti i campi)
    passo("Campi vuoti...")
    tipi = dict(con.execute("SELECT column_name, column_type FROM (DESCRIBE sor)").fetchall())
    campi = list(tipi)

    def vuoto(c: str) -> str:
        return f"({c} IS NULL OR LEN({c}) = 0)" if tipi[c].endswith("[]") else f"({c} IS NULL)"

    colonne = ", ".join(f"COUNT(*) FILTER (WHERE {vuoto(c)}) AS \"{c}\"" for c in campi)
    mesi = con.execute(f"""SELECT STRFTIME(application_date, '%Y-%m') AS mese, COUNT(*) AS n, {colonne}
                          FROM sor GROUP BY 1 ORDER BY 1""").df()
    vuoti = [(c, float(mesi[c].sum()) * 100 / totale) for c in campi]
    per_mese = mesi[["mese", "n"]].copy()
    for c in CAMPI_CHIAVE:
        if c in mesi:
            per_mese[c] = mesi[c] * 100 / mesi["n"]
    per_mese.to_csv(USCITA_CSV / "campi_vuoti_per_mese.csv", index=False, encoding="utf-8", float_format="%.2f")

    # --- Lettura 4: campi a lista
    passo("Campi a lista ed estensione territoriale...")
    liste = con.execute(f"""
        SELECT {', '.join(CAMPI_LISTA)},
               CASE WHEN COALESCE(LEN(territorial_scope), 0) = 0 THEN 'vuoto'
                    WHEN LEN(territorial_scope) >= {PAESI_UE} THEN 'ue'
                    WHEN LEN(territorial_scope) = 1 THEN territorial_scope[1]
                    ELSE 'piu_paesi' END AS estensione,
               COUNT(*) AS n
        FROM sor GROUP BY ALL""").df()

    # --- Lettura 5: motivazioni scritte
    passo("Motivazioni...")
    distinti = con.execute("SELECT APPROX_COUNT_DISTINCT(decision_facts) FROM sor").fetchone()[0] or 0
    if distinti <= 5000:
        motivi = con.execute("""SELECT decision_facts, category, COUNT(*) AS n FROM sor
                                GROUP BY ALL ORDER BY n DESC""").df()
    else:
        motivi = con.execute("""SELECT decision_facts, NULL AS category, COUNT(*) AS n FROM sor
                                GROUP BY 1 ORDER BY n DESC LIMIT 50""").df()

    # --- Lettura 6: controllo del caricamento contro il sito
    elenco_sito = DATI_RAW_TDB.parent / "tdb_elenco_sito.csv"
    confronto = []
    if elenco_sito.exists() and "file_giorno" in tipi:
        passo("Confronto con i conteggi del sito...")
        confronto = con.execute("""
            SELECT e.giorno, e.conteggio_sito, COALESCE(c.n, 0) AS caricate,
                   COALESCE(c.n, 0) - e.conteggio_sito AS differenza
            FROM read_csv(?, header = true, columns = {'giorno': 'DATE', 'conteggio_sito': 'BIGINT'}) e
            LEFT JOIN (SELECT file_giorno, COUNT(*) AS n FROM sor GROUP BY 1) c ON c.file_giorno = e.giorno
            WHERE e.conteggio_sito IS NOT NULL AND e.giorno BETWEEN ? AND ?
            ORDER BY e.giorno""", [elenco_sito.as_posix(), primo, ultimo]).fetchall()
    con.close()

    # ============================================================ testo del rapporto
    passo("Scrivo il rapporto...")
    avvisi: list[str] = []
    fattibilita: list[tuple[str, str, str]] = []
    md: list[str] = []
    giorni_periodo = len(tutti)
    vuoti_giorni = [d for d in tutti if g.at[d, "totale"] == 0]
    mediana = int(g["totale"].median())
    duplicati = int(meta.get("duplicati_uuid") or 0)

    # 1. Copertura
    md.append("\n## 1. Copertura\n\n")
    md.append("Si contano **dichiarazioni di motivazione**, non account ne' persone: "
              "uno stesso account puo' ricevere piu' dichiarazioni.\n\n")
    md.append(tabella_md([
        ("Dichiarazioni", totale),
        ("Primo giorno (applicazione)", primo),
        ("Ultimo giorno (applicazione)", ultimo),
        ("Ultimo giorno di invio all'UE", ultimo_invio or "?"),
        ("Giorni nel periodo", giorni_periodo),
        ("Giorni senza alcuna dichiarazione", len(vuoti_giorni)),
        ("Giorni con dati mancanti o parziali (sotto meta' dei giorni vicini)", len(anomali)),
        ("Dichiarazioni al giorno (mediana)", mediana),
        ("Righe con identificativo (uuid) ripetuto", duplicati),
    ], ["Misura", "Valore"]))
    if anomali:
        md.append("\nGiorni con dati mancanti o parziali (vanno esclusi da ogni stima):\n\n" + tabella_md(
            [(d, int(g.at[d, "totale"]), int(vicini[d])) for d in anomali],
            ["Giorno", "Dichiarazioni", "Mediana dei giorni vicini"]))
    if duplicati:
        md.append(f"\nLe {numero(duplicati)} righe ripetute sono lo "
                  f"{duplicati * 100 / totale:.4f}% del totale: trascurabili per i conteggi, "
                  "ma vanno tolte nell'analisi finale.\n")
    anno = g["totale"].copy()
    anno.index = pd.to_datetime(anno.index)
    mensile = anno.resample("MS").agg(["sum", "median", "count"])
    md.append("\nMese per mese:\n\n" + tabella_md(
        [(i.strftime("%Y-%m"), int(r["sum"]), int(r["median"]), int(r["count"])) for i, r in mensile.iterrows()],
        ["Mese", "Dichiarazioni", "Mediana al giorno", "Giorni"]))
    md.append(f"\n![Serie giornaliere]({grafico.name})\n")
    fattibilita.append(("Quante dichiarazioni ci sono?",
                        f"{numero(totale)} in {giorni_periodo} giorni, mediana {numero(mediana)} al giorno; "
                        f"{len(anomali)} giorni con dati mancanti o parziali",
                        "OK" if len(anomali) <= giorni_periodo * 0.05 else "Da valutare"))
    if len(anomali) > giorni_periodo * 0.05:
        avvisi.append(f"{len(anomali)} giorni con dati mancanti o parziali su {giorni_periodo}.")

    # 1b. Caricamento contro sito
    if confronto:
        with (USCITA_CSV / "controllo_caricamento.csv").open("w", encoding="utf-8") as f:
            f.write("giorno,conteggio_sito,caricate,differenza\n")
            f.writelines(f"{d},{s},{c},{x}\n" for d, s, c, x in confronto)
        tot_sito = sum(r[1] for r in confronto)
        tot_caricate = sum(r[2] for r in confronto)
        verificati = {comune_a_data(x) for x in (cfg.get("giorni_sito_incoerenti") or [])}
        lontani_tutti = [r for r in confronto if r[1] and abs(r[3]) / r[1] > 0.01]
        lontani = [r for r in lontani_tutti if r[0] not in verificati]
        gia_verificati = [r for r in lontani_tutti if r[0] in verificati]
        md.append("\n## 1b. Controllo del caricamento\n\n"
                  "Per ogni giorno il sito dichiara quante dichiarazioni contiene il file. Qui si confronta "
                  "con le righe finite nel database. Una differenza grande vuol dire righe perse o lette male. "
                  "Il file di un giorno puo' contenere anche qualche decisione di giorni precedenti: il "
                  "confronto si fa per file, non per data di applicazione.\n\n")
        md.append(tabella_md([
            ("Giorni confrontati", len(confronto)),
            ("Dichiarate dal sito", tot_sito),
            ("Caricate nel database", tot_caricate),
            ("Differenza (%)", round((tot_caricate - tot_sito) * 100 / tot_sito, 3) if tot_sito else 0.0),
            ("Giorni con differenza oltre l'1% (non ancora verificati)", len(lontani)),
            ("Giorni con differenza oltre l'1% (verificati: e' il sito a non tornare)", len(gia_verificati)),
        ], ["Misura", "Valore"]))
        if gia_verificati:
            md.append("\nGiorni in cui il sito dichiara un numero diverso dal contenuto del suo stesso file "
                      "(verificato contando le righe direttamente nello ZIP: il caricamento e' corretto):\n\n"
                      + tabella_md([(d, sx, c, x, int(vicini[d]) if d in vicini.index else None)
                                    for d, sx, c, x in gia_verificati],
                                   ["Giorno", "Sito", "Caricate", "Differenza", "Vicini"]))
        if lontani:
            peggiori = sorted(lontani, key=lambda r: -abs(r[3]))[:10]
            md.append("\nGiorni piu' lontani (l'ultima colonna e' la mediana dei giorni vicini caricati: "
                      "serve a capire se e' il sito o il caricamento a essere fuori linea):\n\n"
                      + tabella_md([(d, sx, c, x, int(vicini[d]) if d in vicini.index else None)
                                    for d, sx, c, x in peggiori],
                                   ["Giorno", "Sito", "Caricate", "Differenza", "Vicini"]))
            avvisi.append(f"Il caricamento non corrisponde al sito in {len(lontani)} giorni: "
                          "controlla prima di interpretare qualunque serie.")
        fattibilita.append(("Le righe caricate corrispondono a quelle del sito?",
                            f"{numero(tot_caricate)} contro {numero(tot_sito)} dichiarate, "
                            f"{len(lontani)} giorni oltre l'1% da verificare, {len(gia_verificati)} gia' verificati",
                            "OK" if not lontani else "Problema"))

    # 2. Ritardo
    md.append("\n## 2. Ritardo tra decisione e invio all'UE\n\n")
    md.append(f"Si misura sulle decisioni applicate almeno {FINESTRA_RITARDO} giorni prima dell'ultimo invio.\n\n")
    if ritardo:
        md.append(tabella_md([
            ("Dichiarazioni usate per la misura", ritardo[0]),
            ("Ritardo mediano (giorni)", ritardo[1]),
            ("90% inviate entro (giorni)", ritardo[2]),
            ("99% inviate entro (giorni)", ritardo[3]),
            ("Ritardo massimo osservato (giorni)", ritardo[4]),
            ("Quota inviata dopo piu' di 7 giorni (%)", ritardo[5]),
            ("Dichiarazioni con invio prima della decisione (errori di data)", ritardo[6]),
        ], ["Misura", "Valore"]))
        md.append(f"\nPer l'analisi della finestra dell'evento servono file scaricati fino ad almeno "
                  f"{max(ritardo[3], 1)} giorni dopo la fine della finestra.\n")
    else:
        md.append(f"Non ci sono abbastanza dati vecchi di {FINESTRA_RITARDO} giorni, o manca created_at.\n")

    # 3. Cambi strutturali
    md.append("\n## 3. Cambi strutturali nel modo di segnalare\n\n")
    md.append(f"Per ogni giorno si confronta la media dei {W} giorni validi precedenti con quella dei {W} "
              f"giorni validi da quel giorno in poi (i giorni con dati mancanti sono esclusi). Si segnala un "
              f"cambio quando un volume cresce o cala di oltre {SOGLIA_LIVELLO:.1f} volte, o una quota si sposta "
              f"di oltre {SOGLIA_QUOTA:.0f} punti percentuali. I cambi vicini (entro 7 giorni) formano un solo "
              "evento. Un cambio strutturale e' un cambio nel modo in cui Vinted compila i dati, oppure un "
              "cambio reale nella moderazione: questi dati da soli non distinguono le due cose.\n\n")
    if eventi:
        righe_ev = []
        for n, ev in enumerate(eventi, 1):
            descr = "; ".join(
                f"{nome}: {prima:.1f} → {dopo:.1f}" if tipo == "quota" else f"{nome}: {numero(prima)} → {numero(dopo)}"
                for _, nome, tipo, prima, dopo, _ in ev)
            righe_ev.append((n, ev[0][0], len(ev), descr))
        md.append(tabella_md(righe_ev, ["N.", "Inizio", "Metriche coinvolte", "Media prima → dopo"]))
        anni = giorni_periodo / 365.25
        md.append(f"\nEventi trovati: **{len(eventi)}** in {giorni_periodo} giorni "
                  f"(circa {len(eventi) / anni:.1f} all'anno). ")
        md.append("Ogni confronto prima/dopo l'evento del 17 ottobre deve tenere conto di questa frequenza: "
                  "un cambio di quella misura capita anche senza eventi esterni.\n")
    else:
        md.append("Nessun cambio sopra le soglie.\n")
    if not quote_sett.empty:
        md.append(f"\n![Categorie per settimana]({grafico_cat.name})\n")
    fattibilita.append(("Quanto spesso cambia il modo di segnalare?",
                        f"{len(eventi)} cambi strutturali in {giorni_periodo} giorni"
                        + (f" (ultimo: {date_eventi[-1]})" if date_eventi else ""),
                        "Da tenere in conto" if eventi else "OK"))

    # 4. Variazioni normali (distribuzione placebo)
    md.append(f"\n## 4. Quanto varia normalmente la serie in {W} giorni\n\n")
    md.append("Nota: questa sezione serve a descrivere la serie. Le soglie usate per le ipotesi registrate sono "
              "calcolate con la geometria della preregistrazione (finestra di 15 giorni, base registrata) in "
              "`reports/placebo.md`, e possono differire un poco da quelle qui sotto.\n\n")
    md.append(f"Per ogni giorno valido si confronta la media dei {W} giorni successivi con quella dei {W} "
              "precedenti. La distribuzione di queste variazioni, su tutto lo storico, e' il termine di "
              "paragone (placebo) per la finestra dopo il 17 ottobre: la variazione osservata dopo l'evento "
              "si colloca in questa distribuzione. Si mostrano due versioni: tutti i giorni, e solo i giorni "
              "lontani dai cambi strutturali.\n\n")
    righe_p = []
    principali = ["Dichiarazioni al giorno", "Sospensioni di account", "Chiusure definitive di account",
                  "Quota con restrizione sull'account (%)"]
    principali += [m[2] for m in metriche if m[0].startswith("categoria: ")]
    for nome in principali:
        if placebo_df.empty:
            break
        d = placebo_df[placebo_df["metrica"] == nome]
        if d.empty:
            continue
        tipo = d["tipo"].iloc[0]
        for etich, sotto in (("tutti", d), ("lontani dai cambi", d[~d["vicino_a_cambio_strutturale"]])):
            if len(sotto) < 20:
                continue
            q = sotto["variazione"].quantile([0.05, 0.5, 0.95])
            if tipo == "quota":
                fmt = [f"{v:+.1f} pt" for v in q]
            else:
                fmt = [f"{(v - 1) * 100:+.0f}%" for v in q]
            righe_p.append((nome, etich, len(sotto), *fmt))
    if righe_p:
        md.append(tabella_md(righe_p, ["Metrica", "Giorni", "Confronti", "5° percentile", "Mediana",
                                       "95° percentile"]))
        tot_norm = placebo_df[(placebo_df["metrica"] == "Dichiarazioni al giorno")
                              & ~placebo_df["vicino_a_cambio_strutturale"]]["variazione"]
        if len(tot_norm) >= 20:
            lo, hi = tot_norm.quantile([0.05, 0.95])
            fattibilita.append((f"Quanto varia normalmente il totale in {W} giorni?",
                                f"tra {(lo - 1) * 100:+.0f}% e {(hi - 1) * 100:+.0f}% nel 90% dei casi "
                                "(lontano dai cambi strutturali)", "OK"))
    giorno_sett = g.drop(index=anomali)["totale"]
    giorno_sett = giorno_sett / giorno_sett.rolling(7, center=True, min_periods=5).mean()
    nomi_g = ["lunedi'", "martedi'", "mercoledi'", "giovedi'", "venerdi'", "sabato", "domenica"]
    effetto = giorno_sett.groupby([d.weekday() for d in giorno_sett.index]).mean()
    md.append("\nEffetto del giorno della settimana (dichiarazioni rispetto alla media della settimana):\n\n"
              + tabella_md([(nomi_g[i], f"{(v - 1) * 100:+.0f}%") for i, v in effetto.items() if not math.isnan(v)],
                           ["Giorno", "Scarto"]))

    # 5. Finestra di base
    md.append("\n## 5. Finestra di base prima dell'evento\n\n")
    if base:
        if base_registrata:
            md.append(f"Finestra registrata (config `base_da`): dal **{inizio_base}** al **{ultimo}**, esclusi i "
                      f"giorni con dati mancanti o parziali: **{len(base)} giorni validi**. Il rilevatore automatico "
                      f"colloca l'ultimo cambio strutturale al {proposta_base}; quel giorno e' di transizione "
                      "(il cambio avviene durante la giornata), per questo la base parte dal giorno dopo.\n")
        else:
            md.append(f"Proposta: dal **{inizio_base}** al **{ultimo}**, cioe' dall'ultimo cambio strutturale "
                      f"al giorno prima dell'evento, esclusi i giorni con dati mancanti: **{len(base)} giorni validi**.\n")
        md.append("Una finestra che attraversa un cambio strutturale mescolerebbe due modi diversi di "
                  "segnalare e falserebbe il confronto.\n")
        esito_base = "OK" if len(base) >= 21 else "Corta"
        if len(base) < 21:
            avvisi.append(f"La finestra di base dopo l'ultimo cambio strutturale ha solo {len(base)} giorni validi.")
        fattibilita.append(("Quale finestra di base usare?",
                            f"{inizio_base} - {ultimo}, {len(base)} giorni validi", esito_base))

    # 6. Campi vuoti e compilazione
    md.append("\n## 6. Campi vuoti\n\n")
    md.append("Alcuni campi sono vuoti per costruzione (per esempio la decisione sull'account quando la "
              "dichiarazione riguarda solo un annuncio).\n\n")
    md.append(tabella_md(vuoti, ["Campo", "Vuoto (%)"]))
    md.append("\nCampi chiave vuoti, mese per mese (%). Un salto improvviso indica un cambio nel modo "
              "di compilare:\n\n")
    md.append(tabella_md([tuple(r) for r in per_mese.itertuples(index=False)],
                         ["Mese", "Dichiarazioni"] + [c for c in CAMPI_CHIAVE if c in mesi]))
    salti = [c for c in CAMPI_CHIAVE if c in per_mese and per_mese[c].max() - per_mese[c].min() > 20]
    if salti:
        avvisi.append(f"La compilazione cambia nel tempo per: {', '.join(salti)}. "
                      "Confronti prima/dopo su questi campi vanno trattati con cautela.")

    # 7. Come Vinted compila i campi
    md.append("\n## 7. Come Vinted compila i campi\n")
    righe_csv = []
    for c in CAMPI_ENUM:
        dist = a.groupby(a[c].astype(object).where(a[c].notna(), None), dropna=False)["n"].sum()
        dist = dist.sort_values(ascending=False).head(15)
        righe = [(None if (isinstance(v, float) and math.isnan(v)) else str(v), int(n), n * 100 / totale)
                 for v, n in dist.items()]
        md.append(f"\n### {c}\n\n" + tabella_md(righe, ["Valore", "Dichiarazioni", "Quota (%)"]))
        righe_csv += [(c, *r) for r in righe]
    for c in CAMPI_LISTA:
        conteggi: dict = {}
        for valori, n in zip(liste[c], liste["n"]):
            elenco = [x for x in valori] if hasattr(valori, "__len__") and not isinstance(valori, str) else []
            elenco = elenco or [None]
            for v in elenco:
                conteggi[v] = conteggi.get(v, 0) + int(n)
        righe = sorted(((v, n, n * 100 / totale) for v, n in conteggi.items()), key=lambda r: -r[1])[:15]
        md.append(f"\n### {c} (una dichiarazione puo' avere piu' valori)\n\n"
                  + tabella_md(righe, ["Valore", "Dichiarazioni", "Quota sul totale (%)"]))
        righe_csv += [(c, *r) for r in righe]
    with (USCITA_CSV / "distribuzioni.csv").open("w", encoding="utf-8") as f:
        f.write("campo,valore,dichiarazioni,quota\n")
        for campo, valore, n, q in righe_csv:
            f.write(f'{campo},"{valore if valore is not None else ""}",{n},{q:.3f}\n')
    incrocio = a.groupby([a["automated_detection"].astype(str), a["automated_decision"].astype(str)])["n"].sum()
    incrocio = incrocio.sort_values(ascending=False)
    md.append("\n### Rilevamento automatico e decisione automatica\n\n"
              "Sono due cose diverse: un sistema puo' segnalare e una persona decidere.\n\n"
              + tabella_md([(r, d, int(n), n * 100 / totale) for (r, d), n in incrocio.items()],
                           ["Rilevamento automatico", "Decisione automatica", "Dichiarazioni", "Quota (%)"]))
    vuoto_pct = dict(vuoti)
    quota_account = g["con_restrizione_account"].sum() * 100 / totale
    distinguono = (quota_account >= 0.1 and vuoto_pct.get("automated_decision", 100) <= 20
                   and vuoto_pct.get("automated_detection", 100) <= 20 and vuoto_pct.get("source_type", 100) <= 20)
    fattibilita.append(("I campi distinguono annunci/account, automazione, origine?",
                        f"restrizioni account nel {quota_account:.1f}% delle dichiarazioni; "
                        f"decisione automatica vuota nel {vuoto_pct.get('automated_decision', 100):.0f}%",
                        "OK" if distinguono else "Problema"))

    # 8. Estensione territoriale
    est = liste.groupby("estensione")["n"].sum()
    def q_est(k: str) -> float:
        return float(est.get(k, 0)) * 100 / totale
    singoli = est.drop(index=[k for k in ("vuoto", "ue", "piu_paesi") if k in est.index])
    md.append("\n## 8. Estensione territoriale delle restrizioni\n\n")
    md.append("`territorial_scope` dice **dove vale** la restrizione, non dove vive il venditore "
              "ne' dove e' stata rubata la merce.\n\n")
    md.append(tabella_md([
        ("Campo vuoto", q_est("vuoto")),
        (f"Tutta l'UE ({PAESI_UE} paesi o piu')", q_est("ue")),
        ("Piu' paesi, ma non tutta l'UE", q_est("piu_paesi")),
        ("Un solo paese", float(singoli.sum()) * 100 / totale),
        ("Solo Francia", q_est("FR")),
        ("Solo Italia", q_est("IT")),
    ], ["Estensione", "Quota (%)"]))
    if q_est("vuoto") + q_est("ue") > 90:
        avvisi.append("Estensione vuota o pari a tutta l'UE in oltre il 90% dei casi: "
                      "nessun confronto Francia-Italia possibile con questi dati.")

    # 9. Motivazioni
    md.append("\n## 9. Motivazioni scritte\n\n")
    if vuoto_pct.get("decision_facts", 100) >= 99.9:
        md.append("Campo decision_facts assente o vuoto: probabilmente e' stata scaricata la versione light.\n")
        avvisi.append("Motivazioni assenti: riscaricare la versione full.")
        fattibilita.append(("Le motivazioni distinguono i casi?", "motivazioni assenti", "Problema"))
    else:
        testi = motivi.groupby("decision_facts", dropna=False)["n"].sum().sort_values(ascending=False)
        top = testi.head(10)
        n_top = len(top)
        quota_top = float(top.sum()) * 100 / totale
        if len(testi) <= 10:
            md.append(f"Testi diversi: {len(testi)}. Coprono il {quota_top:.1f}% delle dichiarazioni.\n\n")
        else:
            md.append(f"Testi diversi (stima): {numero(distinti)}. I 10 piu' frequenti coprono il "
                      f"{quota_top:.1f}% delle dichiarazioni.\n\n")
        righe_m = []
        for testo, n in top.items():
            cat = ""
            if motivi["category"].notna().any():
                sotto = motivi[motivi["decision_facts"] == testo].groupby("category")["n"].sum()
                if not sotto.empty:
                    cat = f"{etichetta(sotto.idxmax())} ({sotto.max() * 100 / sotto.sum():.0f}%)"
            righe_m.append((str(testo)[:160] if testo is not None else None, int(n), n * 100 / totale, cat))
        md.append(tabella_md(righe_m, ["Inizio del testo", "Dichiarazioni", "Quota (%)", "Categoria prevalente"]))
        # Ricerca di parole chiave sui soli testi distinti: costa poco anche con milioni di righe
        trovati = []
        for nome, regex in GRUPPI_MOTIVO.items():
            maschera = [bool(re.search(regex, str(t).lower())) if t is not None else False for t in testi.index]
            trovati.append((nome, int(testi[maschera].sum())))
        md.append("\nParole chiave nei testi (inglese, francese, italiano):\n\n"
                  + tabella_md([(n, c, c * 100 / totale) for n, c in trovati], ["Gruppo", "Dichiarazioni", "Quota (%)"]))
        standard = quota_top > 80
        if standard:
            avvisi.append(f"Motivazioni standard ({quota_top:.0f}% delle dichiarazioni in {n_top} testi fissi): "
                          "non distinguono merce rubata, contraffazione o vendita commerciale. E' un dato rilevante "
                          "per la trasparenza richiesta dall'art. 17 del DSA. Si analizza la composizione per categoria.")
        fattibilita.append(("Le motivazioni distinguono i casi?",
                            f"{quota_top:.0f}% delle dichiarazioni in {n_top} testi fissi; merce rubata citata in "
                            f"{numero(trovati[0][1])} dichiarazioni",
                            "Problema" if standard or not trovati[0][1] else "OK"))

    testa = [
        "# Qualita' e stabilita' dei dati Vinted nel DSA Transparency Database\n\n",
        f"Generato il {dt.date.today().isoformat()}. {descrivi_modalita(cfg)}. "
        f"Dati caricati il {meta.get('caricato_il', '?')}.\n",
        "\n## Le domande di fattibilita'\n\n",
        tabella_md(fattibilita, ["Domanda", "Risposta", "Esito"]),
        "\n## Da guardare per primo\n\n",
    ]
    testa += [f"- {x}\n" for x in avvisi] or ["- Nessun problema evidente.\n"]
    uscita = REPORTS / "qualita_tdb.md"
    uscita.write_text(accenti("".join(testa + md)), encoding="utf-8")
    print(f"\nRapporto scritto: {uscita}")
    print(f"Grafici: {grafico.name}, {grafico_cat.name} (in {REPORTS})")
    print(f"Tabelle: {USCITA_CSV}")
    for domanda, risposta, esito in fattibilita:
        print(f"  [{esito}] {domanda} {risposta}")
    if date_eventi:
        print("  Cambi strutturali: " + ", ".join(d.isoformat() for d in date_eventi))
    print(f"Tempo totale: {(time.time() - avvio) / 60:.1f} minuti")


if __name__ == "__main__":
    main()
