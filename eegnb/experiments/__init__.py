"""EEG-ExPy paradigm package.

Paradigm classes are lazy-imported via :pep:`562` so that
``import eegnb.experiments`` succeeds on analysis-only installs without
PsychoPy. The actual attribute access — ``eegnb.experiments.VisualN170`` —
imports PsychoPy and raises the usual ``ImportError`` if it isn't installed.
"""

from __future__ import annotations

import importlib

from eegnb.utils.audio import configure_audio_backend

_PARADIGMS = {
    "VisualN170": ("eegnb.experiments.visual_n170.n170", "VisualN170"),
    "VisualP300": ("eegnb.experiments.visual_p300.p300", "VisualP300"),
    "VisualSSVEP": ("eegnb.experiments.visual_ssvep.ssvep", "VisualSSVEP"),
    "AuditoryOddball": ("eegnb.experiments.auditory_oddball.aob", "AuditoryOddball"),
    "VisualFPVSStothart": ("eegnb.experiments.fpvs_stothart.stothart", "VisualFPVSStothart"),
    "VisualFPVSRossion": ("eegnb.experiments.fpvs_rossion.rossion", "VisualFPVSRossion"),
}

__all__ = list(_PARADIGMS) + ["Experiment"]


def __getattr__(name: str):
    if name == "Experiment":
        return importlib.import_module("eegnb.experiments.Experiment")
    if name in _PARADIGMS:
        configure_audio_backend()
        module_name, class_name = _PARADIGMS[name]
        return getattr(importlib.import_module(module_name), class_name)
    raise AttributeError(f"module 'eegnb.experiments' has no attribute {name!r}")
