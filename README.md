# La mia Voce

Programma per **doppiare in spagnolo e inglese, con sottotitoli**, i video pubblici e gratuiti di **Walter Biancalana**, con la voce di Walter.

È l'alternativa "fatta in casa" a Rask ed ElevenLabs: usa solo strumenti con licenza che permette anche l'uso commerciale.

| Passo | Strumento | Cosa fa |
| --- | --- | --- |
| 1 | ffmpeg | estrae l'audio dal video |
| 2 | Whisper large-v3 (faster-whisper) | trascrive l'italiano con i tempi di ogni frase |
| 3 | DeepL + glossario biblico | traduce frase per frase e corregge i versetti noti |
| 4 | Chatterbox Multilingual (licenza MIT) | rifà ogni frase con la voce di Walter; Whisper la riascolta e tiene la versione giusta |
| 5 | Chatterbox VC | avvicina ancora il timbro a quello di Walter |
| 6 | ffmpeg | rimette le frasi a tempo (accelerazione massima 1,1x) |
| 7 | ffmpeg | crea il video finale con voce nuova e sottotitoli |

## Cosa serve

1. Un computer con **scheda video NVIDIA** (per esempio una RTX 4090 noleggiata su RunPod). Funziona anche senza, ma è lentissimo: un video di 2 ore richiederebbe circa 12 ore.
2. Python 3.11 o più recente e **ffmpeg**.
3. Una **chiave DeepL** (account DeepL API).

## Installazione (una volta sola)

1. Scarica il programma:
   ```bash
   git clone https://github.com/asbrendola-cell/la-mia-voce-.git
   cd la-mia-voce-
   ```
2. Crea un ambiente Python separato e installa i pacchetti:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Prepara la chiave DeepL:
   ```bash
   cp .env.example .env
   nano .env        # scrivi la chiave al posto di "metti-qui-la-chiave-deepl"
   set -a; source .env; set +a
   ```
   **Chiave DeepL:** non va mai scritta nel codice né caricata su GitHub. Il file `.env` è già escluso.
4. Controlla che tutto funzioni (pochi secondi, non usa i modelli):
   ```bash
   python -m pytest -q
   ```

La prima volta il programma scarica i modelli (Whisper e Chatterbox, qualche GB).

## Uso

### 1. Prepara il riferimento voce (una volta sola)

Scegli 15-25 secondi in cui parla solo Walter, senza musica né rumori. Nelle prove sono serviti i tratti 0-9,3 s e 12,3-21,7 s del primo video:

```bash
python -m lamiavoce prepara-voce video_walter.mp4 --tratti 0-9.3 12.3-21.7 -o voce_walter.wav
```

### 2. Doppia un video

```bash
python -m lamiavoce doppia predica.mp4 --voce voce_walter.wav --lingua es
```

Per spagnolo e inglese insieme: `--lingua es --lingua en`.

### 3. Modo consigliato: con revisione della traduzione

La traduzione va sempre riletta, soprattutto i versetti.

1. Fermati dopo la traduzione:
   ```bash
   python -m lamiavoce doppia predica.mp4 --voce voce_walter.wav --lingua es --ferma-dopo-traduzione
   ```
2. Apri `lavoro_predica/da_rivedere_es.txt`: elenca solo le frasi segnalate (versetti, "vosotros", frasi troppo lunghe...).
3. Correggi quelle frasi in `lavoro_predica/traduzione_es.json` (campo `"text"`).
4. Rilancia lo stesso comando **senza** `--ferma-dopo-traduzione`: il programma usa la tua versione corretta.

Se il programma si interrompe, rilancia lo stesso comando: riparte da dove era arrivato.

### Opzioni

| Opzione | A cosa serve |
| --- | --- |
| `--lingua es` / `--lingua en` | lingua di arrivo (ripetibile) |
| `--ferma-dopo-traduzione` | si ferma per la revisione del testo |
| `--senza-convertitore` | salta il passo 5 (più veloce, voce un po' meno simile) |
| `--sottotitoli-separati` | non imprime i sottotitoli nel video: restano nel file `.srt` |
| `--cartella` | sceglie la cartella di lavoro |

## Cosa trovi nella cartella di lavoro

| File | Contenuto |
| --- | --- |
| `predica_es.mp4` | **video finale** doppiato con sottotitoli |
| `sottotitoli_es.srt` | sottotitoli sui tempi della voce doppiata |
| `trascrizione_it.json` | testo italiano con i tempi |
| `traduzione_es.json` | traduzione (si può correggere a mano) |
| `da_rivedere_es.txt` | frasi da rileggere e correzioni fatte dal glossario |
| `rapporto_es.txt` | frasi con voce incerta, accelerate o troppo lunghe |
| `voce_es.wav` | solo la voce doppiata |

## Il glossario biblico

Nella cartella `glossario/` c'è un file per lingua:

- `es.json`: versetti nella **Reina-Valera 1960** (per esempio Romani 3,23 → "están destituidos de la gloria de Dios"), spagnolo latinoamericano con "ustedes".
- `en.json`: la Bibbia inglese di riferimento **non è ancora scelta** (KJV o NIV), quindi per ora segnala soltanto le citazioni da controllare.

Ogni errore trovato in revisione va aggiunto al glossario, così non si ripete:
- `"sostituzioni"`: correzioni automatiche (`"da"` → `"a"`, con la fonte);
- `"segnala"`: parole che fanno finire la frase in `da_rivedere`.

## Regole imparate nelle prove

1. DeepL traduce **una frase alla volta** e **senza contesto lungo**: con il contesto "predicazione, versetti" aveva inventato versetti mai detti.
2. Ogni frase viene generata con i seed 5, 11 e 23; si tiene la prima che Whisper riconosce per almeno il 97%.
3. Accelerazione massima 1,1x; una frase può partire fino a 2 secondi prima, mai sopra la precedente.
4. Ambiente: `HF_HUB_DISABLE_XET=1` per scaricare i modelli; `setuptools<81` per il watermark di Chatterbox.

## Limiti noti

1. La voce è ancora meno naturale di Rask (prossimo passo: addestrare Chatterbox sulle ore di video di Walter).
2. Il labiale non è sincronizzato.
3. I tempi e i costi su scheda video vanno ancora misurati su video veri.

## Consenso

Walter ha dato l'ok a voce; il consenso scritto è da firmare come tutela. Il programma va usato solo con la voce di Walter e solo per i suoi video.
