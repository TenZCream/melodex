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

export function beatsToSeconds(notes, tempoBpm, shiftSeconds = 0) {
  const scale = 60 / tempoBpm
  return (notes ?? []).map((note, index) => ({
    pitch: note.pitch,
    start: note.start * scale + shiftSeconds,
    duration: Math.max(0.05, note.duration * scale),
    index,
  }))
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

// Beat 1 and beat 3 of each bar that overlaps the chord. A 2-beat chord lands on only one of them.
function compingStrikes(chord, index, scale, shift) {
  const tones = chord.tones ?? []
  const bass = chord.bass
  if (!tones.length && bass == null) return []
  const end = chord.start + chord.duration
  const ringBeats = 2 * 0.95
  const strikes = []
  for (let bar = Math.floor(chord.start / 4) * 4; bar < end - 1e-4; bar += 4) {
    for (const offset of [0, 2]) {
      const beat = bar + offset
      if (beat < chord.start - 1e-4 || beat >= end - 1e-4) continue
      const beatsHeld = Math.min(ringBeats, end - beat)
      strikes.push({
        start: beat * scale + shift,
        duration: beatsHeld * scale,
        tones,
        bass,
        index,
      })
    }
  }
  if (!strikes.length) {
    strikes.push({
      start: chord.start * scale + shift,
      duration: Math.min(ringBeats, chord.duration) * scale,
      tones,
      bass,
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
