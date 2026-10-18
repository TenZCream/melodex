import { useEffect, useState } from 'react'
import { API_BASE } from '../config'
import {
  INSTRUMENTS,
  setChordInstrument,
  setMelodyInstrument,
  subscribeInstrumentLoading,
} from '../instruments'
import mockFresh from '../mocks/generate_fresh.json'
import mockJazzy from '../mocks/generate_jazzy.json'
import mockVibes from '../mocks/vibes.json'
import { beatsToSeconds, ideaPerformance } from '../music'
import { playSequence, stopPlayback } from '../playback'
import ErrorBanner from './ErrorBanner'
import PianoRoll from './PianoRoll'
import PlayButton from './PlayButton'
import './ExplorePanel.css'

const SERVER_DOWN = "Can't reach the Melodex server. Is the backend running on port 8000?"

async function readDetail(response) {
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string' && body.detail.trim()) return body.detail
    if (Array.isArray(body?.detail)) {
      const messages = body.detail.map((item) => item?.msg).filter(Boolean)
      if (messages.length) return messages.join(' ')
    }
  } catch {
    // A non-JSON error body still needs a readable line in the banner.
  }
  return 'New ideas could not be generated.'
}

function noveltyLabel(label) {
  if (label === 'novel') return 'Not in our index'
  if (label === 'echoes') return 'Echoes a known tune'
  return label
}

let chordsPreference = true
let vibePreference = null
let keyPreference = 'auto'
let melodyPreference = 'piano'
let chordInstPreference = 'piano'

export default function ExplorePanel({ queryNotes, mockMode, playback, onPlayback }) {
  const [ideas, setIdeas] = useState(null)
  const [source, setSource] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [chordsOn, setChordsOn] = useState(chordsPreference)
  const [vibes, setVibes] = useState(mockMode ? mockVibes.vibes : [])
  const [keys, setKeys] = useState(mockMode ? mockVibes.keys : [])
  const [vibeId, setVibeId] = useState(vibePreference)
  const [keyId, setKeyId] = useState(keyPreference)
  const [melodyId, setMelodyId] = useState(melodyPreference)
  const [chordId, setChordId] = useState(chordInstPreference)
  const [loadingSounds, setLoadingSounds] = useState(false)

  useEffect(() => {
    setMelodyInstrument(melodyId)
  }, [melodyId])

  useEffect(() => {
    setChordInstrument(chordId)
  }, [chordId])

  useEffect(() => subscribeInstrumentLoading(setLoadingSounds), [])

  useEffect(() => {
    if (mockMode) return undefined
    const controller = new AbortController()
    fetch(`${API_BASE}/api/vibes`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('vibes')
        return response.json()
      })
      .then((data) => {
        setVibes(data.vibes ?? [])
        setKeys(data.keys ?? [])
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setError(SERVER_DOWN)
      })
    return () => controller.abort()
  }, [mockMode])

  function toggleChords() {
    setChordsOn((current) => {
      chordsPreference = !current
      return chordsPreference
    })
  }

  function chooseVibe(id) {
    vibePreference = id
    setVibeId(id)
  }

  function chooseKey(id) {
    keyPreference = id
    setKeyId(id)
  }

  function chooseMelody(id) {
    melodyPreference = id
    setMelodyId(id)
  }

  function chooseChords(id) {
    chordInstPreference = id
    setChordId(id)
  }

  function requestBody(kind) {
    const body = {}
    if (kind === 'notes') {
      body.notes = (queryNotes ?? []).map((note) => ({
        pitch: note.pitch,
        start: note.start,
        duration: note.duration,
      }))
    }
    if (vibeId) body.vibe = vibeId
    if (keyId !== 'auto') body.key = keyId
    return body
  }

  async function generate(kind) {
    const body = requestBody(kind)
    setError('')
    setSource(kind)
    setGenerating(true)
    try {
      if (mockMode) {
        setIdeas(body.vibe ? mockJazzy : mockFresh)
        stopPlayback()
        return
      }
      let response
      try {
        response = await fetch(`${API_BASE}/api/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      } catch {
        setError(SERVER_DOWN)
        return
      }
      if (!response.ok) {
        setError(await readDetail(response))
        return
      }
      setIdeas(await response.json())
      stopPlayback()
    } catch {
      setError('New ideas could not be generated.')
    } finally {
      setGenerating(false)
    }
  }

  function playIdea(idea) {
    if (playback?.id === idea.id) {
      stopPlayback()
      return
    }
    const { melody, chords } = ideaPerformance(ideas?.seed, idea)
    void playSequence(idea.id, melody, onPlayback, chordsOn ? chords : [])
  }

  const selectedVibe = vibes.find((vibe) => vibe.id === vibeId)

  return (
    <section className="explore" aria-labelledby="explore-heading" aria-busy={generating || loadingSounds}>
      <div className="explore__head">
        <h2 id="explore-heading">Explore</h2>
      </div>
      <div className="explore__vibes" role="radiogroup" aria-label="Vibe">
        <button
          type="button"
          role="radio"
          className={vibeId == null ? 'explore__vibe explore__vibe--on' : 'explore__vibe'}
          aria-checked={vibeId == null}
          onClick={() => chooseVibe(null)}
        >
          🎲 Surprise me
        </button>
        {vibes.map((vibe) => (
          <button
            key={vibe.id}
            type="button"
            role="radio"
            className={vibeId === vibe.id ? 'explore__vibe explore__vibe--on' : 'explore__vibe'}
            aria-checked={vibeId === vibe.id}
            onClick={() => chooseVibe(vibe.id)}
          >
            {vibe.label}
          </button>
        ))}
      </div>
      {selectedVibe?.description ? <p className="explore__vibe-desc">{selectedVibe.description}</p> : null}
      <div className="explore__fields">
        <label className="explore__field">
          Key
          <select value={keyId} onChange={(event) => chooseKey(event.target.value)}>
            <option value="auto">Auto</option>
            {keys.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </label>
        <label className="explore__field">
          Melody
          <select value={melodyId} onChange={(event) => chooseMelody(event.target.value)}>
            {INSTRUMENTS.map((instrument) => (
              <option key={instrument.id} value={instrument.id}>
                {instrument.label}
              </option>
            ))}
          </select>
        </label>
        <label className="explore__field">
          Chords
          <select value={chordId} onChange={(event) => chooseChords(event.target.value)}>
            {INSTRUMENTS.map((instrument) => (
              <option key={instrument.id} value={instrument.id}>
                {instrument.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className={chordsOn ? 'explore__chords explore__chords--on' : 'explore__chords'}
          aria-pressed={chordsOn}
          onClick={toggleChords}
        >
          Chords: {chordsOn ? 'On' : 'Off'}
        </button>
      </div>
      {loadingSounds ? (
        <p className="explore__status" role="status">
          Loading sounds…
        </p>
      ) : null}
      <div className="explore__actions">
        {queryNotes ? (
          <button type="button" className="explore__seed" disabled={generating} onClick={() => generate('notes')}>
            ✨ Explore new ideas from this melody
          </button>
        ) : null}
        <button type="button" className="explore__surprise" disabled={generating} onClick={() => generate('fresh')}>
          Surprise me
        </button>
      </div>
      <ErrorBanner message={error} />
      {ideas ? (
        <button
          type="button"
          className="explore__again"
          disabled={generating || !source}
          onClick={() => generate(source)}
        >
          Generate again
        </button>
      ) : null}
      {generating ? (
        <p className="explore__status" role="status">
          Writing new melodies…
        </p>
      ) : null}
      {ideas ? (
        <>
          <div className="explore__grid">
            {ideas.ideas.map((idea) => {
              const playing = playback?.id === idea.id
              const chordLabels = (idea.chords ?? [])
                .map((chord, index) => ({ symbol: chord.symbol, index }))
                .filter((chord) => chord.symbol)
              return (
                <article key={idea.id} className="idea">
                  <h3>{idea.title}</h3>
                  <div className="idea__tags">
                    {idea.vibe_label ? (
                      <span className={`idea__tag idea__tag--${idea.vibe || 'vibe'}`}>{idea.vibe_label}</span>
                    ) : null}
                    {idea.key ? <span className="idea__tag">{idea.key}</span> : null}
                    {idea.tempo_bpm ? <span className="idea__tag">{Math.round(idea.tempo_bpm)} bpm</span> : null}
                    {idea.form ? <span className="idea__tag">{idea.form}</span> : null}
                    {idea.swing ? <span className="idea__tag">swing</span> : null}
                  </div>
                  <p className="idea__desc">{idea.description}</p>
                  {idea.novelty ? (
                    <div className="idea__novelty">
                      <span className={`idea__badge idea__badge--${idea.novelty.label}`}>
                        {noveltyLabel(idea.novelty.label)}
                      </span>
                      {idea.novelty.message ? <p className="idea__message">{idea.novelty.message}</p> : null}
                    </div>
                  ) : null}
                  <PianoRoll
                    compact
                    query={{ notes: beatsToSeconds(idea.notes, idea.tempo_bpm) }}
                    activeIndex={playing && playback.index >= 0 ? playback.index : -1}
                    label={`Piano roll of ${idea.title}`}
                  />
                  {chordLabels.length ? (
                    <p className="idea__chords">
                      {chordLabels.map((chord, position) => {
                        const on = playing && playback.chordIndex === chord.index
                        return (
                          <span key={`${chord.index}-${chord.symbol}`} className="idea__chord-item">
                            {position > 0 ? (
                              <span className="idea__chord-sep" aria-hidden="true">
                                ·
                              </span>
                            ) : null}
                            <span
                              className={on ? 'idea__chord idea__chord--on' : 'idea__chord'}
                              aria-current={on ? 'true' : undefined}
                            >
                              {chord.symbol}
                            </span>
                          </span>
                        )
                      })}
                    </p>
                  ) : null}
                  <PlayButton
                    playing={playing}
                    onClick={() => playIdea(idea)}
                    label={
                      playing
                        ? `Stop ${idea.title}`
                        : idea.follows_seed
                          ? `Play yours, then ${idea.title}`
                          : `Play ${idea.title}`
                    }
                  >
                    {idea.follows_seed ? '▶ Play yours → continuation' : '▶ Play'}
                  </PlayButton>
                </article>
              )
            })}
          </div>
          <p className="explore__dropped">
            {ideas.too_familiar_dropped} ideas were discarded for sounding too close to known melodies.
          </p>
        </>
      ) : null}
    </section>
  )
}
