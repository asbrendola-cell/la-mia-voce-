"""Passo 6: montaggio a tempo delle frasi doppiate.

Regole (versione 3):
1. ogni frase parte all'inizio della frase italiana;
2. se non ci sta prima della frase successiva, può partire prima, fino a 2 s
   in anticipo, ma mai sopra la frase doppiata precedente;
3. se ancora non ci sta si accelera con atempo, al massimo 1,1x;
4. se nemmeno così ci sta, la frase sfora (e spinge la successiva): finisce nel rapporto.
Poi il mix viene normalizzato con loudnorm I=-16, TP=-1.5.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .audio import ffmpeg, leggi_wav, scrivi_wav

ANTICIPO_MAX = 2.0
VELOCITA_MAX = 1.1


@dataclass
class Posizione:
    inizio: float
    velocita: float
    fine: float
    sfora: float  # secondi oltre lo spazio disponibile (0 se ci sta)


def calcola_posizioni(frasi: list[dict], durate: list[float], fine_video: float | None = None) -> list[Posizione]:
    """Decide dove mettere ogni frase e quanto accelerarla. Funzione pura (testabile)."""
    posizioni: list[Posizione] = []
    fine_precedente = 0.0
    for i, (f, d) in enumerate(zip(frasi, durate)):
        limite = frasi[i + 1]["start"] if i + 1 < len(frasi) else (fine_video or f["end"] + 3.0)
        inizio = max(f["start"], fine_precedente)
        spazio = limite - inizio
        if d > spazio:
            # Regola 2: anticipare solo quanto serve (al massimo 2 s),
            # senza sovrapporsi alla frase doppiata precedente.
            anticipo = min(ANTICIPO_MAX, d - spazio)
            inizio = max(min(inizio, f["start"] - anticipo), fine_precedente)
            spazio = limite - inizio
        velocita = 1.0
        if d > spazio > 0:
            velocita = min(VELOCITA_MAX, d / spazio)
        durata_finale = d / velocita
        sfora = max(0.0, inizio + durata_finale - limite)
        fine = inizio + durata_finale
        posizioni.append(Posizione(round(inizio, 3), round(velocita, 3), round(fine, 3), round(sfora, 3)))
        fine_precedente = fine
    return posizioni


def accelera(entrata: Path, uscita: Path, velocita: float) -> Path:
    if velocita <= 1.0001:
        ffmpeg("-i", str(entrata), str(uscita))
    else:
        ffmpeg("-i", str(entrata), "-filter:a", f"atempo={velocita:.4f}", str(uscita))
    return uscita


def monta(file_frasi: list[Path], posizioni: list[Posizione], durata_totale: float, uscita: Path, cartella: Path, sr: int = 24000) -> Path:
    """Mette ogni frase al suo posto su una traccia unica, poi normalizza il volume."""
    fine = max([durata_totale] + [p.fine for p in posizioni]) + 0.5
    traccia = np.zeros(int(fine * sr) + 1, dtype=np.float32)
    for i, (f, p) in enumerate(zip(file_frasi, posizioni)):
        veloce = accelera(f, cartella / f"tempo_{i:04d}.wav", p.velocita)
        tmp = cartella / f"tempo_{i:04d}_{sr}.wav"
        ffmpeg("-i", str(veloce), "-ac", "1", "-ar", str(sr), str(tmp))
        audio, _ = leggi_wav(tmp)
        a = int(p.inizio * sr)
        traccia[a : a + len(audio)] += audio[: len(traccia) - a]
    grezzo = scrivi_wav(cartella / "mix_grezzo.wav", traccia, sr)
    ffmpeg("-i", str(grezzo), "-af", "loudnorm=I=-16:TP=-1.5", "-ar", str(sr), str(uscita))
    return uscita
