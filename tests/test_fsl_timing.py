"""Unit tests for eegnb.paradigms.fsl_timing."""

import textwrap

import pytest

from eegnb.paradigms.fsl_timing import (
    FSLTimingEvent,
    FSLTimingSchedule,
    load_fsl_three_column,
)


def test_parses_three_columns(tmp_path):
    path = tmp_path / "sched.txt"
    path.write_text(
        "# comment\n"
        "0.0  0.2  1.0\n"
        "\n"  # blank line
        "0.5  0.2  2.0\n"
    )
    sched = load_fsl_three_column(path)
    assert len(sched) == 2
    assert sched.events[0] == FSLTimingEvent(0.0, 0.2, 1.0)
    assert sched.events[1] == FSLTimingEvent(0.5, 0.2, 2.0)
    assert sched.condition_codes == [1.0, 2.0]


def test_total_duration(tmp_path):
    path = tmp_path / "s.txt"
    path.write_text("0.0 0.2 1\n0.5 0.3 1\n")
    sched = load_fsl_three_column(path)
    assert sched.total_duration_s == pytest.approx(0.8)


def test_sorted_by_onset(tmp_path):
    path = tmp_path / "s.txt"
    path.write_text("1.0 0.1 1\n0.0 0.1 1\n0.5 0.1 1\n")
    sched = load_fsl_three_column(path)
    onsets = [e.onset_s for e in sched.events]
    assert onsets == sorted(onsets)


def test_filter_by_value(tmp_path):
    path = tmp_path / "s.txt"
    path.write_text("0.0 0.2 1\n0.3 0.2 2\n0.6 0.2 1\n0.9 0.2 2\n")
    sched = load_fsl_three_column(path)
    oddballs = sched.filter(2.0)
    assert [e.onset_s for e in oddballs.events] == [0.3, 0.9]


def test_rejects_short_rows(tmp_path):
    path = tmp_path / "s.txt"
    path.write_text("0.0 0.2\n")
    with pytest.raises(ValueError, match="expected 3 fields"):
        load_fsl_three_column(path)


def test_rejects_non_numeric(tmp_path):
    path = tmp_path / "s.txt"
    path.write_text("0.0 abc 1\n")
    with pytest.raises(ValueError, match="non-numeric"):
        load_fsl_three_column(path)
