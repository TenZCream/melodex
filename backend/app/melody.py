"""Melody representation + the key/tempo-invariant features used for matching."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_LETTER = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]


@dataclass
class Note:
    pitch: int        # MIDI note number (60 = middle C)
    start: float      # beats (or seconds for raw transcriptions)
    duration: float

    def to_dict(self) -> dict:
        return {"pitch": int(self.pitch), "name": midi_to_name(self.pitch),
                "start": round(float(self.start), 4), "duration": round(float(self.duration), 4)}


@dataclass
class Melody:
    id: str
    title: str
    notes: list[Note]
    artist: str = ""
    collection: str = ""
    license: str = ""
    tempo_bpm: float = 120.0
    meta: dict = field(default_factory=dict)

    @property
    def pitches(self) -> np.ndarray:
        return np.array([n.pitch for n in self.notes], dtype=np.int16)

    @property
    def onsets(self) -> np.ndarray:
        return np.array([n.start for n in self.notes], dtype=np.float64)

    @property
    def durations(self) -> np.ndarray:
        return np.array([n.duration for n in self.notes], dtype=np.float64)


def midi_to_name(p: int) -> str:
    return f"{NOTE_NAMES[int(p) % 12]}{int(p) // 12 - 1}"


def name_to_midi(name: str) -> int:
    """'C4' -> 60, 'F#5' -> 78, 'Bb3' -> 58."""
    letter = name[0].upper()
    rest = name[1:]
    acc = 0
    while rest and rest[0] in "#b":
        acc += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return 12 * (int(rest) + 1) + _LETTER[letter] + acc


def parse_notation(text: str) -> list[Note]:
    """Parse a compact note string: 'E4:1 D4:1 C4:2 r:1 ...' (durations in beats).
    A token without ':dur' reuses the previous duration."""
    notes: list[Note] = []
    t = 0.0
    dur = 1.0
    for tok in text.split():
        if ":" in tok:
            name, d = tok.split(":")
            dur = float(d)
        else:
            name = tok
        if name.lower() != "r":
            notes.append(Note(name_to_midi(name), t, dur))
        t += dur
    return notes


# ---------------------------------------------------------------- features

def intervals(pitches: np.ndarray) -> np.ndarray:
    """Semitone steps between consecutive notes (transposition-invariant)."""
    p = np.asarray(pitches, dtype=np.float64)
    return np.diff(p)


def ioi_ratios(onsets: np.ndarray, durations: np.ndarray) -> np.ndarray:
    """log2 ratio of consecutive inter-onset intervals (tempo-invariant).
    Length = n_notes - 1, aligned with `intervals` (value k describes how note k+1's
    time-slot compares to note k's)."""
    onsets = np.asarray(onsets, dtype=np.float64)
    durations = np.asarray(durations, dtype=np.float64)
    if len(onsets) < 2:
        return np.zeros(0)
    ioi = np.diff(onsets)
    ioi = np.append(ioi, durations[-1])  # last note's slot = its duration
    ioi = np.maximum(ioi, 1e-3)
    return np.clip(np.log2(ioi[1:] / ioi[:-1]), -3, 3)


def estimate_key(pitches, durations=None) -> tuple[int, str, float]:
    """Krumhansl-Schmuckler key estimate. Returns (tonic_pc, 'major'|'minor', corr)."""
    pitches = np.asarray(pitches)
    w = np.ones(len(pitches)) if durations is None else np.asarray(durations, dtype=float)
    hist = np.zeros(12)
    np.add.at(hist, pitches % 12, w)
    best = (0, "major", -2.0)
    if hist.sum() == 0:
        return best
    for tonic in range(12):
        for mode, prof in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
            c = np.corrcoef(hist, np.roll(prof, tonic))[0, 1]
            if np.isfinite(c) and c > best[2]:
                best = (tonic, mode, float(c))
    return best


KEY_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def key_name(tonic: int, mode: str) -> str:
    """Musician-friendly key spelling (flats for flat keys, e.g. 'Bb major')."""
    name = KEY_NAMES[tonic]
    if mode == "minor" and tonic in (1, 6, 8):     # C#m, F#m, G#m read better with sharps
        name = NOTE_NAMES[tonic]
    return f"{name} {mode}"
