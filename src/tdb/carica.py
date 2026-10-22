"""Carica in DuckDB i dati Vinted scaricati, li normalizza e applica la modalita' cieca.

Legge cio' che trova in data/raw/tdb:
  - gli ZIP giornalieri scaricati dal sito (scarica_diretto.py o a mano): ognuno viene
    convertito una volta sola in un file Parquet in data/raw/tdb/giorni_parquet/, leggendo i
    CSV direttamente dentro lo ZIP, senza estrarli sul disco;
  - i file Parquet prodotti da dsa-tdb;
  - CSV sciolti, solo se non c'e' nessun Parquet (o con --anche-csv).
Crea data/interim/vinted.duckdb con la tabella `sor`: una riga per provvedimento,
campi ripuliti, duplicati tolti, solo Vinted, solo le date consentite.

Uso:  python src/tdb/carica.py            (aggiungi --anche-csv per unire Parquet e CSV)
      python src/tdb/carica.py --ricarica 2026-09-30 2026-10-02   rilegge dagli ZIP solo quei giorni
"""
from __future__ import annotations

import argparse
import csv as modulo_csv
import datetime as dt
import io
import re
import sys
import time
import zipfile
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comune import DATI_RAW_TDB, DB_PATH, carica_config, data_limite, descrivi_modalita, prepara_console  # noqa: E402

CARTELLA_ESTRATTI = DATI_RAW_TDB / "_estratti"  # vecchia estrazione su disco: ora ignorata, si puo' cancellare
CARTELLA_PARQUET = DATI_RAW_TDB / "giorni_parquet"

# Come ripulire ogni campo. {c} = colonna originale letta come testo.
CAMPI = {
    "uuid": "NULLIF(TRIM({c}), '')",
    "puid": "NULLIF(TRIM({c}), '')",
    "platform_name": "NULLIF(TRIM({c}), '')",
    "application_date": "TRY_CAST(SUBSTR({c}, 1, 10) AS DATE)",
    "content_date": "TRY_CAST(SUBSTR({c}, 1, 10) AS DATE)",
    "created_at": "TRY_CAST(SUBSTR(REPLACE({c}, 'T', ' '), 1, 19) AS TIMESTAMP)",
    "decision_visibility": "LIST_DISTINCT(REGEXP_EXTRACT_ALL({c}, 'DECISION_VISIBILITY_[A-Z_]+'))",
    "decision_monetary": "REGEXP_EXTRACT({c}, 'DECISION_MONETARY_[A-Z_]+')",
    "decision_provision": "REGEXP_EXTRACT({c}, 'DECISION_PROVISION_[A-Z_]+')",
    "decision_account": "REGEXP_EXTRACT({c}, 'DECISION_ACCOUNT_[A-Z_]+')",
    "account_type": "REGEXP_EXTRACT({c}, 'ACCOUNT_TYPE_[A-Z_]+')",
    "decision_ground": "REGEXP_EXTRACT({c}, 'DECISION_GROUND_[A-Z_]+')",
    "category": "REGEXP_EXTRACT({c}, 'STATEMENT_CATEGORY_[A-Z_]+')",
    "category_specification": "LIST_DISTINCT(REGEXP_EXTRACT_ALL({c}, 'KEYWORD_[A-Z_]+'))",
    "content_type": "LIST_DISTINCT(REGEXP_EXTRACT_ALL({c}, 'CONTENT_TYPE_[A-Z_]+'))",
    "automated_detection": ("CASE WHEN NULLIF(TRIM({c}), '') IS NULL THEN NULL "
                            "ELSE LOWER(TRIM({c})) IN ('yes', 'true', '1') END"),
    "automated_decision": "REGEXP_EXTRACT({c}, 'AUTOMATED_DECISION_[A-Z_]+')",
    "source_type": "REGEXP_EXTRACT({c}, 'SOURCE_[A-Z_0-9]+')",
    "territorial_scope": "LIST_SORT(LIST_DISTINCT(REGEXP_EXTRACT_ALL({c}, '\\b[A-Z]{{2}}\\b')))",
    "content_language": "NULLIF(TRIM({c}), '')",
    "decision_facts": "NULLIF(TRIM({c}), '')",
    "incompatible_content_ground": "NULLIF(TRIM({c}), '')",
    "incompatible_content_explanation": "NULLIF(TRIM({c}), '')",
    "illegal_content_legal_ground": "NULLIF(TRIM({c}), '')",
    "illegal_content_explanation": "NULLIF(TRIM({c}), '')",
    "end_date_account_restriction": "TRY_CAST(SUBSTR({c}, 1, 10) AS DATE)",
    "end_date_visibility_restriction": "TRY_CAST(SUBSTR({c}, 1, 10) AS DATE)",
}

TIPI_VUOTI = {
    "application_date": "DATE", "content_date": "DATE", "created_at": "TIMESTAMP",
    "end_date_account_restriction": "DATE", "end_date_visibility_restriction": "DATE",
    "decision_visibility": "VARCHAR[]", "category_specification": "VARCHAR[]",
    "content_type": "VARCHAR[]", "territorial_scope": "VARCHAR[]",
    "automated_detection": "BOOLEAN",
}


def posix(percorsi: list[Path]) -> list[str]:
    return [p.as_posix() for p in percorsi]


def giorno_del_gruppo(nome: str) -> dt.date | None:
    m = re.search(r"\d{4}-\d{2}-\d{2}", nome)
    return dt.date.fromisoformat(m.group(0)) if m else None


def leggi_csv(dati: bytes, scarti: list[int]) -> pa.Table | None:
    """Legge un CSV del database UE come tabella di testi (nessuna conversione di tipo)."""
    if dati.startswith(b"\xef\xbb\xbf"):
        dati = dati[3:]
    if not dati.strip():
        return None
    intestazione = dati.split(b"\n", 1)[0].decode("utf-8", "replace").rstrip("\r")
    colonne = next(modulo_csv.reader([intestazione]))

    def salta(_riga) -> str:
        scarti.append(1)
        return "skip"

    return pacsv.read_csv(
        io.BytesIO(dati),
        parse_options=pacsv.ParseOptions(newlines_in_values=True, invalid_row_handler=salta),
        convert_options=pacsv.ConvertOptions(column_types={c: pa.string() for c in colonne},
                                             strings_can_be_null=True),
    )


def tabelle_da_zip(z: zipfile.ZipFile, tabelle: list[pa.Table], scarti: list[int], nomi: list[str]) -> None:
    """Raccoglie i CSV di uno ZIP, anche dentro ZIP annidati (come nei file del sito UE)."""
    for info in z.infolist():
        if info.is_dir():
            continue
        if len(nomi) < 8:
            nomi.append(info.filename)
        nome = info.filename.lower()
        if nome.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(z.read(info))) as interno:
                    tabelle_da_zip(interno, tabelle, scarti, nomi)
            except zipfile.BadZipFile:
                print(f"  ZIP interno danneggiato, lo salto: {info.filename}")
        elif nome.endswith(".csv"):
            tabella = leggi_csv(z.read(info), scarti)
            if tabella is not None and tabella.num_rows:
                tabelle.append(tabella)


def converti_zip(salta: set[dt.date]) -> None:
    """Converte ogni ZIP giornaliero in un Parquet (una volta sola). Salta i giorni gia' convertiti
    e quelli gia' nel database."""
    archivi = [a for a in sorted(DATI_RAW_TDB.rglob("*.zip")) if CARTELLA_ESTRATTI not in a.parents]
    da_fare = [a for a in archivi if not (CARTELLA_PARQUET / f"{a.stem}.parquet").exists()
               and giorno_del_gruppo(a.stem) not in salta]
    if not da_fare:
        return
    print(f"  Converto {len(da_fare)} archivi ZIP in Parquet (una volta sola)...")
    CARTELLA_PARQUET.mkdir(parents=True, exist_ok=True)
    for n, archivio in enumerate(da_fare, 1):
        inizio = time.time()
        tabelle: list[pa.Table] = []
        scarti: list[int] = []
        nomi: list[str] = []
        try:
            with zipfile.ZipFile(archivio) as z:
                tabelle_da_zip(z, tabelle, scarti, nomi)
        except zipfile.BadZipFile:
            print(f"  ZIP danneggiato, lo salto: {archivio.name}")
            continue
        if not tabelle:
            print(f"  Nessun CSV dentro {archivio.name}. Contenuto (primi nomi): {nomi}")
            continue
        tabella = pa.concat_tables(tabelle, promote_options="permissive")
        giorno = re.search(r"\d{4}-\d{2}-\d{2}", archivio.stem)
        tabella = tabella.append_column(
            "file_giorno", pa.array([giorno.group(0) if giorno else None] * tabella.num_rows, pa.string()))
        destinazione = CARTELLA_PARQUET / f"{archivio.stem}.parquet"
        parziale = CARTELLA_PARQUET / f"{archivio.stem}.parquet.parte"
        pq.write_table(tabella, parziale, compression="zstd")
        parziale.replace(destinazione)
        righe = f"{tabella.num_rows:,}".replace(",", ".")
        nota = f", {len(scarti)} righe illeggibili saltate" if scarti else ""
        print(f"  Convertito {n}/{len(da_fare)} {archivio.stem}: {righe} righe{nota}, {time.time() - inizio:.1f} s")


def controlla_intestazioni(csv: list[Path]) -> None:
    """Ogni blocco CSV deve avere la riga delle intestazioni: se manca, le righe sarebbero lette male."""
    passo = max(1, len(csv) // 200)
    senza = 0
    for percorso in csv[::passo]:
        with percorso.open("r", encoding="utf-8", errors="replace") as f:
            prima = f.readline()
        if "uuid" not in prima or "application_date" not in prima:
            senza += 1
    if senza:
        print(f"  ATTENZIONE: {senza} file CSV controllati su {len(csv[::passo])} non hanno la riga delle "
              "intestazioni. Le righe potrebbero essere lette male: scrivimelo.")


def raccogli_file(anche_csv: bool, salta: set[dt.date]) -> tuple[list[Path], list[Path]]:
    converti_zip(salta)
    parquet = sorted(p for p in DATI_RAW_TDB.rglob("*.parquet") if CARTELLA_ESTRATTI not in p.parents)
    csv: list[Path] = []
    if anche_csv or not parquet:
        csv = sorted(p for p in DATI_RAW_TDB.rglob("*.csv") if CARTELLA_ESTRATTI not in p.parents)
    return parquet, csv


def gruppi_csv(csv: list[Path]) -> list[tuple[str, list[Path]]]:
    """Raggruppa i CSV per giorno (cartella estratta da uno ZIP) per caricarli un gruppo alla volta."""
    gruppi: dict[str, list[Path]] = {}
    for percorso in csv:
        if CARTELLA_ESTRATTI in percorso.parents:
            chiave = percorso.relative_to(CARTELLA_ESTRATTI).parts[0]
        else:
            chiave = str(percorso.parent)
        gruppi.setdefault(chiave, []).append(percorso)
    return sorted(gruppi.items())


def crea_vista(con: duckdb.DuckDBPyConnection, parquet: list[Path], csv: list[Path]) -> None:
    if parquet:
        con.execute(f"CREATE OR REPLACE TEMP VIEW grezzo AS SELECT * FROM read_parquet({posix(parquet)}, union_by_name = true)")
    else:
        con.execute(
            f"CREATE OR REPLACE TEMP VIEW grezzo AS SELECT * FROM read_csv({posix(csv)}, "
            "union_by_name = true, all_varchar = true, header = true, quote = '\"', escape = '\"', "
            "max_line_size = 20000000, ignore_errors = true, filename = true)"
        )


def main() -> None:
    prepara_console()
    parser = argparse.ArgumentParser(description="Carica in DuckDB i dati Vinted scaricati")
    parser.add_argument("--anche-csv", action="store_true", help="unisci Parquet e CSV/ZIP")
    parser.add_argument("--ricarica", nargs="+", metavar="GIORNO",
                        help="giorni (AAAA-MM-GG) da togliere dal database e rileggere dagli ZIP")
    parser.add_argument("--da-zero", action="store_true",
                        help="ricostruisci il database da capo invece di aggiungere solo i giorni nuovi")
    args = parser.parse_args()

    cfg = carica_config()
    limite = data_limite(cfg)
    print(descrivi_modalita(cfg))

    if not DATI_RAW_TDB.exists():
        sys.exit(f"Non trovo {DATI_RAW_TDB}. Scarica prima i dati (src/tdb/scarica_diretto.py).")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    esiste = bool(con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'sor'").fetchone()[0])
    if args.da_zero and esiste:
        con.execute("DROP TABLE sor")
        esiste = False
    if args.ricarica and esiste:
        for testo in args.ricarica:
            giorno = dt.date.fromisoformat(testo)
            tolte = con.execute("SELECT COUNT(*) FROM sor WHERE file_giorno = ?", [giorno]).fetchone()[0]
            con.execute("DELETE FROM sor WHERE file_giorno = ?", [giorno])
            for p in CARTELLA_PARQUET.glob(f"*{giorno.isoformat()}*.parquet"):
                p.unlink()
            print(f"  {giorno}: tolte {tolte:,} righe dal database e il Parquet; si rilegge dallo ZIP".replace(",", "."))
    gia_caricati: set[dt.date] = set()
    if esiste:
        gia_caricati = {r[0] for r in con.execute(
            "SELECT DISTINCT file_giorno FROM sor WHERE file_giorno IS NOT NULL").fetchall()}
        print(f"  Database esistente: {len(gia_caricati)} giorni gia' caricati, li salto "
              "(per ricostruire tutto: --da-zero)")

    parquet, csv = raccogli_file(args.anche_csv, gia_caricati)
    if not parquet and not csv and not esiste:
        sys.exit(f"Nessun file Parquet, CSV o ZIP in {DATI_RAW_TDB}.")
    if csv:
        controlla_intestazioni(csv)

    # Un gruppo = un giorno: leggere migliaia di file in un'unica query e' lentissimo.
    gruppi: list[tuple[str, list[Path], list[Path]]] = []
    gruppi += [(p.stem, [p], []) for p in parquet]
    gruppi += [(nome, [], file) for nome, file in gruppi_csv(csv)]
    da_caricare = [g for g in gruppi if giorno_del_gruppo(g[0]) is None or giorno_del_gruppo(g[0]) not in gia_caricati]
    print(f"  Giorni da aggiungere al database: {len(da_caricare)}")

    filtri = ["application_date IS NOT NULL"]
    filtro_piattaforma = str(cfg.get("piattaforma_filtro") or "").strip()
    if limite is not None:
        filtri.append(f"application_date <= DATE '{limite.isoformat()}'")

    presenti: set[str] = set()
    inizio = time.time()
    for n, (nome, file_pq, file_csv) in enumerate(da_caricare, 1):
        crea_vista(con, file_pq, file_csv)
        colonne = {r[0] for r in con.execute("DESCRIBE grezzo").fetchall()}
        presenti |= colonne
        selezione = []
        for campo, regola in CAMPI.items():
            if campo in colonne:
                testo = f'CAST("{campo}" AS VARCHAR)'
                selezione.append(f"{regola.format(c=testo)} AS {campo}")
            else:
                selezione.append(f"CAST(NULL AS {TIPI_VUOTI.get(campo, 'VARCHAR')}) AS {campo}")
        if "file_giorno" in colonne:
            selezione.append("TRY_CAST(file_giorno AS DATE) AS file_giorno")
        elif "filename" in colonne:
            # Giorno del file di origine: serve a confrontare le righe caricate con quelle dichiarate dal sito.
            selezione.append("TRY_CAST(REGEXP_EXTRACT(CAST(filename AS VARCHAR), '(\\d{4}-\\d{2}-\\d{2})', 1) AS DATE) AS file_giorno")
        else:
            selezione.append("CAST(NULL AS DATE) AS file_giorno")
        filtri_gruppo = list(filtri)
        if filtro_piattaforma and "platform_name" in colonne:
            filtri_gruppo.append(f"platform_name ILIKE '%{filtro_piattaforma}%'")
        query = (f"SELECT * FROM (SELECT {', '.join(selezione)} FROM grezzo) "
                 f"WHERE {' AND '.join(filtri_gruppo)}")
        if not esiste:
            con.execute(f"CREATE TABLE sor AS {query}")
            esiste = True
        else:
            con.execute(f"INSERT INTO sor BY NAME {query}")
        if n == 1 or n % 10 == 0 or n == len(da_caricare):
            minuti = (time.time() - inizio) / 60
            print(f"  Caricato {n}/{len(da_caricare)} ({nome}), {minuti:.1f} minuti")

    if not esiste:
        sys.exit("Nessun dato caricato.")
    righe, distinti, primo, ultimo = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT uuid), MIN(application_date), MAX(application_date) FROM sor").fetchone()
    mancanti = [c for c in CAMPI if presenti and c not in presenti]
    con.execute("""CREATE OR REPLACE TABLE meta (chiave VARCHAR, valore VARCHAR)""")
    con.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("caricato_il", dt.datetime.now().isoformat(timespec="seconds")),
        ("modalita_cieca", str(limite is not None)),
        ("limite_date", limite.isoformat() if limite else ""),
        ("file_parquet", str(len(parquet))),
        ("file_csv", str(len(csv))),
        ("campi_mancanti", ", ".join(mancanti)),
        ("duplicati_uuid", str(righe - distinti)),
    ])
    con.close()

    print(f"  Righe Vinted nel database: {righe:,}".replace(",", "."))
    print(f"  Periodo (data di applicazione): {primo} - {ultimo}")
    if righe - distinti:
        print(f"  ATTENZIONE: {righe - distinti:,} righe con uuid ripetuto. Scrivimelo.".replace(",", "."))
    if mancanti:
        print(f"  Campi assenti nei file nuovi: {', '.join(mancanti)}")
    if limite is not None:
        print("  Le righe dal giorno dell'evento in poi non sono state caricate (modalita' cieca).")
    print(f"Database pronto: {DB_PATH}\nOra esegui: python src/tdb/qualita.py")


if __name__ == "__main__":
    main()
