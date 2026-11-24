"""Passi 4 e 5: voce clonata (Chatterbox Multilingual) con controllo Whisper, poi convertitore di voce.

Per ogni frase si provano i seed 5, 11 e 23: Whisper riascolta l'audio nella lingua
di arrivo e si tiene la prima versione con almeno il 97% delle parole giuste.
Se nessuna arriva al 97% si tiene la migliore e la frase finisce nel rapporto.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .audio import leggi_wav, ricampiona, scrivi_wav

SEED = (5, 11, 23)
SOGLIA = 0.97
PARAMETRI = {"exaggeration": 0.5, "cfg_weight": 0.5, "temperature": 0.7}


def normalizza(testo: str) -> list[str]:
    """Parole in minuscolo, senza punteggiatura e senza accenti (per il confronto)."""
    testo = unicodedata.normalize("NFKD", testo.lower())
    testo = "".join(c for c in testo if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9ñ]+", testo)


def somiglianza(atteso: str, sentito: str) -> float:
    """Quota di parole attese ritrovate, nell'ordine giusto, in ciò che Whisper ha sentito."""
    a, b = normalizza(atteso), normalizza(sentito)
    if not a:
        return 1.0
    blocchi = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_matching_blocks()
    giuste = sum(bl.size for bl in blocchi)
    # Penalizza anche le parole in più (frasi ripetute o inventate dalla voce).
    extra = max(0, len(b) - len(a))
    return max(0.0, (giuste - extra) / len(a))


@dataclass
class EsitoFrase:
    indice: int
    seed: int
    punteggio: float
    sentito: str
    file: Path


class Voce:
    def __init__(self, riferimento: Path, lingua: str):
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.modello = ChatterboxMultilingualTTS.from_pretrained(device=self.device)
        self.riferimento = str(riferimento)
        self.lingua = lingua

    def genera(self, testo: str, seed: int) -> tuple[np.ndarray, int]:
        self.torch.manual_seed(seed)
        wav = self.modello.generate(
            testo, language_id=self.lingua, audio_prompt_path=self.riferimento, **PARAMETRI
        )
        return wav.squeeze().detach().cpu().numpy(), self.modello.sr

    def frase_controllata(self, indice: int, testo: str, uscita: Path, ascolta) -> EsitoFrase:
        """Genera con i diversi seed e tiene la prima versione sopra soglia (o la migliore)."""
        migliore: EsitoFrase | None = None
        migliore_audio = None
        for seed in SEED:
            audio, sr = self.genera(testo, seed)
            sentito = ascolta(ricampiona(audio, sr, 16000))
            punteggio = somiglianza(testo, sentito)
            if migliore is None or punteggio > migliore.punteggio:
                migliore = EsitoFrase(indice, seed, punteggio, sentito, uscita)
                migliore_audio = (audio, sr)
            if punteggio >= SOGLIA:
                break
        scrivi_wav(uscita, *migliore_audio)
        return migliore


class ConvertitoreVoce:
    """Chatterbox VC: avvicina il timbro della frase generata a quello di Walter."""

    def __init__(self, riferimento: Path):
        import torch
        from chatterbox.vc import ChatterboxVC

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.vc = ChatterboxVC.from_pretrained(device=self.device)
        self.riferimento = str(riferimento)

    def converti(self, entrata: Path, uscita: Path) -> Path:
        wav = self.vc.generate(str(entrata), target_voice_path=self.riferimento)
        return scrivi_wav(uscita, wav.squeeze().detach().cpu().numpy(), self.vc.sr)


def durata_wav(percorso: Path) -> float:
    a, sr = leggi_wav(percorso)
    return len(a) / sr
