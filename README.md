# Melodex

**Hum it. Find it. Then find something new.**

Melodex is a melody search engine and creative playground for musicians. Hum, sing,
whistle, play, or tap a tune, and Melodex finds the closest known melodies — in any key,
at any tempo, starting anywhere in the song.

Built solo at DubHacks '26.

## How it works

1. **Record** — the browser captures your mic and encodes a WAV.
2. **Pitch detection** — the YIN algorithm estimates your pitch every 10 ms.
3. **Notes** — the pitch curve is split into notes; slides and tuning drift are corrected.
4. **Features** — notes become *intervals* (key-independent) and *rhythm ratios*
   (tempo-independent).
5. **Search** — subsequence dynamic time warping aligns your phrase against every
   melody in the index, tolerating extra or missing notes.
6. **Results** — top matches with an honest label: strong / possible / no close match.

## Run it locally

### Backend (Python 3.11+)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs to try the API in your browser.

Run the tests (no extra packages needed):

```powershell
python tests\test_search.py
python tests\test_pitch.py
```

### Frontend (Node 20+)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Project docs

- [`PROJECT.md`](PROJECT.md) — plan, milestones, decisions
- [`API.md`](API.md) — API contract between frontend and backend

## Data

The current index contains 30 well-known public-domain melodies, hand-entered in
`backend/app/famous.py`. "No close match" means no close match **in this index**, not
that a melody is original.

## Credits & disclosure

Built with FastAPI, NumPy, React, Vite, and Tone.js. Developed with AI
assistance (Claude), disclosed per DubHacks rules.
