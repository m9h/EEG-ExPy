"""Region-of-interest helpers for analysis.

Acquisition-side electrode layouts are fixed in hardware on the devices
EEG-ExPy supports (Unicorn, Muse, etc.), so a paradigm can't physically
rewire the montage. What a paradigm *can* do is advertise which channels
carry the signal of interest for that task, via a `channels_of_interest`
attribute. Downstream analysis code (or live-monitoring views) can then
pick those out of the recorded CSV without hand-editing per paradigm.
"""

from __future__ import annotations

from brainflow.board_shim import BoardIds, BoardShim


def channel_names_for_device(device: str) -> list[str]:
    """Return the ordered list of EEG channel names for a device."""
    board_id = _board_id(device)
    return BoardShim.get_eeg_names(board_id)


def resolve_roi(
    channels_of_interest: tuple[str, ...], device: str
) -> dict[str, int]:
    """Map a paradigm's named channels-of-interest onto actual channel
    indices (position inside the brainflow EEG channel array) for a
    given device.

    Silently skips any CoI label that isn't on the device — caller can
    check the returned dict for missing keys.
    """
    names = channel_names_for_device(device)
    index_by_name = {name: i for i, name in enumerate(names)}
    return {
        coi: index_by_name[coi]
        for coi in channels_of_interest
        if coi in index_by_name
    }


def _board_id(device: str) -> int:
    from eegnb.devices.eeg import brainflow_devices

    if device not in brainflow_devices:
        raise ValueError(
            f"device {device!r} is not a brainflow-backed device"
        )
    return getattr(BoardIds, _BOARD_ID_ENUM[device]).value


_BOARD_ID_ENUM = {
    "unicorn": "UNICORN_BOARD",
    "synthetic": "SYNTHETIC_BOARD",
    "notion1": "NOTION_1_BOARD",
    "notion2": "NOTION_2_BOARD",
    "cyton": "CYTON_BOARD",
    "cyton_daisy": "CYTON_DAISY_BOARD",
    "ganglion": "GANGLION_BOARD",
    "ganglion_wifi": "GANGLION_WIFI_BOARD",
    "cyton_wifi": "CYTON_WIFI_BOARD",
    "cyton_daisy_wifi": "CYTON_DAISY_WIFI_BOARD",
    "brainbit": "BRAINBIT_BOARD",
    "unicorn_ble": "UNICORN_BOARD",
    "callibri_eeg": "CALLIBRI_EEG_BOARD",
    "crown": "CROWN_BOARD",
    "freeeeg32": "FREEEEG32_BOARD",
    "museS_bfn": "MUSE_S_BLED_BOARD",
    "muse2_bfn": "MUSE_2_BLED_BOARD",
    "muse2_bfb": "MUSE_2_BOARD",
    "museS_bfb": "MUSE_S_BOARD",
}
