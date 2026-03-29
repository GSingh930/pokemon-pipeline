"""
Image fetcher - fetches official Pokemon artwork from PokeAPI.
Claude picks the most relevant Pokemon per script line.
"""

import os
import json
import re
import time
import logging
from pathlib import Path
import requests
from anthropic import Anthropic

log = logging.getLogger(__name__)

SPRITE_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork"
SHINY_BASE  = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/shiny"
HEADERS     = {"User-Agent": "PokemonShortsPipeline/1.0"}

POKEMON_IDS = {
    "bulbasaur":1,"ivysaur":2,"venusaur":3,"charmander":4,"charmeleon":5,
    "charizard":6,"squirtle":7,"wartortle":8,"blastoise":9,"caterpie":10,
    "pikachu":25,"raichu":26,"clefairy":35,"clefable":36,"jigglypuff":39,
    "meowth":52,"persian":53,"psyduck":54,"golduck":55,"growlithe":58,
    "arcanine":59,"alakazam":65,"machamp":68,"gengar":94,"haunter":93,
    "gastly":92,"onix":95,"hypno":97,"magikarp":129,"gyarados":130,
    "lapras":131,"ditto":132,"eevee":133,"vaporeon":134,"jolteon":135,
    "flareon":136,"porygon":137,"snorlax":143,"articuno":144,"zapdos":145,
    "moltres":146,"dratini":147,"dragonair":148,"dragonite":149,"mewtwo":150,
    "mew":151,"chikorita":152,"cyndaquil":155,"totodile":158,"togepi":175,
    "ampharos":181,"espeon":196,"umbreon":197,"slowking":199,"misdreavus":200,
    "raikou":243,"entei":244,"suicune":245,"larvitar":246,"tyranitar":248,
    "lugia":249,"ho-oh":250,"celebi":251,"treecko":252,"torchic":255,
    "mudkip":258,"blaziken":257,"swampert":260,"gardevoir":282,"shedinja":292,
    "flygon":330,"absol":359,"bagon":371,"salamence":373,"metagross":376,
    "regirock":377,"regice":378,"registeel":379,"latias":380,"latios":381,
    "kyogre":382,"groudon":383,"rayquaza":384,"jirachi":385,"deoxys":386,
    "lucario":448,"garchomp":445,"riolu":447,"spiritomb":442,"togekiss":468,
    "leafeon":470,"glaceon":471,"gliscor":472,"dialga":483,"palkia":484,
    "giratina":487,"darkrai":491,"shaymin":492,"arceus":493,"zoroark":571,
    "chandelure":609,"hydreigon":635,"volcarona":637,"reshiram":643,
    "zekrom":644,"kyurem":646,"keldeo":647,"greninja":658,"sylveon":700,
    "xerneas":716,"yveltal":717,"zygarde":718,"diancie":719,"hoopa":720,
    "volcanion":721,"incineroar":727,"decidueye":724,"primarina":730,
    "lycanroc":745,"mimikyu":778,"toxapex":748,"kommo-o":784,"solgaleo":791,
    "lunala":792,"necrozma":800,"marshadow":802,"zeraora":807,"melmetal":809,
    "rillaboom":812,"cinderace":815,"inteleon":818,"corviknight":823,
    "dragapult":887,"eternatus":890,"zacian":888,"zamazenta":889,"zarude":893,
    "calyrex":898,"cubone":104,"marowak":105,"yamask":562,"cofagrigus":563,
    "litwick":607,"lampent":608,"phantump":708,"trevenant":709,"sandygast":769,
    "palossand":770,"sinistea":854,"polteageist":855,"cursola":864,
}


class ImageFetcher:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.client  = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_for_script(self, script: dict) -> list:
        lines = script.get("lines", [])
        topic = script.get("_topic", {})

        plan = self._plan_visuals(lines, topic)
        log.info(f"Visual plan: {plan}")

        results = []
        for i, line in enumerate(lines):
            line_id  = line.get("id", i + 1)
            duration = line.get("duration_hint", 4)
            pokemon_id = plan.get(str(line_id)) or plan.get(line_id, 25)

            # Every 7th image use shiny for variety
            use_shiny = (i % 7 == 0)
            image_path = self._fetch_artwork(line_id, pokemon_id, use_shiny)

            results.append({
                "line_id":    line_id,
                "image_path": str(image_path) if image_path else None,
                "duration":   duration,
                "text":       line.get("text", ""),
            })
            time.sleep(0.1)

        return results

    def _plan_visuals(self, lines: list, topic: dict) -> dict:
        """Ask Claude which Pokemon to show for each script line."""
        title    = topic.get("title", "")
        subjects = topic.get("subjects", topic.get("pokemon_subjects", []))

        lines_text = "\n".join(
            f"Line {l.get('id', i+1)}: {l.get('text', '')}"
            for i, l in enumerate(lines)
        )

        # Build a helpful hint from known subjects
        subject_hint = ""
        if subjects:
            matched = {s.lower(): POKEMON_IDS.get(s.lower()) for s in subjects if POKEMON_IDS.get(s.lower())}
            if matched:
                subject_hint = f"Key Pokemon in this video: {', '.join(f'{n} (id {i})' for n, i in matched.items())}\n"

        prompt = f"""Pick the best Pokemon to show for each line of this video.

Title: {title}
{subject_hint}
Script:
{lines_text}

Rules:
- Pick Pokemon that are mentioned or thematically relevant to each line
- Vary the Pokemon — never repeat the same ID twice in a row
- Use the numeric Pokemon ID

Respond with a JSON object mapping line number to Pokemon ID integer.
Example: {{"1": 94, "2": 150, "3": 25}}"""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-5",
                max_tokens=300,
                system="You are a JSON API. Always respond with valid JSON only. No markdown, no explanation.",
                messages=[
                    {"role": "user",      "content": prompt},
                    {"role": "assistant", "content": "{"},
                ],
            )
            raw = response.content[0].text.strip()
            if not raw.startswith("{"):
                raw = "{" + raw

            # Trim to valid JSON object
            depth, end = 0, 0
            for i, ch in enumerate(raw):
                if ch == "{": depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end:
                raw = raw[:end]

            plan = json.loads(raw)
            # Convert any name values to IDs
            resolved = {}
            for k, v in plan.items():
                if isinstance(v, int):
                    resolved[k] = v
                elif isinstance(v, str) and v.isdigit():
                    resolved[k] = int(v)
                elif isinstance(v, str):
                    resolved[k] = POKEMON_IDS.get(v.lower(), 25)
            return resolved

        except Exception as e:
            log.warning(f"Visual planning failed: {e} — using subject fallback")
            return self._fallback_plan(lines, subjects)

    def _fallback_plan(self, lines: list, subjects: list) -> dict:
        """Cycle through the topic's Pokemon subjects."""
        fallback_ids = [POKEMON_IDS.get(s.lower(), 25) for s in subjects if s] or [25]
        return {
            str(l.get("id", i+1)): fallback_ids[i % len(fallback_ids)]
            for i, l in enumerate(lines)
        }

    def _fetch_artwork(self, line_id: int, pokemon_id: int, use_shiny: bool = False) -> Path:
        base     = SHINY_BASE if use_shiny else SPRITE_BASE
        url      = f"{base}/{pokemon_id}.png"
        filename = f"{line_id:03d}_pokemon_{pokemon_id}{'_shiny' if use_shiny else ''}.png"
        out      = self.images_dir / filename

        if out.exists() and out.stat().st_size > 5000:
            return out

        try:
            r = self.session.get(url, timeout=15)
            if r.status_code == 200 and len(r.content) > 5000:
                out.write_bytes(r.content)
                log.info(f"  Line {line_id}: Pokemon #{pokemon_id}{' shiny' if use_shiny else ''} ({len(r.content)//1024}KB)")
                return out
            # Shiny not available — fall back to normal
            if use_shiny:
                return self._fetch_artwork(line_id, pokemon_id, use_shiny=False)
        except Exception as e:
            log.warning(f"Failed to fetch #{pokemon_id}: {e}")

        # Last resort: Pikachu
        if pokemon_id != 25:
            return self._fetch_artwork(line_id, 25, use_shiny=False)
        return None
