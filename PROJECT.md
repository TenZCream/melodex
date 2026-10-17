# Melodex — Project Log

> Hum it. Find it. Then find something new.
> DubHacks '26 · Solo · Title track: **Chef's Choice**

This file is the single source of truth for the project: what it is, how it's built,
what's done, and what's next. Read it at the start of every work session.

---

## 1. What Melodex is

A creative toolbox for musicians:

1. **Identify** — hum, sing, whistle, play, or tap a melody on an on-screen piano.
   Melodex extracts the notes and searches an index of known melodies, returning the
   closest matches with a confidence label.
2. **Explore** *(after Identify is solid)* — generate new melodic ideas from your input
   and check each against the same index, so you can see how close it is to known work.

**Honesty rules (also for the pitch & Devpost):**
- Scores are *similarity labels*, not probabilities.
- "Novel" always means "not found among the N melodies in our index", never "original".

---

## 2. Architecture

```
React (Vite) frontend  ── HTTP/JSON ──►  FastAPI backend (Python)
 • mic recording → WAV                     • POST /api/search/audio
 • on-screen piano                         • POST /api/search/notes
 • results + piano roll                    • GET  /api/melodies, /api/melodies/{id}
 • playback (Tone.js)                      • GET  /api/health
                                           • in-memory melody index
```

**Pipeline (Identify):**
1. Browser records mic audio and encodes a mono WAV.
2. **Pitch detection** — YIN algorithm (written in numpy), ~10 ms frames.
3. **Note segmentation** — pitch curve → discrete notes; corrects global tuning offset.
4. **Features** — semitone intervals (key-invariant) + log rhythm ratios (tempo-invariant).
5. **Search** — subsequence DTW against every indexed melody (matches can start mid-song,
   tolerates extra/missing notes).
6. **Results** — top 5 with label, score, and the matching section of each melody.

**Stack:** Python 3.12+, FastAPI, uvicorn, numpy (no SciPy) · React (Vite), Tone.js.

---

## 3. Data

| Set | Size | Source | License | Status |
|---|---|---|---|---|
| Famous public-domain tunes | 30 | Hand-entered in `backend/app/famous.py` | Public domain | **MVP index** |
| Nottingham Music Database | ~1,034 folk tunes | github.com/jukedeck/nottingham-dataset | GPL v3 | Later; download via script, don't commit |
| POP909 | 909 pop melodies | github.com/music-x-lab/POP909-Dataset | MIT (songs themselves copyrighted) | Maybe; likely skip |

---

## 4. Who does what

- **Lexing:** React frontend (with Cursor), running & testing with real voice, GitHub,
  Devpost, demo video, judging, organizer questions.
- **Claude:** backend (pitch detection, index, search, API, later generation), tests,
  API contract, docs, Devpost/pitch drafts, debugging from pasted errors.
- **Tools:** Cursor, GitHub, Vite, Tone.js; later Gemini, VEYZL, (MongoDB Atlas), GoDaddy.

---

## 5. Tracks

- **Title:** Chef's Choice
- **Sponsored (max 3):** VEYZL, SideShift
- **Non-sponsored:** Best Freshman Beginner's Project, MLH Gemini, DubHacks NEXT,
  MLH GoDaddy domain, MLH DEV writing challenge; MLH MongoDB Atlas only if time.

---

## 6. Deadlines (all **Pacific** time — laptop clock is Central, +2h)

- 12:30 PM Sat — hacking began
- **10:30 PM Sat — mandatory Devpost draft**
- **10:00 AM Sun — final submission incl. video** (target 9:30 AM)
- 11:15 AM–2:30 PM Sun — in-person judging (must attend)

---

## 7. Milestones

| # | Milestone | Owner | Status |
|---|---|---|---|
| M0 | Tools installed, GitHub repo created, API contract + mocks | both | ✅ done |
| M1 | Note-based search works on 30 tunes (transposed + mid-song excerpts) | Claude | ✅ done |
| M2 | Audio → notes works on synthetic hums | Claude | ✅ done |
| M3 | API running locally on Lexing's laptop | both | in progress |
| M4 | React MVP against mocks: record, piano, results, piano roll, playback | Lexing | in progress |
| M5 | Frontend ↔ backend connected; 3–5 songs recognized from real voice | both | todo |
| M6 | Devpost draft submitted (by 10:30 PM PT) | Lexing | todo |
| M7+ | Explore/generation, Gemini, VEYZL, extras — **only after M5** | both | blocked |

**Cut order if behind:** deployment → GoDaddy → MongoDB → chords → Gemini.
Never cut working search or the demo video.

---

## 8. Decisions log

- Write YIN pitch detection ourselves instead of librosa (fewer Windows install issues).
- Browser sends WAV, so the backend needs no ffmpeg.
- Removed SciPy (Sat ~4:55 PM PT): Windows Smart App Control blocked an unsigned SciPy
  DLL on Lexing's laptop. WAV reading, resampling, and median filtering are now plain
  NumPy in `backend/app/audio_io.py`. Backend deps: fastapi, uvicorn, python-multipart, numpy.
- MVP index = 30 public-domain tunes only.
- Scores shown as labels (strong / possible / no close match) with numbers secondary.
- Each feature after M5 lands via a GitHub pull request (needed for VEYZL).

## 9. Open questions

- How does AI-assisted code count under the 70/30 rule? (asked in Discord: pending)
- GPL licensing if we add Nottingham tunes.

## 10. Checkpoint notes

*(Claude adds a short summary after each milestone: what works, what's tested, what's weak.)*

### Checkpoint 1 — M1 + M2 (Sat ~3:15 PM PT)

**Works**
- Search over 30 famous public-domain tunes; any key, any tempo, any starting point.
- YIN pitch detection + note segmentation (written in numpy; no librosa).
- Scoop/slide correction and singer tuning-offset correction.
- API: `/api/health`, `/api/search/notes`, `/api/search/audio`, `/api/melodies`,
  `/api/melodies/{id}`; CORS for localhost:5173; friendly 400/413 errors.

**Tested** (`backend/tests/`, synthetic data only)
- Clean excerpts (transposed −7..+7, tempo ×0.5–×2): 100% correct at #1 (120 cases).
- Excerpts with a wrong note + timing jitter: 98% at #1, 100% in top 5.
- Very messy (2 wrong notes + a missing + an extra note in 10): 57% at #1, 82% top 5.
- Random melodies: 0% labeled strong, ~3% labeled possible.
- Synthesized hum / voice-with-vibrato / whistle / noisy-room audio → notes:
  96% interval accuracy; 30/30 songs identified end to end.

**Weak / not yet tested**
- **Not tested on a real human voice yet.** That's the next test (M5).
- Very fast runs (e.g. Turkish March sixteenths) get merged.
- Score calibration is tuned for 10-note queries on a 30-tune index; recalibrate when
  the index grows.
- Key estimate can be off on short phrases (relative major/minor confusion).
- Hand-entered tunes may contain a few wrong notes.

### Checkpoint 2 — first real-voice tuning (Sat ~3:25 PM PT)

**Found on Lexing's real recordings**
- Repeated notes ("E E E") were slurred into one long note: only ~2 dB volume dip
  between "da"s, too small to detect reliably.
- Short slides at the start/end of phrases and an octave-error blip became fake notes.
- Many recordings were only 3–5 s (5–6 notes), which is too short to be certain.

**Fixed**
- Search runs two views and keeps the better fit per song: exact notes, and
  repeated-notes-merged (on both query and index). Slurred hums now match.
- Phrase-edge slide cleanup and octave-blip correction.
- Near-tie rule: if the top two scores are within 0.05, the verdict is "possible"
  and names both songs.

**Result on the 4 real Mary Had a Little Lamb recordings:** 4/4 correct at #1
(before: 0/4). The 11 s recording went from weak 0.26 (wrong song) to strong 0.94.
Synthetic suites unchanged or better (97–100% notes for normal singing; 100% songs).

**Demo tips:** hum 8–12 s (a full phrase), use "da"/"la". Avoid Turkish March.

### Checkpoint 3 — second tuning pass (Sat ~4:00 PM PT)

**Incident:** Cursor had backend files open in tabs and saved stale copies over
Claude's updates (~5:16 PM CT), so Checkpoint 2 never actually ran. Rule from now on:
**don't keep `backend/` files or PROJECT.md open in Cursor; close tabs with "Don't Save".**

**Found on the real Twinkle recording:** the two opening C's were sung 0.61 semitones
apart (read as two notes); slides into notes and a fading, upward-drifting tail added
fake notes.

**Fixed (in `pitch.py`, `_clean_segments`)**
- Neighbouring notes < 0.7 semitones apart = the same pitch sung twice.
- Slides into the next note are absorbed (only if still moving at their end, ≤ 0.2 s,
  within 1.3 semitones of the next note — stricter rules ate real notes).
- Quiet, short notes at phrase edges are dropped (repeatedly, for split tails).
- Each note votes equally on the singer's tuning offset.

**Result:** 5/5 real recordings correct at #1 (`tests/real_eval.py`); Twinkle went from
wrong song to strong 0.71. Synthetic: hum 100%, voice 97%, whistle 100%, noisy 94%
note accuracy; 100% songs identified. Search suite unchanged.
Caveat: tuned on one voice (5 recordings) — collect a few more voices if possible.
