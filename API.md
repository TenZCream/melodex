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

## POST /api/generate  (Explore)
Generate new melodic ideas, each checked against the index. Mocks:
`frontend-mocks/generate_from_hum.json`, `frontend-mocks/generate_fresh.json`.

Request:
```json
{
  "notes": [ { "pitch": 58, "start": 0.3, "duration": 0.5 }, ... ],
  "num_ideas": 4,
  "seed": null
}
```
- `notes`: optional. Pass the user's phrase (e.g. `query.notes` from a search response,
  in seconds) to build on it. Omit or send `[]` for fresh ideas in C major.
  1–2 notes → 400. At least 3 notes to build on.
- `num_ideas`: optional, 1–8, default 4.
- `seed`: optional integer for repeatable results. Omit it to get new ideas every call
  (use that for a "Generate again" button).

Response:
```json
{
  "seed": {
    "used": true, "key": "Bb major", "num_notes": 14, "tempo_bpm": 109,
    "notes": [ Note, ... ]
  },
  "ideas": [
    {
      "id": "idea-1",
      "kind": "continuation",
      "title": "Continuation",
      "description": "What could come next: picks up where you stopped and brings it home.",
      "follows_seed": true,
      "notes": [ Note, ... ],
      "tempo_bpm": 109,
      "novelty": {
        "score": 0.89,
        "label": "novel",
        "message": "Not found among our 30 indexed melodies. Closest: “Jingle Bells” (11% similar).",
        "nearest": { "id": "famous-005", "title": "Jingle Bells", "composer": "...", "similarity": 0.11 }
      },
      "chords": [ { "start": 0.0, "duration": 2.0, "roman": "I", "symbol": "Bb" }, ... ]
    }
  ],
  "candidates_considered": 37,
  "too_familiar_dropped": 7,
  "index_size": 30
}
```
- All `notes`, `chords[].start` and `chords[].duration` here are in **beats**.
  Play with `seconds = beats * 60 / tempo_bpm`. `seed.notes` is the user's phrase
  converted to beats at the same tempo.
- `kind`: `continuation` | `inversion` (shown as "Mirror") | `sequence` | `rhythm`
  (shown as "Rhythm flip") | `fresh`.
- `follows_seed: true` means the idea is meant to be heard **right after** the user's
  phrase: play `seed.notes`, then the idea's notes.
- `novelty.label`: `novel` (score ≥ 0.5) or `echoes` (0.3–0.5). Ideas below 0.3
  (too close to a known melody) are never returned; `too_familiar_dropped` counts them.
- Novelty is always relative to the index. Say "not found in our index", never
  "original".
- Chords: one diatonic triad per 2 beats, ending on the home chord. Play them softly
  under the melody (e.g. a pad playing the triad), or show them as labels above the notes.

---

## Coming later (not built yet)
- `POST /api/explain` — Gemini explanation of a match
