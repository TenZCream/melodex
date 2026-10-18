import { Part, Synth, Volume, getDestination, getDraw, getTransport, start } from 'tone'
import { attachInstrumentBus, ensureChords, ensureMelody, releaseInstruments } from './instruments'

const MIXER_KEY = 'melodex-mixer'
const RAMP_SECONDS = 0.05

function percentToDb(percent) {
  const gain = Math.min(100, Math.max(0, Number(percent))) / 100
  if (gain <= 0) return Number.NEGATIVE_INFINITY
  return 20 * Math.log10(gain ** 2)
}

function clampPercent(value, fallback) {
  const number = Number(value)
  if (!Number.isFinite(number)) return fallback
  return Math.min(100, Math.max(0, number))
}

function loadMixer() {
  const defaults = { melody: 80, chords: 60, melodyMuted: false, chordsMuted: false }
  try {
    const raw = localStorage.getItem(MIXER_KEY)
    if (!raw) return defaults
    const data = JSON.parse(raw)
    return {
      melody: clampPercent(data.melody, defaults.melody),
      chords: clampPercent(data.chords, defaults.chords),
      melodyMuted: data.melodyMuted === true,
      chordsMuted: data.chordsMuted === true,
    }
  } catch {
    return defaults
  }
}

function saveMixer() {
  try {
    localStorage.setItem(MIXER_KEY, JSON.stringify({
      melody: mixer.melody,
      chords: mixer.chords,
      melodyMuted: mixer.melodyMuted,
      chordsMuted: mixer.chordsMuted,
    }))
  } catch {
    // Private mode and blocked storage should not stop playback.
  }
}

const mixer = loadMixer()
const melodyBus = new Volume(0).connect(getDestination())
const chordBus = new Volume(0).connect(getDestination())

function primeBus(bus, percent, muted) {
  const db = percentToDb(percent)
  if (muted) {
    bus.volume.value = Number.isFinite(db) ? db : 0
    bus.mute = true
    bus._unmutedVolume = db
    return
  }
  bus.volume.value = Number.isFinite(db) ? db : Number.NEGATIVE_INFINITY
}

function fadeBus(bus, db) {
  if (bus.context.state !== 'running') {
    bus.volume.value = Number.isFinite(db) ? db : Number.NEGATIVE_INFINITY
    return
  }
  try {
    if (bus.volume.value === Number.NEGATIVE_INFINITY && Number.isFinite(db)) bus.volume.value = -60
    bus.volume.rampTo(Number.isFinite(db) ? db : Number.NEGATIVE_INFINITY, RAMP_SECONDS)
  } catch {
    bus.volume.value = Number.isFinite(db) ? db : Number.NEGATIVE_INFINITY
  }
}

function applyVolume(bus, percent, muted) {
  const db = percentToDb(percent)
  bus._unmutedVolume = db
  if (!muted) fadeBus(bus, db)
}

function applyMute(bus, muted, percent) {
  const db = percentToDb(percent)
  if (muted) {
    fadeBus(bus, Number.NEGATIVE_INFINITY)
    bus._unmutedVolume = db
    return
  }
  if (bus.mute) {
    bus._unmutedVolume = -60
    bus.mute = false
  }
  bus._unmutedVolume = db
  fadeBus(bus, db)
}

primeBus(melodyBus, mixer.melody, mixer.melodyMuted)
primeBus(chordBus, mixer.chords, mixer.chordsMuted)
attachInstrumentBus('melody', melodyBus)
attachInstrumentBus('chords', chordBus)

export function getMixerSettings() {
  return { ...mixer }
}

export function setMelodyVolume(percent) {
  mixer.melody = clampPercent(percent, mixer.melody)
  applyVolume(melodyBus, mixer.melody, mixer.melodyMuted)
  saveMixer()
}

export function setChordVolume(percent) {
  mixer.chords = clampPercent(percent, mixer.chords)
  applyVolume(chordBus, mixer.chords, mixer.chordsMuted)
  saveMixer()
}

export function setMelodyMuted(muted) {
  mixer.melodyMuted = !!muted
  applyMute(melodyBus, mixer.melodyMuted, mixer.melody)
  saveMixer()
}

export function setChordMuted(muted) {
  mixer.chordsMuted = !!muted
  applyMute(chordBus, mixer.chordsMuted, mixer.chords)
  saveMixer()
}

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
