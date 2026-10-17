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

**Stack:** Python 3.12, FastAPI, uvicorn, numpy, scipy · React (Vite), Tone.js.

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
| M0 | Tools installed, GitHub repo created, API contract + mocks | both | in progress |
| M1 | Note-based search works on 30 tunes (transposed + mid-song excerpts) | Claude | todo |
| M2 | Audio → notes works on synthetic hums | Claude | todo |
| M3 | API running locally on Lexing's laptop | both | todo |
| M4 | React MVP against mocks: record, piano, results, piano roll, playback | Lexing | todo |
| M5 | Frontend ↔ backend connected; 3–5 songs recognized from real voice | both | todo |
| M6 | Devpost draft submitted (by 10:30 PM PT) | Lexing | todo |
| M7+ | Explore/generation, Gemini, VEYZL, extras — **only after M5** | both | blocked |

**Cut order if behind:** deployment → GoDaddy → MongoDB → chords → Gemini.
Never cut working search or the demo video.

---

## 8. Decisions log

- Write YIN pitch detection ourselves instead of librosa (fewer Windows install issues).
- Browser sends WAV, so the backend needs no ffmpeg.
- MVP index = 30 public-domain tunes only.
- Scores shown as labels (strong / possible / no close match) with numbers secondary.
- Each feature after M5 lands via a GitHub pull request (needed for VEYZL).

## 9. Open questions

- How does AI-assisted code count under the 70/30 rule? (asked in Discord: pending)
- GPL licensing if we add Nottingham tunes.

## 10. Checkpoint notes

*(Claude adds a short summary after each milestone: what works, what's tested, what's weak.)*
