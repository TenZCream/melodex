"""Melody index + key/tempo-invariant subsequence search.

How matching works
------------------
Each melody is turned into a sequence of *steps*: (semitone interval, rhythm ratio)
between consecutive notes. Intervals don't care what key you hum in; rhythm ratios
don't care how fast you hum.

The query's steps are aligned against every indexed melody at once with a
**subsequence DTW**: the alignment may start and end anywhere inside the reference
(so a hum of the chorus matches mid-song), and the step pattern
(1,1) / (1,2) / (2,1) tolerates one extra or missing note at a time.

All references are concatenated into one long array (with "wall" separators that
cost a lot to cross), so the whole index is searched with ~len(query) vectorized
numpy passes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .melody import Melody, estimate_key, intervals, ioi_ratios, key_name

# --- cost model -------------------------------------------------------------
INTERVAL_CAP = 7.0      # semitone errors beyond this are "completely wrong"
RHYTHM_WEIGHT = 0.25    # rhythm matters, but hummers are sloppy
WALL = 1e6              # cost of crossing from one melody into the next
SKIP_PENALTY = 0.35     # extra cost for the (1,2)/(2,1) steps (missing/extra note)

# --- score calibration ------------------------------------------------------
# avg cost per query step -> score in [0, 1], piecewise-linear. Calibrated with
# tests/test_search.py on 10-note excerpts (30-tune index). Measured costs:
#   exact excerpt (any key/tempo)        0.00
#   1 wrong note + timing jitter         0.08 – 0.17   (median 0.12)
#   2 wrong + dropped + extra note       0.16 – 0.28   (median 0.22)
#   random melody (should NOT match)     0.20 – 0.31   (median 0.26)
# So: < ~0.16 is clearly a match, > ~0.20 overlaps with chance.
# Recalibrate whenever the index grows (more melodies = more chance matches).
_COST_PTS = [0.00, 0.10, 0.16, 0.19, 0.25, 0.32]
_SCORE_PTS = [1.00, 0.85, 0.70, 0.50, 0.25, 0.00]
STRONG = 0.70
POSSIBLE = 0.50
SHORT_QUERY_NOTES = 6   # shorter queries can never be labeled "strong"

MIN_QUERY_NOTES = 4
MIN_DISTINCT_NOTES = 3   # after merging repeated notes
MERGED_HANDICAP = 0.02


def merge_repeats(pitches, onsets, durations):
    """Merge consecutive same-pitch notes into one longer note.

    Hummers often slur repeated notes ("E E E" -> one long E), and pitch trackers
    can't always hear the re-attack. Comparing *both* the query and the index in
    merged form makes matching robust to that. Returns (pitches, onsets, durations,
    keep_idx) where keep_idx maps merged notes back to original note indices."""
    p = np.asarray(pitches)
    o = np.asarray(onsets, dtype=float)
    d = np.asarray(durations, dtype=float)
    if len(p) == 0:
        return p, o, d, np.zeros(0, int)
    keep = [0]
    for i in range(1, len(p)):
        if p[i] != p[keep[-1]]:
            keep.append(i)
    keep = np.array(keep)
    ends = np.append(o[keep[1:]], o[-1] + d[-1])   # each merged note lasts until the next one
    return p[keep], o[keep], ends - o[keep], keep


def _steps(m_pitches, m_onsets, m_durs) -> tuple[np.ndarray, np.ndarray]:
    return intervals(m_pitches), ioi_ratios(m_onsets, m_durs)


def _step_cost(qi: float, qr: float, ri: np.ndarray, rr: np.ndarray) -> np.ndarray:
    """Cost of aligning one query step with every reference step (vectorized)."""
    di = np.abs(ri - qi)
    # soft interval cost: exact = 0, off by 1 semitone = small, wrong direction = large
    ci = np.minimum(di, INTERVAL_CAP) / INTERVAL_CAP
    ci = np.where(di < 0.5, 0.0, 0.15 + 0.85 * ci)
    # contour sign disagreement (up vs down) is extra bad
    sign_flip = (np.sign(ri) * np.sign(qi)) < 0
    ci = np.where(sign_flip, np.maximum(ci, 0.8), ci)
    cr = np.minimum(np.abs(rr - qr), 2.0) / 2.0
    return (1 - RHYTHM_WEIGHT) * ci + RHYTHM_WEIGHT * cr


@dataclass
class Hit:
    melody: Melody
    cost: float
    score: float
    label: str
    start_note: int
    end_note: int
    transpose: int


class _RefSet:
    """All index melodies concatenated into one array of steps, in one 'view'
    (either the original notes, or with repeated notes merged)."""

    def __init__(self, melodies: list[Melody], merged: bool):
        self.merged = merged
        ints, rhys, owner, local = [], [], [], []
        self.keeps: list[np.ndarray] = []      # view-note index -> original note index
        self.view_pitches: list[np.ndarray] = []
        for k, m in enumerate(melodies):
            p, o, d = m.pitches, m.onsets, m.durations
            if merged:
                p, o, d, keep = merge_repeats(p, o, d)
            else:
                keep = np.arange(len(p))
            self.keeps.append(keep)
            self.view_pitches.append(p)
            i, r = _steps(p, o, d)
            ints.append(i); rhys.append(r)
            owner.append(np.full(len(i), k)); local.append(np.arange(len(i)))
            # wall between melodies: two cells wide, so the "skip a note" step
            # can never hop from one melody straight into the next
            ints.append(np.array([999.0, 999.0])); rhys.append(np.array([0.0, 0.0]))
            owner.append(np.array([-1, -1])); local.append(np.array([-1, -1]))
        self.ref_int = np.concatenate(ints)
        self.ref_rhy = np.concatenate(rhys)
        self.owner = np.concatenate(owner)
        self.local = np.concatenate(local)
        self.is_wall = self.owner < 0

    def best_per_melody(self, q_pitches, q_onsets, q_durs) -> dict[int, tuple]:
        """Subsequence DTW of the query against every melody at once.
        Returns {melody_k: (avg_cost, start_note, end_note, transpose)}."""
        q_int, q_rhy = _steps(q_pitches, q_onsets, q_durs)
        n = len(q_int)
        R = len(self.ref_int)
        INF = np.inf
        if n == 0:
            return {}

        # D[j]: best cost aligning query steps 0..i ending at ref step j
        # S[j]: ref index where that alignment started
        prev2_D = prev2_S = prev_D = prev_S = None
        for i in range(n):
            c = _step_cost(q_int[i], q_rhy[i], self.ref_int, self.ref_rhy)
            c[self.is_wall] = WALL
            if i == 0:
                D = c.copy()                       # free start anywhere
                S = np.arange(R)
            else:
                # (1,1): normal step
                d11 = np.full(R, INF); d11[1:] = prev_D[:-1]
                s11 = np.zeros(R, int); s11[1:] = prev_S[:-1]
                # (1,2): reference has an extra note the hummer skipped
                d12 = np.full(R, INF); d12[2:] = prev_D[:-2] + SKIP_PENALTY
                s12 = np.zeros(R, int); s12[2:] = prev_S[:-2]
                # (2,1): hummer added an extra note
                d21 = np.full(R, INF)
                s21 = np.zeros(R, int)
                if prev2_D is not None:
                    d21[1:] = prev2_D[:-1] + SKIP_PENALTY
                    s21[1:] = prev2_S[:-1]
                stack = np.vstack([d11, d12, d21])
                choice = np.argmin(stack, axis=0)
                D = stack[choice, np.arange(R)] + c
                S = np.choose(choice, [s11, s12, s21])
            prev2_D, prev2_S = prev_D, prev_S
            prev_D, prev_S = D, S

        final = prev_D / n
        final[self.is_wall] = INF
        out: dict[int, tuple] = {}
        valid = np.nonzero(~self.is_wall)[0]
        for j in valid[np.argsort(final[valid], kind="stable")]:
            k = int(self.owner[j])
            if k in out:
                continue
            start_step = int(self.local[prev_S[j]]) if self.owner[prev_S[j]] == k else 0
            end_step = int(self.local[j])
            keep = self.keeps[k]
            # steps a..b span view-notes a..b+1; map back to original note indices
            v_start, v_end = start_step, min(end_step + 1, len(keep) - 1)
            start_note = int(keep[v_start])
            end_note = int(keep[v_end + 1] - 1) if v_end + 1 < len(keep) else int(keep[-1])
            if self.merged and v_end + 1 >= len(keep):
                end_note = int(self.keeps[k][-1])
            transpose = _transpose(q_pitches, self.view_pitches[k], v_start)
            out[k] = (float(final[j]), start_note, end_note, transpose)
        return out


def _transpose(q_pitches: np.ndarray, ref_pitches: np.ndarray, start: int) -> int:
    """Semitones to add to the reference to land in the user's key."""
    ref = ref_pitches[start:start + len(q_pitches)]
    k = min(len(ref), len(q_pitches))
    if k == 0:
        return 0
    return int(np.round(np.median(np.asarray(q_pitches[:k]).astype(int) - ref[:k].astype(int))))


class MelodyIndex:
    """Searches two views and keeps whichever fits each melody better:
    - exact view: every note counts (best when repeated notes are sung crisply)
    - merged view: repeated notes merged on both sides (best when they're slurred)
    """

    def __init__(self, melodies: list[Melody]):
        self.melodies = [m for m in melodies if len(m.notes) >= 3]
        self.by_id = {m.id: m for m in self.melodies}
        self.exact = _RefSet(self.melodies, merged=False)
        self.merged = _RefSet(self.melodies, merged=True)

    def __len__(self) -> int:
        return len(self.melodies)

    def search(self, pitches, onsets, durations, top_k: int = 5) -> list[Hit]:
        pitches = np.asarray(pitches)
        onsets = np.asarray(onsets, dtype=float)
        durations = np.asarray(durations, dtype=float)
        if len(pitches) < MIN_QUERY_NOTES:
            raise ValueError(f"need at least {MIN_QUERY_NOTES} notes, got {len(pitches)}")
        mp, mo, md, _ = merge_repeats(pitches, onsets, durations)
        if len(mp) < MIN_DISTINCT_NOTES:
            raise ValueError("too few distinct notes")

        best = self.exact.best_per_melody(pitches, onsets, durations)
        for k, cand in self.merged.best_per_melody(mp, mo, md).items():
            # merged queries carry less information, so they get a small handicap
            cand = (cand[0] + MERGED_HANDICAP,) + cand[1:]
            if k not in best or cand[0] < best[k][0]:
                best[k] = cand

        hits: list[Hit] = []
        for k, (cost, s, e, tr) in sorted(best.items(), key=lambda kv: kv[1][0])[:top_k]:
            score = score_from_cost(cost)
            hits.append(Hit(self.melodies[k], cost, score,
                            label_for(score, len(pitches), len(mp)), s, e, tr))
        return hits


def score_from_cost(cost: float) -> float:
    return float(np.interp(cost, _COST_PTS, _SCORE_PTS))


def label_for(score: float, num_query_notes: int = 99, num_distinct: int = 99) -> str:
    if score >= STRONG and num_query_notes >= SHORT_QUERY_NOTES and num_distinct >= 4:
        return "strong"
    if score >= STRONG:
        return "possible"
    if score >= POSSIBLE:
        return "possible"
    return "weak"


def describe_key(pitches, durations) -> str:
    tonic, mode, _ = estimate_key(np.asarray(pitches), np.asarray(durations))
    return key_name(tonic, mode)
