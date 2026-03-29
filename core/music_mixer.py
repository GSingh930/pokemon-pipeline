"""
Music mixer - matches your exact Pokemon music files to content type by mood.
Hardcoded map built from the actual filenames in your collection.
"""

import os
import json
import random
import logging
import subprocess
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

MUSIC_DIR = Path(os.getenv("MUSIC_DIR", "music"))

# Your exact files mapped to moods
# epic       = top 10s, powerful countdowns
# dark       = fan theories, hidden secrets, lore deep dives
# upbeat     = did you knows, fun facts, light topics
# dramatic   = emotional lore, farewells, endings

TRACK_MOOD_MAP = {
    # === EPIC — battle themes, champion, gym, elite four ===
    "epic": [
        "Battle! (Champion)", "Battle! (Cynthia)", "Battle! (Elite Four)",
        "Battle! (Gym Leader)", "Battle! (Trainer)", "Battle! (Frontier Brain)",
        "Battle! (Reshiram-Zekrom)", "Battle! (Legendary Pokémon)",
        "Battle! (Super-Ancient Pokémon)", "Battle! (Regirock-Regice-Registeel)",
        "Battle! (Kyurem)", "Battle! (N)", "Battle! (Ghetsis)",
        "Battle! (Team Aqua-Team Magma Leaders)", "Battle! (Team Plasma)",
        "Battle! (Brendan-May)", "Battle! (Cheren-Bianca)",
        "Battle! (Battle Subway Trainer)", "Battle! (Strong Wild Pokémon)",
        "Battle! (Mew)", "Final Battle! (N)", "Final Battle! (World Championships)",
        "Battle Frontier", "Battle Tower", "Battle Factory", "Battle Pike",
        "Battle Arena", "Battle Palace", "Battle Pyramid", "Battle Dome (Tournament)",
        "Champion Steven", "Cynthia", "Victory Road",
        "Pokémon League", "Ever Grande City", "Room of Glory",
        "Victory Lies Before You!", "Embracing One's Duty",
        "Onward to Our Own Futures", "An Unwavering Heart",
        "Hall of Fame",
    ],

    # === DARK — mysterious, creepy, villain, ruins, caves ===
    "dark": [
        "Mt. Pyre", "Mt. Pyre Exterior", "Cave of Origin",
        "Abandoned Ship", "Sealed Chamber", "Relic Castle",
        "Distortion World", "Dragonspiral Tower", "Chargestone Cave",
        "Victory Road", "Dreamyard", "Lostlorn Forest",
        "Hideout", "N's Castle", "Abyssal Ruins",
        "Team Rocket!", "Team Aqua Appears!", "Team Plasma Appears!",
        "Battle! (Team Aqua-Team Magma)", "Battle! (Team Plasma)",
        "Battle! (Ghetsis)", "Battle! (N)",
        "Opelucid City (Black)", "Black City",
        "Abnormal Weather", "Drought", "Heavy Rain",
        "Cold Storage", "Lacunosa Town",
    ],

    # === UPBEAT — towns, routes, exploration, adventure ===
    "upbeat": [
        "Route 1", "Route 2 (Spring)", "Route 2 (Summer)", "Route 2 (Autumn)", "Route 2 (Winter)",
        "Route 4 (Spring)", "Route 4 (Summer)", "Route 4 (Autumn)", "Route 4 (Winter)",
        "Route 6 (Spring)", "Route 6 (Summer)", "Route 6 (Autumn)", "Route 6 (Winter)",
        "Route 10", "Route 12 (Spring)", "Route 12 (Summer)", "Route 12 (Autumn)", "Route 12 (Winter)",
        "Route 101", "Route 104", "Route 110", "Route 111", "Route 113", "Route 119", "Route 120",
        "Littleroot Town", "Oldale Town", "Petalburg City", "Rustboro City",
        "Dewford Town", "Slateport City", "Verdanturf Town", "Fallarbor Town",
        "Lilycove City", "Sootopolis City", "Fortree City",
        "Accumula Town", "Nuvema Town", "Nacrene City", "Striaton City",
        "Castelia City", "Nimbasa City", "Mistralton City", "Icirrus City",
        "Pokémon Center", "Poké Mart", "Cycling", "Surf", "Dive",
        "Title Screen", "Introductions", "Onward to Adventure! (Part 2)",
        "Birch Pokémon Lab", "Juniper Pokémon Lab", "Professor Juniper",
        "Brendan", "May", "Cheren", "Let's Go Together!",
        "Driftveil City", "Anville Town", "Undella Town (Summer)",
        "Undella Town (Autumn-Winter-Spring)", "Village Bridge",
        "Marvelous Bridge", "Skyarrow Bridge", "Tubeline Bridge",
        "Driftveil Drawbridge", "Crossing the Sea",
        "Battle! (Wild Pokémon)", "Trainers' School",
        "Game Corner", "Musical Theater", "Contest Lobby",
        "Pokémon Gym", "Pokémon Contest!", "Global Terminal",
        "Shopping Mall Nine", "Gear Station", "Entralink",
        "White Forest", "Trick House",
    ],

    # === DRAMATIC — emotional, endings, farewells, bittersweet ===
    "dramatic": [
        "Farewell", "Ending", "The End", "Hall of Fame",
        "Final Battle! (N)", "Final Battle! (N) (Remix)",
        "N's Castle", "Victory! (Champion)", "Victory! (Gym Leader)",
        "Victory! (Team Plasma)", "Farewell (Refrain)",
        "A Lullaby for Trains", "Summer in Lacunosa",
        "A Ferris Wheel Ride Together", "Cynthia",
        "Looker", "Unity Tower", "Undella Town (Summer)",
        "An Unwavering Heart", "Onward to Our Own Futures",
        "Embracing One's Duty", "Battle! (Cynthia)",
        "Mt. Pyre", "Sealed Chamber", "Relic Castle",
        "Route 119", "Route 120",
    ],
}

CONTENT_TYPE_MOODS = {
    "top10":          ["epic"],
    "fan_theory":     ["dark", "dramatic"],
    "did_you_know":   ["upbeat"],
    "hidden_secret":  ["dark"],
    "lore_deep_dive": ["dark", "dramatic"],
}


class MusicMixer:
    def __init__(self):
        self.ffmpeg = os.getenv("FFMPEG_PATH", "ffmpeg")
        self.music_volume = float(os.getenv("MUSIC_VOLUME", "0.15"))
        self.fade_duration = int(os.getenv("MUSIC_FADE", "2"))

    def mix(self, video_path: Path, content_type: str, output_path: Path) -> Path:
        video_path = Path(video_path)
        output_path = Path(output_path)

        music_path = self._pick_track(content_type)
        if not music_path:
            log.warning("No music found in music/ folder — skipping.")
            shutil.copy2(str(video_path), str(output_path))
            return output_path

        log.info(f"Mixing: {music_path.name}")
        duration = self._get_duration(video_path)

        cmd = [
            self.ffmpeg, "-y",
            "-i", str(video_path),
            "-stream_loop", "-1",
            "-i", str(music_path),
            "-filter_complex", (
                f"[1:a]volume={self.music_volume},"
                f"afade=t=in:st=0:d={self.fade_duration},"
                f"afade=t=out:st={max(0, duration - self.fade_duration)}:d={self.fade_duration}"
                f"[music];"
                "[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            ),
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration),
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log.error(f"Music mix failed: {result.stderr[-300:]}")
            shutil.copy2(str(video_path), str(output_path))
        else:
            log.info(f"Mixed successfully -> {output_path.name}")

        return output_path

    def _pick_track(self, content_type: str) -> Path:
        if not MUSIC_DIR.exists():
            return None

        all_tracks = (
            list(MUSIC_DIR.glob("*.mp3")) +
            list(MUSIC_DIR.glob("*.wav")) +
            list(MUSIC_DIR.glob("*.ogg")) +
            list(MUSIC_DIR.glob("*.m4a")) +
            list(MUSIC_DIR.glob("*.flac"))
        )
        if not all_tracks:
            return None

        target_moods = CONTENT_TYPE_MOODS.get(content_type, ["upbeat"])

        # Build candidate list from target moods
        candidates = []
        for mood in target_moods:
            candidates.extend(TRACK_MOOD_MAP.get(mood, []))

        # Match against actual files — strip track number prefix and extension
        matched = []
        for track in all_tracks:
            # Strip leading "XX - " track number
            clean_name = track.stem
            clean_name = clean_name.split(" - ", 1)[-1] if " - " in clean_name else clean_name
            # Strip [Hidden Track] / [Bonus Track] suffixes
            clean_name = clean_name.replace(" [Hidden Track]", "").replace(" [Bonus Track]", "").replace(" [Bonus track]", "").strip()

            if clean_name in candidates:
                matched.append(track)

        if matched:
            chosen = random.choice(matched)
            log.info(f"Mood match ({content_type}): {chosen.name}")
            return chosen

        # No mood match — fall back to random
        chosen = random.choice(all_tracks)
        log.info(f"No mood match, using random: {chosen.name}")
        return chosen

    def _get_duration(self, video_path: Path) -> float:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video_path)],
            capture_output=True, text=True,
        )
        try:
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception:
            return 45.0
