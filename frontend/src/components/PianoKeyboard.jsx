import { useEffect, useRef, useState } from 'react'
import { COMPUTER_KEY_LABELS, COMPUTER_KEYS, isSharp, midiLabel } from '../music'
import { playNote } from '../playback'
import './PianoKeyboard.css'

const START = 60
const OCTAVES = 2
const WHITE_COUNT = 7 * OCTAVES
const BLACK_WIDTH = (100 / WHITE_COUNT) * 0.62

function keysOf(kind) {
  const keys = []
  for (let octave = 0; octave < OCTAVES; octave += 1) {
    for (let semi = 0; semi < 12; semi += 1) {
      const pitch = START + octave * 12 + semi
      if (isSharp(pitch) === (kind === 'black')) keys.push(pitch)
    }
  }
  return keys
}

const WHITE_KEYS = keysOf('white')
const BLACK_KEYS = keysOf('black')

function blackLeft(pitch) {
  let whitesBefore = 0
  for (let midi = START; midi < pitch; midi += 1) {
    if (!isSharp(midi)) whitesBefore += 1
  }
  return whitesBefore * (100 / WHITE_COUNT) - BLACK_WIDTH / 2
}

function spokenName(pitch) {
  return midiLabel(pitch).replace('#', ' sharp ')
}

export default function PianoKeyboard({ busy = false, onSearch }) {
  const [notes, setNotes] = useState([])
  const [pressed, setPressed] = useState(() => new Set())
  const originRef = useRef(0)
  const addRef = useRef(null)

  function addPitch(pitch) {
    if (busy) return
    const now = performance.now()
    setNotes((prev) => {
      if (prev.length >= 200) return prev
      if (prev.length === 0) {
        originRef.current = now
        return [{ pitch, start: 0, duration: 0.5 }]
      }
      const start = (now - originRef.current) / 1000
      const next = prev.slice()
      const last = next[next.length - 1]
      next[next.length - 1] = { ...last, duration: Math.max(0.05, start - last.start) }
      next.push({ pitch, start, duration: 0.5 })
      return next
    })
    void playNote(pitch)
  }

  useEffect(() => {
    addRef.current = addPitch
  })

  useEffect(() => {
    function onKeyDown(event) {
      if (event.repeat || event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target
      if (
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      ) {
        return
      }
      const pitch = COMPUTER_KEYS[event.key.toLowerCase()]
      if (!pitch) return
      event.preventDefault()
      addRef.current?.(pitch)
      setPressed((current) => {
        const next = new Set(current)
        next.add(pitch)
        return next
      })
    }

    function onKeyUp(event) {
      const pitch = COMPUTER_KEYS[event.key.toLowerCase()]
      if (!pitch) return
      setPressed((current) => {
        if (!current.has(pitch)) return current
        const next = new Set(current)
        next.delete(pitch)
        return next
      })
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [])

  function release(pitch) {
    setPressed((current) => {
      if (!current.has(pitch)) return current
      const next = new Set(current)
      next.delete(pitch)
      return next
    })
  }

  function undo() {
    setNotes((prev) => {
      if (prev.length <= 1) {
        originRef.current = 0
        return []
      }
      const next = prev.slice(0, -1)
      next[next.length - 1] = { ...next[next.length - 1], duration: 0.5 }
      return next
    })
  }

  function clear() {
    originRef.current = 0
    setNotes([])
  }

  const ready = notes.length >= 4 && !busy

  return (
    <div className="keys-panel">
      <p className="keys-panel__hint">Computer keys A W S E D F T G Y H U J K play C4 through C5.</p>
      <div className="keyboard">
        <div className="keyboard__whites">
          {WHITE_KEYS.map((pitch) => (
            <button
              key={pitch}
              type="button"
              className={pressed.has(pitch) ? 'pkey pkey--white pkey--on' : 'pkey pkey--white'}
              aria-label={spokenName(pitch)}
              onPointerDown={(event) => {
                event.preventDefault()
                addPitch(pitch)
                setPressed((current) => new Set(current).add(pitch))
              }}
              onPointerUp={() => release(pitch)}
              onPointerLeave={() => release(pitch)}
            >
              {COMPUTER_KEY_LABELS[pitch] ? (
                <span className="pkey__hint">{COMPUTER_KEY_LABELS[pitch]}</span>
              ) : null}
              <span className="pkey__name">{midiLabel(pitch)}</span>
            </button>
          ))}
        </div>
        {BLACK_KEYS.map((pitch) => (
          <button
            key={pitch}
            type="button"
            className={pressed.has(pitch) ? 'pkey pkey--black pkey--on' : 'pkey pkey--black'}
            style={{ left: `${blackLeft(pitch)}%`, width: `${BLACK_WIDTH}%` }}
            aria-label={spokenName(pitch)}
            onPointerDown={(event) => {
              event.preventDefault()
              addPitch(pitch)
              setPressed((current) => new Set(current).add(pitch))
            }}
            onPointerUp={() => release(pitch)}
            onPointerLeave={() => release(pitch)}
          >
            {COMPUTER_KEY_LABELS[pitch] ? <span className="pkey__hint">{COMPUTER_KEY_LABELS[pitch]}</span> : null}
          </button>
        ))}
      </div>
      <div className="keys-panel__notes">
        {notes.length === 0 ? (
          <p className="keys-panel__empty">Play a melody, then search.</p>
        ) : (
          <ul className="chips" aria-label="Notes entered">
            {notes.map((note, index) => (
              <li key={`${note.start}-${note.pitch}-${index}`} className="chip">
                {midiLabel(note.pitch)}
              </li>
            ))}
          </ul>
        )}
        <div className="keys-panel__actions">
          <button type="button" className="text-btn" onClick={undo} disabled={notes.length === 0 || busy}>
            Undo
          </button>
          <button type="button" className="text-btn" onClick={clear} disabled={notes.length === 0 || busy}>
            Clear
          </button>
          <button type="button" className="search-btn" onClick={() => onSearch?.(notes)} disabled={!ready}>
            {busy ? 'Searching…' : notes.length < 4 ? `Search · ${notes.length}/4` : 'Search'}
          </button>
        </div>
      </div>
    </div>
  )
}
