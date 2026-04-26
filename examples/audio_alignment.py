"""Verify DAC-aligned LSL markers match the analog audio captured by a
labstreamer / oscilloscope-style LSL voltage stream.

Setup
-----
1. Patch the host's audio output into one of the labstreamer's analog
   inputs (the ``RawData`` LSL stream from MAC ``00:c0:08:93:57:d3``,
   6 ch @ 10 kHz).
2. Run this script. It will:

   * subscribe to ``RawData`` and ``eegnb-AudioMarkers`` in parallel;
   * run a brief :class:`AuditoryOddball` block via
     ``eegnb.experiments.AuditoryOddball``;
   * for each marker, find the audio-onset edge in the recorded
     waveform and report mean / std offset.

A perfect rig will show offsets within one audio-input sample period
(0.1 ms at 10 kHz). Tens-of-milliseconds offsets indicate the DAC
clock conversion in :mod:`eegnb.stim.audio` isn't matching the
PortAudio output latency for this card / kernel combination.
"""
from __future__ import annotations

import argparse
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np
from pylsl import StreamInlet, resolve_byprop


def _subscribe(name: str, timeout: float = 5.0) -> Optional[StreamInlet]:
    streams = resolve_byprop("name", name, timeout=timeout)
    if not streams:
        return None
    return StreamInlet(streams[0], max_buflen=120)


def collect(
    inlet: StreamInlet,
    stop: threading.Event,
    samples: list,
    timestamps: list,
    apply_correction: bool = True,
):
    """Pull samples and convert their timestamps into the local LSL clock.

    Cross-host LSL streams carry timestamps in the source's clock; the
    labstreamer is on a separate device so its ``RawData`` timestamps
    differ from this machine's ``local_clock()`` by the offset returned
    by :py:meth:`StreamInlet.time_correction`. Without applying that
    offset, comparing inlet timestamps to marker timestamps gives
    nonsense (gigaseconds of skew).
    """
    correction = 0.0
    if apply_correction:
        try:
            correction = inlet.time_correction(timeout=2.0)
        except Exception:
            correction = 0.0
    while not stop.is_set():
        chunk, ts = inlet.pull_chunk(timeout=0.5, max_samples=4096)
        if ts:
            samples.extend(chunk)
            if correction:
                timestamps.extend(t + correction for t in ts)
            else:
                timestamps.extend(ts)


def detect_onsets(
    waveform: np.ndarray,
    timestamps: np.ndarray,
    samplerate: float,
    threshold_factor: float = 5.0,
    refractory_s: float = 0.05,
) -> np.ndarray:
    """Return LSL timestamps of audio-onset edges in a 1-D waveform.

    Uses a Hilbert-style envelope (rectified + low-pass via moving
    average), thresholds at ``threshold_factor * MAD``, and enforces
    a refractory period to avoid double-detecting the same tone.
    """
    if waveform.size < 2:
        return np.empty(0)

    # DC-remove and rectify
    w = waveform - np.median(waveform)
    env = np.abs(w)

    # Smooth ~5 ms
    win = max(1, int(samplerate * 0.005))
    if win > 1:
        kernel = np.ones(win, dtype=np.float64) / win
        env = np.convolve(env, kernel, mode="same")

    mad = np.median(np.abs(env - np.median(env))) + 1e-12
    thresh = float(np.median(env) + threshold_factor * mad)
    above = env > thresh
    rising = np.where(np.diff(above.astype(np.int8)) == 1)[0] + 1

    refractory_n = int(refractory_s * samplerate)
    onsets = []
    last = -refractory_n
    for idx in rising:
        if idx - last >= refractory_n:
            onsets.append(idx)
            last = idx
    return timestamps[np.asarray(onsets, dtype=int)] if onsets else np.empty(0)


def pick_audio_channel(
    waveforms: np.ndarray, samplerate: float
) -> int:
    """Pick the channel with the largest broadband energy.

    The labstreamer streams 6 voltage channels at 10 kHz; only the one
    wired to the audio loopback should have a tone-shaped envelope.
    """
    if waveforms.ndim != 2:
        raise ValueError(f"expected (n, ch) array, got {waveforms.shape}")
    rms = np.sqrt(np.mean(waveforms.astype(np.float64) ** 2, axis=0))
    return int(np.argmax(rms))


def run_paradigm(duration: int, ttl_channel: Optional[int]) -> None:
    """Drive an oddball-style sequence via :class:`AudioStream` directly.

    The stock :class:`AuditoryOddball` paradigm uses PsychoPy's audio
    stack and pushes markers at wall-clock time of ``play()``; that's
    fine cross-platform but does not produce a DAC-aligned marker
    stream. This alignment test is specifically about the DAC-aligned
    timing path, so it talks to :class:`AudioStream` directly and
    skips PsychoPy.
    """
    from eegnb.stim.audio import AudioStream, sine_tone

    rng = np.random.default_rng(42)
    samplerate = 44100
    secs = 0.2
    standard = sine_tone(523.25, secs, samplerate, volume=0.4)   # C5
    deviant = sine_tone(1174.66, secs, samplerate, volume=0.4)   # D6
    tones = [standard, deviant]

    iti_base, jitter, soa = 0.3, 0.2, 0.2

    audio = AudioStream(
        samplerate=samplerate,
        channels=2,
        marker_stream_name="eegnb-AudioMarkers",
        ttl_channel=ttl_channel,
    )
    audio.start()
    # Let the LSL outlet fully advertise itself before tones start.
    time.sleep(0.7)

    start = time.time()
    n = 0
    while (time.time() - start) < duration:
        ind = int(rng.binomial(1, 0.25))
        marker = ind + 1
        audio.play(tones[ind], marker=marker)
        n += 1
        time.sleep(secs + iti_base + float(rng.random()) * jitter)

    audio.wait_empty(timeout=3.0)
    audio.stop()
    print(f"[paradigm] played {n} tones in {time.time() - start:.1f}s")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", type=int, default=15)
    ap.add_argument(
        "--audio-stream", default="RawData",
        help="Name of the LSL stream carrying the analog audio loopback "
             "(default: RawData, the labstreamer's voltage stream).",
    )
    ap.add_argument(
        "--audio-channel", type=int, default=None,
        help="0-based channel index in the audio stream. If omitted, the "
             "channel with the largest RMS is auto-picked.",
    )
    ap.add_argument(
        "--ttl-channel", type=int, default=None,
        help="If 0 or 1, also emit a TTL pulse on that stereo channel for "
             "hardware-precise onset capture.",
    )
    args = ap.parse_args()

    audio_inlet = _subscribe(args.audio_stream, timeout=5.0)
    if audio_inlet is None:
        raise SystemExit(
            f"could not resolve LSL stream {args.audio_stream!r} on the network"
        )
    audio_info = audio_inlet.info()
    audio_sr = audio_info.nominal_srate()
    audio_nch = audio_info.channel_count()
    print(f"[audio]   {args.audio_stream!r}: {audio_nch}ch @ {audio_sr} Hz")

    marker_inlet = _subscribe("eegnb-AudioMarkers", timeout=5.0)
    print(
        f"[markers] eegnb-AudioMarkers: "
        f"{'connected' if marker_inlet else 'not yet up'} "
        "(will wait for paradigm to create it)"
    )

    audio_samples: list = []
    audio_ts: list = []
    marker_samples: list = []
    marker_ts: list = []
    stop = threading.Event()

    threads = [
        threading.Thread(
            target=collect,
            args=(audio_inlet, stop, audio_samples, audio_ts),
            kwargs=dict(apply_correction=True),
            daemon=True,
        )
    ]
    threads[0].start()

    # Marker inlet may not exist until the paradigm starts — give a
    # second worker that polls for it.
    def lazy_collect_markers():
        inlet = marker_inlet
        deadline = time.time() + args.duration + 5
        while inlet is None and time.time() < deadline:
            inlet = _subscribe("eegnb-AudioMarkers", timeout=1.0)
            if stop.is_set():
                return
        if inlet is None:
            print("[markers] never appeared on LSL — bailing")
            return
        # Markers are produced on this host with explicit local_clock()
        # timestamps from the audio callback, so no correction needed.
        collect(inlet, stop, marker_samples, marker_ts, apply_correction=False)

    threads.append(
        threading.Thread(target=lazy_collect_markers, daemon=True)
    )
    threads[1].start()

    try:
        run_paradigm(args.duration, args.ttl_channel)
    finally:
        # Drain the audio buffer for an extra second to capture the tail
        time.sleep(1.0)
        stop.set()
        for t in threads:
            t.join(timeout=2)

    if not audio_samples:
        print("[result] no audio samples received from the labstreamer")
        return

    audio_arr = np.asarray(audio_samples, dtype=np.float32)
    audio_ts_arr = np.asarray(audio_ts, dtype=np.float64)
    marker_ts_arr = np.asarray(marker_ts, dtype=np.float64)
    marker_codes = [s[0] for s in marker_samples]

    if args.audio_channel is not None:
        ch = args.audio_channel
    else:
        ch = pick_audio_channel(audio_arr, audio_sr)
    print(f"[result] using audio channel {ch} (auto-picked = "
          f"{args.audio_channel is None})")

    onsets = detect_onsets(
        audio_arr[:, ch],
        audio_ts_arr,
        samplerate=audio_sr,
    )
    print(f"[result] {len(onsets)} audio-onset edges detected, "
          f"{len(marker_ts_arr)} markers received")

    if len(onsets) == 0 or len(marker_ts_arr) == 0:
        print("[result] insufficient overlap — check audio loopback wiring "
              "and that the labstreamer is recording")
        return

    # Match each marker to the nearest onset within ±300 ms (audio onset
    # may appear slightly before the DAC-projected marker time if LSL
    # clock-correction over-shoots, or after due to ADC-side buffering).
    # The inter-tone interval is >300 ms so nearest-in-window is
    # unambiguous.
    deltas = []
    matched_codes = []
    for code, m_ts in zip(marker_codes, marker_ts_arr):
        diffs = onsets - m_ts
        in_window = np.abs(diffs) <= 0.3
        if not in_window.any():
            continue
        candidate = diffs[in_window][np.argmin(np.abs(diffs[in_window]))]
        deltas.append(candidate * 1000)  # ms
        matched_codes.append(code)
    deltas_arr = np.asarray(deltas)
    if deltas_arr.size == 0:
        print("[alignment] no marker→onset pairs within ±300 ms — check loopback")
        return
    print(f"[alignment] matched {len(deltas_arr)}/{len(marker_ts_arr)} markers "
          f"to an onset within ±300 ms")

    print()
    print("[alignment] marker → audio onset, ms")
    print(f"  n          : {len(deltas_arr)}")
    print(f"  mean       : {np.mean(deltas_arr):+8.3f} ms "
          "  (positive = audio after marker)")
    print(f"  median     : {np.median(deltas_arr):+8.3f} ms")
    print(f"  std        : {np.std(deltas_arr):8.3f} ms")
    print(f"  jitter p95 : {np.percentile(np.abs(deltas_arr - np.median(deltas_arr)), 95):8.3f} ms")
    print(f"  min / max  : {np.min(deltas_arr):+8.3f} / {np.max(deltas_arr):+8.3f} ms")
    print()
    by_code: dict = {}
    for c, d in zip(matched_codes, deltas_arr):
        by_code.setdefault(c, []).append(d)
    for c, vs in sorted(by_code.items()):
        v = np.asarray(vs)
        print(f"  code {c:<3}: n={len(v):3d}  median={np.median(v):+7.3f}  "
              f"std={np.std(v):6.3f} ms")

    # Per-marker dump for debugging when the picture isn't clean.
    print()
    print("[debug] marker -> nearest-onset delta (ms), all markers:")
    for code, m_ts in zip(marker_codes, marker_ts_arr):
        diffs = (onsets - m_ts) * 1000
        if diffs.size == 0:
            print(f"  code={code} ts={m_ts:.3f} : no onsets at all")
            continue
        i = int(np.argmin(np.abs(diffs)))
        in_w = "  in-window" if abs(diffs[i]) <= 300 else "OUT-of-win"
        print(f"  code={code} ts={m_ts:.3f}  nearest: {diffs[i]:+8.2f} ms  {in_w}")


if __name__ == "__main__":
    main()
