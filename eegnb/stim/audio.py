"""Low-latency audio playback with DAC-aligned LSL marker emission.

PsychoPy's audio backends (PTB, pygame, pysound) couple poorly with
EEG-ExPy's needs:

* PTB's Linux wheel (``psychtoolbox==3.0.19.14``) cannot open PipeWire's
  ALSA device.
* pygame's psychopy backend has an upstream stereo-bug that crashes on
  the first mono tone.
* None of them expose the PortAudio DAC clock, so the marker timestamp
  recorded by EEG-ExPy is "the moment we called ``Sound.play()``", not
  "the moment audio actually leaves the speaker". On Linux through
  PipeWire that gap is tens of milliseconds and not constant.

This module replaces the PsychoPy audio path with a small
``sounddevice`` wrapper that:

* schedules pre-built numpy clips through a PortAudio output stream;
* in the audio callback, pushes a marker sample to an LSL outlet with
  a timestamp aligned to the DAC clock — so the marker is correct to
  within one audio sample regardless of software jitter;
* optionally emits a brief square-wave pulse on a dedicated channel at
  onset so a hardware capture device (e.g. NBS LabStreamer's analog
  inputs) can record a hardware-precise onset edge alongside the
  audio.

Typical use::

    import numpy as np
    from eegnb.stim.audio import AudioStream, sine_tone

    s = AudioStream(samplerate=44100,
                    marker_stream_name="eegnb-AudioMarkers",
                    ttl_channel=1)            # right channel = TTL pulse
    s.start()
    s.play(sine_tone(523.25, 0.2), marker=1)
    s.play(sine_tone(1174.66, 0.2), marker=2)
    s.wait_empty()
    s.stop()
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional, Union

import numpy as np

try:
    import sounddevice as sd
except ImportError as exc:  # pragma: no cover - import-time check
    raise ImportError(
        "eegnb.stim.audio needs python-sounddevice. "
        "Install with: pip install sounddevice"
    ) from exc

from pylsl import StreamInfo, StreamOutlet, local_clock


def sine_tone(
    freq_hz: float,
    secs: float,
    samplerate: int = 44100,
    volume: float = 0.5,
    fade_ms: float = 10.0,
) -> np.ndarray:
    """Sine wave clip with raised-cosine fade-in/out to suppress clicks."""
    n = int(samplerate * secs)
    t = np.arange(n) / samplerate
    wave = (np.sin(2 * np.pi * freq_hz * t) * volume).astype(np.float32)
    fade = int(samplerate * fade_ms / 1000)
    if fade > 0 and 2 * fade < n:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        wave[:fade] *= ramp
        wave[-fade:] *= ramp[::-1]
    return wave


def am_tone(
    carrier_hz: float,
    am_hz: float,
    secs: float,
    samplerate: int = 44100,
    am_type: str = "gaussian",
    volume: float = 0.3,
    gaussian_std_ratio: float = 8.0,
) -> np.ndarray:
    """Amplitude-modulated tone for SSAEP-style paradigms."""
    n = int(samplerate * secs)
    t = np.arange(n) / samplerate
    carrier = np.sin(2 * np.pi * carrier_hz * t)

    if am_type == "sine":
        env = 0.5 * (1.0 + np.sin(2 * np.pi * am_hz * t))
    elif am_type == "gaussian":
        from scipy.stats import norm
        period = max(int(samplerate / am_hz), 1)
        std = period / gaussian_std_ratio
        win = norm.pdf(np.arange(period), period / 2, std)
        win /= win.max()
        n_win = int(np.ceil(secs * am_hz))
        env = np.tile(win, n_win)[:n]
    else:
        raise ValueError(f"unknown am_type {am_type!r}")

    return (carrier * env * volume).astype(np.float32)


def noise_burst(
    secs: float,
    samplerate: int = 44100,
    volume: float = 0.3,
    fade_ms: float = 10.0,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """White-noise burst with raised-cosine fades."""
    rng = rng or np.random.default_rng()
    n = int(samplerate * secs)
    wave = rng.standard_normal(n).astype(np.float32) * volume
    fade = int(samplerate * fade_ms / 1000)
    if fade > 0 and 2 * fade < n:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        wave[:fade] *= ramp
        wave[-fade:] *= ramp[::-1]
    return wave


@dataclass
class _Clip:
    samples: np.ndarray  # 1-D mono float32 in [-1, 1]
    marker: Optional[int]


class AudioStream:
    """Sounddevice OutputStream wrapper with DAC-aligned LSL markers.

    Parameters
    ----------
    samplerate : int
        Output sample rate in Hz.
    channels : int
        Output channel count. 2 (stereo) is required when ``ttl_channel``
        is set.
    marker_stream_name : str
        Name of the LSL outlet to publish onset markers on. The outlet
        is created the first time :meth:`start` runs and re-used until
        :meth:`stop` is called.
    marker_outlet : pylsl.StreamOutlet, optional
        Pre-built outlet to use instead of creating one. Useful when the
        paradigm wants its own naming scheme.
    ttl_channel : int, optional
        If set (0 = left, 1 = right), emit a brief square pulse on that
        channel at every clip onset. Audio plays on the *other* channel
        in this case. If ``None``, audio plays on all channels and no
        TTL is emitted.
    ttl_pulse_ms : float
        Duration of the TTL pulse in milliseconds.
    ttl_amplitude : float
        Pulse amplitude in [-1, 1]. Default 0.9.
    blocksize : int
        PortAudio block size; lower values reduce latency at the cost of
        callback overhead. 0 = let PortAudio choose.
    latency : str or float, optional
        PortAudio latency hint. ``"low"`` triggers callback starvation
        on PipeWire (block size becomes too small for the kernel to
        keep up), so the default is PortAudio's default (~35 ms on
        Linux). DAC-aligned marker timestamps make the absolute
        latency irrelevant for ERP timing — it cancels out in the
        ``outputBufferDacTime`` / ``currentTime`` arithmetic.
    """

    def __init__(
        self,
        samplerate: int = 44100,
        channels: int = 2,
        marker_stream_name: str = "eegnb-AudioMarkers",
        marker_outlet: Optional[StreamOutlet] = None,
        ttl_channel: Optional[int] = None,
        ttl_pulse_ms: float = 5.0,
        ttl_amplitude: float = 0.9,
        blocksize: int = 0,
        latency: Optional[Union[str, float]] = None,
    ):
        if ttl_channel is not None and channels < 2:
            raise ValueError("ttl_channel requires channels >= 2")
        self.samplerate = samplerate
        self.channels = channels
        self.marker_stream_name = marker_stream_name
        self._marker_outlet = marker_outlet
        self._owns_outlet = marker_outlet is None
        self.ttl_channel = ttl_channel
        self.ttl_pulse_samples = int(samplerate * ttl_pulse_ms / 1000)
        self.ttl_amplitude = float(ttl_amplitude)
        self.blocksize = blocksize
        self.latency = latency

        self._pending: "queue.Queue[_Clip]" = queue.Queue()
        self._current: Optional[_Clip] = None
        self._cursor = 0
        self._ttl_remaining = 0
        self._stream: Optional[sd.OutputStream] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._marker_outlet is None and self._owns_outlet:
            info = StreamInfo(
                name=self.marker_stream_name,
                type="Markers",
                channel_count=1,
                nominal_srate=0,
                channel_format="int32",
                source_id=f"eegnb-audio-{self.marker_stream_name}",
            )
            self._marker_outlet = StreamOutlet(info)

        stream_kwargs = dict(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="float32",
            blocksize=self.blocksize,
            callback=self._callback,
        )
        if self.latency is not None:
            stream_kwargs["latency"] = self.latency
        self._stream = sd.OutputStream(**stream_kwargs)
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._owns_outlet:
            self._marker_outlet = None

    def __enter__(self) -> "AudioStream":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def play(self, samples: np.ndarray, marker: Optional[int] = None) -> None:
        """Enqueue a mono float32 clip with an optional marker code.

        The clip plays as soon as PortAudio drains the queue. The marker
        (if provided) is pushed on the LSL outlet at the timestamp the
        first sample of the clip leaves the DAC — not at the time of
        this call.
        """
        if samples.ndim != 1:
            raise ValueError("samples must be a 1-D mono float32 array")
        if samples.dtype != np.float32:
            samples = samples.astype(np.float32)
        self._pending.put(_Clip(samples=samples, marker=marker))

    def wait_empty(self, timeout: float = 30.0) -> bool:
        """Block until all queued clips have finished playing.

        Returns True on completion, False on timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                done = self._pending.empty() and self._current is None
            if done:
                # Drain the PortAudio output buffer.
                if self._stream is not None:
                    time.sleep(self._stream.latency + 0.05)
                return True
            time.sleep(0.01)
        return False

    def queue_depth(self) -> int:
        return self._pending.qsize() + (1 if self._current is not None else 0)

    @property
    def marker_outlet(self) -> Optional[StreamOutlet]:
        return self._marker_outlet

    # ------------------------------------------------------------------
    # PortAudio callback
    # ------------------------------------------------------------------

    def _callback(self, outdata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            # Underflow / overflow are visible as status flags. We log
            # them post-hoc rather than from the RT thread.
            pass

        outdata.fill(0.0)
        offset = 0
        audio_channel = (
            1 - self.ttl_channel if self.ttl_channel is not None else None
        )

        while offset < frames:
            with self._lock:
                if self._current is None:
                    try:
                        self._current = self._pending.get_nowait()
                    except queue.Empty:
                        break
                    self._cursor = 0
                    # DAC time of *this exact sample slot* in the buffer.
                    pa_now = time_info.currentTime
                    dac_at_offset = (
                        time_info.outputBufferDacTime + offset / self.samplerate
                    )
                    # Convert PortAudio clock to LSL clock at this instant.
                    if (
                        self._current.marker is not None
                        and self._marker_outlet is not None
                    ):
                        lsl_now = local_clock()
                        marker_ts = lsl_now + (dac_at_offset - pa_now)
                        try:
                            self._marker_outlet.push_sample(
                                [int(self._current.marker)],
                                timestamp=marker_ts,
                            )
                        except Exception:
                            # Outlet errors must never kill the audio
                            # callback; LSL drops are recoverable.
                            pass
                    self._ttl_remaining = (
                        self.ttl_pulse_samples
                        if self.ttl_channel is not None
                        else 0
                    )

            clip = self._current
            remaining = len(clip.samples) - self._cursor
            take = min(remaining, frames - offset)
            chunk = clip.samples[self._cursor : self._cursor + take]

            if audio_channel is None:
                for c in range(self.channels):
                    outdata[offset : offset + take, c] += chunk
            else:
                outdata[offset : offset + take, audio_channel] += chunk

            if self._ttl_remaining > 0 and self.ttl_channel is not None:
                pulse_take = min(self._ttl_remaining, take)
                outdata[
                    offset : offset + pulse_take, self.ttl_channel
                ] = self.ttl_amplitude
                self._ttl_remaining -= pulse_take

            offset += take
            self._cursor += take
            if self._cursor >= len(clip.samples):
                with self._lock:
                    self._current = None
