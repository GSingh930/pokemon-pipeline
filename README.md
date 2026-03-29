# Pokemon Shorts Pipeline

Fully automated faceless Pokemon YouTube Shorts machine.
Runs daily on Railway — generates topic, writes script, creates voiceover, assembles video, uploads to TikTok + YouTube Shorts + Instagram Reels.

---

## How it works

```
Scheduler (cron)
  → Topic engine (Claude API) — picks content type, generates topic
  → Script writer (Claude API) — full 45-60s narration + B-roll cues
  → gTTS — voiceover audio
  → Video assembler (FFmpeg) — syncs footage + audio
  → Caption burner (FFmpeg) — burnt-in captions
  → Metadata writer (Claude API) — title, description, hashtags
  → Upload to YouTube Shorts + TikTok + Instagram Reels
```

---

## Setup (do this once)

### 1. Clone and install locally for auth setup

```bash
git clone <your-repo>
cd pokemon_pipeline
pip install -r requirements.txt
brew install ffmpeg   # Mac
# or: sudo apt install ffmpeg  (Linux)
```

### 2. Get your API keys

**Anthropic (Claude)**
- Go to https://console.anthropic.com
- Create an API key
- Save as `ANTHROPIC_API_KEY`

**YouTube**
- Go to https://console.cloud.google.com
- Create a project → Enable "YouTube Data API v3"
- Create OAuth 2.0 credentials (Desktop app type)
- Download client_id and client_secret
- Run: `python auth/youtube_auth.py`
- Copy the printed JSON → save as `YOUTUBE_TOKEN_JSON`

**TikTok**
- Go to https://developers.tiktok.com
- Create an app → Request "Content Posting API" scope
- Get your access token from the developer portal
- Save as `TIKTOK_ACCESS_TOKEN`

**Instagram**
- Go to https://developers.facebook.com
- Create an app → Add Instagram Graph API
- Get a long-lived user token with `instagram_content_publish` permission
- Get your Instagram Business user ID
- Save as `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_USER_ID`
- Set up a CDN for video hosting (Cloudflare R2 is free) → `CDN_UPLOAD_URL`

### 3. Add Pokemon footage (optional but recommended)

Create `footage/library/` and add `.mp4` clips of Pokemon gameplay.
Free sources:
- YouTube: search "Pokemon gameplay footage no copyright"
- Archive.org: search "Pokemon game footage"
- Record your own gameplay

Without footage, the pipeline uses a dark purple fallback background.

### 4. Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create project
railway init

# Set all environment variables from .env.example
railway variables set ANTHROPIC_API_KEY=sk-ant-...
railway variables set YOUTUBE_CLIENT_ID=...
# ... (set all variables from .env.example)

# Deploy
railway up
```

### 5. Verify it's running

```bash
railway logs
```

You should see the scheduler loop running. It will execute at your configured `SCHEDULE_HOUR` UTC daily.

---

## Manual test run

```bash
# Test the full pipeline immediately (locally)
RUN_MODE=once python scheduler.py

# Or on Railway
railway run python scheduler.py --once
```

---

## File structure

```
pokemon_pipeline/
├── main.py                  # Pipeline orchestrator
├── scheduler.py             # Daily cron loop for Railway
├── requirements.txt
├── railway.toml             # Railway deployment config
├── .env.example             # All required environment variables
├── core/
│   ├── topic_engine.py      # Claude API: topic generation
│   ├── script_writer.py     # Claude API: script writing
│   ├── tts_engine.py        # gTTS voiceover generation
│   ├── video_assembler.py   # FFmpeg video assembly + captions
│   └── metadata_writer.py   # Claude API: titles + hashtags
├── uploaders/
│   ├── youtube.py           # YouTube Data API v3
│   ├── tiktok.py            # TikTok Content Posting API
│   └── instagram.py         # Meta Graph API
├── auth/
│   └── youtube_auth.py      # One-time OAuth setup script
├── footage/
│   └── library/             # Drop .mp4 clips here
├── output/                  # Generated videos (auto-created)
└── logs/                    # Run logs + topic history
```

---

## Customization

**Change posting time:** Set `SCHEDULE_HOUR` and `SCHEDULE_MINUTE` (UTC) in Railway variables.

**Change TTS voice:** Set `TTS_TLD` — `com` (American), `co.uk` (British), `com.au` (Australian).

**Disable a platform:** Set `YOUTUBE_ENABLED=false`, `TIKTOK_ENABLED=false`, or `INSTAGRAM_ENABLED=false`.

**Post multiple videos per day:** Run multiple Railway services with different `SCHEDULE_HOUR` values.
