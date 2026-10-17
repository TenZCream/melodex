import { Part, Synth, getDraw, getTransport, start } from 'tone'

let synth = null
let part = null
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

export function stopPlayback() {
  generation += 1
  window.clearTimeout(endTimer)
  endTimer = 0
  if (part) {
    part.stop()
    part.dispose()
    part = null
  }
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
  const notify = listener
  listener = null
  notify?.(null)
}

export async function playNote(midi) {
  await start()
  stopPlayback()
  voice().triggerAttackRelease(midiToFreq(midi), 0.42)
}

export async function playSequence(id, notes, onChange) {
  await start()
  stopPlayback()
  if (!notes?.length) return
  const gen = generation
  listener = onChange
  const instrument = voice()
  part = new Part((time, event) => {
    instrument.triggerAttackRelease(midiToFreq(event.pitch), Math.max(0.05, event.duration * 0.92), time)
    getDraw().schedule(() => {
      if (gen !== generation) return
      onChange?.({ id, index: event.index })
    }, time)
  }, notes.map((note, index) => ({
    time: Math.max(0, note.start),
    pitch: note.pitch,
    duration: Math.max(0.05, note.duration),
    index,
  })))
  part.start(0)
  getTransport().start()
  const end = Math.max(...notes.map((note) => note.start + note.duration))
  endTimer = window.setTimeout(() => {
    if (gen === generation) stopPlayback()
  }, (end + 0.08) * 1000)
}
