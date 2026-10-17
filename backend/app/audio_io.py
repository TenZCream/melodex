"""Small NumPy-only audio utilities (no SciPy, so nothing is blocked by Windows
Smart App Control): WAV read/write, resampling, and a 1-D median filter."""
from __future__ import annotations

import io
import struct

import numpy as np


class WavError(ValueError):
    pass


def read_wav(data: bytes) -> tuple[int, np.ndarray]:
    """Parse a RIFF/WAVE file. Supports PCM 8/16/24/32-bit, IEEE float 32/64,
    and WAVE_FORMAT_EXTENSIBLE. Returns (sample_rate, float32 array [n] or [n, ch])."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise WavError("not a WAV file")
    pos = 12
    fmt = None
    raw = None
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            if len(body) < 16:
                raise WavError("bad fmt chunk")
            tag, ch, sr, _br, _ba, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and len(body) >= 26:          # WAVE_FORMAT_EXTENSIBLE
                tag = struct.unpack("<H", body[24:26])[0]
            fmt = (tag, ch, sr, bits)
        elif cid == b"data":
            raw = body
        pos += 8 + size + (size & 1)   # chunks are word-aligned
    if fmt is None or raw is None:
        raise WavError("missing fmt or data chunk")
    tag, ch, sr, bits = fmt
    if ch < 1:
        raise WavError("no channels")
    width = bits // 8
    n = len(raw) // (width * ch)
    raw = raw[:n * width * ch]

    if tag == 3:                                   # IEEE float
        if bits == 32:
            x = np.frombuffer(raw, "<f4").astype(np.float32)
        elif bits == 64:
            x = np.frombuffer(raw, "<f8").astype(np.float32)
        else:
            raise WavError(f"unsupported float width {bits}")
    elif tag == 1:                                 # PCM
        if bits == 8:
            x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
        elif bits == 16:
            x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
        elif bits == 24:
            b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
            v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
            v = np.where(v >= 1 << 23, v - (1 << 24), v)
            x = v.astype(np.float32) / (1 << 23)
        elif bits == 32:
            x = np.frombuffer(raw, "<i4").astype(np.float32) / 2147483648
        else:
            raise WavError(f"unsupported PCM width {bits}")
    else:
        raise WavError(f"unsupported WAV encoding (format {tag})")

    if ch > 1:
        x = x.reshape(-1, ch)
    return int(sr), x


def write_wav(x: np.ndarray, sr: int) -> bytes:
    """Mono 16-bit PCM WAV bytes."""
    pcm = (np.clip(np.asarray(x, dtype=np.float64), -1, 1) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    buf.write(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE")
    buf.write(b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    buf.write(b"data" + struct.pack("<I", len(pcm)) + pcm)
    return buf.getvalue()


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Band-limited resampling via FFT (fine for clips of up to ~30 s)."""
    if sr_in == sr_out or len(x) == 0:
        return x.astype(np.float32)
    n_out = int(round(len(x) * sr_out / sr_in))
    X = np.fft.rfft(x.astype(np.float64))
    n_bins = n_out // 2 + 1
    if n_bins <= len(X):
        Y = X[:n_bins].copy()
    else:
        Y = np.zeros(n_bins, dtype=complex)
        Y[:len(X)] = X
    y = np.fft.irfft(Y, n_out) * (n_out / len(x))
    return y.astype(np.float32)


def median_filter_1d(x: np.ndarray, size: int) -> np.ndarray:
    """Centred running median with edge values repeated (like mode='nearest')."""
    x = np.asarray(x, dtype=np.float64)
    if size <= 1 or len(x) == 0:
        return x.copy()
    half = size // 2
    padded = np.concatenate([np.full(half, x[0]), x, np.full(size - 1 - half, x[-1])])
    windows = np.lib.stride_tricks.sliding_window_view(padded, size)
    return np.median(windows, axis=1)


def nan_median_filter_1d(x: np.ndarray, size: int) -> np.ndarray:
    """Running median that ignores NaNs (NaN where the whole window is NaN)."""
    x = np.asarray(x, dtype=np.float64)
    half = size // 2
    padded = np.concatenate([np.full(half, x[0]), x, np.full(size - 1 - half, x[-1])])
    windows = np.lib.stride_tricks.sliding_window_view(padded, size)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return np.nanmedian(windows, axis=1)
