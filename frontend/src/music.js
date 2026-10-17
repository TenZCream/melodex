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

// Root, third, and fifth with the root in octave 3 (C3 = 48).
export function chordTriad(symbol) {
  const match = /^([A-Ga-g])([b#]?)(.*)$/.exec(String(symbol ?? '').trim())
  if (!match) return []
  const letter = match[1].toUpperCase()
  const accidental = match[2].toLowerCase()
  const key = accidental === 'b' ? `${letter}B` : accidental === '#' ? `${letter}#` : letter
  const pc = PITCH_CLASS[key]
  if (pc == null) return []
  const rest = match[3].toLowerCase()
  const diminished = rest.startsWith('dim') || rest.startsWith('°')
  const minor = diminished || rest.startsWith('min') || /^m(?!aj)/.test(rest)
  const root = 48 + pc
  return [root, root + (minor ? 3 : 4), root + (diminished ? 6 : 7)]
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
  const chords = (idea.chords ?? []).flatMap((chord) => {
    const pitches = chordTriad(chord.symbol)
    if (!pitches.length) return []
    return [{
      start: chord.start * scale + shift,
      duration: Math.max(0.05, chord.duration * scale),
      pitches,
    }]
  })
  return { melody, chords }
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
