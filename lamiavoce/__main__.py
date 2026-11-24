"""Comando unico.

    python -m lamiavoce prepara-voce video.mp4 --tratti 0-9.3 12.3-21.7 -o voce_walter.wav
    python -m lamiavoce doppia video.mp4 --voce voce_walter.wav --lingua es --lingua en

Ogni passo salva il suo risultato nella cartella di lavoro: se il programma si
interrompe, rilanciando lo stesso comando riparte da dove era arrivato. Il file
della traduzione (`traduzione_<lingua>.json`) si può correggere a mano: al giro
successivo viene usata la versione corretta.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from . import __version__


def durata_video(video: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def leggi_tratti(valori: list[str]) -> list[tuple[float, float]]:
    tratti = []
    for v in valori:
        a, b = v.replace(",", ".").split("-")
        tratti.append((float(a), float(b)))
    return tratti


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def cmd_prepara_voce(args) -> None:
    from .audio import durata, prepara_voce

    out = prepara_voce(Path(args.video), leggi_tratti(args.tratti), Path(args.uscita))
    log(f"Riferimento voce pronto: {out} ({durata(out):.1f} s). Consigliati 15-25 s di voce pulita.")


def cmd_doppia(args) -> None:
    from .audio import estrai_audio
    from .glossario import Glossario
    from .trascrivi import trascrivi_file

    video = Path(args.video).resolve()
    voce_rif = Path(args.voce).resolve()
    if not video.exists():
        sys.exit(f"Video non trovato: {video}")
    if not voce_rif.exists():
        sys.exit(f"Riferimento voce non trovato: {voce_rif} (crealo con 'prepara-voce')")

    lavoro = Path(args.cartella or (video.parent / f"lavoro_{video.stem}"))
    lavoro.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # Passo 1: audio a 16 kHz per Whisper
    audio16 = lavoro / "audio16.wav"
    if not audio16.exists():
        log("Passo 1: estraggo l'audio")
        estrai_audio(video, audio16, 16000)

    # Passo 2: trascrizione italiana
    it_json = lavoro / "trascrizione_it.json"
    if it_json.exists():
        frasi_it = json.loads(it_json.read_text(encoding="utf-8"))
    else:
        log("Passo 2: trascrivo in italiano con Whisper large-v3")
        frasi_it = trascrivi_file(audio16, it_json, "it", args.whisper)
    log(f"  {len(frasi_it)} frasi in italiano")

    for lingua in args.lingua:
        doppia_lingua(video, voce_rif, lavoro, frasi_it, lingua, args, Glossario.carica(lingua))

    log(f"Finito in {(time.time() - t0) / 60:.1f} minuti. Risultati in {lavoro}")


def doppia_lingua(video, voce_rif, lavoro, frasi_it, lingua, args, glossario) -> None:
    from .audio import durata
    from .montaggio import calcola_posizioni, monta
    from .sottotitoli import scrivi_srt, video_finale
    from .traduci import salva, scrivi_revisione, traduci_frasi
    from .trascrivi import trascrivi_array

    # Passo 3: traduzione (se il file esiste già si usa quello, anche se corretto a mano)
    tr_json = lavoro / f"traduzione_{lingua}.json"
    if tr_json.exists():
        frasi = json.loads(tr_json.read_text(encoding="utf-8"))
        log(f"[{lingua}] Passo 3: uso la traduzione già salvata ({tr_json.name})")
    else:
        log(f"[{lingua}] Passo 3: traduco con DeepL frase per frase")
        frasi = traduci_frasi(frasi_it, lingua, glossario)
        salva(frasi, tr_json)
    n = scrivi_revisione(frasi, lavoro / f"da_rivedere_{lingua}.txt")
    log(f"[{lingua}]   {n} frasi da rileggere: vedi da_rivedere_{lingua}.txt")

    srt_originale = scrivi_srt(
        [(f["start"], f["end"], f["text"]) for f in frasi], lavoro / f"sottotitoli_{lingua}_tempi_originali.srt"
    )
    if args.ferma_dopo_traduzione:
        log(f"[{lingua}] Mi fermo dopo la traduzione, come richiesto. Sottotitoli provvisori: {srt_originale.name}")
        log(f"[{lingua}] Correggi {tr_json.name} e rilancia lo stesso comando senza --ferma-dopo-traduzione.")
        return

    # Passo 4: voce clonata con controllo Whisper
    from .voce import ConvertitoreVoce, Voce

    cartella_tts = lavoro / f"voce_{lingua}"
    cartella_tts.mkdir(exist_ok=True)
    ascolta = lambda audio: " ".join(s["text"] for s in trascrivi_array(audio, lingua, args.whisper))
    esiti_file = lavoro / f"controllo_voce_{lingua}.json"
    esiti = json.loads(esiti_file.read_text(encoding="utf-8")) if esiti_file.exists() else {}
    voce = None
    for i, f in enumerate(frasi):
        out = cartella_tts / f"{i:04d}.wav"
        if out.exists() and str(i) in esiti:
            continue
        voce = voce or Voce(voce_rif, lingua)
        log(f"[{lingua}] Passo 4: frase {i + 1}/{len(frasi)}")
        e = voce.frase_controllata(i, f["text"], out, ascolta)
        esiti[str(i)] = {"seed": e.seed, "punteggio": round(e.punteggio, 3), "sentito": e.sentito}
        esiti_file.write_text(json.dumps(esiti, ensure_ascii=False, indent=1), encoding="utf-8")
    del voce

    # Passo 5: convertitore di voce
    file_frasi = [cartella_tts / f"{i:04d}.wav" for i in range(len(frasi))]
    if not args.senza_convertitore:
        cartella_vc = lavoro / f"voce_{lingua}_vc"
        cartella_vc.mkdir(exist_ok=True)
        vc = None
        nuovi = []
        for i, src in enumerate(file_frasi):
            out = cartella_vc / src.name
            if not out.exists():
                vc = vc or ConvertitoreVoce(voce_rif)
                log(f"[{lingua}] Passo 5: convertitore di voce {i + 1}/{len(frasi)}")
                vc.converti(src, out)
            nuovi.append(out)
        file_frasi = nuovi

    # Passo 6: montaggio a tempo
    log(f"[{lingua}] Passo 6: montaggio a tempo")
    durate = [durata(p) for p in file_frasi]
    tot = durata_video(video)
    posizioni = calcola_posizioni(frasi, durate, tot)
    cartella_mont = lavoro / f"montaggio_{lingua}"
    cartella_mont.mkdir(exist_ok=True)
    voce_finale = monta(file_frasi, posizioni, tot, lavoro / f"voce_{lingua}.wav", cartella_mont)

    # Passo 7: sottotitoli sui tempi della voce doppiata, e video finale
    srt = scrivi_srt(
        [(p.inizio, p.fine, f["text"]) for p, f in zip(posizioni, frasi)], lavoro / f"sottotitoli_{lingua}.srt"
    )
    log(f"[{lingua}] Passo 7: video finale")
    finale = video_finale(
        video, voce_finale, None if args.sottotitoli_separati else srt, lavoro / f"{video.stem}_{lingua}.mp4"
    )

    scrivi_rapporto(lavoro / f"rapporto_{lingua}.txt", frasi, esiti, posizioni)
    log(f"[{lingua}] Pronto: {finale}")


def scrivi_rapporto(percorso: Path, frasi, esiti, posizioni) -> None:
    from .voce import SOGLIA

    righe = ["Rapporto controlli", ""]
    for i, (f, p) in enumerate(zip(frasi, posizioni)):
        e = esiti.get(str(i), {})
        problemi = []
        if e and e["punteggio"] < SOGLIA:
            problemi.append(f"voce: parole giuste {e['punteggio']:.0%} (Whisper ha sentito: \"{e['sentito']}\")")
        if p.velocita > 1.0:
            problemi.append(f"accelerata {p.velocita:.2f}x")
        if p.sfora > 0:
            problemi.append(f"sfora di {p.sfora:.1f} s: accorciare la traduzione")
        if problemi:
            righe.append(f"#{i + 1} [{f['start']:.1f}s] {f['text']}")
            righe += [f"   - {x}" for x in problemi]
    if len(righe) == 2:
        righe.append("Tutte le frasi hanno passato i controlli.")
    percorso.write_text("\n".join(righe) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="lamiavoce", description="La mia Voce: doppiaggio dei video di Walter")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="comando", required=True)

    pv = sub.add_parser("prepara-voce", help="crea il riferimento voce da tratti puliti di un video")
    pv.add_argument("video")
    pv.add_argument("--tratti", nargs="+", required=True, help="es. 0-9.3 12.3-21.7 (secondi)")
    pv.add_argument("-o", "--uscita", default="voce_walter.wav")
    pv.set_defaults(func=cmd_prepara_voce)

    d = sub.add_parser("doppia", help="doppia un video (tutti i passi)")
    d.add_argument("video")
    d.add_argument("--voce", required=True, help="riferimento voce (da 'prepara-voce')")
    d.add_argument("--lingua", action="append", choices=["es", "en"], help="ripetibile; predefinito: es")
    d.add_argument("--cartella", help="cartella di lavoro (predefinita: lavoro_<nome video>)")
    d.add_argument("--whisper", default="large-v3", help="modello Whisper")
    d.add_argument("--ferma-dopo-traduzione", action="store_true", help="si ferma per la revisione del testo")
    d.add_argument("--senza-convertitore", action="store_true", help="salta Chatterbox VC")
    d.add_argument("--sottotitoli-separati", action="store_true", help="non imprime i sottotitoli nel video")
    d.set_defaults(func=cmd_doppia)

    args = p.parse_args(argv)
    if getattr(args, "lingua", None) is None and args.comando == "doppia":
        args.lingua = ["es"]
    args.func(args)


if __name__ == "__main__":
    main()
