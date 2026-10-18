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

const PITCH_CLASS = {
  C: 0,
  'C#': 1,
  DB: 1,
  D: 2,
  'D#': 3,
  EB: 3,
  E: 4,
  F: 5,
  'F#': 6,
  GB: 6,
  G: 7,
  'G#': 8,
  AB: 8,
  A: 9,
  'A#': 10,
  BB: 10,
  B: 11,
}

export function beatsToSeconds(notes, tempoBpm, shiftSeconds = 0) {
  const scale = 60 / tempoBpm
  return (notes ?? []).map((note, index) => ({
    pitch: note.pitch,
    start: note.start * scale + shiftSeconds,
    duration: Math.max(0.05, note.duration * scale),
    index,
  }))
}

function parseChord(symbol) {
  const match = /^([A-Ga-g])([b#]?)(.*)$/.exec(String(symbol ?? '').trim())
  if (!match) return null
  const letter = match[1].toUpperCase()
  const accidental = match[2].toLowerCase()
  const key = accidental === 'b' ? `${letter}B` : accidental === '#' ? `${letter}#` : letter
  const pc = PITCH_CLASS[key]
  if (pc == null) return null
  const rest = match[3].toLowerCase()
  const diminished = rest.startsWith('dim') || rest.startsWith('°')
  const minor = diminished || rest.startsWith('min') || /^m(?!aj)/.test(rest)
  return { pc, minor, diminished }
}

// Close triad with the root in octave 4 (C4 = 60).
export function chordTriad(symbol) {
  const parsed = parseChord(symbol)
  if (!parsed) return []
  const root = 60 + parsed.pc
  return [
    root,
    root + (parsed.minor ? 3 : 4),
    root + (parsed.diminished ? 6 : 7),
  ]
}

// Triad in octave 4, plus the root an octave lower as a bass note.
export function chordVoicing(symbol) {
  const triad = chordTriad(symbol)
  if (!triad.length) return null
  return { triad, bass: triad[0] - 12 }
}

export function ideaPerformance(seed, idea) {
  const tempo = idea?.tempo_bpm
  if (!tempo) return { melody: [], chords: [] }
  let shift = 0
  let lead = []
  if (idea.follows_seed && seed?.notes?.length) {
    const seedNotes = beatsToSeconds(seed.notes, seed.tempo_bpm || tempo)
    shift = seedNotes.reduce((end, note) => Math.max(end, note.start + note.duration), 0)
    lead = seedNotes.map((note) => ({ ...note, index: -1 }))
  }
  const melody = [...lead, ...beatsToSeconds(idea.notes, tempo, shift)]
  const scale = 60 / tempo
  const chords = (idea.chords ?? []).flatMap((chord, index) =>
    compingStrikes(chord, index, scale, shift),
  )
  return { melody, chords }
}

// Strikes on beat 1 and beat 3, each held until just before the next one.
function compingStrikes(chord, index, scale, shift) {
  const voiced = chordVoicing(chord.symbol)
  if (!voiced) return []
  const end = chord.start + chord.duration
  const ring = 2 * scale * 0.95
  const held = (beat) => {
    const untilEnd = (end - beat) * scale
    return Math.min(ring, untilEnd)
  }
  let beat = Math.floor(chord.start / 2) * 2
  if (beat < chord.start - 1e-4) beat += 2
  const strikes = []
  for (; beat < end - 1e-4; beat += 2) {
    strikes.push({
      start: beat * scale + shift,
      duration: held(beat),
      triad: voiced.triad,
      bass: voiced.bass,
      index,
    })
  }
  if (!strikes.length) {
    strikes.push({
      start: chord.start * scale + shift,
      duration: held(chord.start),
      triad: voiced.triad,
      bass: voiced.bass,
      index,
    })
  }
  return strikes
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
