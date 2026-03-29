"""
Footage sampler - cuts random 30s clips from a long gameplay video.
"""

import os
import random
import logging
import subprocess
import json
from pathlib import Path

log = logging.getLogger(__name__)

FOOTAGE_DIR = Path(os.getenv("FOOTAGE_DIR", "footage"))
CLIP_DURATION = int(os.getenv("CLIP_DURATION", "30"))


class FootageSampler:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir).resolve()
        self.clips_dir = self.output_dir / "clips"
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg = os.getenv("FFMPEG_PATH", "ffmpeg")

    def sample_clips(self, needed_duration: float) -> list:
        source = self._find_source()
        if not source:
            log.warning("No footage found in footage/ folder.")
            return []

        source_duration = self._get_duration(source)
        log.info(f"Source footage: {source.name} ({source_duration/3600:.1f} hours)")

        num_clips = max(1, int(needed_duration / CLIP_DURATION) + 1)
        log.info(f"Cutting {num_clips} x {CLIP_DURATION}s clips to cover {needed_duration:.0f}s")

        safe_start = 60
        safe_end = source_duration - CLIP_DURATION - 60
        if safe_end <= safe_start:
            safe_start = 0
            safe_end = max(source_duration - CLIP_DURATION, 1)

        clips = []
        segment_size = (safe_end - safe_start) / max(num_clips, 1)

        for i in range(num_clips):
            seg_start = safe_start + (i * segment_size)
            seg_end = seg_start + segment_size
            start_time = random.uniform(seg_start, max(seg_start + 1, seg_end - CLIP_DURATION))
            start_time = max(safe_start, min(start_time, safe_end))

            clip_path = self.clips_dir / f"clip_{i:03d}.mp4"
            success = self._cut_clip(source, start_time, CLIP_DURATION, clip_path)
            if success:
                clips.append(clip_path)
                log.info(f"  Clip {i+1}/{num_clips}: t={start_time/3600:.2f}h -> {clip_path.name}")

        log.info(f"Cut {len(clips)} clips")
        return clips

    def _find_source(self) -> Path:
        if not FOOTAGE_DIR.exists():
            return None
        for ext in ["*.mp4", "*.mkv", "*.mov", "*.avi", "*.webm"]:
            files = list(FOOTAGE_DIR.glob(ext))
            if files:
                return max(files, key=lambda f: f.stat().st_size)
        return None

    def _cut_clip(self, source: Path, start: float, duration: int, output: Path) -> bool:
        cmd = [
            self.ffmpeg, "-y",
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-an",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log.warning(f"Clip cut failed at {start:.0f}s: {result.stderr[-200:]}")
            return False
        return True

    def _get_duration(self, path: Path) -> float:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            capture_output=True, text=True,
        )
        try:
            return float(json.loads(result.stdout)["format"]["duration"])
        except Exception:
            return 0.0
