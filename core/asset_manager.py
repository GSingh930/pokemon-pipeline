"""
Asset manager - downloads footage clips and music from Cloudflare R2 (or any CDN).
Assets are cached locally so they only download once per Railway deployment.

Setup:
1. Create a free Cloudflare R2 bucket at dash.cloudflare.com
2. Upload your footage clips and music files to the bucket
3. Make the bucket public (Settings -> Public access -> Allow)
4. Set R2_PUBLIC_URL in Railway env vars

R2_PUBLIC_URL format: https://pub-xxxx.r2.dev  (from your bucket's public URL)

File structure in your R2 bucket:
  footage/clip_000.mp4
  footage/clip_001.mp4
  ...
  music/Lavender Town.mp3
  music/Battle Champion.mp3
  ...
"""

import os
import json
import logging
import requests
from pathlib import Path

log = logging.getLogger(__name__)

R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
FOOTAGE_DIR   = Path("footage/library")
MUSIC_DIR     = Path("music")
CACHE_FILE    = Path("logs/asset_cache.json")
HEADERS       = {"User-Agent": "PokemonShortsPipeline/1.0"}


class AssetManager:
    def __init__(self):
        self.base_url = R2_PUBLIC_URL
        self.session  = requests.Session()
        self.session.headers.update(HEADERS)
        self.cache    = self._load_cache()

    def sync_footage(self) -> list:
        """Download all footage clips from R2 if not already cached."""
        if not self.base_url:
            log.info("R2_PUBLIC_URL not set — using local footage only")
            return list(FOOTAGE_DIR.glob("*.mp4"))

        log.info(f"R2 base URL: {self.base_url}")
        FOOTAGE_DIR.mkdir(parents=True, exist_ok=True)

        # Fetch the manifest of available clips
        clips = self._get_manifest("footage")
        log.info(f"R2 footage manifest: {len(clips)} files found — {clips[:3]}")
        if not clips:
            log.warning("No footage manifest found in R2 — using local clips")
            return list(FOOTAGE_DIR.glob("*.mp4"))

        downloaded = []
        for filename in clips:
            local_path = FOOTAGE_DIR / filename
            if self._is_cached(f"footage/{filename}", local_path):
                downloaded.append(local_path)
                continue

            url = f"{self.base_url}/footage/{filename}"
            path = self._download(url, local_path)
            if path:
                self._mark_cached(f"footage/{filename}", path)
                downloaded.append(path)

        log.info(f"Footage ready: {len(downloaded)} clips")
        return downloaded

    def sync_music(self) -> list:
        """Download all music files from R2 if not already cached."""
        if not self.base_url:
            log.info("R2_PUBLIC_URL not set — using local music only")
            return list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.wav"))

        MUSIC_DIR.mkdir(parents=True, exist_ok=True)

        tracks = self._get_manifest("music")
        if not tracks:
            log.warning("No music manifest found in R2 — using local music")
            return list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.wav"))

        downloaded = []
        for filename in tracks:
            local_path = MUSIC_DIR / filename
            if self._is_cached(f"music/{filename}", local_path):
                downloaded.append(local_path)
                continue

            url = f"{self.base_url}/music/{filename}"
            path = self._download(url, local_path)
            if path:
                self._mark_cached(f"music/{filename}", path)
                downloaded.append(path)

        log.info(f"Music ready: {len(downloaded)} tracks")
        return downloaded

    def _get_manifest(self, folder: str) -> list:
        """
        Fetch list of files from R2.
        You need a manifest.json in each folder listing the files.
        Format: ["clip_000.mp4", "clip_001.mp4", ...]
        """
        url = f"{self.base_url}/{folder}/manifest.json"
        try:
            r = self.session.get(url, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            log.debug(f"Manifest fetch failed for {folder}: {e}")
        return []

    def _is_cached(self, key: str, local_path: Path) -> bool:
        """Check if file is already downloaded and valid."""
        if not local_path.exists() or local_path.stat().st_size < 10000:
            return False
        return key in self.cache

    def _mark_cached(self, key: str, path: Path):
        self.cache[key] = str(path)
        self._save_cache()

    def _download(self, url: str, output: Path) -> Path:
        log.info(f"Downloading: {url.split('/')[-1]}")
        try:
            r = self.session.get(url, timeout=120, stream=True)
            if r.status_code != 200:
                log.warning(f"  Failed ({r.status_code}): {url}")
                return None
            with open(output, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):  # 1MB chunks
                    f.write(chunk)
            mb = output.stat().st_size / (1024 * 1024)
            log.info(f"  Downloaded: {output.name} ({mb:.1f}MB)")
            return output
        except Exception as e:
            log.warning(f"  Download error: {e}")
            return None

    def _load_cache(self) -> dict:
        CACHE_FILE.parent.mkdir(exist_ok=True)
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE) as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        with open(CACHE_FILE, "w") as f:
            json.dump(self.cache, f, indent=2)
