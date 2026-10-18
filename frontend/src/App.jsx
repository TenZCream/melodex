import { useEffect, useState } from 'react'
import ErrorBanner from './components/ErrorBanner'
import ExplorePanel from './components/ExplorePanel'
import Header from './components/Header'
import ModeToggle from './components/ModeToggle'
import PianoKeyboard from './components/PianoKeyboard'
import PianoRoll from './components/PianoRoll'
import RecordButton from './components/RecordButton'
import ResultsList from './components/ResultsList'
import VerdictBanner from './components/VerdictBanner'
import { API_BASE } from './config'
import { segmentToSeconds } from './music'
import { playSequence, stopPlayback } from './playback'
import mockSearch from './mocks/search_strong_match.json'
import './App.css'

const SERVER_DOWN = "Can't reach the Melodex server. Is the backend running on port 8000?"

function mockModeEnabled() {
  return new URLSearchParams(window.location.search).get('mock') === '1'
}

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
  return 'The search could not be completed.'
}

function SearchResults({ result, playback, onPlayQuery, onPlayResult, onExplore }) {
  if (!result) return null
  return (
    <div className="search-results">
      <VerdictBanner verdict={result.verdict} warnings={result.warnings} />
      <PianoRoll
        query={result.query}
        playing={playback?.id === 'query'}
        activeIndex={playback?.id === 'query' ? playback.index : -1}
        onPlay={onPlayQuery}
      />
      <ResultsList
        results={result.results}
        indexSize={result.index_size}
        playingId={playback?.id}
        onPlay={onPlayResult}
      />
      <button type="button" className="from-melody" onClick={onExplore}>
        ✨ Explore new ideas from this melody
      </button>
    </div>
  )
}

export default function App() {
  const mockMode = mockModeEnabled()
  const [connection, setConnection] = useState(mockMode ? 'on' : 'pending')
  const [indexSize, setIndexSize] = useState(mockMode ? mockSearch.index_size : null)
  const [result, setResult] = useState(mockMode ? mockSearch : null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState('hum')
  const [playback, setPlayback] = useState(null)
  const [melodySeed, setMelodySeed] = useState(null)

  useEffect(() => {
    if (mockMode) return undefined
    const controller = new AbortController()
    fetch(`${API_BASE}/api/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('health')
        return response.json()
      })
      .then((data) => {
        setConnection('on')
        setIndexSize(data.index_size)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setConnection('off')
        setIndexSize(null)
      })
    return () => controller.abort()
  }, [mockMode])

  useEffect(() => () => stopPlayback(), [])

  async function runSearch(request) {
    setError('')
    stopPlayback()
    if (mockMode) {
      setResult(mockSearch)
      return
    }

    setSearching(true)
    try {
      let response
      try {
        response = await request()
      } catch {
        setError(SERVER_DOWN)
        return
      }
      if (!response.ok) {
        setError(await readDetail(response))
        return
      }
      setResult(await response.json())
    } catch {
      setError('The search could not be completed.')
    } finally {
      setSearching(false)
    }
  }

  function onRecorded(blob) {
    return runSearch(() => {
      const form = new FormData()
      form.append('file', blob, 'hum.wav')
      return fetch(`${API_BASE}/api/search/audio`, { method: 'POST', body: form })
    })
  }

  function onNotes(notes) {
    const payload = notes.map((note) => ({
      pitch: note.pitch,
      start: Number(note.start.toFixed(3)),
      duration: Number(note.duration.toFixed(3)),
    }))
    return runSearch(() =>
      fetch(`${API_BASE}/api/search/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: payload }),
      }),
    )
  }

  function playQuery() {
    if (playback?.id === 'query') {
      stopPlayback()
      return
    }
    const notes = (result?.query?.notes ?? []).map((note) => ({
      pitch: note.pitch,
      start: note.start,
      duration: note.duration,
    }))
    void playSequence('query', notes, setPlayback, [], 'search')
  }

  function playResult(match) {
    if (playback?.id === match.id) {
      stopPlayback()
      return
    }
    void playSequence(match.id, segmentToSeconds(match), setPlayback, [], 'search')
  }

  function exploreFromMelody() {
    const notes = (result?.query?.notes ?? []).map((note) => ({
      pitch: note.pitch,
      start: note.start,
      duration: note.duration,
    }))
    setMelodySeed({ id: Date.now(), notes })
    setMode('explore')
  }

  return (
    <div className="app">
      <Header connection={connection} indexSize={indexSize} />
      <main className="stage">
        <ModeToggle mode={mode} onChange={setMode} />
        <div
          className="panel"
          id="panel-hum"
          role="tabpanel"
          aria-labelledby="tab-hum"
          hidden={mode !== 'hum'}
        >
          {mode === 'hum' ? (
            <RecordButton
              busy={searching}
              invite={!result && !searching}
              onRecordStart={() => setError('')}
              onRecorded={onRecorded}
            />
          ) : null}
          <ErrorBanner message={error} />
          <SearchResults
            result={result}
            playback={playback}
            onPlayQuery={playQuery}
            onPlayResult={playResult}
            onExplore={exploreFromMelody}
          />
        </div>
        <div
          className="panel"
          id="panel-keys"
          role="tabpanel"
          aria-labelledby="tab-keys"
          hidden={mode !== 'keys'}
        >
          <PianoKeyboard busy={searching} active={mode === 'keys'} onSearch={onNotes} />
          <ErrorBanner message={error} />
          <SearchResults
            result={result}
            playback={playback}
            onPlayQuery={playQuery}
            onPlayResult={playResult}
            onExplore={exploreFromMelody}
          />
        </div>
        <div
          className="panel"
          id="panel-explore"
          role="tabpanel"
          aria-labelledby="tab-explore"
          hidden={mode !== 'explore'}
        >
          <ExplorePanel
            melodySeed={melodySeed}
            mockMode={mockMode}
            playback={playback}
            onPlayback={setPlayback}
          />
        </div>
      </main>
    </div>
  )
}
