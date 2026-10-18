import { Filter, Part, PolySynth, Synth, getDraw, getTransport, start } from 'tone'

let synth = null
let pad = null
let padFilter = null
let parts = []
let endTimer = 0
let generation = 0
let listener = null

function voice() {
  if (!synth) {
    synth = new Synth({
      oscillator: { type: 'triangle' },
      envelope: { attack: 0.02, decay: 0.14, sustain: 0.22, release: 0.35 },
      volume: -8,
    }).toDestination()
  }
  return synth
}

function chordPad() {
  if (!pad) {
    padFilter = new Filter({ frequency: 1200, type: 'lowpass', rolloff: -12, Q: 0.7 }).toDestination()
    pad = new PolySynth(Synth, {
      oscillator: { type: 'fatsawtooth' },
      envelope: { attack: 0.05, decay: 0.4, sustain: 0.5, release: 0.8 },
      volume: -14,
    }).connect(padFilter)
  }
  return pad
}

function midiToFreq(midi) {
  return 440 * 2 ** ((midi - 69) / 12)
}

function disposeParts() {
  for (const item of parts) {
    try {
      item.stop()
      item.dispose()
    } catch {
      // A part that never started can already be gone.
    }
  }
  parts = []
}

function silencePad() {
  if (pad) {
    try {
      pad.releaseAll()
    } catch {
      // The pad may already be silent.
    }
    pad.dispose()
    pad = null
  }
  if (padFilter) {
    padFilter.dispose()
    padFilter = null
  }
}

export function stopPlayback() {
  generation += 1
  window.clearTimeout(endTimer)
  endTimer = 0
  disposeParts()
  const transport = getTransport()
  if (transport.state === 'started') transport.stop()
  transport.cancel(0)
  transport.position = 0
  getDraw().cancel(0)
  try {
    synth?.triggerRelease()
  } catch {
    // The synth may already be silent.
  }
  silencePad()
  const notify = listener
  listener = null
  notify?.(null)
}

export async function playNote(midi) {
  await start()
  stopPlayback()
  voice().triggerAttackRelease(midiToFreq(midi), 0.42)
}

export async function playSequence(id, notes, onChange, chords = []) {
  await start()
  stopPlayback()
  if (!notes?.length) return
  const gen = generation
  listener = onChange
  const highlight = { id, index: -1, chordIndex: -1 }
  const emit = () => {
    if (gen !== generation) return
    onChange?.({ ...highlight })
  }
  emit()
  const instrument = voice()
  const melody = new Part((time, event) => {
    instrument.triggerAttackRelease(midiToFreq(event.pitch), Math.max(0.05, event.duration * 0.92), time)
    if (event.index < 0) return
    getDraw().schedule(() => {
      highlight.index = event.index
      emit()
    }, time)
  }, notes.map((note, index) => ({
    time: Math.max(0, note.start),
    pitch: note.pitch,
    duration: Math.max(0.05, note.duration),
    index: note.index ?? index,
  })))
  melody.start(0)
  parts.push(melody)

  if (chords.length) {
    const harmony = chordPad()
    const chordPart = new Part((time, event) => {
      const length = Math.max(0.08, event.duration)
      harmony.triggerAttackRelease(event.triad.map(midiToFreq), length, time, 0.55)
      harmony.triggerAttackRelease([midiToFreq(event.bass)], length, time, 0.32)
      getDraw().schedule(() => {
        highlight.chordIndex = event.index
        emit()
      }, time)
    }, chords.map((chord) => ({
      time: Math.max(0, chord.start),
      duration: Math.max(0.08, chord.duration),
      triad: chord.triad,
      bass: chord.bass,
      index: chord.index ?? 0,
    })))
    chordPart.start(0)
    parts.push(chordPart)
  }

  getTransport().start()
  const melodyEnd = Math.max(...notes.map((note) => note.start + note.duration))
  const chordEnd = chords.reduce((end, chord) => Math.max(end, chord.start + chord.duration), 0)
  endTimer = window.setTimeout(() => {
    if (gen === generation) stopPlayback()
  }, (Math.max(melodyEnd, chordEnd) + 0.12) * 1000)
}
