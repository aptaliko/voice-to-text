# Υπαγόρευση Συμβολαίων: voice & scan to Word

A small self-hosted web app for drafting Greek property-sale contracts:

- **Dictate**: record in the browser (laptop or phone) or upload an audio file, and it is transcribed with [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
- **Scan**: upload PDFs, scanned pages or phone photos, and the text is extracted with Tesseract (Greek + English). PDFs that already contain text skip OCR.
- **Edit & export**: fix the text in the browser and download it as a `.docx`.

Everything runs on your own server. No audio or document leaves it, and no external API is called.
The only outbound connections are one-time model downloads: Whisper (~1.6 GB) on the first transcription and, if you enable it, the AI correction model.

## Dictation tips

- Dictate in chunks (one clause per recording). Each result is appended to the text in order.
- A pause of 2.5 s or more starts a new paragraph.
- Add recurring names and terms (notaries, areas, standard phrases) to `WHISPER_PROMPT` in `.env` to improve spelling.

### Voice commands for symbols

Say the word and it is replaced by the symbol. The full list is under «Φωνητικές εντολές» in the page.

| Say | Get | Example |
|---|---|---|
| νέα παράγραφος / νέα γραμμή | paragraph / line break | |
| τελεία, κόμμα, άνω και κάτω τελεία, άνω τελεία, ερωτηματικό, θαυμαστικό | `. , : · ; !` | |
| παύλα | `-` | «05 παύλα 001» → `05-001`, «Αθήνα παύλα Πειραιάς» → `Αθήνα - Πειραιάς` |
| κάθετος | `/` | «1234 κάθετος 2020» → `1234/2020` |
| τοις εκατό | `%` | «50 τοις εκατό» → `50%` |
| άνοιγμα / κλείσιμο παρένθεσης | `( )` | |
| άνοιγμα / κλείσιμο εισαγωγικών | `« »` | |
| σύμβολο παραγράφου | `§` | «σύμβολο παραγράφου 3» → `§ 3` |
| αρίθμηση ένα / δύο / 3 … | `1)` `2)` `3)` on a new line | «ότι άνω και κάτω τελεία αρίθμηση ένα …» → `ότι:` ↵ `1) …` |
| άλφα / βήτα / γάμα … στίγμα παρένθεση (or αρίθμηση άλφα …) | `α)` `β)` `γ)` … `στ)` on a new line | |

### Numbers

Dictated numbers are written the contract way: in words, then digits in parentheses.

| Say (or Whisper writes) | Get |
|---|---|
| είκοσι εννέα / `29` | `είκοσι εννέα (29)` |
| διακοσίων πενήντα χιλιάδων ευρώ / `250.000 ευρώ` | `διακοσίων πενήντα χιλιάδων ευρώ (250.000 €)` |
| πενήντα τοις εκατό / `50%` | `πενήντα τοις εκατό (50%)` |
| του ποσού των `3500` ευρώ | `του ποσού των τριών χιλιάδων πεντακοσίων ευρώ (3.500 €)` |
| εμβαδού ογδόντα πέντε τετραγωνικών μέτρων / εμβαδού `85 τ.μ.` | `εμβαδού ογδόντα πέντε τετραγωνικών μέτρων (85 τ.μ.)` |
| έχει ογδόντα πέντε τετραγωνικά μέτρα / `85 m2` | `ογδόντα πέντε τετραγωνικά μέτρα (85 τ.μ.)` |
| άνοιγμα παρένθεσης δύο κλείσιμο παρένθεσης | `(2)`, digits only |

- Words keep exactly what was said, including gender and case. When Whisper writes digits, the words are generated in the neuter, and in the genitive after «των», «εμβαδού», «επιφανείας», «εκτάσεως», «αντί», «ποσού», «τιμήματος», «αξίας», «ύψους», so check the gender for things like «τρεις ημέρες».
- A lone «ένα» / «μία» is left alone because it is usually the article.
- Stays in digits: references after «άρθρο», «παρ.», «αριθμός», «νόμου», «ΦΕΚ», «ΑΦΜ», «ΚΑΕΚ», «ΤΚ», «§»; street numbers after «οδός/λεωφόρος/πλατεία …»; numbers joined with `/`, `-`, `:` or decimals; numbers of 5+ digits without dots (IDs, postcodes); numbers already in parentheses.
- List numbering needs «αρίθμηση», so `2)` (a list item) is never confused with `δύο (2)` (an amount).

Numbered items in scanned documents also keep their own line (`1)`, `2.`, `α)`).
«κάθετος» and «τοις εκατό» only turn into symbols next to a number, so «κάθετος τοίχος» or «πενήντα τοις εκατό» stay as words.
To add a command, add a line to `COMMANDS` in `app/dictation.py` (and a test case in `tests/test_dictation.py`).

## AI spelling correction (optional)

Greek has many words that sound the same but are spelled differently («η γνωστή» / «οι γνωστοί», «της» / «τις», «πωλείτε» / «πωλείται», «δήλωση» / «δηλώσει»).
With this feature on, a local AI model (through [Ollama](https://ollama.com)) suggests corrections after each dictation.

**Safeguard:** a suggested change is applied only if the new word *sounds exactly like* the old one. The model cannot rephrase, add or remove words, or change numbers, names or punctuation; such suggestions are discarded.
Every applied change is listed under the job («AI: N διορθώσεις») with an «Αναίρεση» (undo) button.

Two switches:
- **Feature flag** `AI_CORRECTION=true|false` in `.env`. When `false` (default), the page shows nothing AI-related and the API refuses AI requests.
- **Per-user switch** «Διόρθωση ορθογραφίας με AI» in the page (remembered by the browser), plus a «Διόρθωση με AI» button that corrects the text in the editor. Use it to test models on typed text.

The instructions the model follows are in `app/prompts/correction_el.md`; edit them, or point `AI_PROMPT_FILE` to your own file.

### On a Mac (recommended for testing)

Run Ollama as the native app, which uses the Mac's GPU. Docker on a Mac cannot use it.

```bash
# 1. Install and open Ollama: https://ollama.com/download
ollama pull gemma3:12b

# 2. In .env
AI_CORRECTION=true
AI_URL=http://host.docker.internal:11434
AI_MODEL=gemma3:12b

# 3. Restart the app
docker compose up -d --force-recreate
```

The page then shows «Μοντέλο: gemma3:12b» under the switch; if it shows an error instead, it says what is missing (server not running, model not pulled).

Models worth comparing (change `AI_MODEL`, `ollama pull` it, restart). With 48 GB of RAM all of these fit:

| Model | Size | Notes |
|---|---|---|
| `gemma3:12b` | ~8 GB | default; good multilingual model |
| `gemma3:27b` | ~17 GB | best quality of the list, slower |
| `qwen3:14b` | ~9 GB | strong; "thinking" model, so slower per reply |
| Krikri (ILSP, Greek-specific) | ~5 GB | not in the Ollama library: search Hugging Face for a "Krikri GGUF" build and pull it with `ollama pull hf.co/<user>/<repo>:Q4_K_M` |

A quick test: type «Η γνωστή πωλητές δηλώνουν ότι το ακίνητο πωλείτε ελεύθερο.» into the editor and press «Διόρθωση με AI».

### On a Linux server

```bash
# .env: AI_CORRECTION=true, AI_URL=http://ollama:11434, AI_MODEL=gemma3:4b (or larger if RAM allows)
docker compose --profile ai up -d
docker compose exec ollama ollama pull gemma3:4b
```

On CPU only, expect 30 s to a few minutes per paragraph depending on the model; `AI_CPUS` / `AI_MEMORY` cap the Ollama container.
The model needs RAM on top of Whisper's ~3 GB: roughly 3 GB for `gemma3:4b`, 8 GB for `gemma3:12b`. If the server cannot handle it, set `AI_CORRECTION=false`.
If the AI server is down or too slow, the dictation still completes, uncorrected, with a warning.

## Deploying on the Hetzner server

Requirements: Docker with the compose plugin, plus nginx and certbot on the host. HTTPS is mandatory, because browsers only allow the microphone on `https://` pages.

```bash
git clone <this repo> /opt/voice-to-text && cd /opt/voice-to-text
cp .env.example .env          # set APP_USERNAME / APP_PASSWORD, adjust APP_CPUS / APP_MEMORY
docker compose up -d --build

# nginx: copy and edit the example, then get a certificate
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/symvolaia.example.gr
sudo ln -s /etc/nginx/sites-available/symvolaia.example.gr /etc/nginx/sites-enabled/
sudo certbot --nginx -d symvolaia.example.gr
sudo nginx -t && sudo systemctl reload nginx
```

The container listens only on `127.0.0.1:8000`, so it is reachable only through nginx. The Whisper model is cached in the `models` Docker volume.

### Sizing

Transcription runs on the CPU, one job at a time. `APP_CPUS` and `APP_MEMORY` cap the container so the website on the same server stays responsive.

| Model (`WHISPER_MODEL`) | RAM | Greek quality | Speed on CPU |
|---|---|---|---|
| `large-v3-turbo` (default) | ~3 GB | very good | fastest of the large models |
| `large-v3` | ~4 GB | best | ~3x slower |
| `medium` / `small` | 1–2 GB | noticeably worse | fast |

Measure on the real server: time a 5-minute dictation and pick the model accordingly.

## Development

```bash
pip install -r requirements-dev.txt     # plus: apt install ffmpeg tesseract-ocr tesseract-ocr-ell
pytest
WHISPER_MODEL=small MODEL_DIR=./models uvicorn app.main:app --reload
```

When `APP_USERNAME` is unset, authentication is disabled (local development only).

## Troubleshooting

**«Ο browser μπλοκάρει το μικρόφωνο…»**: browsers allow the microphone only on `https://` pages or on `http://localhost`.
The Docker log says `Uvicorn running on http://0.0.0.0:8000`, but that address is *not* treated as secure, and neither is a LAN IP such as `http://192.168.1.10:8000`.
Locally, open **http://localhost:8000**. To test from a phone or another computer, deploy behind HTTPS (see above).

## Privacy notes

- Uploaded files are deleted as soon as they are processed.
- Results are kept in memory only, and are forgotten after `JOB_TTL_SECONDS` (default 1 h) or on restart.
- The draft in the editor is saved in the browser's local storage so a refresh doesn't lose it. «Καθαρισμός» clears it.
