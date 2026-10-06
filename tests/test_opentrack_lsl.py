"""Tests for the opentrack -> LSL head-pose bridge.

The codec tests are pure (no sockets, no LSL). The bridge tests use a real
UDP socket on an ephemeral port plus a real LSL outlet/inlet, so they verify
the whole path without opentrack installed or a camera attached — the same
thing ``python -m eegnb.devices.opentrack_lsl --selftest`` does interactively.
"""

from __future__ import annotations

import socket
import struct
import time

import pytest

from eegnb.devices.opentrack_lsl import (
    CHANNELS,
    PACKET_SIZE,
    OpentrackLSLBridge,
    decode_packet,
    encode_packet,
)


# --- wire-format codec (pure) ----------------------------------------------

def test_packet_size_is_six_doubles():
    assert PACKET_SIZE == 48  # opentrack proto-udp: 6 little-endian doubles


def test_channels_are_the_opentrack_pose_order():
    assert [c[0] for c in CHANNELS] == ["x", "y", "z", "yaw", "pitch", "roll"]
    # translation in cm, rotation in deg
    assert [c[1] for c in CHANNELS] == ["cm", "cm", "cm", "deg", "deg", "deg"]


def test_encode_decode_round_trip():
    pose = (1.5, -2.25, 3.0, 45.0, -10.5, 0.125)
    assert decode_packet(encode_packet(pose)) == pose


def test_decode_matches_raw_little_endian_doubles():
    pose = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    raw = struct.pack("<6d", *pose)
    assert decode_packet(raw) == pose
    assert encode_packet(pose) == raw


@pytest.mark.parametrize("nbytes", [0, 3, 24, 47, 49, 96])
def test_decode_rejects_wrong_sized_packets(nbytes):
    with pytest.raises(ValueError):
        decode_packet(b"\x00" * nbytes)


def test_encode_rejects_wrong_length_pose():
    with pytest.raises(ValueError):
        encode_packet((1.0, 2.0, 3.0))


# --- bridge (real UDP + real LSL) -----------------------------------------

def _free_udp_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def bridge():
    pytest.importorskip("pylsl")
    port = _free_udp_port()
    b = OpentrackLSLBridge(
        udp_port=port, name=f"opentrack-pytest-{port}"
    ).open()
    yield b
    b.close()


def _send(port: int, pose) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(encode_packet(pose), ("127.0.0.1", port))
    s.close()


def test_bridge_forwards_a_packet(bridge):
    pose = (1.0, 2.0, 3.0, 10.0, -20.0, 30.0)
    _send(bridge.udp_port, pose)
    got = bridge.pump_once(timeout=3.0)
    assert got == pose
    assert bridge.n_forwarded == 1
    assert bridge.n_malformed == 0
    assert bridge.last_pose == pose


def test_bridge_counts_malformed_without_forwarding(bridge):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(b"\x01\x02\x03", ("127.0.0.1", bridge.udp_port))
    s.close()
    assert bridge.pump_once(timeout=3.0) is None
    assert bridge.n_malformed == 1
    assert bridge.n_forwarded == 0


def test_pump_once_returns_none_on_timeout(bridge):
    assert bridge.pump_once(timeout=0.2) is None
    assert bridge.n_forwarded == 0


def test_stream_is_discoverable_with_correct_metadata(bridge):
    from pylsl import resolve_byprop

    streams = resolve_byprop("name", bridge.name, timeout=5)
    assert streams, "bridge's LSL stream was not discoverable"
    info = streams[0]
    assert info.type() == "HeadPose"
    assert info.channel_count() == len(CHANNELS)
    assert info.nominal_srate() == 0.0  # irregular by default


def test_inlet_receives_forwarded_poses(bridge):
    from pylsl import StreamInlet, resolve_byprop

    streams = resolve_byprop("name", bridge.name, timeout=5)
    assert streams
    inlet = StreamInlet(streams[0], max_chunklen=4)
    inlet.open_stream(timeout=5.0)

    # channel labels survive into the inlet's metadata (and thus into XDF)
    ch = inlet.info().desc().child("channels").child("channel")
    labels = []
    for _ in range(len(CHANNELS)):
        labels.append(ch.child_value("label"))
        ch = ch.next_sibling()
    assert labels == [c[0] for c in CHANNELS]

    sent = [(float(i), 0.0, 0.0, 0.0, 0.0, 0.0) for i in range(10)]
    for pose in sent:
        _send(bridge.udp_port, pose)
        bridge.pump_once(timeout=2.0)
    assert bridge.n_forwarded == 10

    time.sleep(0.4)
    chunk, ts = inlet.pull_chunk(timeout=3.0, max_samples=32)
    assert len(chunk) == 10
    assert chunk[0][0] == pytest.approx(0.0)
    assert chunk[-1][0] == pytest.approx(9.0)
    assert all(b >= a for a, b in zip(ts, ts[1:])), "timestamps not monotonic"
    inlet.close_stream()


def test_pump_before_open_raises():
    pytest.importorskip("pylsl")
    b = OpentrackLSLBridge(udp_port=_free_udp_port())
    with pytest.raises(RuntimeError):
        b.pump_once(timeout=0.1)
