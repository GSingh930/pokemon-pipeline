"""
Video assembler - builds video from library clips + Pokemon image overlays.
No yt-dlp. Uses footage/library clips or a generated background.
"""

import os
import subprocess
import json
import logging
import random
from pathlib import Path
from pydub import AudioSegment

from core.image_fetcher import ImageFetcher
from core.subtitle_generator import SubtitleGenerator

log = logging.getLogger(__name__)


class VideoAssembler:
    def __init__(self):
        self.ffmpeg = os.getenv("FFMPEG_PATH", "ffmpeg")
        self.width  = int(os.getenv("VIDEO_WIDTH",  "1080"))
        self.height = int(os.getenv("VIDEO_HEIGHT", "1920"))

    def assemble(self, audio_path: Path, broll_cues: list, output_path: Path, script: dict = None) -> Path:
        audio_path  = Path(audio_path)
        output_path = Path(output_path)
        audio_duration = self._get_audio_duration(audio_path)
        log.info(f"Audio duration: {audio_duration:.1f}s")

        # Step 1: Background — library clips or generated gradient
        library      = Path("footage/library")
        library_clips = sorted(library.glob("*.mp4")) + sorted(library.glob("*.mov")) if library.exists() else []

        if library_clips:
            num_needed = max(2, int(audio_duration / 30) + 1)
            clips = [random.choice(library_clips) for _ in range(num_needed)]
            log.info(f"Using {num_needed} random clips from library ({len(library_clips)} available)")
            try:
                bg_path = self._concat_clips(clips, audio_duration, output_path.parent / "background.mp4")
            except Exception as e:
                log.warning(f"Clip concat failed: {e} — generating background instead")
                bg_path = self._generate_background(audio_duration, output_path.parent / "background.mp4")
        else:
            log.info("No library clips — generating background")
            bg_path = self._generate_background(audio_duration, output_path.parent / "background.mp4")

        # Step 2: Pokemon image overlays
        if script:
            log.info("Fetching Pokemon images...")
            fetcher    = ImageFetcher(output_path.parent)
            image_data = fetcher.fetch_for_script(script)
            composited = self._overlay_images(bg_path, image_data, audio_duration, output_path.parent / "composited.mp4")
        else:
            composited = bg_path

        # Step 3: Merge audio
        self._merge_audio(composited, audio_path, output_path)
        return output_path

    def burn_captions(self, video_path: Path, script: dict, output_path: Path, audio_path: Path = None) -> Path:
        video_path  = Path(video_path)
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
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        self._run(cmd)
        return output_path

    def _concat_clips(self, clips: list, target_duration: float, output_path: Path) -> Path:
        list_file = output_path.parent / "clips_list.txt"
        with open(list_file, "w") as f:
            for clip in clips:
                clip_path = Path(clip["path"]) if isinstance(clip, dict) else Path(clip)
                clip_str  = str(clip_path.resolve()).replace("\\", "/")
                f.write(f"file '{clip_str}'\n")

        cmd = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-t", str(target_duration),
            "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,crop={self.width}:{self.height},setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",
            str(output_path),
        ]
        self._run(cmd)
        return output_path

    def _generate_background(self, duration: float, output_path: Path) -> Path:
        """Generate an animated gradient background — no external files needed."""
        cmd = [
            self.ffmpeg, "-y",
            "-f", "lavfi",
            "-i", (
                f"gradients=size={self.width}x{self.height}:rate=30:duration={duration}"
                f":c0=0x1a0533:c1=0x0d1b4a:x0=0:y0=0:x1={self.width}:y1={self.height}:nb_colors=2"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # gradients filter not available — fall back to solid color
            log.warning("gradients filter unavailable — using solid color")
            cmd = [
                self.ffmpeg, "-y",
                "-f", "lavfi",
                "-i", f"color=c=0x1a0533:size={self.width}x{self.height}:rate=30",
                "-t", str(duration),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                str(output_path),
            ]
            self._run(cmd)
        return output_path

    def _overlay_images(self, bg_path: Path, image_data: list, total_duration: float, output_path: Path) -> Path:
        valid = [d for d in image_data if d.get("image_path") and Path(d["image_path"]).exists()]

        if not valid:
            log.warning("No images to overlay — using background only")
            import shutil
            shutil.copy2(str(bg_path), str(output_path))
            return output_path

        durations = [max(float(d.get("duration", 4)), 2.0) for d in valid]
        scale     = total_duration / max(sum(durations), 0.01)
        durations = [d * scale for d in durations]

        ken_burns = [
            "zoompan=z='min(zoom+0.001,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            "zoompan=z='1.2':x='if(lte(on,1),0,x+0.5)':y='ih/2-(ih/zoom/2)'",
            "zoompan=z='1.2':x='if(lte(on,1),iw*0.2,x-0.5)':y='ih/2-(ih/zoom/2)'",
            "zoompan=z='if(lte(on,1),1.3,max(zoom-0.001,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            "zoompan=z='1.2':x='iw/2-(iw/zoom/2)':y='if(lte(on,1),0,min(y+0.3,ih*0.1))'",
        ]

        fps    = 30
        img_w  = self.width
        img_h  = int(self.height * 0.58)

        inputs       = ["-i", str(bg_path)]
        filter_parts = []
        overlay_labels = []
        current_time   = 0.0

        for i, (item, dur) in enumerate(zip(valid, durations)):
            frames = max(int(dur * fps), fps)
            effect = ken_burns[i % len(ken_burns)]
            label  = f"img{i}"

            inputs += ["-loop", "1", "-t", str(total_duration), "-i", str(item["image_path"])]
            filter_parts.append(
                f"[{i+1}:v]"
                f"scale={img_w*2}:{img_h*2}:force_original_aspect_ratio=increase,"
                f"crop={img_w*2}:{img_h*2},"
                f"{effect}:d={frames}:s={img_w}x{img_h}:fps={fps},"
                f"setsar=1,setpts=PTS-STARTPTS+{current_time:.3f}/TB"
                f"[{label}]"
            )
            overlay_labels.append((label, current_time, dur))
            current_time += dur

        filter_str = ";".join(filter_parts)
        prev = "[0:v]"
        for j, (label, start, dur) in enumerate(overlay_labels):
            out_label   = f"[ov{j}]" if j < len(overlay_labels) - 1 else "[outv]"
            filter_str += (
                f";{prev}[{label}]overlay=x=0:y=0"
                f":enable='between(t,{start:.3f},{start+dur:.3f})'"
                f"{out_label}"
            )
            prev = f"[ov{j}]"

        cmd = (
            [self.ffmpeg, "-y"] + inputs + [
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

    def _merge_audio(self, video_path: Path, audio_path: Path, output_path: Path):
        cmd = [
            self.ffmpeg, "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]
        self._run(cmd)

    def _generate_srt(self, script: dict, srt_path: Path):
        lines       = script.get("lines", [])
        total_words = sum(len(l["text"].split()) for l in lines)
        wps         = total_words / max(script.get("estimated_duration", 50), 1)

        entries      = []
        current_time = 0.0
        idx          = 1

        for line in lines:
            words = line["text"].split()
            for i in range(0, len(words), 5):
                chunk    = " ".join(words[i:i+5])
                duration = len(chunk.split()) / max(wps, 1)
                entries.append((idx, current_time, current_time + duration, chunk.upper()))
                current_time += duration
                idx += 1

        with open(srt_path, "w", encoding="utf-8") as f:
            for idx, start, end, text in entries:
                f.write(f"{idx}\n{self._fmt(start)} --> {self._fmt(end)}\n{text}\n\n")

    def _fmt(self, s: float) -> str:
        h, m = int(s // 3600), int((s % 3600) // 60)
        sec, ms = int(s % 60), int((s % 1) * 1000)
        return f"{h:02}:{m:02}:{sec:02},{ms:03}"

    def _get_audio_duration(self, path: Path) -> float:
        audio = AudioSegment.from_file(str(path))
        return len(audio) / 1000.0

    def _run(self, cmd: list):
        log.info(f"FFmpeg cmd: {' '.join(str(c) for c in cmd[:6])}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # Get the actual error — filter out the frame progress lines
            error_lines = [l for l in result.stderr.split("\n")
                          if l.strip() and "frame=" not in l and "fps=" not in l
                          and "size=" not in l and "time=" not in l]
            clean_error = "\n".join(error_lines[-20:])
            log.error(f"FFmpeg failed:\n{clean_error}")
            raise RuntimeError(f"FFmpeg failed: {clean_error[-400:]}")
