import { useEffect, useState } from 'react'
import ErrorBanner from './components/ErrorBanner'
import Header from './components/Header'
import PianoRoll from './components/PianoRoll'
import RecordButton from './components/RecordButton'
import ResultsList from './components/ResultsList'
import VerdictBanner from './components/VerdictBanner'
import { API_BASE } from './config'
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

export default function App() {
  const mockMode = mockModeEnabled()
  const [connection, setConnection] = useState(mockMode ? 'on' : 'pending')
  const [indexSize, setIndexSize] = useState(mockMode ? mockSearch.index_size : null)
  const [result, setResult] = useState(mockMode ? mockSearch : null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState('')

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

  async function onRecorded(blob) {
    setError('')
    if (mockMode) {
      setResult(mockSearch)
      return
    }

    setSearching(true)
    try {
      const form = new FormData()
      form.append('file', blob, 'hum.wav')
      let response
      try {
        response = await fetch(`${API_BASE}/api/search/audio`, { method: 'POST', body: form })
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

  return (
    <div className="app">
      <Header connection={connection} indexSize={indexSize} />
      <main className="stage">
        <RecordButton
          busy={searching}
          invite={!result && !searching}
          onRecordStart={() => setError('')}
          onRecorded={onRecorded}
        />
        <ErrorBanner message={error} />
        {result ? (
          <>
            <VerdictBanner verdict={result.verdict} warnings={result.warnings} />
            <PianoRoll query={result.query} />
            <ResultsList results={result.results} indexSize={result.index_size} />
          </>
        ) : null}
      </main>
    </div>
  )
}
