const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const SHARPS = new Set([1, 3, 6, 8, 10])

export function isSharp(pitch) {
  return SHARPS.has((((pitch % 12) + 12) % 12))
}

export function midiLabel(pitch) {
  const rounded = Math.round(pitch)
  const name = NOTE_NAMES[((rounded % 12) + 12) % 12]
  const octave = Math.floor(rounded / 12) - 1
  return `${name}${octave}`
}

// DAW-style computer keys, C4 through C5.
export const COMPUTER_KEYS = {
  a: 60,
  w: 61,
  s: 62,
  e: 63,
  d: 64,
  f: 65,
  t: 66,
  g: 67,
  y: 68,
  h: 69,
  u: 70,
  j: 71,
  k: 72,
}

export const COMPUTER_KEY_LABELS = {
  60: 'A',
  61: 'W',
  62: 'S',
  63: 'E',
  64: 'D',
  65: 'F',
  66: 'T',
  67: 'G',
  68: 'Y',
  69: 'H',
  70: 'U',
  71: 'J',
  72: 'K',
}

export function segmentToSeconds(result) {
  const source = result?.matched_segment?.notes ?? []
  if (!source.length || !result.tempo_bpm) return []
  const secondsPerBeat = 60 / result.tempo_bpm
  const origin = source[0].start
  const transpose = result.transpose_semitones ?? 0
  return source.map((note) => ({
    pitch: note.pitch + transpose,
    start: (note.start - origin) * secondsPerBeat,
    duration: note.duration * secondsPerBeat,
  }))
}
