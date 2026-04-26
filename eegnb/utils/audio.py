"""PsychoPy audio backend selection.

PsychoPy has three built-in audio backends: ``ptb``, ``pygame``, ``pysound``.
Which one is usable depends on platform and what's installed:

* ``ptb`` (Psychtoolbox) — lowest latency but the Linux wheel
  (``psychtoolbox==3.0.19.14``, latest on PyPI) has broken Python bindings
  and fails to open PipeWire's ALSA device. Fine on macOS / Windows.
* ``pygame`` — available wherever ``pygame`` installs. PsychoPy 2025.2's
  ``backend_pygame._setSndFromClip`` has an upstream bug where the
  ``isStereo == 2`` test is always false (``_base.py`` coerces the value
  to ``True`` via an ``@attributeSetter``), so mono → stereo conversion
  never runs. We monkey-patch that check here.
* ``pysound`` — needs the unmaintained ``pysoundcard`` package; skip.

Call :func:`configure_audio_backend` exactly once before any paradigm
imports its sound module.
"""

from __future__ import annotations

import importlib
import platform
from typing import Optional


def _patch_pygame_stereo() -> None:
    """Work around psychopy 2025.2's pygame backend mono→stereo bug.

    ``backend_pygame.SoundPygame._setSndFromClip`` checks
    ``self.isStereo == 2`` to decide whether to duplicate a mono array
    into both channels. But ``_base._SoundBase`` defines ``isStereo`` as
    an ``@attributeSetter`` that coerces the assigned value to ``bool``,
    so by the time the check runs it's ``True == 2 → False`` and the
    conversion is skipped. Pygame's stereo mixer then rejects the mono
    array with "Array depth must match number of mixer channels".
    """
    try:
        from psychopy.sound import backend_pygame
    except Exception:
        return

    if getattr(backend_pygame, "_eegnb_patched", False):
        return

    import numpy as np
    from pygame import sndarray

    def _patched_setSndFromClip(self, clip):
        self.clip = clip
        arr = clip.samples
        if self.isStereo and (arr.ndim == 1 or arr.shape[1] < 2):
            if arr.ndim == 2:
                arr = arr[:, 0]
            tmp = np.empty((len(arr), 2), dtype=arr.dtype)
            tmp[:, 0] = arr
            tmp[:, 1] = arr
            arr = tmp
        if self.format == -16:
            arr = (arr * 2 ** 15).astype(np.int16)
        elif self.format == 16:
            arr = ((arr + 1) * 2 ** 15).astype(np.uint16)
        elif self.format == -8:
            arr = (arr * 2 ** 7).astype(np.int8)
        elif self.format == 8:
            arr = ((arr + 1) * 2 ** 7).astype(np.uint8)
        self._snd = sndarray.make_sound(arr)

    backend_pygame.SoundPygame._setSndFromClip = _patched_setSndFromClip
    backend_pygame._eegnb_patched = True


def _set_backend(name: str) -> None:
    """Set the selected sound backend for psychopy 2025.2+.

    In newer psychopy the backend is chosen via ``Sound.backend`` (a
    class attribute), not ``prefs.hardware.audioLib``. Set both so we
    work across the 2024–2025 API change.
    """
    from psychopy import prefs
    prefs.hardware["audioLib"] = [name]
    try:
        from psychopy.sound.sound import Sound
        Sound.backend = name
    except Exception:
        pass


def _probe(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def configure_audio_backend() -> str:
    """Pick the best working PsychoPy audio backend for this machine.

    Preference order:

    * macOS / Windows: ``ptb`` if ``psychtoolbox`` imports, else ``pygame``.
    * Linux: ``pygame`` (with upstream stereo-bug patch), because PTB's
      current Linux wheel cannot open PipeWire's ALSA device.
    * Apple Silicon macOS: ``pygame`` — PTB wheel historically unavailable.

    Returns the name of the backend that was configured, or
    ``"unavailable"`` if PsychoPy itself is not importable.
    """
    try:
        from psychopy import prefs  # noqa: F401
    except ImportError:
        return "unavailable"

    system = platform.system()
    machine = platform.machine()
    apple_silicon = system == "Darwin" and machine in ("arm64", "aarch64")
    linux = system == "Linux"

    prefer_ptb = not (linux or apple_silicon)

    if prefer_ptb and _probe("psychtoolbox"):
        _set_backend("ptb")
        from psychopy import prefs
        prefs.hardware["audioLatencyMode"] = 3
        return "ptb"

    if _probe("pygame"):
        _patch_pygame_stereo()
        _set_backend("pygame")
        return "pygame"

    if prefer_ptb and _probe("psychtoolbox"):
        _set_backend("ptb")
        return "ptb"

    return "default"
