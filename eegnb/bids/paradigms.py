"""Paradigm BIDS-EEG metadata, decoupled from the PsychoPy paradigm classes.

The paradigm classes in `eegnb.experiments.fpvs_*` re-export these
constants so paradigm code and BIDS code share one source of truth.
Anything that only needs the BIDS metadata (CLI, exporters, validators)
imports from here directly and avoids loading PsychoPy/pyglet.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Mapping


def _meta(
    bids_task_name: str,
    bids_event_id: Mapping[int, str],
    bids_task_json: Mapping[str, str],
) -> SimpleNamespace:
    return SimpleNamespace(
        bids_task_name=bids_task_name,
        bids_event_id=dict(bids_event_id),
        bids_task_json=dict(bids_task_json),
    )


STOTHART = _meta(
    bids_task_name="fastballStothart",
    bids_event_id={1: "standard", 2: "oddball"},
    bids_task_json={
        "TaskName": "Fastball (Stothart) — object-recognition FPVS",
        "Instructions": (
            "Fixate centre of the screen. Simply watch the stream of "
            "images — no response is required."
        ),
        "TaskDescription": (
            "Fast periodic visual stimulation of BOSS-style object "
            "photographs at a 3 Hz base rate with an oddball (seen vs "
            "unseen) every 5th stimulus (0.6 Hz). Stothart, Smith, "
            "Milton 2020 NeuroImage; Stothart et al 2021 Brain."
        ),
    },
)


ROSSION = _meta(
    bids_task_name="fpvsFaceIndividuation",
    bids_event_id={1: "baseIdentity", 2: "oddballIdentity"},
    bids_task_json={
        "TaskName": "FPVS face individuation (Rossion 2014)",
        "Instructions": (
            "Fixate centre. Passive viewing of rapidly presented faces; "
            "no response is required."
        ),
        "TaskDescription": (
            "Fast periodic visual stimulation of unfamiliar face "
            "identities at a 5.88 Hz base rate with a novel identity "
            "every 5th stimulus (1.176 Hz). Liu-Shuang, Norcia, Rossion "
            "2014 Neuropsychologia."
        ),
    },
)


BY_NAME: dict[str, SimpleNamespace] = {
    "visual-fpvs-stothart": STOTHART,
    "visual-fpvs-rossion": ROSSION,
}
