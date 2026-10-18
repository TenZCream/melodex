# Melodex API Contract (v1)

Base URL (local): `http://localhost:8000`
Interactive docs once the server runs: `http://localhost:8000/docs`

All responses are JSON. Errors use FastAPI's shape: `{ "detail": "human-readable message" }`.
CORS is open for `http://localhost:5173` (Vite's default dev port).

Mock responses for building the frontend live in `frontend-mocks/`.

---

## Shared types

### Note
```json
{ "pitch": 64, "name": "E4", "start": 0.0, "duration": 0.5 }
```
- `pitch` — MIDI note number (60 = middle C). Integer.
- `name` — display name. Optional on input, always present on output.
- `start`, `duration` — in **seconds** for things you recorded/played, in **beats** for
  indexed melodies (use `tempo_bpm` to convert: `seconds = beats * 60 / tempo_bpm`).
  Only relative timing matters for search, so any consistent unit is accepted on input.

### MatchLabel
`"strong"` | `"possible"` | `"weak"` — show this to users. `score` (0–1) is secondary.
It is a calibrated similarity, **not** a probability.

---

## GET /api/health
```json
{ "status": "ok", "version": "0.1.0", "index_size": 30 }
```

## POST /api/search/notes
For the on-screen piano (or any note list).

Request:
```json
{
  "notes": [ { "pitch": 64, "start": 0.0, "duration": 0.5 }, ... ],
  "top_k": 5
}
```
- `notes`: at least **4** notes, at most 200. Must be monophonic (one note at a time).
- `top_k`: optional, default 5, max 20.

Response: **SearchResponse** (below).

## POST /api/search/audio
For mic recordings. `multipart/form-data`:
- `file` — a **WAV** file (mono or stereo, 16-bit PCM or 32-bit float, any sample rate).
  Max 30 seconds / 10 MB. Use `recordWav.js` from `frontend-helpers/` to produce it.
- `top_k` — optional form field, default 5.

Response: **SearchResponse**, with `query.source = "audio"` and `query.pitch_track` filled.

## SearchResponse
```json
{
  "query": {
    "source": "audio",
    "notes": [ Note, ... ],
    "num_notes": 13,
    "key": "C major",
    "pitch_track": {
      "times": [0.0, 0.02, ...],
      "midi":  [63.9, 64.1, null, ...]
    }
  },
  "verdict": {
    "label": "strong",
    "message": "This sounds like “Ode to Joy (Symphony No. 9)”."
  },
  "results": [
    {
      "rank": 1,
      "id": "famous-002",
      "title": "Ode to Joy (Symphony No. 9)",
      "composer": "Ludwig van Beethoven",
      "collection": "Public-domain classics",
      "license": "Public domain",
      "label": "strong",
      "score": 0.93,
      "matched_segment": {
        "start_index": 0,
        "end_index": 12,
        "notes": [ Note, ... ]
      },
      "transpose_semitones": -2,
      "tempo_bpm": 120
    }
  ],
  "index_size": 30,
  "warnings": []
}
```
- `pitch_track` is `null` for `/api/search/notes`. In audio mode, `midi` has `null` where
  no pitch was detected (silence/noise). Use it to draw the raw pitch curve behind the
  detected notes in the piano roll.
- `verdict.label` is the top result's label, or `"none"` if nothing is close
  (then `message` is e.g. “No close match among 30 indexed melodies.”).
- `matched_segment.notes` are in **beats** at the original key. Add
  `transpose_semitones` to each pitch to play it in the user's key.
- `warnings` — strings to show softly, e.g. “Only 5 notes detected — try humming a longer phrase.”

Errors:
- `400` — too few notes / unreadable audio / not a WAV
- `413` — file too large or too long

## GET /api/melodies
```json
{ "melodies": [ { "id": "famous-001", "title": "...", "composer": "...", "num_notes": 42 } ] }
```

## GET /api/melodies/{id}
```json
{
  "id": "famous-001", "title": "...", "composer": "...", "collection": "...",
  "license": "Public domain", "tempo_bpm": 100, "key": "C major",
  "notes": [ Note, ... ]
}
```

---

## GET /api/vibes
The vibe list for a picker, plus the keys for a key selector. Mock: `frontend-mocks/vibes.json`.
```json
{
  "vibes": [
    { "id": "happy", "label": "Happy", "description": "Bright and bouncy: ...",
      "tempo": [112, 132], "swing": false, "mode": "major" },
    ...  // happy, sad, pop, mysterious, dissonant, jazzy, swingy
  ],
  "keys": ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
}
```

## POST /api/generate  (Explore)
Generate new melodic ideas, each checked against the index. Mocks:
`generate_from_hum.json` (from a hum, no vibe), `generate_fresh.json` ("Surprise me"),
`generate_jazzy.json` (vibe = jazzy).

Request (all fields optional):
```json
{
  "notes": [ { "pitch": 58, "start": 0.3, "duration": 0.5 }, ... ],
  "vibe": "jazzy",
  "key": "D",
  "num_ideas": 4,
  "seed": null
}
```
- `notes`: the user's phrase (e.g. `query.notes` from a search, in seconds) to build on.
  Omit or `[]` for fresh ideas. 1–2 notes → 400.
- `vibe`: an id from `/api/vibes`. Omit / `null` / `"surprise"` = **Surprise me**: without
  notes, every card gets a **different** vibe; with notes, the vibe is inferred
  (major → pop, minor → sad).
- `key`: tonic name (`"C"`, `"F#"`, `"Bb"` …). Omit / `"auto"` = the hum's key, or C.
  With notes, the user's phrase is moved to the new key too (`seed.notes` already is).
- `seed`: integer for repeatable results; omit it for new ideas every call.
- Errors: unknown vibe or key → 400 with a helpful `detail`.

Response:
```json
{
  "seed": { "used": true, "key": "Bb major", "num_notes": 14, "tempo_bpm": 109,
            "notes": [ Note, ... ] },
  "vibe": "jazzy",
  "ideas": [
    {
      "id": "idea-1",
      "kind": "continuation",
      "title": "Continuation",
      "description": "Jazzy answer to your phrase: ...",
      "follows_seed": true,
      "vibe": "jazzy",
      "vibe_label": "Jazzy",
      "key": "Bb major",
      "form": "AABA",
      "swing": true,
      "notes": [ Note, ... ],
      "tempo_bpm": 109,
      "novelty": { "score": 0.89, "label": "novel", "message": "...", "nearest": { ... } },
      "chords": [
        { "start": 0.0, "duration": 4.0, "roman": "ii7", "symbol": "Dm7",
          "root_pc": 2, "quality": "m7", "suffix": "m7",
          "tones": [50, 53, 57, 60], "bass": 38 }
      ]
    }
  ],
  "candidates_considered": 9,
  "too_familiar_dropped": 2,
  "index_size": 30
}
```
- **Each idea has its own `tempo_bpm`** (vibes have different tempos). Notes and chord
  `start`/`duration` are in **beats**: `seconds = beats * 60 / tempo_bpm`.
- **Swing is already applied** in the note timings (offbeat 8ths are delayed). `swing: true`
  is just for display (e.g. a "swing" tag). Don't add swing again.
- **Chords: play `tones` (MIDI note numbers) + `bass`** exactly as given — they include
  7ths/9ths for jazz etc. Convert MIDI → Hz before giving them to Tone.js.
  `symbol` is for display.
- **Transposing in the browser** (instant key change without a new request) is possible:
  add k semitones to every note pitch, chord tone and bass, and rename chords with
  `root_pc = (root_pc + k) % 12` + `suffix`. Re-requesting with `key` gives fresh ideas
  in that key instead.
- `kind`: `continuation` | `fresh` | `inversion` ("Mirror") | `sequence`.
  `follows_seed: true` → play `seed.notes` first (at `seed.tempo_bpm`), then the idea.
- `form`: the phrase shape (`AABA`, `ABAC`, `AAAB` …): which bars repeat the hook.
- `novelty.label`: `novel` (≥ 0.5) or `echoes` (0.3–0.5); ideas below 0.3 are never returned.
  Novelty is relative to the index — say "not in our index", never "original".

---

## Coming later (not built yet)
- `POST /api/explain` — Gemini explanation of a match
