import { useEffect, useId, useRef, useState } from 'react'
import { isSharp, midiLabel } from '../music'
import PlayButton from './PlayButton'
import './PianoRoll.css'

const HEIGHT = 312
const PAD = { top: 14, right: 14, bottom: 28, left: 52 }

function pitchSegments(times, midi, xOf, yOf) {
  const count = Math.min(times?.length ?? 0, midi?.length ?? 0)
  const segments = []
  let current = []

  for (let i = 0; i < count; i++) {
    if (midi[i] == null) {
      if (current.length > 1) segments.push(current)
      current = []
      continue
    }
    current.push([xOf(times[i]), yOf(midi[i])])
  }
  if (current.length > 1) segments.push(current)

  return segments.map((segment) =>
    segment
      .map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`)
      .join(' '),
  )
}

export default function PianoRoll({ query, playing = false, activeIndex = -1, onPlay }) {
  const notes = query?.notes ?? []
  const track = query?.pitch_track
  const wrapRef = useRef(null)
  const clipId = useId().replace(/:/g, '')
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return undefined
    const observer = new ResizeObserver(([entry]) => {
      setWidth(Math.max(280, Math.floor(entry.contentRect.width)))
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const plotW = Math.max(1, width - PAD.left - PAD.right)
  const plotH = HEIGHT - PAD.top - PAD.bottom

  const notePitches = notes.map((note) => note.pitch)
  const trackPitches = (track?.midi ?? []).filter((value) => value != null)
  const pitches = [...notePitches, ...trackPitches]
  const noteTimes = notes.flatMap((note) => [note.start, note.start + note.duration])
  const times = [...noteTimes, ...(track?.times ?? [])]

  const ready = width > 0 && pitches.length > 0 && times.length > 0
  const minPitch = ready ? Math.floor(Math.min(...pitches)) - 1 : 60
  const maxPitch = ready ? Math.ceil(Math.max(...pitches)) + 1 : 72
  const pitchSpan = Math.max(1, maxPitch - minPitch)
  const t0 = ready ? Math.min(...times) : 0
  const t1 = ready ? Math.max(...times) : 1
  const timePad = Math.max(0.05, (t1 - t0) * 0.02)
  const timeSpan = Math.max(0.001, t1 - t0 + timePad * 2)

  const xOf = (time) => PAD.left + ((time - (t0 - timePad)) / timeSpan) * plotW
  const yOf = (pitch) => PAD.top + ((maxPitch - pitch) / pitchSpan) * plotH
  const rowH = plotH / pitchSpan

  const lanes = []
  for (let pitch = minPitch; pitch <= maxPitch; pitch++) lanes.push(pitch)

  let tickStep = 1
  while ((plotW / Math.max(0.001, t1 - t0)) * tickStep < 52 && tickStep < 16) tickStep += 1
  const ticks = []
  if (ready) {
    const first = Math.ceil((t0 - timePad) / tickStep) * tickStep
    for (let second = Math.max(0, first); second <= t1 + timePad; second += tickStep) {
      const x = PAD.left + ((second - (t0 - timePad)) / timeSpan) * plotW
      if (x >= PAD.left + 14 && x <= width - PAD.right - 10) ticks.push(second)
    }
  }

  const curves = ready ? pitchSegments(track?.times, track?.midi, xOf, yOf) : []
  const barH = Math.min(14, Math.max(7, rowH * 0.42))

  return (
    <section className="piano" aria-labelledby="piano-heading">
      <div className="piano__head">
        <div>
          <h2 id="piano-heading">What you hummed</h2>
          <p>
            {query?.key ? `${query.key}` : 'Detected phrase'}
            {query?.num_notes ? ` · ${query.num_notes} notes` : ''}
          </p>
        </div>
        <PlayButton playing={playing} onClick={onPlay} label={playing ? 'Stop playback' : 'Play what you hummed'}>
          ▶ Play what you hummed
        </PlayButton>
      </div>
      <div className="piano__canvas" ref={wrapRef}>
        {ready ? (
            <svg
            className="piano__svg"
            width={width}
            height={HEIGHT}
            viewBox={`0 0 ${width} ${HEIGHT}`}
            role="img"
            aria-label="Piano roll of the hummed notes, with the pitch curve behind them."
          >
            <defs>
              <clipPath id={clipId}>
                <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH} />
              </clipPath>
            </defs>
            <rect className="piano__board" x="0" y="0" width={width} height={HEIGHT} rx="12" />
            {lanes.map((pitch) => (
              <g key={pitch}>
                {isSharp(pitch) ? (
                  <rect
                    className="piano__lane"
                    x={PAD.left}
                    y={yOf(pitch + 0.5)}
                    width={plotW}
                    height={rowH}
                  />
                ) : null}
                <line
                  className={pitch % 12 === 0 ? 'piano__grid piano__grid--c' : 'piano__grid'}
                  x1={PAD.left}
                  x2={PAD.left + plotW}
                  y1={yOf(pitch)}
                  y2={yOf(pitch)}
                />
                {rowH >= 15 ? (
                  <text
                    className={isSharp(pitch) ? 'piano__axis piano__axis--sharp' : 'piano__axis'}
                    x={PAD.left - 8}
                    y={yOf(pitch)}
                    textAnchor="end"
                    dominantBaseline="middle"
                  >
                    {midiLabel(pitch)}
                  </text>
                ) : null}
              </g>
            ))}
            {ticks.map((second) => (
              <g key={second}>
                <line
                  className="piano__beat"
                  x1={xOf(second)}
                  x2={xOf(second)}
                  y1={PAD.top}
                  y2={PAD.top + plotH}
                />
                <text className="piano__time" x={xOf(second)} y={HEIGHT - 8} textAnchor="middle">
                  {second}s
                </text>
              </g>
            ))}
            <g clipPath={`url(#${clipId})`}>
              {curves.map((d, index) => (
                <g key={index}>
                  <path className="piano__curve piano__curve--glow" d={d} />
                  <path className="piano__curve" d={d} />
                </g>
              ))}
              {notes.map((note, index) => {
                const x = xOf(note.start)
                const w = Math.max(2, xOf(note.start + note.duration) - x)
                const y = yOf(note.pitch) - barH / 2
                const active = index === activeIndex
                return (
                  <g key={`${note.start}-${note.pitch}-${index}`}>
                    <rect
                      className={active ? 'piano__note piano__note--active' : 'piano__note'}
                      x={x}
                      y={y}
                      width={w}
                      height={barH}
                      rx="3"
                    />
                    {w > 36 ? (
                      <text
                        className="piano__note-name"
                        x={x + 6}
                        y={y + barH / 2}
                        dominantBaseline="middle"
                      >
                        {note.name ?? midiLabel(note.pitch)}
                      </text>
                    ) : null}
                  </g>
                )
              })}
            </g>
          </svg>
        ) : null}
      </div>
      <p className="piano__legend">
        <span className="piano__swatch piano__swatch--curve" />
        Pitch
        <span className="piano__swatch piano__swatch--note" />
        Notes
      </p>
    </section>
  )
}
