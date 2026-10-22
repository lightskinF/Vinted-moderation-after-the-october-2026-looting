# VintedScope

Studio indipendente e preregistrato sulla moderazione di Vinted dopo i saccheggi del 17-18 ottobre 2026 in Francia e a Milano.
Misura come sono cambiati i provvedimenti di Vinted nell'UE usando le dichiarazioni di motivazione pubbliche del DSA Transparency Database (Vinted UAB), e studia con un questionario i casi di blocco e un gruppo di controllo.
Non ricostruisce l'algoritmo e non stima il tasso di errore dell'intera piattaforma. Non usa dati interni di Vinted.

- **Preregistrazione (OSF):** https://osf.io/4grmp (DOI 10.17605/OSF.IO/4GRMP), registrata il 22 ottobre 2026
- **Autore:** Fabio Greco
- **Stato:** ipotesi, finestre, distribuzione placebo e soglie fissate prima di guardare i dati dal 17 ottobre 2026 (con un'eccezione dichiarata nella sezione 2 della preregistrazione). I dati dell'evento si scaricano dal 2 novembre 2026; l'analisi definitiva usa i file fino al 15 novembre e si fa dal 16 novembre (vedi `docs/registro_modifiche.md`).

## Cosa è stato registrato

Il documento registrato è `docs/preregistrazione.pdf` (stesso testo in `docs/preregistrazione.md`). Contiene domanda di ricerca, ipotesi (H1, H2a, H2b, H3 sul database; H4, H5 sui casi), distribuzione placebo, soglie, regole di decisione e calcolo della numerosità dei casi.
Il codice che produce i risultati preregistrati ha queste impronte SHA-256, scritte anche nella preregistrazione:

| File | SHA-256 |
| --- | --- |
| `src/analisi/placebo.py` | `5b8d19f3a6104222f543e8c97e75a4c32040271df5de5ed0c8ffb9e4ce3f9804` |
| `src/tdb/qualita.py` | `706fd910d5d43947cc47a1a6fd6ba958a8cf3f110683eaac22f4aaa4b4da5180` |
| `src/comune.py` | `dcf41d95ef16417de70f454b7e0a1a558f9a6257b750145f9838d09faefc4a60` |

Se una di queste impronte cambia, il codice non è più quello registrato. Lo stato completo di tutti i file al momento della registrazione è il tag `prereg-v1`. Ogni modifica e ogni imprecisione nota dei file allegati è elencata, con data e motivo, in `docs/registro_modifiche.md`.

## Struttura

```
VintedScope/
├── README.md
├── LICENSE                 MIT (codice)
├── LICENSE-DOCS.md         CC BY 4.0 (documenti e rapporti)
├── CITATION.cff            come citare il progetto
├── requirements.txt        librerie Python
├── config/progetto.yaml    date chiave, nome piattaforma, link OSF
├── docs/
│   ├── preregistrazione.pdf / .md   piano registrato su OSF
│   ├── registro_modifiche.md   modifiche e note successive alla registrazione
│   └── codebook_casi.md        variabili e regole per i casi documentati
├── src/
│   ├── comune.py           funzioni condivise
│   ├── tdb/                scarica_diretto.py, carica.py, qualita.py (database UE);
│   │                       scarica.py è la vecchia versione con dsa-tdb, non usata
│   ├── analisi/placebo.py  distribuzione placebo e test delle ipotesi
│   ├── sim/tasso_base.py   simulazione del tasso base
│   └── casi/               modello_casi.csv (intestazioni del foglio dei casi),
│                           analisi_casi.py (numerosità, H4, H5)
├── data/                   dati (non pubblicati)
└── reports/                rapporti e grafici generati
```

I dati scaricati e i casi raccolti non sono nel repository: `data/` è escluso perché contiene file pesanti e, per i casi, dati personali.

## Come riprodurre

### Installazione su Windows (una volta sola)

1. Installa **Python 3.11 o 3.12** da python.org e spunta **"Add python.exe to PATH"**.
2. Apri il **Prompt dei comandi** nella cartella del progetto e crea l'ambiente virtuale:
   ```
   py -3.11 -m venv .venv
   .venv\Scripts\activate.bat
   python -m pip install -r requirements.txt
   ```
   Se compare `CERTIFICATE_VERIFY_FAILED` (antivirus o proxy che sostituiscono i certificati), prima esegui
   `python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org pip-system-certs truststore`.

Il pacchetto ufficiale `dsa-tdb` non serve (richiede PySpark e Java): i file si scaricano direttamente dal sito con `scarica_diretto.py`.

### Pipeline

1. **Controllo dell'elenco dei file** (non scarica nulla):
   `python src/tdb/scarica_diretto.py --prova`
2. **Download** dello storico usato per la preregistrazione (dal 1 luglio 2025 al 16 ottobre 2026) e della finestra dell'evento. Ogni giorno è uno ZIP di circa 10-12 MB; servono circa 15 GB liberi. Si può rilanciare dopo un'interruzione: salta i file già scaricati e integri (checksum SHA1).
   `python src/tdb/scarica_diretto.py --da 2025-07-01 --a 2026-10-16`
   `python src/tdb/scarica_diretto.py --da 2026-10-17 --a 2026-11-15`

   I file fino al 15 novembre servono per due motivi: la validità di ogni giorno si giudica sulla mediana dei 29 giorni attorno (per il 31 ottobre, fino al 14 novembre), e alcune decisioni arrivano al database il giorno dopo. Dal 2 novembre i dati si possono già scaricare e guardare in forma descrittiva.

   Da dicembre, per il periodo "Dopo" (solo descrittivo) e per il controllo dei cambi strutturali fino al 30 novembre:
   `python src/tdb/scarica_diretto.py --da 2026-11-16 --a 2026-12-01`
3. **Caricamento e qualità**: converte ogni ZIP in Parquet senza estrarre i CSV e produce `reports/qualita_tdb.md` con i grafici.
   `python src/tdb/carica.py` e poi `python src/tdb/qualita.py`
4. **Analisi preregistrata** (distribuzione placebo e, dal 16 novembre, l'evento):
   `python src/analisi/placebo.py` e poi `python src/analisi/placebo.py --evento`
5. **Sensibilità del tasso base** (scenari ipotetici, non stime su Vinted):
   `python src/sim/tasso_base.py`
6. **Casi e controlli** (foglio compilato in `data/casi/casi.csv`, vedi `docs/codebook_casi.md`):
   `python src/casi/analisi_casi.py --numerosita` quando ci sono 30 controlli validi (legge solo i controlli); poi, registrata la numerosità, `python src/casi/analisi_casi.py`

Ogni esecuzione riscrive i file in `reports/`. Le versioni allegate alla preregistrazione restano su OSF e nel tag `prereg-v1` di questo repository.

Piano B se `scarica_diretto.py` non funziona: scarica a mano i file **full** (non light) di Vinted UAB da https://transparency.dsa.ec.europa.eu/explore-data/download, mettili in `data/raw/tdb/manuale/` e lancia `python src/tdb/carica.py`.

## Modalità cieca

Fino alla preregistrazione, in `config/progetto.yaml` c'era `modalita_cieca: true` e gli script non scaricavano né caricavano dati dal 17 ottobre 2026 in poi. Per spegnerla serve il link della preregistrazione: senza, `comune.py` si ferma con un errore. Dal 22 ottobre 2026 il link è inserito e la modalità cieca è `false`. Questa regola è la garanzia verificabile che le ipotesi non sono state adattate ai risultati.

## Regole

- Niente account finti, annunci esca, intercettazione dell'app o aggiramento di limiti.
- Niente raccolta automatica massiva da Vinted.
- Niente username o accuse a singoli nei materiali pubblicati.
- Niente soglie operative ("sotto N articoli sei al sicuro") nei risultati.
- `data/` non va mai su GitHub.

## Licenza e citazione

Codice con licenza MIT (vedi `LICENSE`). Documenti e rapporti, come la preregistrazione su OSF, con licenza CC BY 4.0 (vedi `LICENSE-DOCS.md`). Per citare il progetto usa `CITATION.cff` o il DOI 10.17605/OSF.IO/4GRMP.
