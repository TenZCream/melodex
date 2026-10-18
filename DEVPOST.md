# Melodex — Devpost submission draft

Copy each section into the matching Devpost field. Edit freely so it sounds like you.

---

## Project name
Melodex

## Elevator pitch (Devpost limit: 200 characters)
Hum, sing, or play a melody. Melodex tells you if it already exists, then helps you write something new, checked so it doesn't copy known songs.

---

## About the project

### Inspiration
Every musician knows the feeling: a melody pops into your head and you can't tell whether
you wrote it or remembered it. Existing tools like hum-to-search are built to identify
songs. They answer "what is this?" but not "is this mine?", and they don't help you
take the next step.

I wanted a tool that sits on the artist's side: one that tells you honestly how close your
idea is to existing music, and then helps you explore directions that *don't* copy anyone.
AI in music is often framed as competition for artists. Melodex is built to be the
opposite: a creative toolbox that protects originality.

### What it does
**Identify.** Hum, sing, whistle, or tap notes on the on-screen piano (or your computer
keyboard). Melodex turns your audio into notes, searches its melody index, and returns
the closest matches with an honest label (*strong match*, *possible match*, or *no close
match*), plus the exact section of the song that matched. It works in any key, at any
tempo, and starting anywhere in the song (you can hum the chorus). You can play back what
you hummed and the matched melody in your key.

**Explore.** From your melody, Melodex generates new ideas:
- **Continuation**: an answer phrase that reuses your rhythm and resolves home
- **Mirror**: your phrase turned upside-down
- **Sequence**: your motif restated on a new step of the scale
- **Fresh idea**: a new 4-bar phrase over a real chord progression

Every idea comes with chord suggestions and is run back through the same search engine.
Anything too close to a known melody is thrown away before you ever see it, and each
surviving idea shows its novelty, e.g. *"Not found among our 30 indexed melodies.
Closest: Jingle Bells (11% similar)."*

### How I built it
- **Pitch detection:** I implemented the YIN pitch-detection algorithm in NumPy, with a
  pitch estimate every 10 ms.
- **Notes from a real voice:** a cleanup pipeline turns the pitch curve into notes. It
  corrects the singer's tuning drift, merges repeated notes sung slightly off, and
  filters out "swoops" (the voice travelling between notes), wobbly phrase starts, and
  fading tails. I tuned it on my own recordings: 9 of 9 real hums identified correctly.
- **Matching:** melodies become sequences of *intervals* (key-independent) and *rhythm
  ratios* (tempo-independent). A vectorized **subsequence dynamic time warping** search
  aligns your phrase against every melody at once, tolerating extra or missing notes. It
  searches two views — exact notes and repeated-notes-merged — because people slur
  repeated notes when they hum.
- **Honest scores:** scores are calibrated against random melodies so "strong match" means
  something (random tunes are never labeled strong), and near-ties are reported as
  "might be X or Y" instead of false certainty.
- **Generation:** a rule-based composer encodes songwriting principles: chord progression
  first, chord tones on strong beats, motif repetition, mostly stepwise motion with
  gap-fill after leaps, and a real cadence. It composes ~40 candidates, scores them for
  musicality, and keeps the best ones that pass the novelty check.
- **Stack:** Python + FastAPI backend (NumPy only), React + Vite frontend, Tone.js for
  playback and chords.
- **Testing:** synthetic test suites (synthesized humming, singing with vibrato,
  whistling, a noisy room, slurred notes) plus an evaluation on real recordings.

### Challenges I ran into
- **Real voices are messy.** My synthetic tests passed at ~100%, then my real humming
  failed. I recorded myself, analyzed the pitch frame by frame, and found specific causes:
  repeated notes with only a ~2 dB dip between them, a second note sung 0.6 semitones
  flat, and 70 ms "swoops" between notes that looked like real notes. Each fix was
  measured against both real and synthetic data so nothing regressed.
- **A loudness gate didn't work.** I expected stray notes to be quiet. Measuring showed
  they were as loud as real ones; what gave them away was speed. That changed my approach.
- **Windows security blocked SciPy.** Smart App Control blocked an unsigned SciPy DLL,
  so I rewrote WAV parsing, resampling, and filtering in plain NumPy.
- **Honesty about "originality."** Novelty can only ever be relative to what's indexed, so
  the app never claims a melody is "original," only that it isn't close to anything in
  the index.

### Accomplishments that I'm proud of
- Real-voice identification that works: Twinkle Twinkle, Mary Had a Little Lamb, and
  Happy Birthday all recognized as strong matches from my own humming.
- Pitch detection and search written from scratch, explainable end to end.
- An originality filter that throws away its own ideas when they sound too familiar.
- Built solo, as a freshman, in one night.

### What I learned
How pitch detection actually works, why matching melodies has to be key- and
tempo-invariant, dynamic time warping, how to calibrate a score so it means something,
and, most of all, to test on real data early. Synthetic tests told me I was done hours
before I actually was.

### What's next for Melodex
- A much larger index (folk-tune collections, then licensed catalogs) with vector search
  to find candidates quickly
- A neural pitch tracker for messier recordings and polyphonic input
- Exporting ideas as MIDI to drop straight into a DAW
- Harmony and rhythm exploration, not just melody
- A "check my song" mode for songwriters before they release

---

## Built with
python, fastapi, numpy, react, vite, tone.js, javascript, dynamic-time-warping, yin

## Try it out
- GitHub: https://github.com/TenZCream/melodex

---

## AI assistance disclosure
I used AI tools during the hackathon: Claude helped design and write the backend
(pitch detection, search, generation, tests) and debug it against my recordings, and
Cursor helped build the React frontend. All code was written during DubHacks '26. I
directed the design, tested everything with my own voice, and can explain how every
part works.

---

## Track notes (for any per-track questions)

**Chef's Choice:** A creative music tool built around one idea: the same engine that
identifies melodies also protects originality when generating new ones.

**SideShift: Best Startup Idea:** Musicians and creators constantly post "did I write
this or steal it?" content. Melodex turns that into a 10-second check with a shareable
result ("not found in 30 / 10,000 / 1M melodies"), a natural creator-led growth loop.
Free tier for hobbyists; paid tier for producers and songwriters (large catalog search,
MIDI export, DAW plugin).

**DubHacks NEXT:**
- *Problem:* songwriters can't easily check whether a new melody is accidentally copied,
  and accidental similarity leads to real lawsuits.
- *Users:* bedroom producers, songwriters, music students, content creators.
- *Who pays:* producers and songwriters (subscription), music schools (seats), and
  potentially publishers and labels (pre-release checks via API).
- *Evidence of iteration:* recognition went from 0/4 to 9/9 on real recordings over the
  weekend through measured, data-driven fixes.

**Best Freshman Beginner's Project:** Solo freshman project. *(Add a line about your
experience level, e.g. whether this was your first hackathon or first audio project.)*

**MLH Gemini / MongoDB / VEYZL:** *(fill in only if we build these tonight)*
