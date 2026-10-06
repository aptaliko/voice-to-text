# System requirements

Everything runs on one machine in Docker, on the CPU (no graphics card needed).
Sizes and speeds below are **approximate**: they depend on the CPU, the speech model and the length of the recordings.
Check real usage on a running server with `docker stats` and `docker system df`.

## 1. Without AI correction (`AI_CORRECTION=false`, current production setup)

The app transcribes speech with Whisper and reads scans with Tesseract.

### Server

| | Minimum | Recommended |
|---|---|---|
| CPU | 2 vCPU (x86-64 or ARM64) | 4 vCPU |
| RAM for the app | 2 GB, with `WHISPER_MODEL=medium` | 3 GB, with `WHISPER_MODEL=large-v3-turbo` |
| Free disk | 6 GB | 10 GB |
| OS | Linux with Docker Engine and Docker Compose v2 | same |

RAM and disk depend mostly on the speech model (`WHISPER_MODEL` in `.env`):

| Model | Model download (disk) | App RAM while transcribing | Greek quality | Speed on CPU |
|---|---|---|---|---|
| `small` | ~0.5 GB | ~1 GB | fair | fast |
| `medium` | ~1.5 GB | ~1.5–2 GB | good | ~1–2× the recording length on 2 vCPU |
| `large-v3-turbo` (default) | ~1.6 GB | ~2.5–3 GB | very good | ~0.5–1× the recording length on 4 vCPU |
| `large-v3` | ~3 GB | ~4 GB | best | ~3× slower than turbo |

Disk use, besides the model:
- the app's Docker image: about 2 GB;
- during each deploy, temporary build files: up to about 2 GB more;
- uploads: deleted after processing, up to `MAX_UPLOAD_MB` (200 MB) each while in use.

Leave RAM for everything else on the server. `APP_MEMORY` and `APP_CPUS` in `.env` cap the app, so it cannot take memory or CPU from other services (for example a website).

### Network

- **HTTPS is required** (browsers only allow the microphone on `https://`), so a domain or hostname and a certificate are needed. A reverse proxy (nginx) handles it.
- Outbound internet only for: the one-time speech-model download (from Hugging Face), Docker images, and code updates from GitHub. Audio and documents never leave the server.

### Users

- A recent Chrome, Edge, Firefox or Safari, on a computer or phone.
- A microphone. A headset or desk microphone gives much better results than a laptop's built-in one.

### Current production server

2 vCPU, 3.7 GB RAM (about 2 GB free beside the website), `WHISPER_MODEL=medium`, `APP_CPUS=1.5`, `APP_MEMORY=2g`.
This is the **minimum** setup: it works, but there is no room for a larger speech model or for AI correction.
Expect transcription to take roughly as long as the recording itself, or up to twice as long.

## 2. With AI correction (`AI_CORRECTION=true`)

Adds a local language model (through Ollama) that fixes words that sound the same but are spelled differently («η/οι», «της/τις»).
It runs on the same machine as an extra container and needs **its own RAM, CPU and disk on top of section 1**.

| AI model (`AI_MODEL`) | Extra disk | Extra RAM | Time per dictated paragraph, CPU only |
|---|---|---|---|
| `gemma3:4b` | ~3.5 GB | ~4 GB | ~20–60 s on 4 vCPU |
| `gemma3:12b` | ~8 GB | ~9 GB | ~1–3 min on 8 vCPU |
| `gemma3:27b` | ~17 GB | ~18 GB | several minutes; practical only with a GPU or a Mac |

### Whole-server totals

| Setup | CPU | RAM (app + AI, plus 1–2 GB for the system) | Free disk |
|---|---|---|---|
| Without AI (section 1) | 2–4 vCPU | 2–3 GB | 6–10 GB |
| AI with `gemma3:4b` | 4 vCPU | 8 GB | 15 GB |
| AI with `gemma3:12b` | 8 vCPU | 16 GB | 25 GB |

Add whatever else runs on the server, such as a website and its database.

Notes:
- **The current production server cannot run AI correction.** It has 3.7 GB RAM in total. Even the smallest model needs a server with about 8 GB (more if the website stays on it).
- **A GPU or an Apple Silicon Mac** makes the AI step much faster (seconds instead of minutes). On a Mac, run the Ollama app natively; Docker on a Mac cannot use the GPU (see README).
- **If the AI is slow or down, nothing breaks:** the dictation still arrives, uncorrected, with a warning.
- With `AI_CORRECTION=false` the AI container does not run and costs nothing. The AI switch and button are not shown in the page.
