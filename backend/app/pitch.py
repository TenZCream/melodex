"""Audio -> notes for monophonic input (humming, singing, whistling, one instrument).

1. Load WAV, mix to mono, resample to 16 kHz.
2. YIN pitch detection (de Cheveigné & Kawahara, 2002), vectorized with numpy,
   one estimate every 10 ms.
3. Voicing: keep frames that are loud enough AND clearly periodic.
4. Clean up: median filter, fix octave jumps.
5. Segment into notes: split when the pitch moves to a new semitone and stays,
   or when the sound stops / re-attacks.
6. Correct the singer's overall tuning offset, then round to MIDI notes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .audio_io import WavError, median_filter_1d, nan_median_filter_1d, read_wav, resample
from .melody import Note

SR = 16000
FRAME = 1024          # 64 ms analysis window (fits 2+ periods of a 65 Hz low hum)
HOP = 160             # 10 ms between estimates
FMIN, FMAX = 65.0, 1100.0   # ~C2 .. C#6 covers humming, singing, whistling
YIN_THRESHOLD = 0.15
MAX_APERIODICITY = 0.35     # frames less periodic than this are treated as unvoiced
MIN_NOTE_SEC = 0.07
MAX_SECONDS = 30.0


class AudioError(ValueError):
    pass


@dataclass
class Transcription:
    notes: list[Note]               # start/duration in seconds
    times: np.ndarray               # frame times (s)
    midi: np.ndarray                # smoothed pitch per frame (MIDI float, nan = unvoiced)
    tuning_offset: float            # cents/100 the singer was sharp(+) / flat(-)
    duration_sec: float


# ------------------------------------------------------------------ loading

def load_wav(data: bytes) -> tuple[np.ndarray, int]:
    try:
        sr, x = read_wav(data)
    except WavError as e:
        raise AudioError("Could not read audio. Please upload a WAV file.") from e
    if x.ndim == 2:
        x = x.mean(axis=1)
    if len(x) == 0:
        raise AudioError("The recording is empty.")
    return x, int(sr)


def to_16k(x: np.ndarray, sr: int) -> np.ndarray:
    return resample(x, sr, SR)


# ------------------------------------------------------------------ YIN

def yin(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (f0_hz, aperiodicity, rms) per frame. f0 = nan where no pitch found."""
    if len(x) < FRAME:
        x = np.pad(x, (0, FRAME - len(x)))
    n_frames = 1 + (len(x) - FRAME) // HOP
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = x[idx].astype(np.float64)
    frames -= frames.mean(axis=1, keepdims=True)
    rms = np.sqrt((frames ** 2).mean(axis=1))

    tau_min = int(SR / FMAX)
    tau_max = int(SR / FMIN)
    W = FRAME - tau_max                      # integration window

    # difference function d(tau) = sum (x[t] - x[t+tau])^2 over t in [0, W)
    #   = E0 + E_tau - 2 * r(tau), with r via FFT cross-correlation
    nfft = 1 << int(np.ceil(np.log2(FRAME + W)))
    F_full = np.fft.rfft(frames, nfft, axis=1)
    F_win = np.fft.rfft(frames[:, :W], nfft, axis=1)
    r = np.fft.irfft(F_full * np.conj(F_win), nfft, axis=1)[:, :tau_max + 1]
    sq = np.concatenate([np.zeros((n_frames, 1)), np.cumsum(frames ** 2, axis=1)], axis=1)
    E0 = sq[:, W][:, None]
    taus = np.arange(tau_max + 1)
    E_tau = sq[:, taus + W] - sq[:, taus]
    d = np.maximum(E0 + E_tau - 2 * r, 0)

    # cumulative mean normalized difference
    cmnd = np.ones_like(d)
    cs = np.cumsum(d[:, 1:], axis=1)
    cmnd[:, 1:] = d[:, 1:] * np.arange(1, tau_max + 1)[None, :] / np.maximum(cs, 1e-12)

    f0 = np.full(n_frames, np.nan)
    aper = np.ones(n_frames)
    region = cmnd[:, tau_min:tau_max]
    for i in range(n_frames):
        row = region[i]
        below = np.nonzero(row < YIN_THRESHOLD)[0]
        if len(below):
            t = below[0]
            # walk down to the local minimum
            while t + 1 < len(row) and row[t + 1] < row[t]:
                t += 1
        else:
            t = int(np.argmin(row))
        a = row[t]
        tau = t + tau_min
        # parabolic interpolation for sub-sample accuracy
        if 1 <= t < len(row) - 1:
            y0, y1, y2 = row[t - 1], row[t], row[t + 1]
            den = y0 - 2 * y1 + y2
            if abs(den) > 1e-12:
                tau = tau + 0.5 * (y0 - y2) / den
        aper[i] = a
        if a < MAX_APERIODICITY:
            f0[i] = SR / tau
    return f0, aper, rms


# ------------------------------------------------------------------ cleanup

def hz_to_midi(f):
    return 69 + 12 * np.log2(np.asarray(f) / 440.0)


def _voicing(f0, aper, rms):
    peak = np.percentile(rms, 98) if len(rms) else 0
    loud = rms > max(peak * 10 ** (-30 / 20), 1e-3)   # within 30 dB of the peak, above noise floor
    return loud & ~np.isnan(f0) & (aper < MAX_APERIODICITY)


def _fix_octaves(midi, voiced):
    """YIN sometimes jumps an octave for a frame or two; pull those back."""
    m = midi.copy()
    v = np.nonzero(voiced)[0]
    if len(v) < 3:
        return m
    ref = nan_median_filter_1d(np.where(voiced, m, np.nan), size=15)
    for i in v:
        r = ref[i]
        if np.isnan(r):
            continue
        for shift in (-12, 12):
            if abs(m[i] + shift - r) < abs(m[i] - r) - 6:
                m[i] += shift
    return m


def _runs(mask):
    """Start/end (exclusive) index pairs of True runs."""
    if not mask.any():
        return []
    d = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]))


# ------------------------------------------------------------------ segmentation

def _segment(midi, voiced, rms, min_frames):
    """Return list of (start_frame, end_frame) note segments."""
    segs = []
    for a, b in _runs(voiced):
        if b - a < min_frames:
            continue
        seg_start = a
        cur = np.median(midi[a:a + min_frames])
        pending = None  # frame where a possible new note began
        for i in range(a, b):
            if abs(midi[i] - cur) > 0.6:
                if pending is None:
                    pending = i
                elif i - pending + 1 >= min_frames and \
                        abs(np.median(midi[pending:i + 1]) - cur) > 0.6:
                    if pending - seg_start >= min_frames:
                        segs.append((seg_start, pending))
                    seg_start = pending
                    cur = np.median(midi[pending:i + 1])
                    pending = None
            else:
                pending = None
                # slowly track drift within a held note
                cur = 0.95 * cur + 0.05 * midi[i]
        if b - seg_start >= min_frames:
            segs.append((seg_start, b))

    # split re-attacks of the same pitch (energy dips inside a segment)
    out = []
    for a, b in segs:
        e = rms[a:b]
        cuts = [a]
        if len(e) > 3 * min_frames:
            sm = np.convolve(e, np.ones(3) / 3, mode="same")
            for i in range(min_frames, len(sm) - min_frames):
                left = sm[max(0, i - min_frames):i].max()
                right = sm[i:i + min_frames + 2].max()
                if sm[i] < 0.45 * min(left, right) and sm[i] == sm[i - 1:i + 2].min():
                    if a + i - cuts[-1] >= min_frames:
                        cuts.append(a + i)
        cuts.append(b)
        for s, t in zip(cuts[:-1], cuts[1:]):
            if t - s >= min_frames:
                out.append((s, t))
    return out


SCOOP_MAX_SEC = 0.11     # slide between two notes
EDGE_BLIP_MAX_SEC = 0.16  # slide at the very start / end of a phrase
BLIP_MAX_SEC = 0.16      # octave-error blips
TOUCH_SEC = 0.05         # notes this close count as connected (frames smear ~40 ms)
PHRASE_GAP_SEC = 0.12     # silence that separates phrases


def _touching(a: Note, b: Note) -> bool:
    return b.start - (a.start + a.duration) < TOUCH_SEC


def _fix_octave_blips(notes: list[Note]) -> list[Note]:
    """A short note ~an octave away from both neighbours is a YIN octave error."""
    out = list(notes)
    for i, n in enumerate(out):
        if n.duration > BLIP_MAX_SEC:
            continue
        neigh = [out[j].pitch for j in (i - 1, i + 1) if 0 <= j < len(out)]
        if not neigh:
            continue
        ref = int(np.median(neigh))
        for shift in (12, -12, 24, -24):
            if abs(n.pitch + shift - ref) <= 2 and abs(n.pitch - ref) >= 10:
                out[i] = Note(n.pitch + shift, n.start, n.duration)
                break
    return out


def _absorb(into: Note, blip: Note) -> Note:
    start = min(into.start, blip.start)
    end = max(into.start + into.duration, blip.start + blip.duration)
    return Note(into.pitch, start, round(end - start, 3))


def _remove_scoops(notes: list[Note]) -> list[Note]:
    """Clean up transition artifacts:
    - scoop: a short note sliding into the next note (pitch between its neighbours)
    - onset blip: a short note at the start of a phrase, right before a nearby note
    - release blip: a short note at the end of a phrase, right after a nearby note
    Each is folded into the neighbouring real note."""
    notes = _fix_octave_blips(notes)
    out: list[Note] = []
    i = 0
    while i < len(notes):
        n = notes[i]
        nxt = notes[i + 1] if i + 1 < len(notes) else None
        prev = out[-1] if out else None
        gap_before = (n.start - (prev.start + prev.duration)) if prev else 9.0
        gap_after = (nxt.start - (n.start + n.duration)) if nxt else 9.0
        joins_next = nxt is not None and gap_after < TOUCH_SEC and n.pitch != nxt.pitch
        joins_prev = prev is not None and gap_before < TOUCH_SEC and n.pitch != prev.pitch

        # scoop between two notes
        if n.duration <= SCOOP_MAX_SEC and joins_next and joins_prev \
                and abs(n.pitch - nxt.pitch) <= 2 \
                and min(prev.pitch, nxt.pitch) <= n.pitch <= max(prev.pitch, nxt.pitch):
            notes[i + 1] = _absorb(nxt, n)
            i += 1
            continue
        # onset blip: right after silence, sliding into the first real note
        if n.duration <= EDGE_BLIP_MAX_SEC and gap_before >= PHRASE_GAP_SEC and joins_next \
                and abs(n.pitch - nxt.pitch) <= 2 and n.duration < 0.6 * nxt.duration:
            notes[i + 1] = _absorb(nxt, n)
            i += 1
            continue
        # release blip: tail of the last real note, right before silence
        if n.duration <= EDGE_BLIP_MAX_SEC and gap_after >= PHRASE_GAP_SEC and joins_prev \
                and abs(n.pitch - prev.pitch) <= 2 and n.duration < 0.6 * prev.duration:
            out[-1] = _absorb(prev, n)
            i += 1
            continue
        out.append(n)
        i += 1
    return out


# ------------------------------------------------------------------ segment cleanup
# Tuned on real hums (tests/real_eval.py). All of these fix artifacts of how people
# actually sing, not of the pitch tracker.
UNISON_SEMITONES = 0.7     # neighbouring notes closer than this are one pitch sung twice
TAIL_MAX_SEC = 0.30        # a fading start/end of a phrase is at most this long...
TAIL_QUIET_DB = 4.5        # ...and this much quieter than the typical note
GLIDE_MAX_SEC = 0.20       # a slide into the next note is at most this long
TINY_SEC = 0.0             # (disabled: hurt real short notes in testing)
GLIDE_NEAR = 1.3           # a slide ends within this many semitones of the next note
SWOOP_MAX_SEC = 0.12       # a fragment this short whose pitch moves a lot is a transition
SWOOP_SEMITONES = 1.5
WOBBLE_MAX_SEC = 0.12      # fragments at a phrase start before a much longer note
WOBBLE_RATIO = 4.0
CORE_TRIM = 0.0            # fraction trimmed from each end of a note before taking its pitch
WEIGHTED_OFFSET = 0.0      # 0 = every note votes equally on the singer's tuning


@dataclass
class _Seg:
    a: int          # start frame
    b: int          # end frame (exclusive)
    f: float        # pitch (MIDI float), from the stable middle of the note
    f_start: float
    f_end: float
    db: float       # mean loudness

    @property
    def dur(self) -> float:
        return (self.b - self.a) * HOP / SR


def _seg_from(a, b, midi, db) -> _Seg:
    m = midi[a:b]
    m = m[~np.isnan(m)]
    if len(m) == 0:
        m = np.array([0.0])
    k = len(m)
    lo = int(k * CORE_TRIM)
    core = m[lo:max(k - lo, lo + 1)]
    edge = max(1, min(3, k // 3))
    return _Seg(a, b, float(np.median(core)), float(np.median(m[:edge])),
                float(np.median(m[-edge:])), float(np.mean(db[a:b])))


def _clean_segments(segs, midi, rms) -> list[_Seg]:
    db = 20 * np.log10(np.maximum(rms, 1e-9))
    S = [_seg_from(a, b, midi, db) for a, b in segs]
    if not S:
        return S
    gap = lambda x, y: (y.a - x.b) * HOP / SR  # noqa: E731
    touching = lambda x, y: gap(x, y) < TOUCH_SEC  # noqa: E731

    # 1) quiet, short notes at the start/end of a phrase (breath onsets, fading tails).
    #    Repeat, because a fading tail can be split into several pieces.
    typical_db = float(np.median([s.db for s in S]))
    changed = True
    while changed and S:
        changed = False
        keep = []
        for i, s in enumerate(S):
            first = i == 0 or gap(S[i - 1], s) >= PHRASE_GAP_SEC
            last = i == len(S) - 1 or gap(s, S[i + 1]) >= PHRASE_GAP_SEC
            if (first or last) and s.dur <= TAIL_MAX_SEC and s.db < typical_db - TAIL_QUIET_DB:
                changed = True
                continue
            keep.append(s)
        S = keep

    # 2a) fast swoops between notes: very short, pitch moving fast -> part of the next note
    out: list[_Seg] = []
    for i, s in enumerate(S):
        if s.dur <= SWOOP_MAX_SEC and abs(s.f_end - s.f_start) >= SWOOP_SEMITONES:
            nxt = S[i + 1] if i + 1 < len(S) else None
            if nxt is not None and touching(s, nxt):
                S[i + 1] = _Seg(s.a, nxt.b, nxt.f, s.f_start, nxt.f_end, nxt.db)
                continue
            if out and touching(out[-1], s):
                p = out[-1]
                out[-1] = _Seg(p.a, s.b, p.f, p.f_start, s.f_end, p.db)
                continue
        out.append(s)
    S = out

    # 2b) wobbly fragments at the start of a phrase, before the first real note
    #     (possibly several in a row: the voice "finding" the pitch)
    out = []
    i = 0
    while i < len(S):
        phrase_start = not out or gap(out[-1], S[i]) >= PHRASE_GAP_SEC
        j = i
        while phrase_start and j + 1 < len(S) and S[j].dur <= WOBBLE_MAX_SEC and touching(S[j], S[j + 1]):
            j += 1
        if j > i:
            frags, real = S[i:j], S[j]
            if real.dur >= WOBBLE_RATIO * max(f.dur for f in frags) \
                    and all(abs(f.f - real.f) <= 3.0 for f in frags):
                S[j] = _Seg(frags[0].a, real.b, real.f, frags[0].f_start, real.f_end, real.db)
                i = j
                continue
        out.append(S[i])
        i += 1
    S = out

    # 2c) slides into the next note, and tiny transition fragments
    out = []
    i = 0
    while i < len(S):
        s = S[i]
        nxt = S[i + 1] if i + 1 < len(S) else None
        if nxt is not None and touching(s, nxt):
            toward = np.sign(nxt.f - s.f)
            gliding = (s.dur <= GLIDE_MAX_SEC and abs(s.f - nxt.f) <= GLIDE_NEAR
                       and toward * (s.f_end - s.f) >= 0.25          # still moving at its end
                       and toward * (s.f_end - s.f_start) >= 0.4)    # moving overall
            if gliding or s.dur <= TINY_SEC:
                S[i + 1] = _Seg(s.a, nxt.b, nxt.f, s.f_start, nxt.f_end, nxt.db)
                i += 1
                continue
        if s.dur <= TINY_SEC and out and touching(out[-1], s):
            p = out[-1]
            out[-1] = _Seg(p.a, s.b, p.f, p.f_start, s.f_end, p.db)
            i += 1
            continue
        out.append(s)
        i += 1
    S = out

    # 3) near-unison neighbours are one pitch sung twice (repeated note, slightly off)
    for i in range(1, len(S)):
        p, s = S[i - 1], S[i]
        if gap(p, s) < PHRASE_GAP_SEC and abs(s.f - p.f) < UNISON_SEMITONES:
            w1, w2 = p.dur, s.dur
            f = (p.f * w1 + s.f * w2) / (w1 + w2)
            S[i - 1] = _Seg(p.a, p.b, f, p.f_start, p.f_end, p.db)
            S[i] = _Seg(s.a, s.b, f, s.f_start, s.f_end, s.db)
    return S


def transcribe(data: bytes) -> Transcription:
    x, sr = load_wav(data)
    duration = len(x) / sr
    if duration > MAX_SECONDS:
        raise AudioError(f"Recording is {duration:.0f}s; please keep it under {MAX_SECONDS:.0f}s.")
    x = to_16k(x, sr)
    if np.max(np.abs(x)) < 1e-3:
        raise AudioError("The recording is silent. Check your microphone.")

    f0, aper, rms = yin(x)
    voiced = _voicing(f0, aper, rms)
    midi = np.where(voiced, hz_to_midi(np.where(np.isnan(f0), 440, f0)), np.nan)
    midi = _fix_octaves(midi, voiced)

    # median filter within voiced regions only
    filled = np.where(voiced, midi, 0.0)
    for a, b in _runs(voiced):
        if b - a >= 3:
            filled[a:b] = median_filter_1d(filled[a:b], size=5)
    midi = np.where(voiced, filled, np.nan)

    min_frames = max(2, int(MIN_NOTE_SEC * SR / HOP))
    segs = _segment(np.nan_to_num(midi), voiced, rms, min_frames)
    segs = _clean_segments(segs, midi, rms)

    # tuning offset: how far (in semitones) the singer sits from equal temperament
    centers = np.array([s.f for s in segs])
    if len(centers):
        weights = np.array([s.b - s.a for s in segs], dtype=float) if WEIGHTED_OFFSET \
            else np.ones(len(segs))
        frac = centers - np.round(centers)
        # duration-weighted circular mean of fractional offsets
        ang = np.angle(np.sum(weights * np.exp(2j * np.pi * frac)))
        offset = float(ang / (2 * np.pi))
    else:
        offset = 0.0

    hop_s = HOP / SR
    t0 = FRAME / 2 / SR                     # frame i is centred at i*hop + FRAME/2
    notes = [Note(int(np.round(s.f - offset)), float(round(t0 + s.a * hop_s, 3)),
                  float(round((s.b - s.a) * hop_s, 3)))
             for s in segs]
    notes = _remove_scoops(notes)

    times = t0 + np.arange(len(midi)) * hop_s
    return Transcription(notes, times, midi, offset, duration)
