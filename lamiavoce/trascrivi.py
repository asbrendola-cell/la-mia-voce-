"""Passo 2: trascrizione italiana con faster-whisper (modello large-v3)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from .audio import leggi_wav


def dispositivo() -> tuple[str, str]:
    """Usa la scheda video (CUDA) se c'è, altrimenti la CPU."""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda", "float16"
    except ImportError:
        pass
    return "cpu", "int8"


@lru_cache(maxsize=1)
def modello_whisper(nome: str = "large-v3"):
    from faster_whisper import WhisperModel

    device, compute_type = dispositivo()
    return WhisperModel(nome, device=device, compute_type=compute_type)


def trascrivi_array(audio16k: np.ndarray, lingua: str, modello: str = "large-v3") -> list[dict]:
    """Trascrive un array a 16 kHz.

    L'audio si passa come array numpy e non come file: con alcune versioni del
    pacchetto `av` faster-whisper fallisce leggendo i file (problema visto nelle prove).
    """
    segs, _info = modello_whisper(modello).transcribe(
        audio16k, language=lingua, vad_filter=True, beam_size=5
    )
    return [
        {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
        for s in segs
        if s.text.strip()
    ]


def trascrivi_file(wav16k: Path, uscita: Path, lingua: str = "it", modello: str = "large-v3") -> list[dict]:
    audio, sr = leggi_wav(wav16k)
    if sr != 16000:
        raise ValueError(f"{wav16k} deve essere a 16 kHz (trovato {sr})")
    frasi = trascrivi_array(audio, lingua, modello)
    uscita.write_text(json.dumps(frasi, ensure_ascii=False, indent=1), encoding="utf-8")
    return frasi
