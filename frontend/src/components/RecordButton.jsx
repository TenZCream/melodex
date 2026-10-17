import { useEffect, useRef, useState } from 'react'
import { startRecording } from '../recordWav'
import './RecordButton.css'

const LIMIT_SECONDS = 20

function formatTime(seconds) {
  const whole = Math.max(0, Math.floor(seconds))
  const mins = Math.floor(whole / 60)
  const secs = String(whole % 60).padStart(2, '0')
  return `${mins}:${secs}`
}

export default function RecordButton({ busy = false, invite = false, onRecordStart, onRecorded }) {
  const recRef = useRef(null)
  const stopLock = useRef(false)
  const onRecordedRef = useRef(onRecorded)
  const [phase, setPhase] = useState('idle')
  const [elapsed, setElapsed] = useState(0)
  const [micError, setMicError] = useState('')

  useEffect(() => {
    onRecordedRef.current = onRecorded
  }, [onRecorded])

  async function stopAndSend() {
    if (stopLock.current) return
    const rec = recRef.current
    if (!rec) return
    stopLock.current = true
    recRef.current = null
    setPhase('encoding')
    try {
      const blob = await rec.stop()
      setPhase('idle')
      await onRecordedRef.current?.(blob)
    } catch (err) {
      console.error(err)
      setMicError('Could not finish that recording.')
      setPhase('idle')
    } finally {
      stopLock.current = false
      setElapsed(0)
    }
  }

  const stopRef = useRef(stopAndSend)
  useEffect(() => {
    stopRef.current = stopAndSend
  })

  useEffect(() => {
    if (phase !== 'recording') return undefined
    const started = performance.now()
    const id = window.setInterval(() => {
      const next = (performance.now() - started) / 1000
      if (next >= LIMIT_SECONDS) {
        setElapsed(LIMIT_SECONDS)
        window.clearInterval(id)
        stopRef.current()
      } else {
        setElapsed(next)
      }
    }, 100)
    return () => window.clearInterval(id)
  }, [phase])

  useEffect(() => {
    return () => {
      recRef.current?.stream?.getTracks().forEach((track) => track.stop())
      recRef.current = null
    }
  }, [])

  async function onClick() {
    if (busy || phase === 'encoding' || stopLock.current) return
    setMicError('')

    if (phase === 'recording') {
      await stopAndSend()
      return
    }

    try {
      onRecordStart?.()
      const rec = await startRecording()
      recRef.current = rec
      setElapsed(0)
      setPhase('recording')
    } catch (err) {
      console.error(err)
      setMicError('Allow the microphone to record a hum.')
    }
  }

  const recording = phase === 'recording'
  const remaining = Math.max(0, Math.ceil(LIMIT_SECONDS - elapsed))
  const status = busy ? 'Listening for the melody…' : phase === 'encoding' ? 'Encoding…' : ''
  const showInvite = invite && !busy && phase === 'idle'

  return (
    <div className="record">
      <button
        type="button"
        className={`record__button${recording ? ' record__button--live' : ''}`}
        onClick={onClick}
        disabled={busy || phase === 'encoding'}
        aria-pressed={recording}
        aria-label={
          recording ? `Stop recording, ${remaining} seconds left` : 'Start recording'
        }
      >
        <span className="record__pulse" aria-hidden="true" />
        <span className="record__pulse record__pulse--late" aria-hidden="true" />
        <span className="record__disc" aria-hidden="true">
          {recording ? <span className="record__stop" /> : null}
        </span>
        {recording ? <span className="record__timer">{formatTime(remaining)}</span> : null}
      </button>
      {status || showInvite || micError ? (
        <div className="record__copy">
          {status ? <p className="record__status">{status}</p> : null}
          {showInvite ? (
            <p className="record__invite">Hum, sing, or whistle a melody for 5–15 seconds</p>
          ) : null}
          {micError ? (
            <p className="record__error" role="alert">
              {micError}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
