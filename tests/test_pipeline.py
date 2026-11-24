"""Test delle parti che non richiedono i modelli (girano in pochi secondi, anche senza scheda video)."""

import shutil

import numpy as np
import pytest

from lamiavoce.__main__ import leggi_tratti, scrivi_rapporto
from lamiavoce.audio import leggi_wav, ricampiona, scrivi_wav
from lamiavoce.glossario import Glossario
from lamiavoce.montaggio import ANTICIPO_MAX, VELOCITA_MAX, calcola_posizioni, monta
from lamiavoce.sottotitoli import scrivi_srt, tempo_srt
from lamiavoce.traduci import scrivi_revisione, traduci_frasi
from lamiavoce.voce import normalizza, somiglianza

# ---------- glossario ----------


def test_glossario_corregge_romani_3_23():
    g = Glossario.carica("es")
    testo, modifiche = g.applica("Porque todos pecaron y carecen de la gloria de Dios.")
    assert "están destituidos de la gloria de Dios" in testo
    assert modifiche


def test_glossario_mantiene_maiuscola():
    g = Glossario.carica("es")
    testo, _ = g.applica("Gloria y honor a Él.")
    assert testo.startswith("Gloria y honra")


def test_glossario_segnala_vosotros_ma_non_parole_simili():
    g = Glossario.carica("es")
    assert g.avvisi("Vosotros sois la sal de la tierra")
    assert not g.avvisi("Ustedes son la sal de la tierra")
    assert not g.avvisi("Los osos comen miel")  # "os" solo come parola intera


def test_glossario_lingua_mancante_vuoto():
    g = Glossario.carica("xx")
    assert g.applica("ciao") == ("ciao", [])


# ---------- traduzione (DeepL finto) ----------


def test_traduzione_frase_per_frase_e_revisione(tmp_path):
    frasi = [
        {"start": 0.0, "end": 3.0, "text": "Tutti hanno peccato"},
        {"start": 3.0, "end": 4.0, "text": "Voi siete"},
    ]
    finto = {
        "Tutti hanno peccato": "Todos pecaron y carecen de la gloria de Dios",
        "Voi siete": "Vosotros sois",
    }
    chiamate = []

    def tradurre(t):
        chiamate.append(t)
        return finto[t]

    out = traduci_frasi(frasi, "es", Glossario.carica("es"), tradurre)
    assert chiamate == ["Tutti hanno peccato", "Voi siete"]  # una chiamata per frase
    assert "destituidos" in out[0]["text"]
    assert out[1]["avvisi"]
    n = scrivi_revisione(out, tmp_path / "rev.txt")
    assert n >= 1
    assert "DA RIVEDERE" in (tmp_path / "rev.txt").read_text(encoding="utf-8")


# ---------- controllo voce ----------


def test_somiglianza():
    assert somiglianza("Romanos 3,23 dice", "romanos 3 23 dice") == 1.0
    assert somiglianza("están destituidos de la gloria", "están destituidos de la gloria") == 1.0
    assert somiglianza("uno dos tres cuatro", "uno dos") == 0.5
    # parole in più (voce che ripete) abbassano il punteggio
    assert somiglianza("uno dos", "uno dos uno dos") < 0.97
    assert normalizza("¡Señor, está aquí!") == ["senor", "esta", "aqui"]


# ---------- montaggio ----------


def _frasi(*tempi):
    return [{"start": a, "end": b, "text": "x"} for a, b in tempi]


def test_frase_che_ci_sta_parte_in_orario():
    p = calcola_posizioni(_frasi((1, 3), (5, 7)), [1.5, 1.5], 10)
    assert p[0].inizio == 1 and p[0].velocita == 1.0 and p[0].sfora == 0


def test_frase_lunga_anticipa_al_massimo_2_secondi():
    # spazio originale 4 s (5->9), frase da 5 s: anticipa di 1 s, nessuna accelerazione
    p = calcola_posizioni(_frasi((0, 1), (5, 8), (9, 10)), [0.5, 5.0, 0.5], 12)
    assert p[1].inizio == 4.0 and p[1].velocita == 1.0
    # anticipo mai oltre 2 s
    p = calcola_posizioni(_frasi((5, 8), (9, 10)), [10.0, 0.5], 12)
    assert p[0].inizio == 5 - ANTICIPO_MAX


def test_non_si_sovrappone_alla_frase_precedente():
    p = calcola_posizioni(_frasi((0, 2), (2.5, 4), (5, 6)), [2.4, 2.6, 0.5], 8)
    assert p[1].inizio >= p[0].fine


def test_accelerazione_massima_1_1():
    p = calcola_posizioni(_frasi((0, 2), (2, 4)), [2.5, 0.5], 6)
    assert p[0].velocita == VELOCITA_MAX
    assert p[0].sfora > 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="serve ffmpeg")
def test_monta_crea_traccia(tmp_path):
    sr = 24000
    t = np.arange(int(0.5 * sr)) / sr
    a = scrivi_wav(tmp_path / "a.wav", 0.3 * np.sin(2 * np.pi * 220 * t), sr)
    b = scrivi_wav(tmp_path / "b.wav", 0.3 * np.sin(2 * np.pi * 330 * t), sr)
    pos = calcola_posizioni(_frasi((0, 1), (1, 2)), [0.5, 0.5], 3)
    out = monta([a, b], pos, 3.0, tmp_path / "voce.wav", tmp_path)
    audio, sr2 = leggi_wav(out)
    assert sr2 == sr and len(audio) / sr >= 3.0


# ---------- varie ----------


def test_srt(tmp_path):
    assert tempo_srt(3723.456) == "01:02:03,456"
    p = scrivi_srt([(0, 1.5, "Hola"), (2, 3, "Adiós")], tmp_path / "x.srt")
    testo = p.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:01,500\nHola" in testo


def test_tratti():
    assert leggi_tratti(["0-9.3", "12,3-21,7"]) == [(0.0, 9.3), (12.3, 21.7)]


def test_ricampiona_e_wav(tmp_path):
    x = np.zeros(24000, dtype=np.float32)
    assert len(ricampiona(x, 24000, 16000)) == 16000
    scrivi_wav(tmp_path / "z.wav", x, 24000)
    y, sr = leggi_wav(tmp_path / "z.wav")
    assert sr == 24000 and len(y) == 24000


def test_rapporto(tmp_path):
    pos = calcola_posizioni(_frasi((0, 2), (2, 4)), [2.5, 0.5], 6)
    esiti = {"0": {"seed": 23, "punteggio": 0.9, "sentito": "x"}, "1": {"seed": 5, "punteggio": 1.0, "sentito": "x"}}
    scrivi_rapporto(tmp_path / "r.txt", _frasi((0, 2), (2, 4)), esiti, pos)
    r = (tmp_path / "r.txt").read_text(encoding="utf-8")
    assert "90%" in r and "accelerata" in r and "#2" not in r
