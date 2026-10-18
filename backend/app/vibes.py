"""Vibe engine: composes melodies with a distinct character per vibe.

Melody first. Each vibe defines how the *melody* behaves (intervals, rhythm cells,
direction, rests, ornaments, how phrases end, how the hook repeats), plus the scale,
chords (with 7ths/extensions where it fits), tempo and swing that support it.

Pitches are semitone offsets from the tonic (0 = tonic, 12 = tonic an octave up), so
non-scale notes (blue notes, chromatic approaches, tritones) are easy to express.

Pipeline per idea:
  hook (1 bar) -> phrase built from a form like AABA / ABAC / AAAB, where A' is the hook
  re-fitted to the new chord and slightly varied -> ornaments (sighs, chromatic
  approaches, blue notes) -> optional climax -> ending (resolved or open) -> swing.
Many candidates are composed and scored against the vibe's target profile; the best
are kept.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

BAR = 4.0

# ------------------------------------------------------------------ chords

QUALITY_TONES = {
    "maj": [0, 4, 7], "min": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8],
    "sus4": [0, 5, 7], "sus2": [0, 2, 7], "add9": [0, 4, 7, 14],
    "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "7": [0, 4, 7, 10],
    "m7b5": [0, 3, 6, 10], "dim7": [0, 3, 6, 9], "m(maj7)": [0, 3, 7, 11],
    "maj9": [0, 4, 7, 11, 14], "m9": [0, 3, 7, 10, 14], "9": [0, 4, 7, 10, 14],
    "7b9": [0, 4, 7, 10, 13], "7#9": [0, 4, 7, 10, 15], "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9],
}
QUALITY_SUFFIX = {
    "maj": "", "min": "m", "dim": "dim", "aug": "aug", "sus4": "sus4", "sus2": "sus2",
    "add9": "add9", "maj7": "maj7", "m7": "m7", "7": "7", "m7b5": "m7b5", "dim7": "dim7",
    "m(maj7)": "m(maj7)", "maj9": "maj9", "m9": "m9", "9": "9", "7b9": "7b9", "7#9": "7#9",
    "6": "6", "m6": "m6",
}
CHORD_FLOOR = 48   # C3: lowest chord tone (laptop speakers can't reproduce much lower)
BASS_FLOOR = 33    # A1 (bass may sit low; chords carry the harmony on small speakers)
NOTE_NAMES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


@dataclass
class Chord:
    root: int          # semitones above the tonic
    quality: str
    roman: str
    beats: float = BAR

    @property
    def tones(self) -> list[int]:
        return [self.root + t for t in QUALITY_TONES[self.quality]]

    def pcs(self) -> set[int]:
        return {t % 12 for t in self.tones}


def C(root, quality, roman, beats=BAR):
    return Chord(root, quality, roman, beats)


# ------------------------------------------------------------------ vibe presets

@dataclass
class Vibe:
    id: str
    label: str
    description: str
    scale: list[int]
    progressions: list[list[Chord]]
    tempo: tuple[int, int]
    swing: float                      # 0.5 = straight, ~0.66 = triplet swing
    rhythms: list[tuple[list[float], float]]   # bar rhythms (negative = rest), weight
    forms: list[str]
    # interval preferences (relative weights) for |interval| in semitones
    w_repeat: float = 0.25
    w_step: float = 1.0               # 1-2
    w_small: float = 0.5              # 3-4
    w_leap: float = 0.15              # 5, 7-9
    w_tritone: float = 0.01           # 6
    w_big: float = 0.02               # 10+
    direction: float = 0.0            # >0 upward bias, <0 downward
    chord_tone_strong: float = 0.85   # share of strong beats on chord tones
    extra_pcs: list[int] = field(default_factory=list)   # e.g. blue notes
    sigh: float = 0.0                 # falling appoggiatura on strong beats
    approach: float = 0.0             # chromatic approach into strong-beat targets
    blue: float = 0.0                 # bend 3rd/7th down on weak beats
    climax: float = 0.5               # chance of one clear high point
    end_tonic: float = 0.85           # chance the phrase resolves home
    center: int = 7                   # melody register centre (semitones above tonic)
    spread: float = 6.0               # register spread
    open_endings: list[int] = field(default_factory=lambda: [4, 7])   # where unresolved endings land
    targets: dict = field(default_factory=dict)          # scoring profile
    mode_label: str = "major"

    def public(self) -> dict:
        return {"id": self.id, "label": self.label, "description": self.description,
                "tempo": list(self.tempo), "swing": self.swing > 0.55, "mode": self.mode_label}


MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
DORIAN = [0, 2, 3, 5, 7, 9, 10]
PHRYGIAN = [0, 1, 3, 5, 7, 8, 10]
HARMONIC_MINOR = [0, 2, 3, 5, 7, 8, 11]
CHROMATIC = list(range(12))

VIBES: dict[str, Vibe] = {}


def _add(v: Vibe):
    VIBES[v.id] = v


_add(Vibe(
    "happy", "Happy", "Bright and bouncy: upward leaps, a hook that comes back, a firm ending.",
    MAJOR,
    [[C(0, "maj", "I"), C(5, "maj", "IV"), C(7, "maj", "V"), C(0, "maj", "I")],
     [C(0, "maj", "I"), C(9, "min", "vi"), C(5, "maj", "IV"), C(7, "maj", "V")],
     [C(0, "maj", "I"), C(5, "maj", "IV"), C(0, "maj", "I"), C(7, "7", "V7")],
     [C(5, "maj", "IV"), C(7, "maj", "V"), C(0, "maj", "I"), C(0, "maj", "I")]],
    (112, 132), 0.5,
    [([1, 0.5, 0.5, 1, 1], 3), ([1.5, 0.5, 1, 1], 3), ([0.5, 0.5, 1, 0.5, 0.5, 1], 2),
     ([1, 1, 1, 1], 2), ([0.75, 0.25, 1, 0.75, 0.25, 1], 2), ([1, 1, 2], 1)],
    ["AABA", "ABAB", "AABC"],
    w_step=1.0, w_small=0.7, w_leap=0.35, direction=0.25, chord_tone_strong=0.9,
    climax=0.6, end_tonic=0.9, center=7,
    targets={"step": (0.45, 0.7), "leap": (0.08, 0.25), "ct_strong": (0.8, 1.0),
             "rest": (0, 0.05), "slope": (-0.1, 0.5), "ends_tonic": (1, 1),
             "density": (1.0, 2.0), "tritone": (0, 0.02)},
))

_add(Vibe(
    "sad", "Sad", "Slow and falling: long notes, sighing figures, minor color; may not fully resolve.",
    MINOR,
    [[C(0, "min", "i"), C(8, "maj", "VI"), C(3, "maj", "III"), C(10, "maj", "VII")],
     [C(0, "min", "i"), C(5, "min", "iv"), C(0, "min", "i"), C(7, "maj", "V")],
     [C(0, "min", "i"), C(8, "maj7", "VImaj7"), C(5, "m7", "iv7"), C(7, "7", "V7")],
     [C(8, "maj", "VI"), C(10, "maj", "VII"), C(0, "min", "i"), C(0, "min", "i")],
     [C(0, "m7", "i7"), C(5, "m7", "iv7"), C(10, "maj", "VII"), C(3, "maj7", "IIImaj7")]],
    (64, 80), 0.5,
    [([2, 2], 3), ([3, 1], 2), ([1, 1, 2], 3), ([1.5, 0.5, 2], 3), ([2, 1, 1], 2),
     ([1, 1, -1, 1], 1), ([3, -1], 1)],
    ["ABAC", "AABA", "ABAB"],
    w_repeat=0.2, w_step=1.0, w_small=0.35, w_leap=0.1, direction=-0.35, mode_label="minor",
    chord_tone_strong=0.75, sigh=0.4, climax=0.35, end_tonic=0.55, center=5, spread=5,
    open_endings=[3, 7, 2],
    targets={"step": (0.6, 0.9), "leap": (0, 0.12), "rest": (0, 0.15), "slope": (-0.6, -0.05),
             "density": (0.5, 1.1), "ct_strong": (0.55, 0.9), "tritone": (0, 0.02)},
))

_add(Vibe(
    "pop", "Pop", "Catchy and singable: one short syncopated hook, repeated with small changes.",
    MAJOR,
    [[C(0, "maj", "I"), C(7, "maj", "V"), C(9, "min", "vi"), C(5, "maj", "IV")],
     [C(9, "min", "vi"), C(5, "maj", "IV"), C(0, "maj", "I"), C(7, "maj", "V")],
     [C(0, "maj", "I"), C(9, "min", "vi"), C(5, "maj", "IV"), C(7, "maj", "V")],
     [C(5, "add9", "IVadd9"), C(0, "maj", "I"), C(7, "maj", "V"), C(9, "min", "vi")]],
    (96, 118), 0.5,
    [([1, 0.5, 1, 0.5, 1], 4), ([0.5, 1, 0.5, 1, 1], 3), ([1.5, 1.5, 1], 3),
     ([0.5, 0.5, 0.5, 1, 0.5, 1], 2), ([1, 0.5, 0.5, 0.5, 1.5], 2), ([-0.5, 0.5, 1, 0.5, 1.5], 2)],
    ["AABA", "ABAB", "AAAB"],
    w_repeat=0.45, w_step=1.0, w_small=0.6, w_leap=0.12, direction=0.0,
    chord_tone_strong=0.85, climax=0.4, end_tonic=0.8, center=5, spread=4,
    targets={"step": (0.5, 0.8), "leap": (0, 0.12), "synco": (0.2, 0.6), "range": (5, 12),
             "ct_strong": (0.75, 1.0), "hook": (0.6, 1.0), "tritone": (0, 0.02)},
))

_add(Vibe(
    "mysterious", "Mysterious", "Sparse and modal: creeping half-steps, space between notes, open endings.",
    DORIAN,
    [[C(0, "m7", "i7"), C(5, "7", "IV7"), C(0, "m7", "i7"), C(10, "maj", "bVII")],
     [C(0, "min", "i"), C(1, "maj", "bII"), C(0, "min", "i"), C(10, "min", "bvii")],
     [C(0, "sus2", "isus2"), C(8, "maj7", "bVImaj7"), C(1, "maj", "bII"), C(0, "min", "i")],
     [C(0, "m(maj7)", "i(maj7)"), C(5, "m6", "iv6"), C(8, "maj", "bVI"), C(7, "sus4", "Vsus4")]],
    (70, 92), 0.5,
    [([1, -1, 1, 1], 3), ([2, -1, 1], 3), ([1.5, 0.5, -2], 2), ([1, 1, -0.5, 1.5], 2),
     ([-1, 1, 1, 1], 2), ([3, -1], 1), ([0.5, 0.5, -1, 2], 1)],
    ["ABAC", "ABCA", "AABA"],
    w_repeat=0.3, w_step=1.2, w_small=0.4, w_leap=0.18, w_tritone=0.08, direction=0.0,
    mode_label="minor (modal)", chord_tone_strong=0.6, extra_pcs=[1, 9], climax=0.3, end_tonic=0.3, center=5, spread=6,
    open_endings=[1, 2, 7, 10],
    targets={"rest": (0.1, 0.35), "half": (0.15, 0.45), "ends_tonic": (0, 0), "density": (0.5, 1.2),
             "ct_strong": (0.4, 0.8)},
))

_add(Vibe(
    "dissonant", "Dissonant", "Tense and unsettled: tritones, chromatic clashes, jagged leaps, no easy resolution.",
    CHROMATIC,
    [[C(0, "min", "i"), C(6, "dim7", "#IVdim7"), C(1, "maj", "bII"), C(0, "m(maj7)", "i(maj7)")],
     [C(0, "dim7", "idim7"), C(11, "aug", "VIIaug"), C(6, "7b9", "bV7b9"), C(1, "7", "bII7")],
     [C(0, "m7b5", "iø7"), C(6, "maj", "bV"), C(5, "dim", "ivdim"), C(11, "7b9", "VII7b9")],
     [C(0, "aug", "Iaug"), C(3, "dim7", "bIIIdim7"), C(8, "7#9", "bVI7#9"), C(1, "maj7", "bIImaj7")]],
    (80, 108), 0.5,
    [([1.5, 1.5, 1], 3), ([0.5, 1.5, 0.5, 1.5], 3), ([1, 0.5, 1.5, 1], 2), ([3, 1], 1),
     ([0.5, 0.5, 1.5, -0.5, 1], 2), ([0.75, 0.75, 0.5, 2], 2)],
    ["ABCD", "ABAC", "ABCA"],
    w_repeat=0.15, w_step=0.8, w_small=0.6, w_leap=0.6, w_tritone=0.9, w_big=0.15,
    mode_label="(chromatic)", chord_tone_strong=0.35, climax=0.5, end_tonic=0.15, center=6, spread=8,
    open_endings=[1, 6, 11, 10],
    targets={"tritone": (0.08, 0.35), "leap": (0.2, 0.5), "ct_strong": (0.1, 0.55),
             "ends_tonic": (0, 0), "half": (0.1, 0.4)},
))

_add(Vibe(
    "jazzy", "Jazzy", "Swung 8ths over 7th chords: chord-tone arpeggios, chromatic approach notes.",
    MAJOR,
    [[C(2, "m7", "ii7"), C(7, "7", "V7"), C(0, "maj7", "Imaj7"), C(0, "maj7", "Imaj7")],
     [C(0, "maj7", "Imaj7"), C(9, "m7", "vi7"), C(2, "m7", "ii7"), C(7, "7", "V7")],
     [C(4, "m7", "iii7"), C(9, "7", "VI7"), C(2, "m7", "ii7"), C(7, "7", "V7")],
     [C(0, "maj9", "Imaj9"), C(2, "m9", "ii9"), C(4, "m7", "iii7"), C(7, "9", "V9")],
     [C(2, "m7", "ii7", 2), C(7, "7", "V7", 2), C(0, "maj7", "Imaj7"),
      C(4, "m7", "iii7", 2), C(9, "7", "VI7", 2), C(2, "m7", "ii7", 2), C(7, "7", "V7", 2)]],
    (112, 150), 0.64,
    [([0.5, 0.5, 0.5, 0.5, 1, 1], 3), ([1, 0.5, 0.5, 0.5, 0.5, 1], 3), ([0.5, 1, 0.5, 1, 1], 3),
     ([1.5, 0.5, 0.5, 0.5, 1], 2), ([-0.5, 0.5, 0.5, 0.5, 1, 1], 2), ([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1], 1)],
    ["ABAC", "AABA", "ABCB"],
    w_repeat=0.15, w_step=1.0, w_small=0.9, w_leap=0.25, direction=0.0,
    chord_tone_strong=0.85, approach=0.4, blue=0.08, climax=0.5, end_tonic=0.35,
    center=7, spread=6, open_endings=[4, 9, 2, 11],
    targets={"density": (1.5, 3.0), "chromatic": (0.08, 0.35), "ct_strong": (0.7, 1.0),
             "synco": (0.15, 0.5), "tritone": (0, 0.06)},
))

_add(Vibe(
    "swingy", "Swingy", "Bluesy swing: short riffs repeated call-and-response, blue notes, laid-back feel.",
    [0, 2, 3, 4, 5, 7, 9, 10],
    [[C(0, "7", "I7"), C(5, "7", "IV7"), C(0, "7", "I7"), C(7, "7", "V7")],
     [C(0, "7", "I7"), C(0, "7", "I7"), C(5, "7", "IV7"), C(0, "7", "I7")],
     [C(5, "7", "IV7"), C(5, "7", "IV7"), C(0, "7", "I7"), C(7, "7", "V7")],
     [C(0, "6", "I6"), C(5, "9", "IV9"), C(0, "6", "I6"), C(7, "7#9", "V7#9")]],
    (100, 132), 0.66,
    [([0.5, 0.5, 1, 0.5, 1.5], 3), ([1, 0.5, 1, 1.5], 3), ([0.5, 0.5, 0.5, 0.5, 2], 2),
     ([-0.5, 0.5, 0.5, 0.5, 2], 3), ([0.5, 1, 0.5, 2], 2)],
    ["AAAB", "AABA", "AAAB"],
    w_repeat=0.5, w_step=1.0, w_small=0.8, w_leap=0.2, direction=0.0,
    mode_label="blues", chord_tone_strong=0.75, extra_pcs=[3, 6, 10], blue=0.35, approach=0.15,
    climax=0.25, end_tonic=0.75, center=5, spread=5,
    targets={"blue": (0.1, 0.4), "hook": (0.6, 1.0), "synco": (0.25, 0.7), "tritone": (0, 0.1)},
))

VIBE_ORDER = ["happy", "sad", "pop", "mysterious", "dissonant", "jazzy", "swingy"]


# ------------------------------------------------------------------ composing

@dataclass
class Event:
    pitch: int | None     # semitones above tonic; None = rest
    start: float
    dur: float
    strong: bool


def _weighted(options, rng):
    w = np.array([o[1] for o in options], dtype=float)
    return options[rng.choice(len(options), p=w / w.sum())][0]


def _interval_weight(v: Vibe, iv: int) -> float:
    a = abs(iv)
    if a == 0:
        w = v.w_repeat
    elif a <= 2:
        w = v.w_step
    elif a <= 4:
        w = v.w_small
    elif a == 6:
        w = v.w_tritone
    elif a <= 9:
        w = v.w_leap
    else:
        w = v.w_big
    if iv != 0:
        w *= max(0.05, 1.0 + v.direction * np.sign(iv))
    return w


def _allowed_pcs(v: Vibe, chord: Chord) -> set[int]:
    return set(p % 12 for p in v.scale) | chord.pcs() | set(v.extra_pcs)


def _pick_pitch(v: Vibe, chord: Chord, prev: int, strong: bool, rng, lo: int, hi: int) -> int:
    allowed = _allowed_pcs(v, chord)
    chord_pcs = chord.pcs()
    cands, weights = [], []
    for p in range(lo, hi + 1):
        if p % 12 not in allowed:
            continue
        w = _interval_weight(v, p - prev)
        if strong:
            w *= (v.chord_tone_strong if p % 12 in chord_pcs else (1 - v.chord_tone_strong)) * 2
        w *= np.exp(-((p - v.center) / v.spread) ** 2 / 2)
        cands.append(p)
        weights.append(w)
    w = np.array(weights)
    return int(cands[rng.choice(len(cands), p=w / w.sum())])


def _bar(v: Vibe, chord_at, rhythm, bar_start, prev, rng, lo, hi) -> list[Event]:
    out, t = [], 0.0
    for d in rhythm:
        absd = abs(d)
        pos = bar_start + t
        strong = abs(t - round(t)) < 1e-6 and int(round(t)) % 2 == 0
        if d < 0:
            out.append(Event(None, pos, absd, strong))
        else:
            p = _pick_pitch(v, chord_at(pos), prev, strong, rng, lo, hi)
            out.append(Event(p, pos, absd, strong))
            prev = p
        t += absd
    return out


def _refit(v: Vibe, hook: list[Event], hook_chord: Chord, chord_at, bar_start, prev, rng, lo, hi,
           vary: float) -> list[Event]:
    """Re-use the hook's rhythm and interval shape over a new chord (A')."""
    notes = [e for e in hook if e.pitch is not None]
    if not notes:
        return [Event(None, bar_start + (e.start - hook[0].start), e.dur, e.strong) for e in hook]
    first = notes[0].pitch
    new_chord = chord_at(bar_start)
    # keep the hook's first note in the same role (root/3rd/5th...) of the new chord
    role = min(range(len(hook_chord.tones)),
               key=lambda i: abs(((first - hook_chord.tones[i]) % 12 + 6) % 12 - 6))
    target_pc = new_chord.tones[role % len(new_chord.tones)] % 12
    start_p = min((p for p in range(lo, hi + 1) if p % 12 == target_pc), key=lambda p: abs(p - prev),
                  default=first)
    shift = start_p - first
    out = []
    offset0 = hook[0].start
    for i, e in enumerate(hook):
        pos = bar_start + (e.start - offset0)
        if e.pitch is None:
            out.append(Event(None, pos, e.dur, e.strong))
            continue
        p = e.pitch + shift
        while p > hi:                                   # out of range: move by octaves,
            p -= 12                                     # never clip (clipping lands off-key)
        while p < lo:
            p += 12
        allowed = _allowed_pcs(v, chord_at(pos))
        if p % 12 not in allowed:                       # snap to nearest allowed note
            p = min((q for q in range(p - 2, p + 3) if q % 12 in allowed), key=lambda q: abs(q - p))
        out.append(Event(p, pos, e.dur, e.strong))
    # vary the tail so A' isn't a copy-paste
    if rng.random() < vary:
        k = len(out) - 1
        while k >= 0 and out[k].pitch is None:
            k -= 1
        if k > 0:
            prevp = next((x.pitch for x in reversed(out[:k]) if x.pitch is not None), start_p)
            out[k].pitch = _pick_pitch(v, chord_at(out[k].start), prevp, out[k].strong, rng, lo, hi)
    return out


def _ornament(v: Vibe, events: list[Event], chord_at, rng):
    notes = [e for e in events if e.pitch is not None]
    for a, b in zip(notes, notes[1:]):
        ch_b = chord_at(b.start)
        # jazz/swing: chromatic approach into a strong-beat chord tone
        if v.approach and b.strong and not a.strong and b.pitch % 12 in ch_b.pcs() \
                and a.dur <= 1.0 and rng.random() < v.approach:
            a.pitch = b.pitch + (1 if rng.random() < 0.4 else -1)
        # sad: sigh — strong-beat note one scale step above, falling into the next note
        if v.sigh and a.strong and not b.strong and rng.random() < v.sigh:
            scale_pcs = {x % 12 for x in v.scale}
            above = [q for q in (b.pitch + 1, b.pitch + 2) if q % 12 in scale_pcs]
            if above:
                a.pitch = above[0]
    if v.blue:
        for e in notes:
            pc = e.pitch % 12
            if not e.strong and pc in (4, 11) and rng.random() < v.blue:
                e.pitch -= 1                             # bluesy b3 / b7
            elif not e.strong and pc == 7 and rng.random() < v.blue * 0.3:
                e.pitch -= 1                             # occasional b5


def _climax(v: Vibe, events: list[Event], bars, rng, hi):
    notes = [e for e in events if e.pitch is not None]
    if len(notes) < 6:
        return
    region = [e for e in notes if 2 * BAR <= e.start < 3.75 * BAR] or notes[len(notes) // 2:]
    top = max(notes, key=lambda e: e.pitch).pitch
    peak = max(region, key=lambda e: (e.dur, e.pitch))
    allowed = set(p % 12 for p in v.scale)
    for up in range(1, 6):
        cand = top + up
        if cand % 12 in allowed and cand <= hi + 2:
            peak.pitch = cand
            return


def _ending(v: Vibe, events: list[Event], chord_at, rng):
    notes = [e for e in events if e.pitch is not None]
    if not notes:
        return False
    last = notes[-1]
    prev = notes[-2].pitch if len(notes) > 1 else last.pitch
    resolve = rng.random() < v.end_tonic
    if resolve:
        pcs = [0]
    else:
        pcs = list(v.open_endings)
    last.pitch = min((p for p in range(prev - 9, prev + 10) if p % 12 in pcs),
                     key=lambda p: abs(p - prev))
    last.dur = max(last.dur, 1.5)
    return resolve


def _apply_swing(events: list[Event], swing: float):
    if swing <= 0.5:
        return
    shift = swing - 0.5
    for i, e in enumerate(events):
        frac = e.start % 1.0
        if abs(frac - 0.5) < 1e-6:
            e.start += shift
            e.dur = max(0.15, e.dur - shift)
            if i > 0 and abs(events[i - 1].start + events[i - 1].dur - (e.start - shift)) < 1e-6:
                events[i - 1].dur += shift


def _chord_timeline(prog: list[Chord]):
    spans, t = [], 0.0
    for ch in prog:
        spans.append((t, t + ch.beats, ch))
        t += ch.beats

    def at(pos):
        for a, b, ch in spans:
            if a - 1e-6 <= pos < b - 1e-6:
                return ch
        return spans[-1][2]
    return at, spans, t


def compose(v: Vibe, rng, start: int | None = None, motif: list[float] | None = None):
    """One 4-bar phrase for vibe `v`. Returns (events, progression, form)."""
    prog = [Chord(c.root, c.quality, c.roman, c.beats) for c in
            v.progressions[rng.integers(len(v.progressions))]]
    chord_at, spans, total = _chord_timeline(prog)
    n_bars = int(round(total / BAR))
    form = v.forms[rng.integers(len(v.forms))][:n_bars].ljust(n_bars, "A")
    lo, hi = v.center - 10, v.center + 10
    prev = start if start is not None else v.center + int(rng.integers(-3, 4))

    sections: dict[str, list[Event]] = {}
    hook_chord = chord_at(0.0)
    events: list[Event] = []
    for b, letter in enumerate(form):
        bar_start = b * BAR
        last_bar = b == n_bars - 1
        if letter in sections:
            src = sections[letter]
            bar = _refit(v, src, chord_at(src[0].start), chord_at, bar_start, prev, rng, lo, hi,
                         vary=0.6 if not last_bar else 0.3)
        else:
            rhythm = motif if (b == 0 and motif) else _weighted(v.rhythms, rng)
            if last_bar and sum(1 for d in rhythm if d > 0) > 3 and rng.random() < 0.6:
                rhythm = _weighted([(r, w) for r, w in v.rhythms
                                    if sum(1 for d in r if d > 0) <= 3] or v.rhythms, rng)
            bar = _bar(v, chord_at, rhythm, bar_start, prev, rng, lo, hi)
            sections[letter] = bar
        if b == 0:
            hook_chord = chord_at(0.0)
        events.extend(bar)
        ps = [e.pitch for e in bar if e.pitch is not None]
        if ps:
            prev = ps[-1]

    _ornament(v, events, chord_at, rng)
    if rng.random() < v.climax:
        _climax(v, events, n_bars, rng, hi)
    _ending(v, events, chord_at, rng)
    # trim trailing rests
    while events and events[-1].pitch is None:
        events.pop()
    _apply_swing(events, v.swing)
    del hook_chord
    return events, prog, form


# ------------------------------------------------------------------ scoring

def features(v: Vibe, events: list[Event], prog: list[Chord], form: str) -> dict:
    chord_at, _, total = _chord_timeline(prog)
    notes = [e for e in events if e.pitch is not None]
    p = np.array([e.pitch for e in notes])
    iv = np.diff(p) if len(p) > 1 else np.zeros(1)
    a = np.abs(iv)
    strong = [e for e in notes if e.strong]
    ct = np.mean([e.pitch % 12 in chord_at(e.start).pcs() for e in strong]) if strong else 0.5
    rest = sum(e.dur for e in events if e.pitch is None) / max(total, 1)
    synco = np.mean([abs(e.start % 1.0) > 1e-6 and e.dur >= 0.5 for e in notes]) if notes else 0
    scale_pcs = set(x % 12 for x in v.scale)
    chromatic = np.mean([e.pitch % 12 not in scale_pcs and e.pitch % 12 not in chord_at(e.start).pcs()
                         for e in notes]) if notes else 0
    blue = np.mean([e.pitch % 12 in (3, 6, 10) for e in notes]) if notes else 0
    # hook similarity: bar 1 intervals vs the most similar later bar
    bars = [[e.pitch for e in notes if b * BAR <= e.start < (b + 1) * BAR] for b in range(4)]
    def ivs(b):
        return np.diff(b) if len(b) > 1 else np.array([])
    h0 = ivs(bars[0])
    hook = 0.0
    for b in bars[1:]:
        hb = ivs(b)
        k = min(len(h0), len(hb))
        if k:
            hook = max(hook, float(np.mean(np.abs(h0[:k] - hb[:k]) <= 1)))
    return {
        "step": float(np.mean((a >= 1) & (a <= 2))),
        "leap": float(np.mean(a >= 5)),
        "tritone": float(np.mean(a == 6)),
        "half": float(np.mean(a == 1)),
        "ct_strong": float(ct),
        "rest": float(rest),
        "synco": float(synco),
        "slope": float(np.mean(np.sign(iv))),
        "density": len(notes) / max(total / 1.0, 1),
        "range": float(p.max() - p.min()) if len(p) else 0.0,
        "ends_tonic": float(notes[-1].pitch % 12 == 0) if notes else 0.0,
        "chromatic": float(chromatic),
        "blue": float(blue),
        "hook": hook,
        "max_run": float(_max_run(p)),
    }


def _max_run(p):
    best = run = 1
    for a, b in zip(p, p[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best


def score(v: Vibe, f: dict) -> float:
    """How well a phrase matches the vibe's profile (0..1)."""
    parts = []
    for key, (lo, hi) in v.targets.items():
        x = f[key]
        if lo <= x <= hi:
            parts.append(1.0)
        else:
            width = max(hi - lo, 0.1)
            dist = (lo - x) if x < lo else (x - hi)
            parts.append(max(0.0, 1.0 - dist / width))
    # universal sanity: no droning, singable-ish range, enough notes
    parts.append(1.0 if f["max_run"] <= (4 if v.id == "swingy" else 3) else 0.3)
    parts.append(1.0 if f["range"] <= 16 else 0.4)
    parts.append(1.0 if f["density"] >= 0.4 else 0.3)
    return float(np.mean(parts))


def best_of(v: Vibe, rng, n=30, keep=4, start=None, motif=None):
    cands = []
    for _ in range(n):
        ev, prog, form = compose(v, rng, start, motif)
        if sum(1 for e in ev if e.pitch is not None) < 5:
            continue
        f = features(v, ev, prog, form)
        cands.append((score(v, f), ev, prog, form, f))
    cands.sort(key=lambda c: -c[0])
    out, seen = [], set()
    for c in cands:
        key = tuple(e.pitch for e in c[1])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) >= keep:
            break
    return out


# ------------------------------------------------------------------ output helpers

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SHARP_MAJOR_KEYS = {7, 2, 9, 4, 11, 6}          # G D A E B F# use sharps


def prefers_sharps(tonic_pc: int, minor: bool) -> bool:
    relative_major = (tonic_pc + 3) % 12 if minor else tonic_pc
    return relative_major in SHARP_MAJOR_KEYS


def chord_symbol(tonic_pc: int, ch: Chord, minor: bool = False) -> str:
    names = NOTE_NAMES_SHARP if prefers_sharps(tonic_pc, minor) else NOTE_NAMES_FLAT
    return names[(tonic_pc + ch.root) % 12] + QUALITY_SUFFIX[ch.quality]


def voice_chord(tonic_midi: int, ch: Chord, melody_low: int) -> tuple[list[int], int]:
    """Close voicing sitting just below the melody; plus a bass note."""
    tones = sorted(tonic_midi + t for t in ch.tones)
    top_limit = max(melody_low - 1, tonic_midi + 4)
    while max(tones) > top_limit + 2 and min(tones) - 12 >= tonic_midi - 14:
        tones = [t - 12 for t in tones]
    while min(tones) < max(tonic_midi - 14, CHORD_FLOOR):
        tones = [t + 12 for t in tones]
    # keep it compact: fold wide extensions down
    root = min(tones)
    tones = sorted({root + ((t - root) % 12) if t - root >= 12 else t for t in tones})
    bass = tonic_midi + ch.root % 12 - 12
    while bass > min(tones) - 5:
        bass -= 12
    while bass < BASS_FLOOR:
        bass += 12
    return tones, bass
