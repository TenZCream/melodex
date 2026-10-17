"""Explore: generate new melodic ideas and check each against the index.

Every idea is built in *scale degrees* (so it stays in the user's key), then turned
back into MIDI notes. Each candidate is run through the same search engine used for
Identify; ideas that sound too much like something in the index are dropped. What's
left gets a novelty score: how far it is from its nearest neighbour **in our index**
(not a claim of originality).

Generators
- continuation: a Markov chain over scale-degree steps, trained on the index,
  continues the user's phrase and resolves home
- inversion:    the user's phrase upside-down (mirror the contour), in key
- sequence:     the user's opening motif repeated a step higher, then resolved
- rhythm flip:  same pitches, long/short rhythm pattern swapped
- fresh:        a brand-new 2-bar phrase from the Markov chain (no seed needed)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from .melody import MAJOR_SCALE, MINOR_SCALE, Melody, Note, estimate_key, key_name
from .search import MelodyIndex

DEGREE_RANGE = (-7, 14)          # keep generated lines within ~3 octaves of scale steps
NOVEL = 0.50                     # novelty >= this: "not found in index"
FAMILIAR = 0.30                  # below this: too close; dropped
RHYTHM_CHOICES = [0.5, 1.0, 1.0, 1.0, 1.5, 2.0]


@dataclass
class Idea:
    kind: str
    title: str
    description: str
    notes: list[Note]                      # beats
    novelty: float = 0.0
    nearest: dict | None = None
    chords: list[dict] = field(default_factory=list)


# ------------------------------------------------------------------ scale helpers

class Scale:
    def __init__(self, tonic_pc: int, mode: str, tonic_midi: int):
        self.tonic_pc = tonic_pc
        self.mode = mode
        self.steps = MAJOR_SCALE if mode == "major" else MINOR_SCALE
        self.tonic_midi = tonic_midi       # the tonic in the user's octave

    def to_midi(self, degree: int) -> int:
        octave, idx = divmod(degree, 7)
        return self.tonic_midi + 12 * octave + self.steps[idx]

    def to_degree(self, midi: int) -> int:
        """Nearest scale degree (out-of-key notes snap to the closest scale tone)."""
        rel = midi - self.tonic_midi
        octave, pc = divmod(rel, 12)
        best = min(range(7), key=lambda i: (abs(self.steps[i] - pc), i))
        # an out-of-key pitch exactly between two scale tones snaps down; fine for ideas
        if pc - self.steps[best] > 6:
            return 7 * (octave + 1)
        return 7 * octave + best


def _scale_for(pitches, durations) -> Scale:
    tonic, mode, _ = estimate_key(np.asarray(pitches), np.asarray(durations))
    center = int(np.median(pitches))
    # tonic at or just below the middle of the user's range
    tonic_midi = center - ((center - tonic) % 12)
    return Scale(tonic, mode, tonic_midi)


# ------------------------------------------------------------------ seed -> beats

def seed_to_beats(notes: list[Note]) -> tuple[list[Note], float]:
    """Convert a recorded phrase (seconds) to beats on a simple grid.
    The most common inter-onset interval becomes one beat; durations snap to halves.
    Returns (notes_in_beats, seconds_per_beat)."""
    if len(notes) < 2:
        return [Note(n.pitch, 0.0, 1.0) for n in notes], 0.5
    onsets = np.array([n.start for n in notes])
    iois = np.diff(onsets)
    iois = iois[iois > 0.05]
    beat = float(np.median(iois)) if len(iois) else 0.5
    out = []
    t = 0.0
    for i, n in enumerate(notes):
        nxt = notes[i + 1].start if i + 1 < len(notes) else n.start + n.duration
        d = max(0.5, round(((nxt - n.start) / beat) * 2) / 2)
        d = min(d, 4.0)
        out.append(Note(n.pitch, t, d))
        t += d
    return out, beat


# ------------------------------------------------------------------ Markov model

class DegreeMarkov:
    """Order-2 Markov chain over scale-degree *steps*, trained on the index."""

    def __init__(self, melodies: list[Melody]):
        self.table: dict[tuple[int, int], dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.uni: dict[int, int] = defaultdict(int)
        self.rhythms: dict[float, dict[float, int]] = defaultdict(lambda: defaultdict(int))
        for m in melodies:
            if len(m.notes) < 4:
                continue
            sc = _scale_for(m.pitches, m.durations)
            deg = [sc.to_degree(int(p)) for p in m.pitches]
            steps = [max(-7, min(7, b - a)) for a, b in zip(deg, deg[1:])]
            for a, b, c in zip(steps, steps[1:], steps[2:]):
                self.table[(a, b)][c] += 1
            for s in steps:
                self.uni[s] += 1
            durs = [float(d) for d in m.durations]
            for a, b in zip(durs, durs[1:]):
                self.rhythms[a][b] += 1

    def next_step(self, prev2: tuple[int, int], rng, temperature=1.0, avoid=None) -> int:
        dist = self.table.get(prev2) or self.uni
        keys = np.array(list(dist.keys()))
        w = np.array([dist[k] for k in keys], dtype=float) ** (1.0 / temperature)
        if avoid is not None:
            w[keys == avoid] *= 0.3
        return int(rng.choice(keys, p=w / w.sum()))

    def next_duration(self, prev: float, rng) -> float:
        dist = self.rhythms.get(prev)
        if not dist:
            return float(rng.choice(RHYTHM_CHOICES))
        keys = list(dist.keys())
        w = np.array([dist[k] for k in keys], dtype=float)
        d = float(keys[rng.choice(len(keys), p=w / w.sum())])
        return min(max(d, 0.25), 3.0)


# ------------------------------------------------------------------ generators

def _from_degrees(sc: Scale, degrees, durations, start=0.0) -> list[Note]:
    notes, t = [], start
    for g, d in zip(degrees, durations):
        g = int(np.clip(g, *DEGREE_RANGE))
        notes.append(Note(sc.to_midi(g), t, float(d)))
        t += float(d)
    return notes


def _resolve(degrees: list[int]) -> list[int]:
    """Nudge the last note home (nearest tonic)."""
    if degrees:
        last = degrees[-1]
        degrees[-1] = 7 * round(last / 7)
    return degrees


def gen_continuation(seed_deg, seed_dur, sc, model, rng, length=8):
    deg = list(seed_deg[-2:]) if len(seed_deg) >= 2 else [0, 0]
    steps = (deg[-1] - deg[-2],) if len(deg) >= 2 else (0,)
    prev2 = (0, steps[-1])
    out_deg, out_dur = [], []
    cur = deg[-1]
    prev_d = seed_dur[-1] if seed_dur else 1.0
    for i in range(length):
        s = model.next_step(prev2, rng, temperature=1.3, avoid=0)
        cur = int(np.clip(cur + s, *DEGREE_RANGE))
        out_deg.append(cur)
        prev_d = model.next_duration(prev_d, rng)
        out_dur.append(prev_d)
        prev2 = (prev2[1], s)
    out_deg = _resolve(out_deg)
    out_dur[-1] = max(out_dur[-1], 2.0)
    return out_deg, out_dur


def gen_inversion(seed_deg, seed_dur):
    axis = seed_deg[0]
    return [axis - (g - axis) for g in seed_deg], list(seed_dur)


def gen_sequence(seed_deg, seed_dur, rng):
    k = min(4, len(seed_deg))
    motif, mdur = seed_deg[:k], seed_dur[:k]
    shift = int(rng.choice([1, 2, -1]))
    deg = motif + [g + shift for g in motif] + [g + 2 * shift for g in motif[:2]]
    dur = mdur + mdur + mdur[:2]
    deg.append(7 * round(deg[-1] / 7))
    dur.append(2.0)
    return deg, dur


def gen_rhythm_flip(seed_deg, seed_dur):
    mx, mn = max(seed_dur), min(seed_dur)
    if mx == mn:
        pattern = [1.5, 0.5] * (len(seed_dur) // 2 + 1)
        return list(seed_deg), pattern[:len(seed_deg)]
    return list(seed_deg), [mx + mn - d for d in seed_dur]


def gen_fresh(model, rng, length=8):
    deg = [0]
    dur = [1.0]
    prev2 = (0, int(rng.choice([1, 2, -1, 4])))
    cur = prev2[1]
    deg.append(cur)
    dur.append(1.0)
    for _ in range(length - 2):
        s = model.next_step(prev2, rng, temperature=1.4, avoid=0)
        cur = int(np.clip(cur + s, -4, 11))
        deg.append(cur)
        dur.append(model.next_duration(dur[-1], rng))
        prev2 = (prev2[1], s)
    deg = _resolve(deg)
    dur[-1] = max(dur[-1], 2.0)
    return deg, dur


# ------------------------------------------------------------------ chords

_TRIADS_MAJOR = [("I", 0), ("ii", 1), ("iii", 2), ("IV", 3), ("V", 4), ("vi", 5)]
_TRIADS_MINOR = [("i", 0), ("iv", 3), ("v", 4), ("V", 4), ("VI", 5), ("III", 2), ("VII", 6)]
_PREF = {"I": 0.3, "i": 0.3, "IV": 0.2, "iv": 0.2, "V": 0.25, "v": 0.1, "vi": 0.1, "VI": 0.1}
_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def suggest_chords(notes: list[Note], sc: Scale, bar_beats: float = 2.0) -> list[dict]:
    """One diatonic triad per `bar_beats`, chosen to cover the melody notes in that span."""
    if not notes:
        return []
    end = notes[-1].start + notes[-1].duration
    triads = _TRIADS_MAJOR if sc.mode == "major" else _TRIADS_MINOR
    out = []
    t = 0.0
    while t < end - 1e-6:
        span = [(n, min(n.start + n.duration, t + bar_beats) - max(n.start, t))
                for n in notes if n.start < t + bar_beats and n.start + n.duration > t]
        best, best_score = triads[0], -1.0
        for name, root in triads:
            tones = {(sc.steps[(root + k) % 7] + sc.tonic_pc) % 12 for k in (0, 2, 4)}
            if name == "V" and sc.mode == "minor":     # harmonic-minor dominant
                tones = {(sc.tonic_pc + 7) % 12, (sc.tonic_pc + 11) % 12, (sc.tonic_pc + 2) % 12}
            cover = sum(w for n, w in span if n.pitch % 12 in tones)
            total = sum(w for _, w in span) or 1.0
            score = cover / total + _PREF.get(name, 0.0)
            if out and out[-1]["roman"] == name:
                score -= 0.15                           # prefer some movement
            if score > best_score:
                best, best_score = (name, root), score
        name, root = best
        root_pc = (sc.steps[root] + sc.tonic_pc) % 12
        quality = "" if name[0].isupper() else "m"
        if name in ("V",):
            quality = ""
        out.append({"start": round(t, 3), "duration": bar_beats, "roman": name,
                    "symbol": f"{_NAMES[root_pc]}{quality}"})
        t += bar_beats
    # end on the home chord
    home = "I" if sc.mode == "major" else "i"
    if out and out[-1]["roman"] != home:
        out[-1].update(roman=home, symbol=f"{_NAMES[sc.tonic_pc]}{'' if sc.mode == 'major' else 'm'}")
    return out


# ------------------------------------------------------------------ main entry

class Explorer:
    def __init__(self, index: MelodyIndex):
        self.index = index
        self.model = DegreeMarkov(index.melodies)

    def _novelty(self, notes: list[Note]):
        p = [n.pitch for n in notes]
        hits = self.index.search(p, [n.start for n in notes], [n.duration for n in notes], top_k=1)
        h = hits[0]
        nearest = {"id": h.melody.id, "title": h.melody.title, "composer": h.melody.artist,
                   "similarity": round(h.score, 3)}
        return round(1.0 - h.score, 3), nearest

    def generate(self, seed_notes: list[Note] | None, num_ideas: int = 4,
                 rng_seed: int | None = None) -> dict:
        rng = np.random.default_rng(rng_seed)
        has_seed = bool(seed_notes) and len(seed_notes) >= 3

        if has_seed:
            seed_beats, beat_sec = seed_to_beats(seed_notes)
            sc = _scale_for([n.pitch for n in seed_beats], [n.duration for n in seed_beats])
            seed_deg = [sc.to_degree(n.pitch) for n in seed_beats]
            seed_dur = [n.duration for n in seed_beats]
        else:
            sc = Scale(0, "major", 60)
            seed_deg, seed_dur = [], []
            seed_beats, beat_sec = [], 0.5

        candidates: list[Idea] = []
        attempts = 0
        while len(candidates) < 40 and attempts < 80:
            attempts += 1
            kinds = ["continuation", "inversion", "sequence", "rhythm", "fresh"] if has_seed else ["fresh"]
            kind = kinds[attempts % len(kinds)]
            if kind == "continuation":
                d, r = gen_continuation(seed_deg, seed_dur, sc, self.model, rng)
                notes = _from_degrees(sc, d, r)   # only the new part; it follows the seed
                title, desc = "Continuation", "What could come next: picks up where you stopped and brings it home."
            elif kind == "inversion":
                d, r = gen_inversion(seed_deg, seed_dur)
                notes = _from_degrees(sc, d, r)
                title, desc = "Mirror", "Your phrase turned upside-down: every rise becomes a fall."
            elif kind == "sequence":
                d, r = gen_sequence(seed_deg, seed_dur, rng)
                notes = _from_degrees(sc, d, r)
                title, desc = "Sequence", "Your opening motif, restated on a new step of the scale."
            elif kind == "rhythm":
                d, r = gen_rhythm_flip(seed_deg, seed_dur)
                notes = _from_degrees(sc, d, r)
                title, desc = "Rhythm flip", "Same notes, with long and short swapped."
            else:
                d, r = gen_fresh(self.model, rng)
                notes = _from_degrees(sc, d, r)
                title, desc = "Fresh idea", f"A new phrase in {key_name(sc.tonic_pc, sc.mode)}."
            if len(notes) < 4 or len({n.pitch for n in notes}) < 3:
                continue
            if any(_same_pitches(notes, c.notes) for c in candidates):
                continue
            novelty, nearest = self._novelty(notes)
            candidates.append(Idea(kind, title, desc, notes, novelty, nearest))

        kept = [c for c in candidates if c.novelty >= FAMILIAR]
        dropped = len(candidates) - len(kept)
        # one of each kind first (most novel), then fill by novelty
        kept.sort(key=lambda c: -c.novelty)
        chosen: list[Idea] = []
        for k in ["continuation", "inversion", "sequence", "rhythm", "fresh"]:
            for c in kept:
                if c.kind == k and c not in chosen:
                    chosen.append(c)
                    break
        for c in kept:
            if len(chosen) >= num_ideas:
                break
            if c not in chosen:
                chosen.append(c)
        chosen = chosen[:num_ideas]
        for c in chosen:
            c.chords = suggest_chords(c.notes, sc)

        tempo = float(np.clip(round(60.0 / max(beat_sec, 0.2)), 60, 160))
        return {
            "seed": {"used": has_seed, "key": key_name(sc.tonic_pc, sc.mode),
                     "num_notes": len(seed_notes or []), "tempo_bpm": tempo,
                     "notes": seed_beats},
            "ideas": chosen,
            "candidates_considered": len(candidates),
            "too_familiar_dropped": dropped,
        }


def _same_pitches(a: list[Note], b: list[Note]) -> bool:
    return [n.pitch for n in a] == [n.pitch for n in b]


def novelty_label(novelty: float) -> str:
    if novelty >= NOVEL:
        return "novel"
    if novelty >= FAMILIAR:
        return "echoes"
    return "familiar"
