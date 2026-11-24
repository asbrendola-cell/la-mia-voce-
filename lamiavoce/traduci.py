"""Passo 3: traduzione con DeepL, frase per frase, più glossario biblico.

Regole imparate nelle prove (dossier, sezione 2):
- un testo per frase, così i tempi restano allineati;
- NIENTE campo "context" lungo: con un contesto tipo "predicazione, versetti"
  DeepL ha inventato versetti interi mai detti da Walter;
- registro informale (formality "less"), spagnolo con "ustedes";
- dopo DeepL serve sempre una revisione: il glossario corregge i versetti noti
  e segnala le frasi da rileggere nel file `da_rivedere_<lingua>.txt`.

La chiave DeepL si legge SOLO dalla variabile d'ambiente DEEPL_AUTH_KEY.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .glossario import Glossario

# Codici DeepL per le lingue di arrivo.
CODICI_DEEPL = {"es": "ES", "en": "EN-US"}

# Velocità tipica del parlato, usata per stimare se una frase tradotta è troppo lunga.
SILLABE_AL_SECONDO = {"es": 7.0, "en": 5.5}


def traduttore():
    chiave = os.environ.get("DEEPL_AUTH_KEY")
    if not chiave:
        raise SystemExit(
            "Manca la chiave DeepL. Imposta la variabile d'ambiente DEEPL_AUTH_KEY "
            "(vedi README, sezione 'Chiave DeepL'). Non scriverla mai nel codice."
        )
    import deepl

    return deepl.DeepLClient(chiave)


def traduci_frasi(frasi: list[dict], lingua: str, glossario: Glossario, tradurre=None) -> list[dict]:
    """Traduce ogni frase separatamente e applica il glossario.

    `tradurre` permette di passare una funzione finta nei test.
    """
    if tradurre is None:
        t = traduttore()
        codice = CODICI_DEEPL[lingua]

        def tradurre(testo: str) -> str:
            r = t.translate_text(
                testo, source_lang="IT", target_lang=codice, formality="prefer_less"
            )
            return r.text

    risultato = []
    for f in frasi:
        tradotto = tradurre(f["text"]).strip()
        corretto, modifiche = glossario.applica(tradotto)
        avvisi = glossario.avvisi(corretto)
        if troppo_lunga(corretto, f["end"] - f["start"], lingua):
            avvisi.append("più lunga della frase italiana: valutare se accorciarla (isocronia)")
        risultato.append(
            {
                "start": f["start"],
                "end": f["end"],
                "it": f["text"],
                "text": corretto,
                "glossario": modifiche,
                "avvisi": avvisi,
            }
        )
    return risultato


def conta_sillabe(testo: str) -> int:
    """Stima grossolana: gruppi di vocali consecutive."""
    import re

    return max(1, len(re.findall(r"[aeiouyáéíóúü]+", testo.lower())))


def troppo_lunga(testo: str, durata_it: float, lingua: str) -> bool:
    stimata = conta_sillabe(testo) / SILLABE_AL_SECONDO.get(lingua, 6.0)
    return durata_it > 0 and stimata > durata_it * 1.1


def scrivi_revisione(frasi: list[dict], percorso: Path) -> int:
    """Scrive il file per la revisione umana. Restituisce quante frasi vanno rilette."""
    righe = []
    n = 0
    for i, f in enumerate(frasi, 1):
        if f["avvisi"] or f["glossario"]:
            n += bool(f["avvisi"])
            righe.append(f"#{i}  [{f['start']:.1f}s - {f['end']:.1f}s]")
            righe.append(f"  IT: {f['it']}")
            righe.append(f"  TR: {f['text']}")
            for m in f["glossario"]:
                righe.append(f"  corretto dal glossario: {m}")
            for a in f["avvisi"]:
                righe.append(f"  DA RIVEDERE: {a}")
            righe.append("")
    if not righe:
        righe = ["Nessuna frase segnalata."]
    percorso.write_text("\n".join(righe), encoding="utf-8")
    return n


def salva(frasi: list[dict], percorso: Path) -> None:
    percorso.write_text(json.dumps(frasi, ensure_ascii=False, indent=1), encoding="utf-8")
