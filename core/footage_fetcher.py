"""
Footage fetcher - uses yt-dlp to download relevant gameplay/anime clips
from YouTube based on the topic and category. Downloads short segments,
not full videos. Caches clips to avoid re-downloading.
"""

import os
import json
import re
import random
import logging
import subprocess
import hashlib
from pathlib import Path
from anthropic import Anthropic

log = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("FOOTAGE_CACHE_DIR", "footage/cache"))
CLIP_DURATION = int(os.getenv("CLIP_DURATION", "30"))

# Search queries per category — used to find relevant YouTube videos
CATEGORY_SEARCH_TEMPLATES = {
    "pokemon":       [
        "Pokemon {game} gameplay walkthrough no commentary",
        "Pokemon {subject} battle gameplay",
        "Pokemon {subject} evolution scene",
        "Pokemon game footage {subject}",
    ],
    "anime":         [
        "{subject} anime gameplay cutscene no commentary",
        "{subject} anime scene HD",
        "{subject} fight scene HD 1080p",
        "{subject} anime moments compilation",
    ],
    "video_games":   [
        "{subject} gameplay no commentary HD",
        "{subject} game footage walkthrough",
        "{subject} 4K gameplay",
    ],
    "jrpg":          [
        "{subject} JRPG gameplay no commentary",
        "{subject} cutscene HD",
        "{subject} gameplay walkthrough",
    ],
    "retro_gaming":  [
        "{subject} retro gameplay original",
        "{subject} classic game footage",
        "{subject} SNES NES N64 gameplay",
    ],
    "game_lore":     [
        "{subject} lore explained gameplay",
        "{subject} game footage HD",
        "{subject} walkthrough no commentary",
    ],
    "manga":         [
        "{subject} anime adaptation scene",
        "{subject} manga anime comparison",
        "{subject} scene HD",
    ],
    "marvel_dc":     [
        "{subject} scene HD clip",
        "{subject} movie clip official",
        "{subject} gameplay Marvel DC",
    ],
    "star_wars":     [
        "{subject} Star Wars scene HD",
        "{subject} clip official",
        "Star Wars {subject} gameplay",
    ],
    "studio_ghibli": [
        "{subject} Ghibli scene HD",
        "Studio Ghibli {subject} clip",
        "{subject} Miyazaki scene",
    ],
}

# Fallback searches when subject-specific search fails
CATEGORY_FALLBACKS = {
    "pokemon":       ["Pokemon game footage gameplay HD", "Pokemon battle footage"],
    "anime":         ["anime gameplay footage HD", "anime scene HD no copyright"],
    "video_games":   ["video game gameplay footage HD", "gaming footage no commentary"],
    "jrpg":          ["JRPG gameplay footage HD", "RPG game footage"],
    "retro_gaming":  ["retro gaming footage SNES NES", "classic game gameplay"],
    "game_lore":     ["video game lore footage HD", "indie game gameplay footage"],
    "manga":         ["anime footage HD no commentary", "anime scene HD"],
    "marvel_dc":     ["Marvel DC comic footage HD", "superhero game footage"],
    "star_wars":     ["Star Wars footage HD", "Star Wars game gameplay"],
    "studio_ghibli": ["Studio Ghibli anime footage HD", "anime nature scene footage"],
}


class FootageFetcher:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir).resolve()
        self.clips_dir = self.output_dir / "clips"
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.ffmpeg = os.getenv("FFMPEG_PATH", "ffmpeg")

    def fetch_clips(self, topic: dict, needed_duration: float) -> list:
        """
        Download enough clips to cover needed_duration.
        Returns list of local clip paths.
        """
        category = topic.get("category", "pokemon")
        subjects = topic.get("subjects", topic.get("pokemon_subjects", ["pokemon"]))
        title = topic.get("title", "")

        num_clips = max(2, int(needed_duration / CLIP_DURATION) + 1)
        log.info(f"Need {num_clips} clips for {needed_duration:.0f}s of footage")

        # Ask Claude for the best search queries
        queries = self._plan_searches(title, category, subjects)
        log.info(f"Search queries: {queries}")

        clips = []
        for i, query in enumerate(queries[:num_clips]):
            log.info(f"Searching YouTube: '{query}'")
            clip = self._download_clip(query, i, category)
            if clip:
                clips.append(clip)
                log.info(f"  Got clip {len(clips)}/{num_clips}: {clip.name}")
            if len(clips) >= num_clips:
                break

        # If we didn't get enough, try fallbacks
        if len(clips) < num_clips:
            fallbacks = CATEGORY_FALLBACKS.get(category, CATEGORY_FALLBACKS["video_games"])
            for fb_query in fallbacks:
                if len(clips) >= num_clips:
                    break
                clip = self._download_clip(fb_query, len(clips), category)
                if clip:
                    clips.append(clip)

        log.info(f"Total clips fetched: {len(clips)}")
        return clips

    def _plan_searches(self, title: str, category: str, subjects: list) -> list:
        """Ask Claude to generate the best YouTube search queries for this topic."""
        subject_str = ", ".join(subjects[:3]) if subjects else category

        prompt = f"""Generate 4 YouTube search queries to find relevant background footage for this video.

Video topic: {title}
Category: {category}
Main subjects: {subject_str}

Rules:
- Queries should find gameplay footage, anime scenes, or movie clips
- Include "no commentary" or "HD" to get clean footage
- Be specific to the subjects — avoid generic terms
- Each query on its own line, no numbering or bullets

Just output the 4 search queries, one per line."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-5",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            result = []
            for line in raw.split("\n"):
                line = line.strip()
                line = line.strip('",').strip()
                if not line:
                    continue
                if "queries" in line.lower():
                    continue
                if line[0] in ('{', '[', '"'):
                    continue
                result.append(line)
            return result[:4]
        except Exception as e:
            log.warning(f"Query planning failed: {e}")
            # Fall back to template-based queries
            templates = CATEGORY_SEARCH_TEMPLATES.get(category, CATEGORY_SEARCH_TEMPLATES["video_games"])
            subject = subjects[0] if subjects else category
            return [t.replace("{subject}", subject).replace("{game}", subject) for t in templates[:4]]

    def _download_clip(self, query: str, clip_index: int, category: str) -> Path:
        """Search YouTube and download a random 30s segment from a relevant video."""

        # Check cache first
        cache_key = hashlib.md5(query.encode()).hexdigest()[:12]
        cached = list(CACHE_DIR.glob(f"{cache_key}_*.mp4"))
        if cached:
            # Copy from cache to clips dir
            src = random.choice(cached)
            dest = self.clips_dir / f"clip_{clip_index:03d}.mp4"
            import shutil
            shutil.copy2(str(src), str(dest))
            log.info(f"  Using cached clip for '{query}'")
            return dest

        # Search YouTube for relevant video
        video_url = self._search_youtube(query)
        if not video_url:
            log.warning(f"  No results for '{query}'")
            return None

        # Get video duration
        duration = self._get_yt_duration(video_url)
        if not duration or duration < 30:
            log.warning(f"  Video too short: {duration}s")
            return None

        # Pick random start time (avoid first/last 60s)
        safe_start = 60
        safe_end = max(safe_start + 30, duration - 60)
        start_time = random.uniform(safe_start, safe_end - CLIP_DURATION)
        start_time = max(0, start_time)

        # Download the clip segment
        out_path = self.clips_dir / f"clip_{clip_index:03d}.mp4"
        cache_path = CACHE_DIR / f"{cache_key}_{clip_index}.mp4"

        success = self._download_segment(video_url, start_time, CLIP_DURATION, out_path)
        if success:
            # Cache it
            import shutil
            shutil.copy2(str(out_path), str(cache_path))
            return out_path

        return None

    def _search_youtube(self, query: str) -> str:
        """Use yt-dlp to search YouTube and return the first video URL."""
        search_url = f"ytsearch5:{query}"
        for attempt in [
            ["yt-dlp", search_url, "--get-id", "--no-playlist",
             "--ignore-errors", "--quiet", "--no-warnings",
             "--flat-playlist", "--no-check-certificate"],
            ["yt-dlp", "--default-search", "ytsearch5", "--get-id",
             "--no-playlist", "--ignore-errors", "--quiet", "--no-warnings",
             "--flat-playlist", "--no-check-certificate", query],
        ]:
            result = subprocess.run(attempt, capture_output=True, text=True, timeout=45)
            ids = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and len(l.strip()) == 11]
            if ids:
                return f"https://www.youtube.com/watch?v={random.choice(ids[:3])}"
        log.debug(f"No results for: {query}")
        return None

    def _get_yt_duration(self, url: str) -> float:
        """Get video duration without downloading."""
        cmd = [
            "yt-dlp",
            "--get-duration",
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            "--no-check-certificate",
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        duration_str = result.stdout.strip()
        try:
            parts = duration_str.split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            return float(parts[0])
        except Exception:
            return 0.0

    def _download_segment(self, url: str, start: float, duration: int, output: Path) -> bool:
        """Download a specific segment of a YouTube video using yt-dlp + FFmpeg."""

        # Use external downloader with time range
        # yt-dlp downloads to temp, FFmpeg cuts the segment
        temp_path = output.parent / f"temp_{output.stem}.%(ext)s"

        # Download best available video (not 4K to save time)
        dl_cmd = [
            "yt-dlp",
            "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            "--no-check-certificate",
            "--merge-output-format", "mp4",
            "-o", str(temp_path),
            url,
        ]

        log.info(f"  Downloading from {url} ...")
        dl_result = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=120)

        # Find the downloaded file
        temp_files = list(output.parent.glob(f"temp_{output.stem}.*"))
        if not temp_files:
            log.warning(f"  Download produced no file: {dl_result.stderr[-200:]}")
            return False

        temp_file = temp_files[0]

        # Cut the segment with FFmpeg
        cut_cmd = [
            self.ffmpeg, "-y",
            "-ss", str(start),
            "-i", str(temp_file),
            "-t", str(duration),
            "-vf", f"scale={1080}:{1920}:force_original_aspect_ratio=increase,crop={1080}:{1920},setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "26",
            "-an",
            str(output),
        ]

        cut_result = subprocess.run(cut_cmd, capture_output=True, text=True, timeout=60)
        temp_file.unlink(missing_ok=True)

        if cut_result.returncode != 0:
            log.warning(f"  FFmpeg cut failed: {cut_result.stderr[-200:]}")
            return False

        if not output.exists() or output.stat().st_size < 10000:
            log.warning(f"  Output file too small or missing")
            return False

        return True
