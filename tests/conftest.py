"""Shared pytest fixtures for test_frame.py and test_pgn.py."""

from collections.abc import Callable
from pathlib import Path

import pytest

from pybsen.frame import RawFrame, parse_rbus_frames
from pybsen.models import AlarmState, BatteryState
from pybsen.pgn import decode

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_bin() -> Callable[[str], bytes]:
    """Returns a callable: load_bin(name) -> bytes. Loads a fixture .bin file by name."""

    def _load(name: str) -> bytes:
        with open(_FIXTURE_DIR / name, "rb") as fh:
            return fh.read()

    return _load


@pytest.fixture
def parse_notify() -> Callable[[bytes], list[RawFrame]]:
    """Returns a callable: parse_notify(notify_bytes) -> list[RawFrame]."""
    return parse_rbus_frames


@pytest.fixture
def decode_sequence() -> Callable[[list[tuple[bytes, str, object]]], tuple[BatteryState, AlarmState]]:
    """Returns a callable: decode_sequence(sequence) -> tuple[BatteryState, AlarmState].

    Drives an entire SEQUENCE_* list through parse → decode and returns final states.
    State carries forward across all entries in the sequence.
    """

    def _run(sequence: list[tuple[bytes, str, object]]) -> tuple[BatteryState, AlarmState]:
        battery = BatteryState()
        alarms = AlarmState()
        for notify_bytes, _field, _expected in sequence:
            for frame in parse_rbus_frames(notify_bytes):
                battery, alarms = decode(frame, battery, alarms)
        return battery, alarms

    return _run
