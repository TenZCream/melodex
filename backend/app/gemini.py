"""Gemini: turn a free-text mood ("rainy 3am drive") into musical settings.

Gemini reads the description and picks one of Melodex's vibes, a key, a tempo, an
instrument, and a short evocative title per idea, returned as JSON. The composer
(vibes.py) then writes the actual melodies, so the music itself stays rule-based and
explainable; Gemini acts as the "producer" choosing the direction.

No extra dependencies: plain HTTPS via urllib. The API key comes from the
GEMINI_API_KEY environment variable (put it in backend/.env, which git ignores).
If Gemini is unavailable (no key, no network, quota), a keyword fallback keeps the
feature working, and the response says which one was used.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from .vibes import VIBE_ORDER, VIBES

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Tried in order; the first that works is remembered. Override with GEMINI_MODEL.
MODEL_CANDIDATES = ["gemini-flash-latest", "gemini-3.6-flash", "gemini-3.5-flash",
                    "gemini-2.5-flash", "gemini-2.0-flash"]
INSTRUMENTS = ["piano", "strings", "guitar", "flute", "synth", "electric-piano"]
KEYS = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
TIMEOUT = 12

_working_model: str | None = None


def _vibe_menu() -> str:
    return "\n".join(f'- "{v}": {VIBES[v].description} (tempo {VIBES[v].tempo[0]}-{VIBES[v].tempo[1]} bpm)'
                     for v in VIBE_ORDER)


PROMPT = """You are the music producer inside Melodex, a melody-writing tool.
A user described the feeling they want: "{text}"

Choose musical settings that fit it. Pick exactly one vibe from this list:
{menu}

Reply with ONLY a JSON object, no markdown, with these fields:
{{
  "vibe": one of {vibes},
  "key": one of {keys},
  "tempo_bpm": an integer within the chosen vibe's tempo range,
  "instrument": one of {instruments},
  "titles": a list of {n} short, evocative, original titles (2-4 words each) for melodies in this mood,
  "reason": one friendly sentence (max 25 words) explaining why these settings fit the description
}}
Never reference or imitate existing songs or artists."""


def _load_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _call(model: str, prompt: str, key: str) -> str:
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(API.format(model=model), data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.loads(r.read().decode())
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def _parse(raw: str, n: int) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    obj = json.loads(m.group(0) if m else raw)
    vibe = str(obj.get("vibe", "")).lower().strip()
    if vibe not in VIBES:
        raise ValueError(f"bad vibe {vibe!r}")
    v = VIBES[vibe]
    key = str(obj.get("key", "C")).strip()
    key = next((k for k in KEYS if k.lower() == key.lower()), "C")
    try:
        tempo = int(obj.get("tempo_bpm", sum(v.tempo) // 2))
    except (TypeError, ValueError):
        tempo = sum(v.tempo) // 2
    tempo = max(v.tempo[0] - 10, min(v.tempo[1] + 10, tempo))
    inst = str(obj.get("instrument", "piano")).lower().strip()
    if inst not in INSTRUMENTS:
        inst = "piano"
    titles = [str(t).strip()[:40] for t in obj.get("titles", []) if str(t).strip()][:n]
    reason = str(obj.get("reason", "")).strip()[:200]
    return {"vibe": vibe, "key": key, "tempo_bpm": tempo, "instrument": inst,
            "titles": titles, "reason": reason}


# --------------------------------------------------------------- keyword fallback
_KEYWORDS = {
    "sad": ["sad", "rain", "lonely", "heartbreak", "cry", "tears", "melanchol", "grief", "miss",
            "goodbye", "blue", "grey", "gray", "nostalg", "autumn", "breakup", "sorrow"],
    "happy": ["happy", "sun", "joy", "bright", "summer", "smile", "celebrat", "birthday",
              "cheer", "morning", "spring", "excited", "fun", "party"],
    "pop": ["pop", "catchy", "radio", "dance", "chorus", "anthem", "road trip", "drive",
            "upbeat", "hype", "confident", "love"],
    "mysterious": ["myster", "dark", "night", "fog", "forest", "secret", "space", "dream",
                   "ghost", "midnight", "moon", "cave", "ancient", "magic", "3am", "3 am"],
    "dissonant": ["tense", "horror", "chaos", "anxious", "anxiety", "scary", "glitch", "panic",
                  "danger", "creepy", "nightmare", "villain", "storm", "angry"],
    "jazzy": ["jazz", "cafe", "coffee", "smooth", "lounge", "cocktail", "city", "sophist",
              "elegant", "bar", "candle", "late"],
    "swingy": ["swing", "blues", "groove", "funky", "bounce", "strut", "dance hall", "retro",
               "old school", "saloon", "shuffle"],
}
_INSTR = {"sad": "piano", "happy": "guitar", "pop": "synth", "mysterious": "electric-piano",
          "dissonant": "strings", "jazzy": "electric-piano", "swingy": "piano"}
_TITLES = {
    "sad": ["Window Rain", "Last Light", "Paper Boats", "Quiet Kitchen"],
    "happy": ["Lemon Sky", "Bike Bells", "Open Windows", "Good Morning Kite"],
    "pop": ["Neon Hallway", "Backseat Echo", "Glow Up", "Summer Static"],
    "mysterious": ["Fog Lantern", "Hidden Door", "Moth Light", "Under Stone"],
    "dissonant": ["Broken Signal", "Cold Static", "Wrong Stairs", "Splinter"],
    "jazzy": ["Velvet Corner", "Two Sugars", "Late Taxi", "Smoke Ring"],
    "swingy": ["Shoeshine Strut", "Porch Shuffle", "Brass Pocket", "Saturday Strut"],
}


def fallback(text: str, n: int) -> dict:
    t = text.lower()
    scores = {v: sum(t.count(k) for k in kws) for v, kws in _KEYWORDS.items()}
    vibe = max(VIBE_ORDER, key=lambda v: (scores[v], -VIBE_ORDER.index(v)))
    if scores[vibe] == 0:
        vibe = "pop"
    v = VIBES[vibe]
    key = "A" if vibe in ("sad", "mysterious") else "C"
    matched = [k for k in _KEYWORDS[vibe] if k in t][:2]
    why = (f"Matched “{'”, “'.join(matched)}” to a {v.label.lower()} feel."
           if matched else "No strong mood words found, so here's something catchy.")
    return {"vibe": vibe, "key": key, "tempo_bpm": sum(v.tempo) // 2,
            "instrument": _INSTR[vibe], "titles": _TITLES[vibe][:n], "reason": why}


def interpret(text: str, n: int = 4) -> dict:
    """Returns settings plus {"source": "gemini"|"fallback", "model": ..., "note": ...}."""
    global _working_model
    key = _load_key()
    if not key:
        out = fallback(text, n)
        out.update(source="fallback", model=None,
                   note="Gemini isn't configured (no GEMINI_API_KEY); used keyword matching.")
        return out
    prompt = PROMPT.format(text=text.replace('"', "'")[:300], menu=_vibe_menu(),
                           vibes=VIBE_ORDER, keys=KEYS, instruments=INSTRUMENTS, n=n)
    models = [os.environ["GEMINI_MODEL"]] if os.environ.get("GEMINI_MODEL") else []
    models += [_working_model] if _working_model else []
    models += [m for m in MODEL_CANDIDATES if m not in models]
    last_err = ""
    for model in models:
        try:
            out = _parse(_call(model, prompt, key), n)
            _working_model = model
            out.update(source="gemini", model=model, note=None)
            return out
        except urllib.error.HTTPError as e:
            last_err = f"{model}: HTTP {e.code}"
            if e.code in (401, 403):          # bad key: no point trying other models
                break
        except Exception as e:  # noqa: BLE001  (network, timeout, bad JSON)
            last_err = f"{model}: {type(e).__name__}"
    out = fallback(text, n)
    out.update(source="fallback", model=None,
               note=f"Gemini was unavailable ({last_err}); used keyword matching.")
    return out


def load_dotenv(path: str) -> None:
    """Tiny .env reader (KEY=value lines) so we don't need python-dotenv."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass
