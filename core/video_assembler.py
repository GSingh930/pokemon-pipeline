"""
Video assembler - samples random clips from gameplay footage,
overlays Ken Burns images on top, burns captions, renders final Short.
"""

import os
import subprocess
import json
import logging
import random
from pathlib import Path
from pydub import AudioSegment

from core.image_fetcher import ImageFetcher
from core.footage_fetcher import FootageFetcher
from core.subtitle_generator import SubtitleGenerator

log = logging.getLogger(__name__)


class VideoAssembler:
    def __init__(self):
        self.ffmpeg = os.getenv("FFMPEG_PATH", "ffmpeg")
        self.width = int(os.getenv("VIDEO_WIDTH", "1080"))
        self.height = int(os.getenv("VIDEO_HEIGHT", "1920"))

    def assemble(self, audio_path: Path, broll_cues: list, output_path: Path, script: dict = None) -> Path:
        audio_path = Path(audio_path)
        output_path = Path(output_path)
        audio_duration = self._get_audio_duration(audio_path)
        log.info(f"Audio duration: {audio_duration:.1f}s")

        # Step 1: Get background footage
        # Priority: local library clips -> yt-dlp -> dark background
        clips = []

        # Check footage/library first
        library = Path("footage/library")
        library_clips = list(library.glob("*.mp4")) + list(library.glob("*.mov")) if library.exists() else []
        if library_clips:
            import random as _random
            num_needed = max(2, int(audio_duration / 30) + 1)
            clips = [_random.choice(library_clips) for _ in range(num_needed)]
            log.info(f"Using {num_needed} random clips from footage/library ({len(library_clips)} available)")
        else:
            # Fall back to yt-dlp
            try:
                from core.footage_fetcher import FootageFetcher
                fetcher_obj = FootageFetcher(output_path.parent)
                topic = script.get("_topic", {}) if script else {}
                if not topic:
                    topic = {"category": script.get("category", "pokemon") if script else "pokemon",
                             "subjects": [], "title": ""}
                clips = fetcher_obj.fetch_clips(topic, audio_duration)
            except Exception as e:
                log.warning(f"yt-dlp fetch failed: {e} — using fallback background")

        if clips:
            log.info(f"Building background from {len(clips)} gameplay clips...")
            bg_path = self._concat_clips(clips, audio_duration, output_path.parent / "background.mp4")
        else:
            log.info("No footage found — using dark background fallback")
            bg_path = self._generate_fallback_background(audio_duration, output_path.parent / "background.mp4")

        # Step 2: Fetch relevant Pokemon images and overlay them
        if script:
            log.info("Fetching Pokemon images for overlay...")
            fetcher = ImageFetcher(output_path.parent)
            image_data = fetcher.fetch_for_script(script)
            composited_path = self._overlay_images(bg_path, image_data, audio_duration, output_path.parent / "composited.mp4")
        else:
            composited_path = bg_path

        # Step 3: Merge with audio
        self._merge_audio(composited_path, audio_path, output_path)
        return output_path

    def burn_captions(self, video_path: Path, script: dict, output_path: Path, audio_path: Path = None) -> Path:
        video_path = Path(video_path)
        output_path = Path(output_path)

        srt_path = output_path.parent / "captions.srt"
        if audio_path and Path(audio_path).exists():
            gen = SubtitleGenerator()
            gen.generate(script, Path(audio_path), srt_path)
        else:
            self._generate_srt(script, srt_path)

        srt_str = str(srt_path.resolve()).replace("\\", "/")
        if len(srt_str) > 1 and srt_str[1] == ":":
            srt_str = srt_str[0] + "\\:" + srt_str[2:]

        cmd = [
            self.ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", (
                f"subtitles='{srt_str}':force_style='"
                "FontName=Arial,"
                "FontSize=13,"
                "Bold=1,"
                "PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00000000,"
                "BackColour=&H60000000,"
                "BorderStyle=4,"
                "Outline=0,"
                "Shadow=0,"
                "Alignment=2,"
                "MarginV=60,"
                "MarginL=40,"
                "MarginR=40'"
            ),
            "-c:a", "copy",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            str(output_path),
        ]
        self._run(cmd)
        return output_path

    def _concat_clips(self, clips: list, target_duration: float, output_path: Path) -> Path:
        """Concatenate gameplay clips to fill the full video duration."""
        list_file = output_path.parent / "clips_list.txt"
        with open(list_file, "w") as f:
            for clip in clips:
                f.write(f"file '{str(clip).replace(chr(92), '/')}'\n")

        cmd = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-t", str(target_duration),
            "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,crop={self.width}:{self.height},setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an",
            str(output_path),
        ]
        self._run(cmd)
        return output_path

    def _overlay_images(self, bg_path: Path, image_data: list, total_duration: float, output_path: Path) -> Path:
        """
        Overlay Pokemon images on top of gameplay background.
        Images appear in the top ~60% of the screen with Ken Burns effect.
        Bottom 40% stays as pure gameplay so captions have clean space.
        """
        valid = [d for d in image_data if d.get("image_path") and Path(d["image_path"]).exists()]

        if not valid:
            log.warning("No valid images to overlay — using background only")
            import shutil
            shutil.copy2(str(bg_path), str(output_path))
            return output_path

        # Build per-image duration from script hints
        durations = [max(float(d.get("duration", 4)), 2.0) for d in valid]
        total_img_duration = sum(durations)
        # Scale durations to match audio
        scale = total_duration / total_img_duration
        durations = [d * scale for d in durations]

        # Build FFmpeg filter for slideshow overlay with Ken Burns
        inputs = ["-i", str(bg_path)]
        for item in valid:
            inputs += ["-loop", "1", "-t", str(total_duration), "-i", str(item["image_path"])]

        ken_burns = [
            "zoompan=z='min(zoom+0.001,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            "zoompan=z='1.2':x='if(lte(on,1),0,x+0.5)':y='ih/2-(ih/zoom/2)'",
            "zoompan=z='1.2':x='if(lte(on,1),iw*0.2,x-0.5)':y='ih/2-(ih/zoom/2)'",
            "zoompan=z='if(lte(on,1),1.3,max(zoom-0.001,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            "zoompan=z='1.2':x='iw/2-(iw/zoom/2)':y='if(lte(on,1),0,min(y+0.3,ih*0.1))'",
        ]

        fps = 30
        img_w = self.width          # Full width
        img_h = int(self.height * 0.58)  # Top 58% of screen

        filter_parts = []
        overlay_labels = []
        current_time = 0.0

        for i, (item, dur) in enumerate(zip(valid, durations)):
            frames = max(int(dur * fps), fps)
            effect = ken_burns[i % len(ken_burns)]
            label = f"img{i}"

            filter_parts.append(
                f"[{i+1}:v]"
                f"scale={img_w*2}:{img_h*2}:force_original_aspect_ratio=increase,"
                f"crop={img_w*2}:{img_h*2},"
                f"{effect}:d={frames}:s={img_w}x{img_h}:fps={fps},"
                f"setsar=1,setpts=PTS-STARTPTS+{current_time}/TB"
                f"[{label}]"
            )
            overlay_labels.append((label, current_time, dur))
            current_time += dur

        # Chain overlays onto background one by one
        filter_str = ";".join(filter_parts)

        # First overlay
        prev = "[0:v]"
        for j, (label, start, dur) in enumerate(overlay_labels):
            out_label = f"[ov{j}]" if j < len(overlay_labels) - 1 else "[outv]"
            filter_str += (
                f";{prev}[{label}]overlay=x=0:y=0"
                f":enable='between(t,{start:.2f},{start+dur:.2f})'"
                f"{out_label}"
            )
            prev = f"[ov{j}]"

        cmd = (
            [self.ffmpeg, "-y"] +
            inputs + [
                "-filter_complex", filter_str,
                "-map", "[outv]",
                "-t", str(total_duration),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-an",
                str(output_path),
            ]
        )

        try:
            self._run(cmd)
            return output_path
        except Exception as e:
            log.warning(f"Image overlay failed ({e}) — using background only")
            import shutil
            shutil.copy2(str(bg_path), str(output_path))
            return output_path

    def _generate_fallback_background(self, duration: float, output_path: Path) -> Path:
        cmd = [
            self.ffmpeg, "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x1a0533:size={self.width}x{self.height}:rate=30:duration={duration}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        self._run(cmd)
        return output_path

    def _merge_audio(self, video_path: Path, audio_path: Path, output_path: Path):
        cmd = [
            self.ffmpeg, "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(output_path),
        ]
        self._run(cmd)

    def _generate_srt(self, script: dict, srt_path: Path):
        lines = script.get("lines", [])
        total_words = sum(len(l["text"].split()) for l in lines)
        words_per_sec = total_words / max(script.get("estimated_duration", 50), 1)

        entries = []
        current_time = 0.0
        idx = 1

        for line in lines:
            words = line["text"].split()
            for i in range(0, len(words), 5):
                chunk = " ".join(words[i:i+5])
                duration = len(chunk.split()) / max(words_per_sec, 1)
                entries.append((idx, current_time, current_time + duration, chunk.upper()))
                current_time += duration
                idx += 1

        with open(srt_path, "w", encoding="utf-8") as f:
            for idx, start, end, text in entries:
                f.write(f"{idx}\n{self._fmt_time(start)} --> {self._fmt_time(end)}\n{text}\n\n")

    def _fmt_time(self, s: float) -> str:
        h, m = int(s // 3600), int((s % 3600) // 60)
        sec, ms = int(s % 60), int((s % 1) * 1000)
        return f"{h:02}:{m:02}:{sec:02},{ms:03}"

    def _get_audio_duration(self, path: Path) -> float:
        audio = AudioSegment.from_file(str(path))
        return len(audio) / 1000.0

    def _run(self, cmd: list):
        log.debug(f"FFmpeg: {' '.join(str(c) for c in cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log.error(f"FFmpeg error:\n{result.stderr[-500:]}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr[-300:]}")
