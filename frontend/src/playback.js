import { Part, Synth, getDraw, getTransport, start } from 'tone'
import { ensureChords, ensureMelody, releaseInstruments } from './instruments'

let synth = null
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
  releaseInstruments()
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
  const melodyReady = ensureMelody()
  const chordsReady = chords.length ? ensureChords() : null
  const melodyVoice = await melodyReady
  const chordVoice = chordsReady ? await chordsReady : null
  if (gen !== generation) return
  listener = onChange
  const highlight = { id, index: -1, chordIndex: -1 }
  const emit = () => {
    if (gen !== generation) return
    onChange?.({ ...highlight })
  }
  emit()
  const melody = new Part((time, event) => {
    melodyVoice.trigger(midiToFreq(event.pitch), Math.max(0.05, event.duration * 0.92), time)
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

  if (chordVoice && chords.length) {
    const chordPart = new Part((time, event) => {
      const length = Math.max(0.08, event.duration)
      const tones = (event.tones ?? []).map(midiToFreq)
      if (tones.length) chordVoice.trigger(tones, length, time, 0.55)
      if (event.bass != null) chordVoice.trigger([midiToFreq(event.bass)], length, time, 0.32)
      getDraw().schedule(() => {
        highlight.chordIndex = event.index
        emit()
      }, time)
    }, chords.map((chord) => ({
      time: Math.max(0, chord.start),
      duration: Math.max(0.08, chord.duration),
      tones: chord.tones ?? [],
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
