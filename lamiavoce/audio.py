"""Funzioni audio: estrazione con ffmpeg, lettura e scrittura di file WAV."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np


def ffmpeg(*args: str) -> None:
    """Esegue ffmpeg in modo silenzioso; solleva un errore leggibile se fallisce."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg non riuscito:\n{' '.join(cmd)}\n{res.stderr}")


def estrai_audio(video: Path, uscita: Path, sr: int) -> Path:
    """Estrae l'audio mono del video alla frequenza indicata (16 kHz per Whisper)."""
    ffmpeg("-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), str(uscita))
    return uscita


def prepara_voce(video: Path, tratti: list[tuple[float, float]], uscita: Path) -> Path:
    """Crea il riferimento voce: unisce i tratti puliti di Walter, filtra e normalizza.

    Come nella prova v3: highpass 70 Hz, loudnorm I=-18, 24 kHz mono.
    """
    parti = []
    for i, (a, b) in enumerate(tratti):
        parti.append(f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[p{i}]")
    concat = "".join(f"[p{i}]" for i in range(len(tratti)))
    filtro = ";".join(parti) + f";{concat}concat=n={len(tratti)}:v=0:a=1,highpass=f=70,loudnorm=I=-18[out]"
    ffmpeg("-i", str(video), "-filter_complex", filtro, "-map", "[out]", "-ac", "1", "-ar", "24000", str(uscita))
    return uscita


def leggi_wav(percorso: Path) -> tuple[np.ndarray, int]:
    """Legge un WAV PCM 16 bit mono e restituisce (campioni float32 in [-1, 1], frequenza)."""
    with wave.open(str(percorso)) as w:
        sr = w.getframerate()
        canali = w.getnchannels()
        dati = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if canali > 1:
        dati = dati.reshape(-1, canali).mean(axis=1)
    return dati, sr


def scrivi_wav(percorso: Path, campioni: np.ndarray, sr: int) -> Path:
    """Scrive campioni float in un WAV PCM 16 bit mono."""
    campioni = np.clip(np.asarray(campioni, dtype=np.float32).reshape(-1), -1.0, 1.0)
    with wave.open(str(percorso), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((campioni * 32767).astype(np.int16).tobytes())
    return percorso


def ricampiona(campioni: np.ndarray, sr_da: int, sr_a: int) -> np.ndarray:
    """Ricampionamento lineare semplice (basta per far riascoltare la frase a Whisper)."""
    if sr_da == sr_a or len(campioni) == 0:
        return campioni.astype(np.float32)
    n = int(round(len(campioni) * sr_a / sr_da))
    x_vecchio = np.linspace(0, 1, num=len(campioni), endpoint=False)
    x_nuovo = np.linspace(0, 1, num=n, endpoint=False)
    return np.interp(x_nuovo, x_vecchio, campioni).astype(np.float32)


def durata(percorso: Path) -> float:
    campioni, sr = leggi_wav(percorso)
    return len(campioni) / sr
