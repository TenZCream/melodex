import { useEffect, useRef, useState } from 'react'
import { API_BASE } from '../config'
import {
  INSTRUMENTS,
  setChordInstrument,
  setMelodyInstrument,
  subscribeInstrumentLoading,
} from '../instruments'
import mockDescribe from '../mocks/describe_rainy.json'
import mockFresh from '../mocks/generate_fresh.json'
import mockJazzy from '../mocks/generate_jazzy.json'
import mockVibes from '../mocks/vibes.json'
import { beatsToSeconds, ideaPerformance } from '../music'
import {
  getMixerSettings,
  playSequence,
  setChordMuted,
  setChordVolume,
  setMelodyMuted,
  setMelodyVolume,
  stopPlayback,
} from '../playback'
import ErrorBanner from './ErrorBanner'
import PianoRoll from './PianoRoll'
import PlayButton from './PlayButton'
import './ExplorePanel.css'

const SERVER_DOWN = "Can't reach the Melodex server. Is the backend running on port 8000?"

async function readDetail(response, fallback = 'New ideas could not be generated.') {
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
  return fallback
}

function noveltyLabel(label) {
  if (label === 'novel') return 'Not in our index'
  if (label === 'echoes') return 'Echoes a known tune'
  return label
}

const MELODY_FROM_API = {
  piano: 'piano',
  strings: 'strings',
  guitar: 'guitar',
  flute: 'flute',
  synth: 'synth',
  'electric-piano': 'epiano',
}

const VIBE_ORDER = ['happy', 'sad', 'pop', 'mysterious', 'dissonant', 'jazzy', 'swingy']

let vibePreference = null
let keyPreference = 'auto'
let melodyPreference = 'piano'
let chordInstPreference = 'piano'

function orderedVibes(vibes) {
  const ranked = VIBE_ORDER.map((id) => vibes.find((vibe) => vibe.id === id)).filter(Boolean)
  const rest = vibes.filter((vibe) => !VIBE_ORDER.includes(vibe.id))
  return [...ranked, ...rest]
}

function SeedChip({ notes, onClear }) {
  if (!notes) return null
  return (
    <p className="seed-chip">
      Building on your melody
      <button type="button" aria-label="Clear melody" onClick={onClear}>
        ✕
      </button>
    </p>
  )
}

function Interpretation({ interpretation }) {
  if (!interpretation) return null
  return (
    <div className="interpret">
      {interpretation.source === 'gemini' ? <span className="interpret__source">Powered by Gemini</span> : null}
      {interpretation.source === 'fallback' ? (
        <span className="interpret__source" title={interpretation.note || undefined}>
          Keyword mode
        </span>
      ) : null}
      <p className="interpret__heard">
        Gemini heard:{' '}
        {[
          interpretation.vibe_label,
          interpretation.key,
          Number.isFinite(Number(interpretation.tempo_bpm)) ? `${Math.round(Number(interpretation.tempo_bpm))} bpm` : null,
          interpretation.instrument,
        ]
          .filter(Boolean)
          .join(' · ')}
      </p>
      {interpretation.reason ? <p className="interpret__reason">{interpretation.reason}</p> : null}
    </div>
  )
}

function IdeaResults({ ideas, playback, onPlay }) {
  if (!ideas) return null
  return (
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
                  <span className={`idea__badge idea__badge--${idea.novelty.label}`}>{noveltyLabel(idea.novelty.label)}</span>
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
                onClick={() => onPlay(idea)}
                label={
                  playing ? `Stop ${idea.title}` : idea.follows_seed ? `Play yours, then ${idea.title}` : `Play ${idea.title}`
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
  )
}

export default function ExplorePanel({ melodySeed, mockMode, playback, onPlayback }) {
  const [submode, setSubmode] = useState(null)
  const [pickIdeas, setPickIdeas] = useState(null)
  const [describeIdeas, setDescribeIdeas] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [describing, setDescribing] = useState(false)
  const [describeText, setDescribeText] = useState('')
  const [buildingNotes, setBuildingNotes] = useState(null)
  const [pickError, setPickError] = useState('')
  const [describeError, setDescribeError] = useState('')
  const [catalogError, setCatalogError] = useState('')
  const savedMixer = getMixerSettings()
  const [melodyOn, setMelodyOn] = useState(!savedMixer.melodyMuted)
  const [melodyVolume, setMelodyLevel] = useState(savedMixer.melody)
  const [chordsOn, setChordsOn] = useState(!savedMixer.chordsMuted)
  const [chordVolume, setChordLevel] = useState(savedMixer.chords)
  const [vibes, setVibes] = useState(mockMode ? mockVibes.vibes : [])
  const [keys, setKeys] = useState(mockMode ? mockVibes.keys : [])
  const [vibeId, setVibeId] = useState(vibePreference)
  const [keyId, setKeyId] = useState(keyPreference)
  const [melodyId, setMelodyId] = useState(melodyPreference)
  const [chordId, setChordId] = useState(chordInstPreference)
  const [loadingSounds, setLoadingSounds] = useState(false)
  const settingsRef = useRef({ keyId })
  const generateRef = useRef(null)
  const handledSeeds = useRef(new Set())
  const busy = generating || describing
  const vibeChoices = orderedVibes(vibes)
  const selectedVibe = vibes.find((vibe) => vibe.id === vibeId) ?? null

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
        setCatalogError(SERVER_DOWN)
      })
    return () => controller.abort()
  }, [mockMode])

  function chooseVibe(id) {
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

  function applyInterpretation(interpretation) {
    if (!interpretation) return
    const melody = MELODY_FROM_API[interpretation.instrument]
    if (melody) chooseMelody(melody)
  }

  async function generate(notes = buildingNotes, vibe = vibeId, key = keyId) {
    const body = { notes: notes ?? [] }
    if (vibe) body.vibe = vibe
    if (key && key !== 'auto') body.key = key
    setPickError('')
    setGenerating(true)
    try {
      if (mockMode) {
        setPickIdeas(body.vibe ? mockJazzy : mockFresh)
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
        setPickError(SERVER_DOWN)
        return
      }
      if (!response.ok) {
        setPickError(await readDetail(response))
        return
      }
      setPickIdeas(await response.json())
      stopPlayback()
    } catch {
      setPickError('New ideas could not be generated.')
    } finally {
      setGenerating(false)
    }
  }

  useEffect(() => {
    vibePreference = vibeId
    settingsRef.current = { keyId }
    generateRef.current = generate
  })

  useEffect(() => {
    if (!melodySeed || handledSeeds.current.has(melodySeed.id)) return
    handledSeeds.current.add(melodySeed.id)
    const notes = melodySeed.notes ?? []
    setBuildingNotes(notes)
    setVibeId(null)
    setSubmode('pick')
    void generateRef.current?.(notes, null, settingsRef.current.keyId)
  }, [melodySeed])

  async function describe() {
    const text = describeText.trim()
    if (text.length < 2 || describing || generating) return
    const notes = buildingNotes ?? []
    setDescribeError('')
    setDescribing(true)
    try {
      if (mockMode) {
        setDescribeIdeas(mockDescribe)
        applyInterpretation(mockDescribe.interpretation)
        stopPlayback()
        return
      }
      let response
      try {
        response = await fetch(`${API_BASE}/api/describe`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, notes }),
        })
      } catch {
        setDescribeError(SERVER_DOWN)
        return
      }
      if (!response.ok) {
        setDescribeError(await readDetail(response, 'The description could not be composed.'))
        return
      }
      const data = await response.json()
      setDescribeIdeas(data)
      applyInterpretation(data.interpretation)
      stopPlayback()
    } catch {
      setDescribeError('The description could not be composed.')
    } finally {
      setDescribing(false)
    }
  }

  function playFrom(result, idea) {
    if (playback?.id === idea.id) {
      stopPlayback()
      return
    }
    const { melody, chords } = ideaPerformance(result?.seed, idea)
    void playSequence(idea.id, melody, onPlayback, chords)
  }

  function clearMelody() {
    setBuildingNotes(null)
  }

  const settings = (
    <div className="explore__settings">
      <h2 className="explore__label">Settings</h2>
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
      </div>
    </div>
  )

  const mixer = (
    <div className="mixer" aria-label="Mixer">
      <span className="mixer__title">Mixer</span>
      <div className="mixer__row">
        <button
          type="button"
          className={melodyOn ? 'mixer__toggle mixer__toggle--on' : 'mixer__toggle'}
          aria-pressed={melodyOn}
          title="Turn the melody off to sing along over the chords."
          onClick={() => {
            const next = !melodyOn
            setMelodyOn(next)
            setMelodyMuted(!next)
          }}
        >
          Melody
        </button>
        <input
          className={melodyOn ? 'mixer__slider' : 'mixer__slider mixer__slider--off'}
          type="range"
          min="0"
          max="100"
          value={melodyVolume}
          aria-label="Melody volume"
          onChange={(event) => {
            const next = Number(event.target.value)
            setMelodyLevel(next)
            setMelodyVolume(next)
          }}
        />
      </div>
      <div className="mixer__row">
        <button
          type="button"
          className={chordsOn ? 'mixer__toggle mixer__toggle--on' : 'mixer__toggle'}
          aria-pressed={chordsOn}
          onClick={() => {
            const next = !chordsOn
            setChordsOn(next)
            setChordMuted(!next)
          }}
        >
          Chords
        </button>
        <input
          className={chordsOn ? 'mixer__slider' : 'mixer__slider mixer__slider--off'}
          type="range"
          min="0"
          max="100"
          value={chordVolume}
          aria-label="Chords volume"
          onChange={(event) => {
            const next = Number(event.target.value)
            setChordLevel(next)
            setChordVolume(next)
          }}
        />
      </div>
      {!melodyOn && !chordsOn ? <p className="mixer__hint">Both parts are muted</p> : null}
    </div>
  )

  return (
    <div className="explore" aria-label="Explore" aria-busy={busy || loadingSounds}>
      {submode == null ? (
        <>
          <SeedChip notes={buildingNotes} onClear={clearMelody} />
          <ErrorBanner message={catalogError} />
          <div className="explore__choices">
            <button type="button" className="explore__choice" onClick={() => setSubmode('describe')}>
              <span className="explore__choice-title">💬 Describe a vibe</span>
              <span className="explore__choice-sub">Tell Gemini the mood in words</span>
            </button>
            <button type="button" className="explore__choice" onClick={() => setSubmode('pick')}>
              <span className="explore__choice-title">🎛️ Pick a vibe</span>
              <span className="explore__choice-sub">Choose Happy, Sad, Jazzy and more</span>
            </button>
          </div>
        </>
      ) : null}

      {submode === 'describe' ? (
        <form
          className="explore__mode"
          onSubmit={(event) => {
            event.preventDefault()
            void describe()
          }}
        >
          <button type="button" className="explore__back" onClick={() => setSubmode(null)}>
            ← Back
          </button>
          <label className="explore__label" htmlFor="describe-vibe">
            Describe a vibe
          </label>
          <input
            id="describe-vibe"
            className="describe__input"
            value={describeText}
            maxLength={300}
            placeholder="Describe a vibe… e.g. rainy 3am drive home"
            onChange={(event) => setDescribeText(event.target.value)}
          />
          {settings}
          {mixer}
          {loadingSounds ? (
            <p className="explore__status" role="status">
              Loading sounds…
            </p>
          ) : null}
          <SeedChip notes={buildingNotes} onClear={clearMelody} />
          <button type="submit" className="explore__compose" disabled={busy || describeText.trim().length < 2}>
            ✨ Compose with Gemini
          </button>
          <ErrorBanner message={describeError} />
          {describing ? (
            <p className="explore__status" role="status">
              Gemini is choosing the vibe…
            </p>
          ) : null}
          <Interpretation interpretation={describeIdeas?.interpretation} />
          <IdeaResults ideas={describeIdeas} playback={playback} onPlay={(idea) => playFrom(describeIdeas, idea)} />
        </form>
      ) : null}

      {submode === 'pick' ? (
        <div className="explore__mode">
          <button type="button" className="explore__back" onClick={() => setSubmode(null)}>
            ← Back
          </button>
          <div className="explore__vibes" role="radiogroup" aria-label="Vibe">
            {vibeChoices.map((vibe) => (
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
            <button
              type="button"
              role="radio"
              className={vibeId == null ? 'explore__vibe explore__vibe--on' : 'explore__vibe'}
              aria-checked={vibeId == null}
              onClick={() => chooseVibe(null)}
            >
              🎲 Surprise me
            </button>
          </div>
          {selectedVibe?.description ? <p className="explore__vibe-desc">{selectedVibe.description}</p> : null}
          <ErrorBanner message={catalogError} />
          {settings}
          {mixer}
          {loadingSounds ? (
            <p className="explore__status" role="status">
              Loading sounds…
            </p>
          ) : null}
          <SeedChip notes={buildingNotes} onClear={clearMelody} />
          <button type="button" className="explore__compose" disabled={busy} onClick={() => void generate()}>
            ✨ Compose
          </button>
          <ErrorBanner message={pickError} />
          {generating ? (
            <p className="explore__status" role="status">
              Writing new melodies…
            </p>
          ) : null}
          <IdeaResults ideas={pickIdeas} playback={playback} onPlay={(idea) => playFrom(pickIdeas, idea)} />
        </div>
      ) : null}
    </div>
  )
}
