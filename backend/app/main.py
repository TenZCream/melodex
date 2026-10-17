"""Melodex API. Run from the backend folder:

    uvicorn app.main:app --reload --port 8000

Docs: http://localhost:8000/docs   ·   Contract: ../API.md
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .catalog import load_catalog
from .generate import Explorer, novelty_label
from .melody import Note, midi_to_name
from .pitch import AudioError, transcribe
from .search import MIN_QUERY_NOTES, MelodyIndex, describe_key

VERSION = "0.1.0"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PITCH_TRACK_POINTS = 600   # downsample the per-frame curve for the frontend
DEBUG_DIR = Path(__file__).resolve().parent.parent / "debug_recordings"
DEBUG_KEEP = 10
TIE_MARGIN = 0.05

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Melodex API", version=VERSION,
              description="Hum it. Find it. Then find something new.")
app.add_middleware(
    CORSMiddleware,
    # any Vite dev port (5173, 5174, ...) on this machine
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

INDEX = MelodyIndex(load_catalog())
EXPLORER = Explorer(INDEX)


# ------------------------------------------------------------------ models

class NoteIn(BaseModel):
    pitch: int = Field(ge=0, le=127)
    start: float = Field(ge=0)
    duration: float = Field(gt=0)
    name: str | None = None


class GenerateRequest(BaseModel):
    notes: list[NoteIn] = Field(default_factory=list, max_length=200)
    num_ideas: int = Field(default=4, ge=1, le=8)
    seed: int | None = None


class NotesSearchRequest(BaseModel):
    notes: list[NoteIn] = Field(min_length=1, max_length=200)
    top_k: int = Field(default=5, ge=1, le=20)


# ------------------------------------------------------------------ helpers

def _note_out(pitch, start, duration) -> dict:
    return Note(int(pitch), float(start), float(duration)).to_dict()


def _run_search(pitches, onsets, durations, top_k, source, pitch_track=None, warnings=None):
    warnings = list(warnings or [])
    n = len(pitches)
    if n < MIN_QUERY_NOTES:
        log.info("search rejected: %d notes", n)
    if n == 0:
        raise HTTPException(400, "We couldn't hear a melody. Try humming louder, closer to the "
                                 "mic, or in a quieter spot.")
    if n < MIN_QUERY_NOTES:
        raise HTTPException(400, f"Only {n} note{'s' if n != 1 else ''} detected. "
                                 f"Hum a longer phrase (at least {MIN_QUERY_NOTES} notes).")
    if n < 6:
        warnings.append(f"Only {n} notes — a longer phrase gives better matches.")

    hits = INDEX.search(pitches, onsets, durations, top_k=top_k)
    results = []
    for rank, h in enumerate(hits, start=1):
        m = h.melody
        seg = m.notes[h.start_note:h.end_note + 1]
        results.append({
            "rank": rank,
            "id": m.id,
            "title": m.title,
            "composer": m.artist,
            "collection": m.collection,
            "license": m.license,
            "label": h.label,
            "score": round(h.score, 3),
            "matched_segment": {
                "start_index": h.start_note,
                "end_index": h.end_note,
                "notes": [n.to_dict() for n in seg],
            },
            "transpose_semitones": h.transpose,
            "tempo_bpm": m.tempo_bpm,
        })

    top = results[0] if results else None
    runner = results[1] if len(results) > 1 else None
    # a near-tie between the top two means we can't honestly be sure
    if top and runner and top["label"] == "strong" and runner["score"] >= top["score"] - TIE_MARGIN:
        verdict = {"label": "possible",
                   "message": f"This might be “{top['title']}” or “{runner['title']}”. "
                              "Try a longer phrase to tell them apart."}
    elif top and top["label"] == "strong":
        verdict = {"label": "strong", "message": f"This sounds like “{top['title']}”."}
    elif top and top["label"] == "possible":
        verdict = {"label": "possible", "message": f"This might be “{top['title']}”."}
    else:
        verdict = {"label": "none",
                   "message": f"No close match among {len(INDEX)} indexed melodies."}

    return {
        "query": {
            "source": source,
            "notes": [_note_out(p, o, d) for p, o, d in zip(pitches, onsets, durations)],
            "num_notes": n,
            "key": describe_key(pitches, durations),
            "pitch_track": pitch_track,
        },
        "verdict": verdict,
        "results": results,
        "index_size": len(INDEX),
        "warnings": warnings,
    }


def _downsample_track(times: np.ndarray, midi: np.ndarray) -> dict:
    step = max(1, int(np.ceil(len(times) / PITCH_TRACK_POINTS)))
    t = times[::step]
    m = midi[::step]
    return {
        "times": [round(float(x), 3) for x in t],
        "midi": [None if np.isnan(x) else round(float(x), 2) for x in m],
    }


# ------------------------------------------------------------------ routes

@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION, "index_size": len(INDEX)}


@app.post("/api/search/notes")
def search_notes(req: NotesSearchRequest):
    notes = sorted(req.notes, key=lambda n: n.start)
    pitches = np.array([n.pitch for n in notes])
    onsets = np.array([n.start for n in notes], dtype=float)
    durs = np.array([n.duration for n in notes], dtype=float)
    return _run_search(pitches, onsets - onsets[0], durs, req.top_k, "notes")


def _save_debug_recording(data: bytes, outcome: str) -> None:
    """Keep the last few recordings locally for tuning (folder is gitignored).
    Disable with MELODEX_SAVE_RECORDINGS=0."""
    if os.environ.get("MELODEX_SAVE_RECORDINGS", "1") == "0":
        return
    try:
        DEBUG_DIR.mkdir(exist_ok=True)
        stamp = time.strftime("%H%M%S")
        (DEBUG_DIR / f"{stamp}_{outcome}.wav").write_bytes(data)
        files = sorted(DEBUG_DIR.glob("*.wav"))
        for old in files[:-DEBUG_KEEP]:
            old.unlink(missing_ok=True)
    except OSError:
        pass


@app.post("/api/search/audio")
async def search_audio(file: UploadFile = File(...), top_k: int = Form(5)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 10 MB).")
    top_k = int(min(max(top_k, 1), 20))
    try:
        tx = transcribe(data)
    except AudioError as e:
        _save_debug_recording(data, "unreadable")
        log.info("audio rejected: %s", e)
        status = 413 if "under" in str(e) else 400
        raise HTTPException(status, str(e)) from e

    log.info("transcribed %d notes from %.1fs: %s", len(tx.notes), tx.duration_sec,
             " ".join(midi_to_name(n.pitch) for n in tx.notes))
    _save_debug_recording(data, f"{len(tx.notes)}notes")

    warnings = []
    if abs(tx.tuning_offset) > 0.3:
        warnings.append("Your pitch sat between notes; we adjusted for it.")
    pitches = np.array([n.pitch for n in tx.notes])
    onsets = np.array([n.start for n in tx.notes], dtype=float)
    durs = np.array([n.duration for n in tx.notes], dtype=float)
    return _run_search(pitches, onsets, durs, top_k, "audio",
                       pitch_track=_downsample_track(tx.times, tx.midi), warnings=warnings)


@app.post("/api/generate")
def generate(req: GenerateRequest):
    seed_notes = [Note(n.pitch, n.start, n.duration) for n in sorted(req.notes, key=lambda n: n.start)]
    if 0 < len(seed_notes) < 3:
        raise HTTPException(400, "Give at least 3 notes to build on, or none for fresh ideas.")
    out = EXPLORER.generate(seed_notes or None, num_ideas=req.num_ideas, rng_seed=req.seed)
    tempo = out["seed"]["tempo_bpm"]
    ideas = []
    for k, idea in enumerate(out["ideas"], start=1):
        label = novelty_label(idea.novelty)
        near = idea.nearest
        pct = round(near["similarity"] * 100)
        if label == "novel":
            msg = (f"Not found among our {len(INDEX)} indexed melodies. "
                   f"Closest: “{near['title']}” ({pct}% similar).")
        else:
            msg = f"Echoes “{near['title']}” ({pct}% similar) but isn't a match."
        ideas.append({
            "id": f"idea-{k}",
            "kind": idea.kind,
            "title": idea.title,
            "description": idea.description,
            "follows_seed": idea.kind == "continuation",
            "notes": [n.to_dict() for n in idea.notes],
            "tempo_bpm": tempo,
            "novelty": {"score": idea.novelty, "label": label, "message": msg,
                        "nearest": near},
            "chords": idea.chords,
        })
    seed = out["seed"]
    return {
        "seed": {**seed, "notes": [n.to_dict() for n in seed["notes"]]},
        "ideas": ideas,
        "candidates_considered": out["candidates_considered"],
        "too_familiar_dropped": out["too_familiar_dropped"],
        "index_size": len(INDEX),
    }


@app.get("/api/melodies")
def list_melodies():
    return {"melodies": [
        {"id": m.id, "title": m.title, "composer": m.artist, "num_notes": len(m.notes)}
        for m in INDEX.melodies
    ]}


@app.get("/api/melodies/{melody_id}")
def get_melody(melody_id: str):
    m = INDEX.by_id.get(melody_id)
    if m is None:
        raise HTTPException(404, "Melody not found.")
    return {
        "id": m.id, "title": m.title, "composer": m.artist, "collection": m.collection,
        "license": m.license, "tempo_bpm": m.tempo_bpm,
        "key": describe_key(m.pitches, m.durations),
        "notes": [n.to_dict() for n in m.notes],
    }


__all__ = ["app", "midi_to_name"]
