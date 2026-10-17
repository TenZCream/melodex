"""Synthesize realistic-ish 'hums' of a note list for testing pitch detection."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.audio_io import write_wav  # noqa: E402


def synth_hum(notes, sr=44100, seconds_per_beat=0.45, detune_cents=0.0,
              vibrato_cents=25.0, noise_db=-35.0, glide=True, gap=0.04,
              timbre="hum", seed=0):
    """notes: iterable of (midi_pitch, start_beats, dur_beats). Returns float32 audio."""
    rng = np.random.default_rng(seed)
    notes = list(notes)
    total = (notes[-1][1] + notes[-1][2]) * seconds_per_beat + 0.5
    n = int(total * sr)
    out = np.zeros(n, np.float32)
    harmonics = {"hum": [1, 0.5, 0.25, 0.12, 0.06],
                 "whistle": [1, 0.03],
                 "voice": [1, 0.7, 0.5, 0.4, 0.3, 0.2, 0.15, 0.1]}[timbre]
    prev_pitch = None
    for p, s, d in notes:
        start = int((0.25 + s * seconds_per_beat) * sr)
        length = int(max(0.05, d * seconds_per_beat - gap) * sr)
        t = np.arange(length) / sr
        cents = detune_cents + vibrato_cents * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.25, 0, 1)
        cents = cents + rng.normal(0, 4, 1)  # per-note pitch error
        midi = np.full(length, float(p))
        if glide and prev_pitch is not None:  # scoop into the note from the previous one
            g = min(length, int(0.04 * sr))
            midi[:g] = np.linspace(prev_pitch, p, g)
        f = 440 * 2 ** ((midi - 69 + cents / 100) / 12)
        phase = 2 * np.pi * np.cumsum(f) / sr
        wave = sum(a * np.sin((k + 1) * phase) for k, a in enumerate(harmonics))
        env = np.minimum(1, t / 0.02) * np.minimum(1, (length / sr - t) / 0.03)
        env *= 0.8 + 0.2 * rng.random()
        out[start:start + length] += (wave * env).astype(np.float32)
        prev_pitch = p
    out /= np.max(np.abs(out)) + 1e-9
    out *= 0.6
    out += (10 ** (noise_db / 20) * rng.normal(0, 1, n)).astype(np.float32)
    return out, sr


def to_wav_bytes(x, sr):
    return write_wav(x, sr)
