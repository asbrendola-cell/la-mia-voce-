"""Glossario biblico: correzioni automatiche dopo DeepL e segnalazioni per la revisione.

Ogni lingua ha un file `glossario/<lingua>.json` con:
- "sostituzioni": coppie {"da", "a"} applicate in automatico (es. versetti Reina-Valera 1960);
- "segnala": parole o espressioni che rendono una frase "da rivedere" (es. "vosotros");
- "note": promemoria per chi rivede.
Il glossario cresce con le correzioni: ogni errore trovato a mano va aggiunto qui.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CARTELLA_GLOSSARI = Path(__file__).resolve().parent.parent / "glossario"


@dataclass
class Glossario:
    lingua: str
    sostituzioni: list[dict] = field(default_factory=list)
    segnala: list[dict] = field(default_factory=list)
    note: list[str] = field(default_factory=list)

    @classmethod
    def carica(cls, lingua: str, cartella: Path = CARTELLA_GLOSSARI) -> "Glossario":
        percorso = cartella / f"{lingua}.json"
        if not percorso.exists():
            return cls(lingua)
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        return cls(
            lingua,
            dati.get("sostituzioni", []),
            dati.get("segnala", []),
            dati.get("note", []),
        )

    def applica(self, testo: str) -> tuple[str, list[str]]:
        """Applica le sostituzioni (senza distinguere maiuscole). Restituisce testo e modifiche fatte."""
        modifiche = []
        for s in self.sostituzioni:
            schema = re.compile(re.escape(s["da"]), re.IGNORECASE)
            if schema.search(testo):
                testo = schema.sub(lambda m, a=s["a"]: _stessa_maiuscola(m.group(0), a), testo)
                modifiche.append(f'"{s["da"]}" -> "{s["a"]}"')
        return testo, modifiche

    def avvisi(self, testo: str) -> list[str]:
        """Elenca i motivi per cui la frase va riletta."""
        motivi = []
        for s in self.segnala:
            if re.search(rf"(?<!\w){re.escape(s['parola'])}(?!\w)", testo, re.IGNORECASE):
                motivi.append(s.get("motivo", f'contiene "{s["parola"]}"'))
        return motivi


def _stessa_maiuscola(originale: str, nuovo: str) -> str:
    if originale[:1].isupper() and nuovo[:1].islower():
        return nuovo[:1].upper() + nuovo[1:]
    return nuovo
