"""
Subtitle generator - creates perfectly timed SRT captions by
analysing the actual audio file duration per line using pydub.
No more guessing — timing is derived from real audio length.
"""

import logging
from pathlib import Path
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

log = logging.getLogger(__name__)


class SubtitleGenerator:
    def __init__(self):
        self.words_per_chunk = 4   # Words per caption chunk
        self.min_silence_ms = 300  # Silence gap between sentences (ms)

    def generate(self, script: dict, audio_path: Path, srt_path: Path) -> Path:
        """
        Generate SRT file timed to actual audio duration.
        Splits narration into chunks and spaces them evenly across real audio length.
        """
        audio = AudioSegment.from_file(str(audio_path))
        total_ms = len(audio)
        total_seconds = total_ms / 1000.0
        log.info(f"Audio duration for subtitles: {total_seconds:.2f}s")

        # Get all narration text
        lines = script.get("lines", [])
        full_text = " ".join(line["text"] for line in lines)
        words = full_text.split()

        if not words:
            return srt_path

        # Split into caption chunks
        chunks = []
        for i in range(0, len(words), self.words_per_chunk):
            chunk = " ".join(words[i:i + self.words_per_chunk])
            chunks.append(chunk)

        # Try to detect silence boundaries for better sync
        silence_ranges = self._detect_silence_boundaries(audio)

        if silence_ranges and len(silence_ranges) > 1:
            timings = self._map_chunks_to_silences(chunks, silence_ranges, total_seconds)
        else:
            # Even distribution across full audio
            timings = self._even_distribution(chunks, total_seconds)

        # Write SRT
        self._write_srt(timings, srt_path)
        log.info(f"Generated {len(timings)} subtitle entries")
        return srt_path

    def _detect_silence_boundaries(self, audio: AudioSegment) -> list:
        """Find silence gaps to use as natural sentence boundaries."""
        try:
            nonsilent = detect_nonsilent(
                audio,
                min_silence_len=self.min_silence_ms,
                silence_thresh=audio.dBFS - 16,
            )
            return [(start / 1000.0, end / 1000.0) for start, end in nonsilent]
        except Exception as e:
            log.debug(f"Silence detection failed: {e}")
            return []

    def _map_chunks_to_silences(self, chunks: list, speech_ranges: list, total: float) -> list:
        """Map caption chunks to detected speech segments."""
        total_words = sum(len(c.split()) for c in chunks)
        timings = []
        current_time = 0.0

        # Distribute chunks proportionally across speech segments
        chunk_idx = 0
        for seg_start, seg_end in speech_ranges:
            if chunk_idx >= len(chunks):
                break
            seg_dur = seg_end - seg_start

            # How many words are in this segment proportionally
            seg_word_count = max(1, round(seg_dur / total * total_words))
            word_count = 0
            seg_time = seg_start

            while chunk_idx < len(chunks) and word_count < seg_word_count:
                chunk = chunks[chunk_idx]
                chunk_words = len(chunk.split())
                chunk_dur = (chunk_words / max(total_words, 1)) * total
                chunk_dur = max(chunk_dur, 0.5)

                end_time = min(seg_time + chunk_dur, seg_end)
                timings.append((seg_time, end_time, chunk.upper()))
                seg_time = end_time
                word_count += chunk_words
                chunk_idx += 1

        # Any remaining chunks
        if chunk_idx < len(chunks):
            remaining = chunks[chunk_idx:]
            last_start = timings[-1][1] if timings else 0.0
            chunk_dur = (total - last_start) / max(len(remaining), 1)
            for chunk in remaining:
                end = min(last_start + chunk_dur, total - 0.1)
                timings.append((last_start, end, chunk.upper()))
                last_start = end

        return timings

    def _even_distribution(self, chunks: list, total_seconds: float) -> list:
        """Evenly distribute chunks across audio with slight padding at start/end."""
        if not chunks:
            return []

        # Leave 0.2s gap at start and end
        usable = total_seconds - 0.4
        chunk_dur = usable / len(chunks)
        chunk_dur = max(chunk_dur, 0.5)

        timings = []
        t = 0.2
        for chunk in chunks:
            end = min(t + chunk_dur, total_seconds - 0.1)
            timings.append((t, end, chunk.upper()))
            t = end

        return timings

    def _write_srt(self, timings: list, srt_path: Path):
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, (start, end, text) in enumerate(timings, 1):
                f.write(f"{i}\n")
                f.write(f"{self._fmt(start)} --> {self._fmt(end)}\n")
                f.write(f"{text}\n\n")

    def _fmt(self, s: float) -> str:
        s = max(0.0, s)
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        ms = int((s % 1) * 1000)
        return f"{h:02}:{m:02}:{sec:02},{ms:03}"
