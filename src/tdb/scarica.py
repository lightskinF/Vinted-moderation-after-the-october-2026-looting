"""Scarica i dump giornalieri di Vinted dal DSA Transparency Database con dsa-tdb.

Uso, dalla cartella del progetto con l'ambiente attivo:

    python src/tdb/scarica.py --cerca-nome          trova come dsa-tdb chiama Vinted
    python src/tdb/scarica.py --prova               mostra il comando senza eseguirlo
    python src/tdb/scarica.py                       scarica il periodo scritto in config
    python src/tdb/scarica.py --da 2026-10-10 --a 2026-10-16

In modalita' cieca la data di fine viene fermata al giorno prima dell'evento.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comune import DATI_RAW_TDB, a_data, carica_config, data_limite, descrivi_modalita, prepara_console  # noqa: E402

ISTRUZIONI_INSTALLAZIONE = (
    "Non trovo il comando dsa-tdb-cli. Con l'ambiente attivo esegui:\n"
    "  pip install dsa-tdb --index-url https://code.europa.eu/api/v4/projects/943/packages/pypi/simple "
    "--extra-index-url https://pypi.org/simple\n"
    "Se l'installazione fallisce, usa il piano B descritto nel README (download dal sito)."
)


def trova_cli() -> str:
    exe = shutil.which("dsa-tdb-cli")
    if not exe:
        sys.exit(ISTRUZIONI_INSTALLAZIONE)
    return exe


def cerca_nome(exe: str) -> None:
    risultato = subprocess.run([exe, "preprocess", "-h"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
    testo = (risultato.stdout or "") + (risultato.stderr or "")
    nomi = sorted(set(re.findall(r"[\w.\-]*[Vv][Ii][Nn][Tt][Ee][Dd][\w.\-]*", testo)))
    if nomi:
        print("Nomi che contengono 'vinted' nell'help di dsa-tdb-cli:")
        for nome in nomi:
            print(f"  {nome}")
        print("\nCopia quello giusto in config/progetto.yaml alla voce piattaforma_cli.")
    else:
        print(testo)
        print("\nNell'help non compare 'vinted'. Cerca sopra l'elenco delle piattaforme "
              "accettate dall'opzione -p, oppure usa il piano B del README.")


def main() -> None:
    prepara_console()
    parser = argparse.ArgumentParser(description="Scarica i dati di Vinted dal database UE")
    parser.add_argument("--cerca-nome", action="store_true", help="mostra il nome di Vinted per dsa-tdb")
    parser.add_argument("--da", help="primo giorno (AAAA-MM-GG)")
    parser.add_argument("--a", help="ultimo giorno (AAAA-MM-GG)")
    parser.add_argument("--prova", action="store_true", help="mostra il comando senza eseguirlo")
    args = parser.parse_args()

    cfg = carica_config()
    exe = "dsa-tdb-cli" if args.prova else trova_cli()

    if args.cerca_nome:
        cerca_nome(trova_cli())
        return

    piattaforma = str(cfg.get("piattaforma_cli") or "").strip()
    if not piattaforma:
        sys.exit("Manca piattaforma_cli in config/progetto.yaml. "
                 "Esegui prima: python src/tdb/scarica.py --cerca-nome")

    da = a_data(args.da or cfg["download_da"])
    a = a_data(args.a or cfg["download_a"])
    limite = data_limite(cfg)
    print(descrivi_modalita(cfg))
    if limite is not None and a > limite:
        print(f"Fine spostata da {a} a {limite} per la modalita' cieca.")
        a = limite
    if da > a:
        sys.exit(f"Periodo vuoto: {da} e' dopo {a}.")

    DATI_RAW_TDB.mkdir(parents=True, exist_ok=True)
    comando = [
        exe, "preprocess",
        "-o", str(DATI_RAW_TDB),
        "-v", str(cfg.get("versione", "full")),
        "-p", piattaforma,
        "-i", da.isoformat(),
        "-f", a.isoformat(),
        "--format", "parquet",
    ]
    print("Comando:", " ".join(f'"{c}"' if " " in c else c for c in comando))
    if args.prova:
        return
    esito = subprocess.run(comando)
    if esito.returncode != 0:
        sys.exit(f"dsa-tdb-cli e' terminato con errore ({esito.returncode}). "
                 "Controlla il messaggio qui sopra, oppure usa il piano B del README.")
    print("Fatto. Ora esegui: python src/tdb/carica.py")


if __name__ == "__main__":
    main()
