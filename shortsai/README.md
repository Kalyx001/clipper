# ShortsAI Studio

Paste a YouTube link (or upload a video) → it gets transcribed, the best
moments get picked out, cut into ≤30s vertical clips with word-by-word
burned captions, and you can publish straight to your connected YouTube
channel.

**Only process videos you own or have explicit permission to re-edit and
re-publish.** Downloading and re-uploading someone else's content can
violate YouTube's Terms of Service and copyright law — this tool doesn't
check that for you.

## How it works

```
YouTube URL / file upload
   -> download (yt-dlp) or accept upload
   -> transcribe with word-level timestamps (faster-whisper, runs locally)
   -> Claude reads the transcript and picks the best clip segments
   -> ffmpeg cuts each clip, reframes to 1080x1920 (blurred vertical backdrop)
   -> word-by-word animated captions burned in (.ass subtitles)
   -> thumbnail extracted
   -> optional: publish to YouTube via the Data API
```

## Requirements

- Python 3.11+
- `ffmpeg` and `ffprobe` on the PATH (`apt install ffmpeg` / `brew install ffmpeg`)
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com)) -- new accounts get some free evaluation credit before billing is required
- ~2GB+ RAM free for the Whisper model (more for larger model sizes)

## Run it locally

```bash
cd shortsai
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env
# edit .env and paste in your ANTHROPIC_API_KEY at minimum

cd backend
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000`.

The first run downloads the Whisper model (a few hundred MB) — this can
take a minute.

## Run it with Docker

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY
docker compose up --build
```

Open `http://localhost:8000`. Generated files persist in the `shortsai_storage`
volume between restarts.

## Deploying so you can use it from anywhere

Any host that lets you run a long-lived Docker container with a couple GB
of RAM works. Two easy options:

**Railway / Render (simplest)**
1. Push this folder to a GitHub repo.
2. Create a new service from the repo, pick "Docker" as the build method
   (both platforms auto-detect the `Dockerfile`).
3. Add the environment variables from `.env.example` in the platform's
   dashboard.
4. Attach a persistent volume mounted at `/app/backend/storage` (both
   platforms support this) so clips and your YouTube login survive restarts.
5. Once deployed, set `PUBLIC_BASE_URL` and `YOUTUBE_REDIRECT_URI` to your
   real deployed URL, e.g. `https://yourapp.up.railway.app/api/youtube/oauth2callback`.

**A cheap VPS (DigitalOcean, Hetzner, etc.)**
```bash
git clone <your-repo> && cd shortsai
cp .env.example .env && nano .env
docker compose up -d --build
```
Put it behind a reverse proxy (Caddy or nginx) for HTTPS — Google's OAuth
requires an `https://` redirect URI for anything other than `localhost`.

## If YouTube blocks downloads ("Sign in to confirm you're not a bot")

Cloud hosts (Render, Railway, etc.) share IP ranges that YouTube sometimes
flags, even for videos you own and are allowed to download. The fix is to
give `yt-dlp` cookies from a real logged-in browser session:

1. Install a browser extension like **"Get cookies.txt LOCALLY"** while
   signed into youtube.com.
2. Export a `cookies.txt` file.
3. In the app, open **Advanced: fix "sign in to confirm you're not a bot"**
   (below the main input card) and upload that file.
4. Try your video again.

The file is stored at `backend/storage/youtube_cookies.txt` on the server
only — it's in `.gitignore` so it never ends up in your repo. Cookies do
expire eventually; re-export and re-upload if the error comes back.

## Connecting YouTube (for the Publish button)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) →
   create a project (or use an existing one).
2. **APIs & Services → Library** → enable the **YouTube Data API v3**.
3. **APIs & Services → OAuth consent screen** → set it up (External is fine;
   while it's in "Testing" mode, add your own Google account as a test user).
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   → Application type: **Web application**.
5. Under "Authorized redirect URIs," add exactly the value you set for
   `YOUTUBE_REDIRECT_URI` in `.env` (e.g. `http://localhost:8000/api/youtube/oauth2callback`,
   or your real domain once deployed).
6. Copy the Client ID and Client Secret into `.env`.
7. Restart the app, click **Connect YouTube** in the top right, and sign in.

Uploads default to `privacy_status="private"` so nothing goes public by
accident — change that in `backend/main.py`'s `publish_clip` call, or add a
visibility toggle in the UI, once you're happy with the results.

## Where things live

```
backend/
  main.py               FastAPI app + all routes
  pipeline.py            Orchestrates the full job: download -> transcribe -> detect -> render
  db.py                  SQLite job/clip tracking (storage/jobs.db)
  config.py               Env var loading
  services/
    downloader.py        yt-dlp download + ffprobe
    transcriber.py        faster-whisper word-level transcription
    viral_detector.py     Claude call that picks clip segments
    clipper.py            ffmpeg cut + vertical reframe + thumbnail
    captions.py            Builds the word-by-word .ass caption file
    youtube_uploader.py   OAuth + YouTube Data API upload
  storage/
    uploads/               Source videos land here
    outputs/<job_id>/      Rendered clips, thumbnails, caption files
frontend/
  index.html             The whole UI (no build step)
```

## Known limitations / good next steps

- **Processing is single-threaded per job** (a plain background thread).
  Fine for personal use; if you're queuing up many videos at once, swap
  in Celery + Redis or RQ so jobs run in a real worker pool.
- **Reframing uses a blurred-backdrop crop, not face tracking.** It looks
  good for most talking-head and demo content. True face-tracked reframing
  (keeping a speaker's face centered as they move) would need a model like
  a face/person detector run per-frame — a solid next feature, but real
  compute cost.
- **Single-user YouTube token.** The OAuth token is stored in one file
  (`storage/youtube_token.json`). Fine for "just me" use; if you ever add
  other users, key that file (or a DB table) by user ID.
- **Whisper model size** trades speed for accuracy — `small` is a good
  default; bump to `medium` or `large-v3` in `.env` if transcripts look off,
  at the cost of slower processing and more RAM.
- No auth on the app itself — if you deploy it publicly, put it behind at
  least a basic password (e.g., a reverse-proxy basic-auth rule) so random
  people can't burn through your Anthropic credit or bill.
