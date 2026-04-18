"""PsychoPy audio backend selection.

PTB (Psychtoolbox) gives the lowest latency but isn't always available
(macOS Apple Silicon historically, or any system without the psychtoolbox
wheel). Fall back to PsychoPy's built-in `sounddevice` backend, which
requires the `sounddevice` Python package to be importable.

Call `configure_audio_backend` exactly once before any paradigm imports
its sound module.
"""

from __future__ import annotations

import importlib
import platform


def configure_audio_backend() -> str:
    """Pick the best available PsychoPy audio backend.

    Returns the name of the backend that was configured.
    """
    from psychopy import prefs

    system = platform.system()
    machine = platform.machine()

    # macOS Apple Silicon — PTB has not historically been freely
    # redistributable on arm64, so prefer sounddevice.
    apple_silicon = system == "Darwin" and machine in ("arm64", "aarch64")

    if not apple_silicon:
        try:
            importlib.import_module("psychtoolbox")
            prefs.hardware["audioLib"] = "PTB"
            prefs.hardware["audioLatencyMode"] = 3
            return "PTB"
        except ImportError:
            pass

    try:
        importlib.import_module("sounddevice")
        prefs.hardware["audioLib"] = "sounddevice"
        return "sounddevice"
    except ImportError:
        # Leave PsychoPy's default in place; paradigms that need audio
        # will surface the missing backend at sound construction time.
        return prefs.hardware.get("audioLib", "default")
