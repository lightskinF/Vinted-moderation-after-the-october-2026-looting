"""Scarica i file giornalieri di Vinted direttamente dal sito del DSA Transparency Database.

Alternativa leggera a dsa-tdb (che richiede PySpark e Java). Il sito offre, per ogni
piattaforma e per ogni giorno, uno ZIP con tutte le dichiarazioni di motivazione:
per Vinted sono circa 10-12 MB al giorno (circa 130 MB di CSV).

Uso, dalla cartella del progetto con l'ambiente attivo:

    python src/tdb/scarica_diretto.py --prova                      elenca i giorni, non scarica
    python src/tdb/scarica_diretto.py --da 2026-10-14 --a 2026-10-16   tre giorni di prova
    python src/tdb/scarica_diretto.py                              il periodo scritto in config
    python src/tdb/scarica_diretto.py --da 2026-09-30 --a 2026-10-02 --forza   riscarica e confronta con il file che hai

Gli ZIP finiscono in data/raw/tdb/manuale/, dove carica.py li legge. I file gia' scaricati
e integri si saltano, quindi si puo' rilanciare dopo un'interruzione.
In modalita' cieca la data di fine viene fermata al giorno prima dell'evento.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comune import DATI_RAW_TDB, a_data, carica_config, data_limite, descrivi_modalita, prepara_console  # noqa: E402

try:  # usa i certificati di Windows: utile se un antivirus o un proxy sostituisce i certificati
    import truststore
    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass
import requests  # noqa: E402

BASE = "https://transparency.dsa.ec.europa.eu"
LISTA = BASE + "/explore-data/download"
CARTELLA = DATI_RAW_TDB / "manuale"
RIGA = re.compile(r"<tr[^>]*dayarchive-row[^>]*>(.*?)</tr>", re.S)
DATA = re.compile(r'data-ecl-table-header="Date"[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*<')
ID_FILE = re.compile(r"/download-file/(\d+)/")
CONTEGGIO = re.compile(r'data-ecl-table-header="Statements of reasons"[^>]*>\s*([^<]*?)\s*<')
ELENCO_SITO = DATI_RAW_TDB.parent / "tdb_elenco_sito.csv"  # fuori da data/raw/tdb: carica.py non lo legge come dato
SHA1 = re.compile(r"\b[0-9a-fA-F]{40}\b")
GB_PER_GIORNO = 0.03  # ZIP (circa 10 MB) + Parquet (circa 8 MB) + database (circa 7 MB)
PAUSA = 0.5


def sessione() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "VintedScope/0.1 (ricerca indipendente sui dati pubblici DSA)"
    return s


def prendi(s: requests.Session, url: str, **kw) -> requests.Response:
    ultimo: Exception | None = None
    for tentativo in range(1, 4):
        try:
            r = s.get(url, timeout=(15, 120), **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            ultimo = e
            time.sleep(2 * tentativo)
    raise RuntimeError(f"Richiesta fallita dopo 3 tentativi: {url}\n  {ultimo}")


def elenca_giorni(s: requests.Session, piattaforma_id: int, da: dt.date, a: dt.date) -> dict[dt.date, tuple[str, int | None]]:
    """Legge l'elenco dei file della piattaforma e restituisce {giorno: (id del file, dichiarazioni dette dal sito)}."""
    trovati: dict[dt.date, tuple[str, int | None]] = {}
    viste: set[dt.date] = set()
    for pagina in range(1, 200):
        r = prendi(s, LISTA, params={"platform_id": piattaforma_id, "page": pagina})
        date_pagina = []
        for riga in RIGA.findall(r.text):
            m, i = DATA.search(riga), ID_FILE.search(riga)
            if not m or not i:
                continue
            giorno = dt.date.fromisoformat(m.group(1))
            date_pagina.append(giorno)
            if da <= giorno <= a:
                c = CONTEGGIO.search(riga)
                cifre = re.sub(r"\D", "", c.group(1)) if c else ""
                trovati[giorno] = (i.group(1), int(cifre) if cifre else None)
        nuove = set(date_pagina) - viste
        if not nuove:  # pagina vuota o ripetuta: elenco finito
            break
        viste |= nuove
        if min(date_pagina) < da:
            break
    else:
        sys.exit("Troppe pagine nell'elenco: interrompo.")
    if not viste:
        sys.exit("Non ho trovato nessuna riga nell'elenco del sito. Il sito potrebbe aver cambiato formato: "
                 "usa il piano B del README (download a mano).")
    return trovati


def salva_elenco(giorni: dict[dt.date, tuple[str, int | None]]) -> None:
    """Salva quante dichiarazioni dichiara il sito per ogni giorno (solo i giorni richiesti, quindi
    mai oltre il limite della modalita' cieca). qualita.py le confronta con le righe caricate."""
    esistenti: dict[str, str] = {}
    if ELENCO_SITO.exists():
        for riga in ELENCO_SITO.read_text(encoding="utf-8").splitlines()[1:]:
            giorno, _, conteggio = riga.partition(",")
            esistenti[giorno] = conteggio
    for giorno, (_, conteggio) in giorni.items():
        esistenti[giorno.isoformat()] = "" if conteggio is None else str(conteggio)
    ELENCO_SITO.parent.mkdir(parents=True, exist_ok=True)
    ELENCO_SITO.write_text("giorno,conteggio_sito\n" + "".join(f"{g},{c}\n" for g, c in sorted(esistenti.items())),
                           encoding="utf-8")


def sha1_atteso(s: requests.Session, id_file: str, versione: str) -> str | None:
    tipo = "sha1light" if versione == "light" else "sha1"
    try:
        m = SHA1.search(prendi(s, f"{BASE}/explore-data/download-file/{id_file}/{tipo}").text)
        return m.group(0).lower() if m else None
    except RuntimeError:
        return None


def sha1_file(percorso: Path) -> str:
    h = hashlib.sha1()
    with percorso.open("rb") as f:
        for blocco in iter(lambda: f.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


def scarica_giorno(s: requests.Session, id_file: str, versione: str, dest: Path, forza: bool = False) -> str:
    """Scarica un file. Restituisce 'ok', 'gia presente' o solleva RuntimeError.
    Con forza=True riscarica anche se il file c'e' e dice se il sito lo ha cambiato."""
    vecchio: str | None = None
    if dest.exists() and dest.stat().st_size > 0:
        if forza:
            vecchio = sha1_file(dest)
        else:
            try:
                with zipfile.ZipFile(dest) as z:
                    if z.namelist():
                        return "gia presente"
            except zipfile.BadZipFile:
                dest.unlink()
    atteso = sha1_atteso(s, id_file, versione)
    tmp = dest.with_suffix(".part")
    ultimo = "errore sconosciuto"
    for tentativo in range(1, 4):
        try:
            h = hashlib.sha1()
            with s.get(f"{BASE}/explore-data/download-file/{id_file}/{versione}", stream=True, timeout=(15, 300)) as r:
                r.raise_for_status()
                with tmp.open("wb") as f:
                    for blocco in r.iter_content(1 << 20):
                        f.write(blocco)
                        h.update(blocco)
            if atteso and h.hexdigest() != atteso:
                ultimo = "checksum SHA1 diverso"
                continue
            with zipfile.ZipFile(tmp) as z:
                if not z.namelist():
                    ultimo = "ZIP vuoto"
                    continue
            tmp.replace(dest)
            nota = "" if vecchio is None else (", IDENTICO a prima" if h.hexdigest() == vecchio
                                               else ", DIVERSO da prima (il sito ha cambiato il file)")
            return ("ok" if atteso else "ok (checksum non verificato)") + nota
        except (requests.RequestException, zipfile.BadZipFile) as e:
            ultimo = str(e)
            time.sleep(2 * tentativo)
    tmp.unlink(missing_ok=True)
    raise RuntimeError(ultimo)


def main() -> None:
    prepara_console()
    parser = argparse.ArgumentParser(description="Scarica i file giornalieri di Vinted dal sito UE")
    parser.add_argument("--da", help="primo giorno (AAAA-MM-GG)")
    parser.add_argument("--a", help="ultimo giorno (AAAA-MM-GG)")
    parser.add_argument("--prova", action="store_true", help="elenca i giorni senza scaricare")
    parser.add_argument("--forza", action="store_true",
                        help="riscarica anche i file gia' presenti e dice se il sito li ha cambiati")
    args = parser.parse_args()

    cfg = carica_config()
    versione = str(cfg.get("versione", "full")).strip().lower()
    if versione not in ("full", "light"):
        sys.exit("In config 'versione' deve essere full o light.")
    piattaforma_id = int(cfg.get("piattaforma_id_sito") or 40)
    da = a_data(args.da or cfg["download_da"])
    a = a_data(args.a or cfg["download_a"])
    limite = data_limite(cfg)
    print(descrivi_modalita(cfg))
    if limite is not None and a > limite:
        print(f"Fine spostata da {a} a {limite} per la modalita' cieca.")
        a = limite
    if da > a:
        sys.exit(f"Periodo vuoto: {da} e' dopo {a}.")

    s = sessione()
    print(f"Leggo l'elenco dei file (piattaforma n. {piattaforma_id}, versione {versione})...")
    giorni = elenca_giorni(s, piattaforma_id, da, a)
    if not giorni:
        sys.exit(f"Nessun file tra {da} e {a} per questa piattaforma.")
    richiesti = [da + dt.timedelta(days=i) for i in range((a - da).days + 1)]
    mancanti = [g for g in richiesti if g not in giorni]
    print(f"  File trovati: {len(giorni)} su {len(richiesti)} giorni ({min(giorni)} - {max(giorni)}).")
    if mancanti:
        elenco = ", ".join(g.isoformat() for g in mancanti[:15])
        print(f"  Giorni senza file: {len(mancanti)} ({elenco}{' ...' if len(mancanti) > 15 else ''}). "
              "Annotalo: e' un'informazione sulla completezza dei dati.")

    DATI_RAW_TDB.mkdir(parents=True, exist_ok=True)
    salva_elenco(giorni)
    libero = shutil.disk_usage(DATI_RAW_TDB).free / 1e9
    servono = len(giorni) * GB_PER_GIORNO
    print(f"  Spazio libero: {libero:.0f} GB. Ne servono circa {servono:.0f} GB tra file, estrazione e database.")
    if libero < servono:
        print("  ATTENZIONE: lo spazio sembra insufficiente.")
    if args.prova:
        return

    CARTELLA.mkdir(parents=True, exist_ok=True)
    errori = []
    for n, giorno in enumerate(sorted(giorni), 1):
        dest = CARTELLA / f"sor-vinted-uab-{giorno.isoformat()}-{versione}.zip"
        try:
            esito = scarica_giorno(s, giorni[giorno][0], versione, dest, args.forza)
        except RuntimeError as e:
            errori.append(giorno)
            esito = f"ERRORE ({e})"
        dimensione = f"{dest.stat().st_size / 1e6:.1f} MB" if dest.exists() else "-"
        print(f"  [{n}/{len(giorni)}] {giorno}: {esito}, {dimensione}")
        if esito.startswith("ok"):
            time.sleep(PAUSA)

    if errori:
        print(f"\n{len(errori)} giorni non scaricati: {', '.join(g.isoformat() for g in errori)}. "
              "Rilancia lo stesso comando: scarica solo quelli che mancano.")
        sys.exit(1)
    print("\nFatto. Ora esegui: python src/tdb/carica.py")


if __name__ == "__main__":
    main()
