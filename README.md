# Υπαγόρευση Συμβολαίων: voice & scan to Word

A small self-hosted web app for drafting Greek property-sale contracts:

- **Dictate**: record in the browser (laptop or phone) or upload an audio file, and it is transcribed with [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
- **Scan**: upload PDFs, scanned pages or phone photos, and the text is extracted with Tesseract (Greek + English). PDFs that already contain text skip OCR.
- **Edit & export**: fix the text in the browser and download it as a `.docx`.

Everything runs on your own server. No audio or document leaves it, and no external API is called.
The only outbound connection is a one-time download of the Whisper model (~1.6 GB) on the first transcription.

## Dictation tips

- Say **«νέα παράγραφος»** for a new paragraph and **«νέα γραμμή»** for a line break. A pause of 2.5 s or more also starts a new paragraph.
- Dictate in chunks (one clause per recording). Each result is appended to the text in order.
- Add recurring names and terms (notaries, areas, standard phrases) to `WHISPER_PROMPT` in `.env` to improve spelling.

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
