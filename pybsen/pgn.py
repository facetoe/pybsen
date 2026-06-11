"""PGN decode layer: maps Kaitai-parsed RBUS frames to domain model updates.

Consumes Kaitai RbusFrame computed properties (already-applied formulas) and
produces updated BatteryState / AlarmState snapshots via model_copy().

Architecture note: this module reads Kaitai computed properties, not raw bytes.
All formula application is in the Kaitai layer (pybsen/kaitai/rbus_frame.py).
"""

from datetime import datetime
from typing import Any

from pybsen.frame import RawFrame
from pybsen.kaitai.rbus_frame import RbusFrame  # type: ignore[attr-defined]
from pybsen.models import AlarmState, BatteryState

_PGN_F100 = 0xF100
_PGN_F102 = 0xF102
_PGN_F104 = 0xF104
_PGN_F10A = 0xF10A
_PGN_F280 = 0xF280
_PGN_F304 = 0xF304
_PGN_F404 = 0xF404


def decode(raw: RawFrame, battery: BatteryState, alarms: AlarmState) -> tuple[BatteryState, AlarmState]:
    """Decode one RawFrame into updated BatteryState and AlarmState.

    Returns (new_battery, new_alarms) — uses model_copy for immutable update.
    Unknown PGN keys are silently ignored (no-op).
    """
    header = bytes([0xA0, raw.pdu_fmt, raw.pdu_spec, raw.src_addr, 0x80 | (len(raw.payload) & 0x0F)])
    kf: Any = RbusFrame.from_bytes(header + raw.payload)
    pgn_key = raw.pdu_fmt << 8 | raw.pdu_spec

    if pgn_key == _PGN_F280:
        battery = _decode_f280(kf, battery)

    elif pgn_key == _PGN_F104:
        battery = _decode_f104(kf, battery)

    elif pgn_key == _PGN_F102:
        battery = _decode_f102(kf, battery)

    elif pgn_key == _PGN_F10A:
        alarms = _decode_f10a(kf, alarms)

    elif pgn_key == _PGN_F100:
        battery = _decode_f100(kf, battery)

    # F3:04 (RTC) and F4:04 (device info) are no-ops — no domain model fields.

    return battery, alarms


def _decode_f280(kf: Any, battery: BatteryState) -> BatteryState:
    """F2:80 RBusPGNBatterySensorMeasurementsAveraged — primary 1 Hz PGN."""
    p = kf.payload

    raw_current: int = int(p.raw_current)
    raw_voltage: int = int(p.raw_voltage)
    raw_temp: int = int(p.raw_temp)

    net_current_a: float | None = None if raw_current == 20000 else float(p.net_current_a)
    voltage_v: float | None = None if raw_voltage == 643 else float(p.voltage_v)
    temp_c: float | None = None if raw_temp == 0xFA else float(p.temp_c)

    return battery.model_copy(
        update={
            "net_current_a": net_current_a,
            "voltage_v": voltage_v,
            "temp_c": temp_c,
            "timestamp": datetime.now(),
        }
    )


def _decode_f104(kf: Any, battery: BatteryState) -> BatteryState:
    """F1:04 RBusPGNBatteryChargeStatus — SOC, SoH, time remaining."""
    p = kf.payload

    soc_pct: int = int(p.soc_pct)
    raw_soh: int = int(p.state_of_health_pct)
    state_of_health_pct: int | None = None if raw_soh == 0xFF else raw_soh

    time_to_full_min: int | None = None
    time_to_flat_min: int | None = None

    if int(p.raw_time) != 0xFFFA:
        val: int = int(p.time_until_fullflat_min)
        if val > 0:
            time_to_full_min = val
        elif val < 0:
            time_to_flat_min = abs(val)
        # val == 0: crossover — both remain None

    return battery.model_copy(
        update={
            "soc_pct": soc_pct,
            "state_of_health_pct": state_of_health_pct,
            "time_to_full_min": time_to_full_min,
            "time_to_flat_min": time_to_flat_min,
        }
    )


def _decode_f102(kf: Any, battery: BatteryState) -> BatteryState:
    """F1:02 RBusPGNBatterySensorMeasurements — secondary voltage source (0.5 Hz)."""
    p = kf.payload

    raw_mv: int = int(p.raw_voltage_mv)
    if raw_mv == 0xFFFF:
        return battery

    voltage_v: float = float(p.voltage_v)
    return battery.model_copy(update={"voltage_v": voltage_v})


def _decode_f10a(kf: Any, alarms: AlarmState) -> AlarmState:
    """F1:0A RBusPGNLowBatteryAlarm — alarm thresholds and status."""
    p = kf.payload

    raw_vs: int = int(p.raw_voltage_setpoint)
    voltage_alarm_setpoint_v: float | None = None if raw_vs == 0xFFFA else float(p.voltage_alarm_setpoint_v)

    return alarms.model_copy(
        update={
            "soc_alarm_active": bool(p.soc_alarm_active),
            "voltage_alarm_active": bool(p.voltage_alarm_active),
            "soc_alarm_setpoint_pct": int(p.soc_alarm_setpoint_pct),
            "voltage_alarm_setpoint_v": voltage_alarm_setpoint_v,
        }
    )


def _decode_f100(kf: Any, battery: BatteryState) -> BatteryState:
    """F1:00 RBusPGNBatteryProperties — charge_state byte (meaning unknown)."""
    p = kf.payload
    return battery.model_copy(update={"charge_state": int(p.charge_state)})
