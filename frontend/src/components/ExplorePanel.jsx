import { useState } from 'react'
import { API_BASE } from '../config'
import mockFresh from '../mocks/generate_fresh.json'
import mockFromHum from '../mocks/generate_from_hum.json'
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

export default function ExplorePanel({ queryNotes, mockMode, playback, onPlayback }) {
  const [ideas, setIdeas] = useState(null)
  const [requestBody, setRequestBody] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [chordsOn, setChordsOn] = useState(chordsPreference)

  function toggleChords() {
    setChordsOn((current) => {
      chordsPreference = !current
      return chordsPreference
    })
  }

  async function generate(body) {
    setError('')
    setRequestBody(body)
    setGenerating(true)
    try {
      if (mockMode) {
        setIdeas(body.notes ? mockFromHum : mockFresh)
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

  function fromThisMelody() {
    const notes = (queryNotes ?? []).map((note) => ({
      pitch: note.pitch,
      start: note.start,
      duration: note.duration,
    }))
    return generate({ notes })
  }

  function playIdea(idea) {
    if (playback?.id === idea.id) {
      stopPlayback()
      return
    }
    const { melody, chords } = ideaPerformance(ideas?.seed, idea)
    void playSequence(idea.id, melody, onPlayback, chordsOn ? chords : [])
  }

  return (
    <section className="explore" aria-labelledby="explore-heading" aria-busy={generating}>
      <div className="explore__head">
        <h2 id="explore-heading">Explore</h2>
        <button
          type="button"
          className={chordsOn ? 'explore__chords explore__chords--on' : 'explore__chords'}
          aria-pressed={chordsOn}
          onClick={toggleChords}
        >
          Chords: {chordsOn ? 'On' : 'Off'}
        </button>
      </div>
      <div className="explore__actions">
        {queryNotes ? (
          <button type="button" className="explore__seed" disabled={generating} onClick={fromThisMelody}>
            ✨ Explore new ideas from this melody
          </button>
        ) : null}
        <button type="button" className="explore__surprise" disabled={generating} onClick={() => generate({})}>
          Surprise me
        </button>
      </div>
      <ErrorBanner message={error} />
      {ideas ? (
        <button
          type="button"
          className="explore__again"
          disabled={generating || !requestBody}
          onClick={() => generate(requestBody)}
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
                            <span className={on ? 'idea__chord idea__chord--on' : 'idea__chord'} aria-current={on ? 'true' : undefined}>
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
