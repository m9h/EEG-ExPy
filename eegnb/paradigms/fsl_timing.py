"""Read FSL-style 3-column timing files.

The format is inherited from FMRIB's FEAT:

    <onset_seconds>  <duration_seconds>  <value>

One event per whitespace-separated line. `value` is the "weight" of the
event (FSL uses this to support parametric modulators) but for the
FPVS paradigms ported here we overload it as a **stimulus condition
code** — e.g. 1 for a standard, 2 for an oddball.

Stothart's original Fastball toolbox drove presentation from files of
this form; being able to replay the exact published schedule is what
makes inter-lab replication trivial.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FSLTimingEvent:
    onset_s: float
    duration_s: float
    value: float


@dataclass
class FSLTimingSchedule:
    events: list[FSLTimingEvent]
    source: Path | None = None

    def __len__(self) -> int:
        return len(self.events)

    def __iter__(self):
        return iter(self.events)

    @property
    def total_duration_s(self) -> float:
        if not self.events:
            return 0.0
        last = self.events[-1]
        return last.onset_s + last.duration_s

    @property
    def condition_codes(self) -> list[float]:
        return [e.value for e in self.events]

    def filter(self, value: float) -> "FSLTimingSchedule":
        return FSLTimingSchedule(
            [e for e in self.events if e.value == value],
            source=self.source,
        )


def load_fsl_three_column(path: str | Path) -> FSLTimingSchedule:
    """Parse an FSL-style 3-column timing file.

    Tolerates blank lines and `#`-prefixed comments. Raises
    `ValueError` if any non-comment line has fewer than 3 whitespace-
    separated fields or if a field isn't a float.
    """
    path = Path(path)
    events: list[FSLTimingEvent] = []
    with path.open() as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                raise ValueError(
                    f"{path}:{line_no}: expected 3 fields, got {len(parts)}"
                )
            try:
                onset = float(parts[0])
                duration = float(parts[1])
                value = float(parts[2])
            except ValueError as exc:
                raise ValueError(
                    f"{path}:{line_no}: non-numeric field: {exc}"
                ) from exc
            events.append(FSLTimingEvent(onset, duration, value))

    # Sort by onset; FSL doesn't mandate it but FPVS needs monotonicity.
    events.sort(key=lambda e: e.onset_s)
    return FSLTimingSchedule(events, source=path)
