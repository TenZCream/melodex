import { FMSynth, Filter, PolySynth, Sampler, Synth, loaded } from 'tone'

export const INSTRUMENTS = [
  { id: 'piano', label: 'Piano' },
  { id: 'strings', label: 'Strings' },
  { id: 'guitar', label: 'Guitar' },
  { id: 'flute', label: 'Flute' },
  { id: 'synth', label: 'Synth' },
  { id: 'epiano', label: 'Electric piano' },
]

const SAMPLE_SETS = {
  piano: {
    baseUrl: 'https://tonejs.github.io/audio/salamander/',
    urls: pianoUrls(),
  },
  strings: {
    baseUrl: 'https://nbrosowsky.github.io/tonejs-instruments/samples/violin/',
    urls: {
      A4: 'A4.mp3',
      C5: 'C5.mp3',
      E5: 'E5.mp3',
      G4: 'G4.mp3',
      A5: 'A5.mp3',
      C6: 'C6.mp3',
      E6: 'E6.mp3',
      G5: 'G5.mp3',
    },
    attack: 0.08,
    release: 0.6,
  },
  guitar: {
    baseUrl: 'https://nbrosowsky.github.io/tonejs-instruments/samples/guitar-acoustic/',
    urls: {
      A2: 'A2.mp3',
      C3: 'C3.mp3',
      E3: 'E3.mp3',
      G3: 'G3.mp3',
      A3: 'A3.mp3',
      C4: 'C4.mp3',
      E4: 'E4.mp3',
      G4: 'G4.mp3',
      A4: 'A4.mp3',
      C5: 'C5.mp3',
    },
    release: 0.45,
  },
  flute: {
    baseUrl: 'https://nbrosowsky.github.io/tonejs-instruments/samples/flute/',
    urls: {
      A4: 'A4.mp3',
      C5: 'C5.mp3',
      E5: 'E5.mp3',
      A5: 'A5.mp3',
      C6: 'C6.mp3',
      E6: 'E6.mp3',
    },
    attack: 0.04,
    release: 0.35,
  },
}

function epianoOptions(volume) {
  return {
    harmonicity: 2,
    modulationIndex: 6,
    oscillator: { type: 'sine' },
    envelope: { attack: 0.01, decay: 0.35, sustain: 0.2, release: 0.9 },
    modulation: { type: 'sine' },
    modulationEnvelope: { attack: 0.01, decay: 0.25, sustain: 0.1, release: 0.5 },
    volume,
  }
}

let melodyChoice = 'piano'
let chordChoice = 'piano'
let loading = 0
let loadingListener = null
const ready = new Map()
const inflight = new Map()
const buses = { melody: null, chords: null }
const outputs = []

export function setMelodyInstrument(id) {
  melodyChoice = id
}

export function setChordInstrument(id) {
  chordChoice = id
}

export function attachInstrumentBus(role, bus) {
  buses[role] = bus
  for (const output of outputs) {
    if (output.role !== role) continue
    try {
      output.node.disconnect()
    } catch {
      // A disposed voice is already disconnected.
    }
    output.node.connect(bus)
  }
}

function route(role, node) {
  const bus = buses[role]
  if (bus) node.connect(bus)
  else node.toDestination()
  outputs.push({ role, node })
  return node
}

export function subscribeInstrumentLoading(listener) {
  loadingListener = listener
  listener(loading > 0)
  return () => {
    if (loadingListener === listener) loadingListener = null
  }
}

function pianoUrls() {
  const names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
  const urls = {}
  for (let midi = 21; midi <= 108; midi += 3) {
    const name = names[midi % 12]
    const octave = Math.floor(midi / 12) - 1
    urls[`${name}${octave}`] = `${name.replaceAll('#', 's')}${octave}.mp3`
  }
  return urls
}

function notifyLoading() {
  loadingListener?.(loading > 0)
}

function beginLoad() {
  loading += 1
  notifyLoading()
}

function endLoad() {
  loading = Math.max(0, loading - 1)
  notifyLoading()
}

function wrapTrigger(node, { polyphonic }) {
  return {
    trigger(notes, duration, time, velocity) {
      const length = Math.max(0.05, duration)
      if (polyphonic) {
        const list = Array.isArray(notes) ? notes : [notes]
        if (!list.length) return
        node.triggerAttackRelease(list, length, time, velocity)
        return
      }
      node.triggerAttackRelease(notes, length, time, velocity)
    },
    release() {
      try {
        if (polyphonic) node.releaseAll()
        else node.triggerRelease()
      } catch {
        // The voice may already be silent.
      }
    },
  }
}

function synthVoice(role) {
  if (role === 'chords') {
    const filter = route(role, new Filter({ frequency: 1200, type: 'lowpass', rolloff: -12, Q: 0.7 }))
    const pad = new PolySynth(Synth, {
      oscillator: { type: 'fatsawtooth' },
      envelope: { attack: 0.05, decay: 0.4, sustain: 0.5, release: 0.8 },
      volume: -14,
    }).connect(filter)
    return wrapTrigger(pad, { polyphonic: true })
  }
  const melody = route(role, new Synth({
    oscillator: { type: 'triangle' },
    envelope: { attack: 0.02, decay: 0.14, sustain: 0.22, release: 0.35 },
    volume: -8,
  }))
  return wrapTrigger(melody, { polyphonic: false })
}

function epianoVoice(role) {
  const volume = role === 'chords' ? -16 : -8
  if (role === 'chords') {
    return wrapTrigger(route(role, new PolySynth(FMSynth, epianoOptions(volume))), { polyphonic: true })
  }
  return wrapTrigger(route(role, new FMSynth(epianoOptions(volume))), { polyphonic: false })
}

async function samplerVoice(id, role) {
  const spec = SAMPLE_SETS[id]
  let failed = false
  const sampler = new Sampler({
    urls: spec.urls,
    baseUrl: spec.baseUrl,
    volume: role === 'chords' ? -16 : -8,
    onerror: () => {
      failed = true
    },
  })
  if (spec.attack) sampler.attack = spec.attack
  if (spec.release) sampler.release = spec.release
  try {
    await loaded()
  } catch {
    failed = true
  }
  if (failed) {
    try {
      sampler.dispose()
    } catch {
      // A half-loaded sampler may already be closing.
    }
    throw new Error('samples')
  }
  return wrapTrigger(route(role, sampler), { polyphonic: true })
}

function remember(key, voice) {
  ready.set(key, voice)
  return voice
}

async function build(id, role) {
  const key = `${role}:${id}`
  if (ready.has(key)) return ready.get(key)
  if (inflight.has(key)) return inflight.get(key)
  const job = (async () => {
    if (id === 'synth') return remember(key, synthVoice(role))
    if (id === 'epiano') return remember(key, epianoVoice(role))
    beginLoad()
    try {
      return remember(key, await samplerVoice(id, role))
    } catch {
      return remember(key, synthVoice(role))
    } finally {
      endLoad()
    }
  })()
  inflight.set(key, job)
  try {
    return await job
  } finally {
    inflight.delete(key)
  }
}

export function ensureMelody() {
  return build(melodyChoice, 'melody')
}

export function ensureSearchPiano() {
  return build('piano', 'search')
}

export function ensureChords() {
  return build(chordChoice, 'chords')
}

export function releaseInstruments() {
  for (const voice of ready.values()) voice.release()
}
