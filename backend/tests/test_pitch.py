"""Pitch-detection tests on synthesized hums, plus full audio -> search end-to-end."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from app.catalog import load_famous  # noqa: E402
from app.pitch import transcribe  # noqa: E402
from app.search import MelodyIndex  # noqa: E402
from synth import synth_hum, to_wav_bytes  # noqa: E402

MELODIES = load_famous()
INDEX = MelodyIndex(MELODIES)


def note_accuracy(target, got):
    """Fraction of target intervals reproduced (order-aware, via simple alignment)."""
    t = np.diff([p for p, *_ in target])
    g = np.diff([n.pitch for n in got])
    if len(g) == 0:
        return 0.0
    # Levenshtein-style alignment on interval sequences
    D = np.zeros((len(t) + 1, len(g) + 1))
    D[:, 0] = np.arange(len(t) + 1)
    D[0, :] = np.arange(len(g) + 1)
    for i in range(1, len(t) + 1):
        for j in range(1, len(g) + 1):
            D[i, j] = min(D[i - 1, j] + 1, D[i, j - 1] + 1, D[i - 1, j - 1] + (t[i - 1] != g[j - 1]))
    return 1 - D[-1, -1] / max(len(t), 1)


def run(verbose=False):
    rng = np.random.default_rng(0)
    rows = []
    configs = [
        dict(timbre="hum"),
        dict(timbre="voice", vibrato_cents=40, detune_cents=30),
        dict(timbre="whistle", noise_db=-30),
        dict(timbre="hum", noise_db=-22, detune_cents=-35),   # noisy room, flat singer
        dict(timbre="hum", gap=0.0, glide=True),              # legato: repeated notes slurred
    ]
    for m in MELODIES:
        n = len(m.notes)
        L = min(12, n)
        start = int(rng.integers(0, max(1, n - L)))
        seg = m.notes[start:start + L]
        tr = int(rng.integers(-5, 6))
        notes = [(x.pitch + tr, x.start - seg[0].start, x.duration) for x in seg]
        cfg = configs[len(rows) % len(configs)]
        audio, sr = synth_hum(notes, seconds_per_beat=float(rng.uniform(0.3, 0.6)), seed=len(rows), **cfg)
        tx = transcribe(to_wav_bytes(audio, sr))
        acc = note_accuracy(notes, tx.notes)
        p = [x.pitch for x in tx.notes]
        o = [x.start for x in tx.notes]
        d = [x.duration for x in tx.notes]
        hit = INDEX.search(p, o, d, top_k=5) if len(p) >= 4 else []
        ok = bool(hit) and hit[0].melody.id == m.id
        rows.append((m.title, cfg["timbre"], acc, len(notes), len(tx.notes), ok,
                     hit[0].label if hit else "-", hit[0].score if hit else 0))
        if verbose:
            print(f"{m.title[:32]:32s} {cfg['timbre']:7s} acc={acc:.2f} notes {len(notes):2d}->{len(tx.notes):2d} "
                  f"top1={'OK ' if ok else 'MISS'} {rows[-1][6]:8s} {rows[-1][7]:.2f}")
    return rows


def test_transcription_accuracy():
    rows = run()
    assert np.mean([r[2] for r in rows]) >= 0.85


def test_end_to_end_audio_search():
    rows = run()
    assert np.mean([r[5] for r in rows]) >= 0.85


if __name__ == "__main__":
    rows = run(verbose=True)
    print(f"\nmean interval accuracy: {np.mean([r[2] for r in rows]):.2f}")
    print(f"end-to-end top-1:       {np.mean([r[5] for r in rows]):.2f}")
