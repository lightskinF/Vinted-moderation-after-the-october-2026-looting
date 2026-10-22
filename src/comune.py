"""Funzioni comuni: percorsi del progetto, configurazione, modalita' cieca."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import yaml

RADICE = Path(__file__).resolve().parents[1]
CONFIG = RADICE / "config" / "progetto.yaml"
DATI_RAW_TDB = RADICE / "data" / "raw" / "tdb"
DATI_INTERIM = RADICE / "data" / "interim"
DATI_PROCESSED = RADICE / "data" / "processed"
REPORTS = RADICE / "reports"
DB_PATH = DATI_INTERIM / "vinted.duckdb"


def prepara_console() -> None:
    """Evita errori con le lettere accentate nel terminale di Windows."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def a_data(valore) -> dt.date:
    if isinstance(valore, dt.datetime):
        return valore.date()
    if isinstance(valore, dt.date):
        return valore
    return dt.date.fromisoformat(str(valore).strip()[:10])


def carica_config() -> dict:
    if not CONFIG.exists():
        sys.exit(f"Manca il file di configurazione: {CONFIG}")
    with CONFIG.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg["data_evento"] = a_data(cfg["data_evento"])
    return cfg


def data_limite(cfg: dict) -> dt.date | None:
    """Ultimo giorno di dati consentito. None = nessun limite.

    In modalita' cieca il limite e' il giorno prima dell'evento. La modalita'
    cieca si puo' spegnere solo dopo aver registrato le ipotesi su OSF.
    """
    if cfg.get("modalita_cieca", True):
        return cfg["data_evento"] - dt.timedelta(days=1)
    if not str(cfg.get("preregistrazione_osf") or "").strip():
        sys.exit(
            "Hai messo modalita_cieca: false senza registrare le ipotesi.\n"
            "Registra docs/preregistrazione.md su OSF, incolla il link in "
            "config/progetto.yaml (preregistrazione_osf) e riprova."
        )
    return None


def descrivi_modalita(cfg: dict) -> str:
    limite = data_limite(cfg)
    if limite is None:
        return f"Modalita' cieca: SPENTA (preregistrazione: {cfg.get('preregistrazione_osf')})"
    return f"Modalita' cieca: ATTIVA, dati fino al {limite.isoformat()} compreso"


_ACUTI = {"perche", "poiche", "affinche", "benche", "nonche", "ne", "se", "sicche", "finche"}


def accenti(testo: str) -> str:
    """Trasforma gli apostrofi usati al posto degli accenti (e', piu', perche') in lettere accentate.
    Non tocca gli apostrofi seguiti da una lettera (dell'evento) ne' "po'"."""
    import re

    def sostituisci(m: re.Match) -> str:
        parola, vocale = m.group(1), m.group(2)
        intera = (parola + vocale).lower()
        if intera == "po":
            return m.group(0)
        if vocale.lower() == "e" and intera in _ACUTI:
            nuova = "é" if vocale == "e" else "É"
        else:
            nuova = {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù",
                     "A": "À", "E": "È", "I": "Ì", "O": "Ò", "U": "Ù"}[vocale]
        return parola + nuova

    return re.sub(r"\b([A-Za-z]*?)([aeiouAEIOU])'(?![A-Za-zÀ-ÿ])", sostituisci, testo)
