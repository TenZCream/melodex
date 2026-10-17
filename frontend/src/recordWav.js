// recordWav.js — record from the microphone and return a mono 16-bit WAV Blob.
//
// Usage in React:
//   import { startRecording } from "./recordWav";
//   const rec = await startRecording();      // asks for mic permission
//   ... later ...
//   const wavBlob = await rec.stop();         // Blob, type "audio/wav"
//   const form = new FormData();
//   form.append("file", wavBlob, "hum.wav");
//   const res = await fetch("http://localhost:8000/api/search/audio", { method: "POST", body: form });
//
// Works in Chrome, Edge, Firefox, Safari. Requires localhost or https.

const TARGET_RATE = 16000; // the backend resamples anyway; 16 kHz keeps uploads small

export async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: false, // these "voice" filters distort pitch; turn them off
      noiseSuppression: false,
      autoGainControl: false,
    },
  });
  const recorder = new MediaRecorder(stream);
  const chunks = [];
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.start();

  return {
    stream, // expose so you can draw a live level meter if you want
    stop: () =>
      new Promise((resolve, reject) => {
        recorder.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop());
          try {
            const blob = new Blob(chunks, { type: recorder.mimeType });
            resolve(await blobToWav(blob));
          } catch (err) {
            reject(err);
          }
        };
        recorder.stop();
      }),
  };
}

// Decode any browser-recorded blob (webm/ogg/mp4) and re-encode as WAV.
export async function blobToWav(blob) {
  const arrayBuf = await blob.arrayBuffer();
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const decoded = await ctx.decodeAudioData(arrayBuf);
  ctx.close();

  // Mix down to mono
  const n = decoded.length;
  const mono = new Float32Array(n);
  for (let c = 0; c < decoded.numberOfChannels; c++) {
    const data = decoded.getChannelData(c);
    for (let i = 0; i < n; i++) mono[i] += data[i] / decoded.numberOfChannels;
  }

  const samples = resample(mono, decoded.sampleRate, TARGET_RATE);
  return encodeWav(samples, TARGET_RATE);
}

function resample(input, fromRate, toRate) {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    // average the source samples in this window (simple anti-aliasing)
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    out[i] = sum / Math.max(1, end - start);
  }
  return out;
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeStr = (off, s) => [...s].forEach((ch, i) => view.setUint8(off + i, ch.charCodeAt(0)));

  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}
