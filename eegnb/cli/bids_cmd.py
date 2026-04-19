"""Click command for converting a brainflow CSV recording to BIDS-EEG.

Lives in its own module so the test suite can import the command
without pulling the rest of `eegnb.cli.__main__` into the process —
the latter instantiates visual paradigms at import time, which needs
a display server.
"""

from __future__ import annotations

from pathlib import Path

import click

from eegnb.bids.paradigms import BY_NAME as PARADIGMS


@click.command(name="to-bids")
@click.option("--csv", "csv_path", required=True,
              type=click.Path(exists=True, dir_okay=False),
              help="Brainflow-style CSV to convert.")
@click.option("--paradigm", required=True,
              type=click.Choice(sorted(PARADIGMS), case_sensitive=False),
              help="Paradigm the recording came from.")
@click.option("--subject", required=True, help="BIDS subject label, e.g. 01.")
@click.option("--session", required=True, help="BIDS session label.")
@click.option("--bids-root", "bids_root", required=True,
              type=click.Path(file_okay=False),
              help="Root of the BIDS dataset to create or append to.")
@click.option("--device", default="unicorn",
              help="Acquisition device name (recorded as Manufacturer).")
@click.option("--run", "run", default="01", help="BIDS run label.")
@click.option("--line", "line_freq", type=float, default=50.0,
              help="Power line frequency in Hz (50 EU, 60 US).")
def to_bids_cmd(
    csv_path: str, paradigm: str, subject: str, session: str,
    bids_root: str, device: str, run: str, line_freq: float,
) -> None:
    """Convert a brainflow CSV recording to BIDS-EEG via mne-bids."""
    from eegnb.bids import to_bids

    out = to_bids(
        csv_path=Path(csv_path),
        paradigm=PARADIGMS[paradigm],
        subject=subject,
        session=session,
        bids_root=Path(bids_root),
        device=device,
        run=run,
        line_freq=line_freq,
    )
    click.echo(f"BIDS dataset written to: {out}")
