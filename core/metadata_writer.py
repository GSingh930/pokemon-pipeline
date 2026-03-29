"""
Metadata writer - generates upload-ready title, description, and hashtags.
"""

import os
import json
import re
from anthropic import Anthropic


class MetadataWriter:
    def __init__(self):
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def generate(self, topic: dict, script: dict) -> dict:
        prompt = self._build_prompt(topic, script)

        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=800,
            system="You are a JSON API. You only ever respond with valid RFC8259 JSON. No markdown, no code fences, no explanation, no apostrophes inside string values. Always use double quotes.",
            messages=[{"role": "user", "content": prompt}, {"role": "assistant", "content": "{"}],
        )

        raw = response.content[0].text.strip()
        # Prepend the { used as prefill (Claude continues from after it)
        if not raw.startswith("{"):
            raw = "{" + raw

        # Trim any trailing content after JSON closes
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


        # Strip markdown code fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON object
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

            # Fallback: build metadata from topic directly
            return self._build_fallback(topic)

    def _build_prompt(self, topic: dict, script: dict) -> str:
        narration_preview = script.get("narration", "")[:300]

        return f"""You are a viral Pokemon social media strategist.

Topic: {topic['title']}
Content type: {topic['type']}
Script preview: {narration_preview}

Generate upload metadata. Respond with ONLY a raw JSON object. No markdown, no code fences. Start with {{ and end with }}.

{{
  "youtube": {{
    "title": "YouTube title max 70 chars with Pokemon keyword",
    "description": "2-3 sentence description with hashtags",
    "tags": ["Pokemon", "PokemonFacts", "up to 15 tags"]
  }},
  "tiktok": {{
    "caption": "Short punchy caption under 150 chars #Pokemon #PokemonFacts"
  }},
  "instagram": {{
    "caption": "Slightly longer caption with 10-12 hashtags"
  }},
  "universal_hashtags": ["#Pokemon", "#PokemonFacts", "#PokemonLore", "#Nintendo", "#Anime"]
}}"""

    def _build_fallback(self, topic: dict) -> dict:
        title = topic.get("title", "Pokemon Facts You Never Knew")
        return {
            "youtube": {
                "title": title[:70],
                "description": f"{title} #Pokemon #PokemonFacts #Nintendo #Anime #Gaming",
                "tags": ["Pokemon", "PokemonFacts", "PokemonLore", "Nintendo", "Anime", "Gaming", "DidYouKnow", "PokemonShorts"],
            },
            "tiktok": {
                "caption": f"{title[:100]} #Pokemon #PokemonFacts #Nintendo",
            },
            "instagram": {
                "caption": f"{title}\n\n#Pokemon #PokemonFacts #PokemonLore #Nintendo #Anime #Gaming #DidYouKnow #PokemonShorts",
            },
            "universal_hashtags": ["#Pokemon", "#PokemonFacts", "#PokemonLore", "#Nintendo", "#Anime", "#Gaming"],
        }
