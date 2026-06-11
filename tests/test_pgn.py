"""End-to-end tests: notification bytes → BatteryState / AlarmState field values.

Each test decodes real fixture bytes through parse_rbus_frames → pgn.decode
and asserts that the resulting state fields match known-good values from
live device captures (provenance: tests/fixtures.py).
"""

import struct
from collections.abc import Callable
from datetime import datetime

import pytest

from pybsen.frame import parse_rbus_frames
from pybsen.models import AlarmState, BatteryState
from pybsen.pgn import decode
from tests.fixtures import (
    NET_CURRENT_SCALE_POINTS,
    NOTIFY_A_CHARGESTATE,
    NOTIFY_A_CURRENT,
    NOTIFY_A_SOC,
    NOTIFY_A_TEMP,
    NOTIFY_A_VOLTAGE,
    NOTIFY_E_ALARM,
    SEQUENCE_3_DISCHARGING,
    SEQUENCE_A_CHARGING,
    SEQUENCE_B_LESS_CHARGING,
    SEQUENCE_C_CHARGING,
    SEQUENCE_D_DISCHARGING,
    SEQUENCE_E_DISCHARGING,
    TIME_REMAINING_SCALE_POINTS,
)

# ---------------------------------------------------------------------------
# Field name mapping from fixtures.py (discover.py naming) → model field names
# ---------------------------------------------------------------------------

_FIXTURE_FIELD_REMAP: dict[str, str] = {
    "net_current_A": "net_current_a",
    "voltage_V": "voltage_v",
    "voltage_alarm_setpoint_V": "voltage_alarm_setpoint_v",
}

_ALARM_FIELDS = frozenset(
    {"soc_alarm_active", "voltage_alarm_active", "soc_alarm_setpoint_pct", "voltage_alarm_setpoint_v"}
)


def _normalize(field: str) -> str:
    return _FIXTURE_FIELD_REMAP.get(field, field)


def _get_field(battery: BatteryState, alarms: AlarmState, field: str) -> object:
    normalized = _normalize(field)
    if normalized in _ALARM_FIELDS:
        return getattr(alarms, normalized)
    return getattr(battery, normalized)


def _check(battery: BatteryState, alarms: AlarmState, field: str, expected: object) -> None:
    actual = _get_field(battery, alarms, field)
    if isinstance(expected, float):
        assert actual == pytest.approx(expected)
    else:
        assert actual == expected


def _decode_notify(notify_bytes: bytes, battery: BatteryState, alarms: AlarmState) -> tuple[BatteryState, AlarmState]:
    """Decode all frames from one notification into updated state."""
    for frame in parse_rbus_frames(notify_bytes):
        battery, alarms = decode(frame, battery, alarms)
    return battery, alarms


def _run_sequence(
    sequence: list[tuple[bytes, str, object]],
) -> None:
    """Drive a SEQUENCE_* list with carry-forward state, checking each entry."""
    battery = BatteryState()
    alarms = AlarmState()
    for notify_bytes, field, expected in sequence:
        battery, alarms = _decode_notify(notify_bytes, battery, alarms)
        _check(battery, alarms, field, expected)


# ---------------------------------------------------------------------------
# SEQUENCE_* end-to-end decode tests
# ---------------------------------------------------------------------------


class TestSequenceA:
    def test_sequence_a_charging(self) -> None:
        _run_sequence(SEQUENCE_A_CHARGING)


class TestSequence3:
    def test_sequence_3_discharging(self) -> None:
        _run_sequence(SEQUENCE_3_DISCHARGING)


class TestSequenceB:
    def test_sequence_b_less_charging(self) -> None:
        _run_sequence(SEQUENCE_B_LESS_CHARGING)


class TestSequenceC:
    def test_sequence_c_charging(self) -> None:
        _run_sequence(SEQUENCE_C_CHARGING)


class TestSequenceD:
    def test_sequence_d_discharging(self) -> None:
        _run_sequence(SEQUENCE_D_DISCHARGING)


class TestSequenceE:
    def test_sequence_e_discharging(self) -> None:
        _run_sequence(SEQUENCE_E_DISCHARGING)


# ---------------------------------------------------------------------------
# decode_sequence fixture — final accumulated state
# ---------------------------------------------------------------------------


def test_decode_sequence_final_state(
    decode_sequence: Callable[[list[tuple[bytes, str, object]]], tuple[BatteryState, AlarmState]],
) -> None:
    battery, alarms = decode_sequence(SEQUENCE_A_CHARGING)
    assert battery.soc_pct == 99
    assert battery.net_current_a == pytest.approx(0.5)
    assert battery.voltage_v == pytest.approx(13.3)
    assert battery.temp_c == pytest.approx(7.0)
    assert battery.charge_state == 1
    assert alarms.soc_alarm_active is False
    assert alarms.voltage_alarm_active is False
    assert alarms.soc_alarm_setpoint_pct == 14
    assert alarms.voltage_alarm_setpoint_v == pytest.approx(11.5)


# ---------------------------------------------------------------------------
# NET_CURRENT_SCALE_POINTS — formula calibration
# ---------------------------------------------------------------------------


def _make_f280_notify(raw_current: int) -> bytes:
    header = bytes([0xA0, 0xF2, 0x80, 0x36, 0x88])
    payload = struct.pack("<HHHB", raw_current, 133, 0xFFFF, 0x43) + b"\xff"
    return header + payload


@pytest.mark.parametrize("raw_u16,expected_a,_source", NET_CURRENT_SCALE_POINTS)
def test_net_current_scale_points(raw_u16: int, expected_a: float, _source: str) -> None:
    battery, _ = _decode_notify(_make_f280_notify(raw_u16), BatteryState(), AlarmState())
    assert battery.net_current_a == pytest.approx(expected_a, abs=0.05)


# ---------------------------------------------------------------------------
# TIME_REMAINING_SCALE_POINTS — formula calibration
# ---------------------------------------------------------------------------


def _make_f104_notify(raw_time: int, soc: int = 99) -> bytes:
    header = bytes([0xA0, 0xF1, 0x04, 0x36, 0x88])
    payload = struct.pack("<BBH", soc, 0xFF, raw_time) + bytes([0xFF, 0xFF, 0xFF, 0xFF])
    return header + payload


@pytest.mark.parametrize("raw_u16,expected_min", [(r, e) for r, e, *_ in TIME_REMAINING_SCALE_POINTS])
def test_time_remaining_scale_points(raw_u16: int, expected_min: int) -> None:
    battery, _ = _decode_notify(_make_f104_notify(raw_u16), BatteryState(), AlarmState())
    if expected_min > 0:
        assert battery.time_to_full_min == expected_min
        assert battery.time_to_flat_min is None
    elif expected_min < 0:
        assert battery.time_to_flat_min == abs(expected_min)
        assert battery.time_to_full_min is None
    else:
        # Zero-crossover: both should be None
        assert battery.time_to_full_min is None
        assert battery.time_to_flat_min is None


# ---------------------------------------------------------------------------
# Sentinel value handling
# ---------------------------------------------------------------------------


class TestSentinels:
    def test_f280_raw_current_sentinel_returns_none(self) -> None:
        battery, _ = _decode_notify(_make_f280_notify(20000), BatteryState(), AlarmState())
        assert battery.net_current_a is None

    def test_f280_raw_voltage_sentinel_returns_none(self) -> None:
        header = bytes([0xA0, 0xF2, 0x80, 0x36, 0x88])
        payload = struct.pack("<HHHB", 10000, 643, 0xFFFF, 0x43) + b"\xff"
        battery, _ = _decode_notify(header + payload, BatteryState(), AlarmState())
        assert battery.voltage_v is None

    def test_f280_raw_temp_sentinel_returns_none(self) -> None:
        header = bytes([0xA0, 0xF2, 0x80, 0x36, 0x88])
        payload = struct.pack("<HHHB", 10000, 133, 0xFFFF, 0xFA) + b"\xff"
        battery, _ = _decode_notify(header + payload, BatteryState(), AlarmState())
        assert battery.temp_c is None

    def test_f104_raw_time_sentinel_both_none(self) -> None:
        battery, _ = _decode_notify(_make_f104_notify(0xFFFA), BatteryState(), AlarmState())
        assert battery.time_to_full_min is None
        assert battery.time_to_flat_min is None

    def test_f104_soh_0xff_returns_none(self) -> None:
        header = bytes([0xA0, 0xF1, 0x04, 0x36, 0x88])
        payload = struct.pack("<BBH", 99, 0xFF, 32198) + bytes([0xFF, 0xFF, 0xFF, 0xFF])
        battery, _ = _decode_notify(header + payload, BatteryState(), AlarmState())
        assert battery.state_of_health_pct is None

    def test_f10a_voltage_setpoint_sentinel_returns_none(self) -> None:
        header = bytes([0xA0, 0xF1, 0x0A, 0x36, 0x88])
        # alarm_flags=0xF0, soc_setpoint=14, voltage_setpoint=0xFFFA
        payload = struct.pack("<BBHBBBB", 0xF0, 14, 0xFFFA, 0xFF, 0xFF, 0xFF, 0xFF)
        _, alarms = _decode_notify(header + payload, BatteryState(), AlarmState())
        assert alarms.voltage_alarm_setpoint_v is None

    def test_f102_raw_voltage_0xffff_no_update(self) -> None:
        header = bytes([0xA0, 0xF1, 0x02, 0x36, 0x88])
        payload = struct.pack("<HHHB", 0, 0, 0xFFFF, 0x43) + b"\xff"
        battery = BatteryState(voltage_v=12.5)
        new_battery, _ = _decode_notify(header + payload, battery, AlarmState())
        assert new_battery.voltage_v == pytest.approx(12.5)


# ---------------------------------------------------------------------------
# Alarm state — active and inactive cases
# ---------------------------------------------------------------------------


class TestAlarmState:
    def test_alarms_inactive_session_a(self) -> None:
        _, alarms = _decode_notify(NOTIFY_A_TEMP, BatteryState(), AlarmState())
        assert alarms.soc_alarm_active is False
        assert alarms.voltage_alarm_active is False

    def test_alarm_setpoints_session_a(self) -> None:
        _, alarms = _decode_notify(NOTIFY_A_TEMP, BatteryState(), AlarmState())
        assert alarms.soc_alarm_setpoint_pct == 14
        assert alarms.voltage_alarm_setpoint_v == pytest.approx(11.5, abs=0.001)

    def test_alarms_inactive_session_e(self) -> None:
        _, alarms = _decode_notify(NOTIFY_E_ALARM, BatteryState(), AlarmState())
        assert alarms.soc_alarm_active is False
        assert alarms.voltage_alarm_active is False

    def test_alarm_active_soc(self) -> None:
        # Construct a payload with SOC alarm active: bits[1:0] != 0
        header = bytes([0xA0, 0xF1, 0x0A, 0x36, 0x88])
        payload = struct.pack("<BBHBBBB", 0xF1, 14, 11500, 0xFF, 0xFF, 0xFF, 0xFF)
        _, alarms = _decode_notify(header + payload, BatteryState(), AlarmState())
        assert alarms.soc_alarm_active is True
        assert alarms.voltage_alarm_active is False

    def test_alarm_active_voltage(self) -> None:
        # Construct a payload with voltage alarm active: bits[3:2] != 0
        header = bytes([0xA0, 0xF1, 0x0A, 0x36, 0x88])
        payload = struct.pack("<BBHBBBB", 0xF4, 14, 11500, 0xFF, 0xFF, 0xFF, 0xFF)
        _, alarms = _decode_notify(header + payload, BatteryState(), AlarmState())
        assert alarms.soc_alarm_active is False
        assert alarms.voltage_alarm_active is True


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_decode_returns_new_battery_instance(self) -> None:
        battery = BatteryState()
        alarms = AlarmState()
        frames = parse_rbus_frames(NOTIFY_A_CURRENT)
        assert len(frames) == 1
        new_battery, _ = decode(frames[0], battery, alarms)
        assert new_battery is not battery

    def test_decode_returns_new_alarms_instance(self) -> None:
        battery = BatteryState()
        alarms = AlarmState()
        frames = parse_rbus_frames(NOTIFY_A_TEMP)
        assert len(frames) == 1
        _, new_alarms = decode(frames[0], battery, alarms)
        assert new_alarms is not alarms

    def test_original_state_unchanged_after_decode(self) -> None:
        battery = BatteryState()
        alarms = AlarmState()
        frames = parse_rbus_frames(NOTIFY_A_CURRENT)
        decode(frames[0], battery, alarms)
        assert battery.net_current_a is None  # original unaffected

    def test_battery_model_is_frozen(self) -> None:
        battery = BatteryState()
        with pytest.raises(Exception):  # ValidationError or TypeError  # noqa: B017
            battery.soc_pct = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------


class TestTimestamp:
    def test_timestamp_none_before_f280(self) -> None:
        # F1:04 does NOT set timestamp
        battery, _ = _decode_notify(NOTIFY_A_SOC, BatteryState(), AlarmState())
        assert battery.timestamp is None

    def test_timestamp_set_after_f280(self) -> None:
        before = datetime.now()
        battery, _ = _decode_notify(NOTIFY_A_CURRENT, BatteryState(), AlarmState())
        after = datetime.now()
        assert battery.timestamp is not None
        assert before <= battery.timestamp <= after

    def test_f102_does_not_set_timestamp(self) -> None:
        # F1:02 only updates voltage_v, not timestamp
        battery, _ = _decode_notify(NOTIFY_A_VOLTAGE, BatteryState(), AlarmState())
        assert battery.timestamp is None

    def test_f10a_does_not_set_battery_timestamp(self) -> None:
        # F1:0A updates alarms only
        battery, _ = _decode_notify(NOTIFY_A_TEMP, BatteryState(), AlarmState())
        assert battery.timestamp is None

    def test_f100_does_not_set_timestamp(self) -> None:
        # F1:00 only updates charge_state
        battery, _ = _decode_notify(NOTIFY_A_CHARGESTATE, BatteryState(), AlarmState())
        assert battery.timestamp is None
