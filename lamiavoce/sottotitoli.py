"""Passo 7: sottotitoli SRT e video finale con ffmpeg."""

from __future__ import annotations

from pathlib import Path

from .audio import ffmpeg

STILE = "FontName=DejaVu Sans,FontSize=16,Outline=2,Bold=1,MarginV=22"


def tempo_srt(secondi: float) -> str:
    ms = int(round(secondi * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def scrivi_srt(voci: list[tuple[float, float, str]], percorso: Path) -> Path:
    blocchi = []
    for i, (a, b, testo) in enumerate(voci, 1):
        blocchi.append(f"{i}\n{tempo_srt(a)} --> {tempo_srt(b)}\n{testo.strip()}\n")
    percorso.write_text("\n".join(blocchi), encoding="utf-8")
    return percorso


def _percorso_filtro(p: Path) -> str:
    """Il filtro subtitles di ffmpeg vuole i caratteri speciali protetti."""
    return str(p.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def video_finale(video: Path, voce: Path, srt: Path | None, uscita: Path) -> Path:
    """Unisce il video originale, la voce doppiata e (se dati) i sottotitoli impressi."""
    args = ["-i", str(video), "-i", str(voce)]
    if srt is not None:
        args += ["-vf", f"subtitles='{_percorso_filtro(srt)}':force_style='{STILE}'"]
        args += ["-c:v", "libx264", "-crf", "20"]
    else:
        args += ["-c:v", "copy"]
    args += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "160k", "-shortest", str(uscita)]
    ffmpeg(*args)
    return uscita
