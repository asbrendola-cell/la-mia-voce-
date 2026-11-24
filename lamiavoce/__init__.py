"""La mia Voce: doppiaggio dei video di Walter Biancalana in spagnolo e inglese.

Flusso: video -> audio -> trascrizione (Whisper) -> traduzione (DeepL + glossario)
-> voce clonata (Chatterbox Multilingual, con controllo Whisper) -> convertitore di voce
(Chatterbox VC) -> montaggio a tempo -> video con sottotitoli (ffmpeg).
"""

__version__ = "0.3.0"
