"""
Pytest regression tests for rbus_frame.ksy Kaitai Struct specification.

Covers all PGN types with available binary fixtures plus in-test synthetic
frames for sentinel value edge cases.

Expected values are verified against tests/fixtures.py SEQUENCE_* entries and
NOTIFY_* byte constants from tests/fixtures.py.

Run from repo root:
    make test
"""

import os
import struct

import pytest

from pybsen.kaitai.rbus_frame import RbusFrame

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_frame(name: str) -> RbusFrame:
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return RbusFrame.from_bytes(f.read())


def make_f2_80(raw_current: int, raw_voltage: int, raw_load: int, raw_temp: int) -> RbusFrame:
    """Construct a minimal F2:80 RbusFrame from raw field values."""
    header = bytes([0xA0, 0xF2, 0x80, 0x36, 0x88])
    payload = struct.pack("<HHHB", raw_current, raw_voltage, raw_load, raw_temp) + b"\xff"
    return RbusFrame.from_bytes(header + payload)


def make_f1_04(soc_pct: int, soh_pct: int, raw_time: int) -> RbusFrame:
    """Construct a minimal F1:04 RbusFrame from raw field values."""
    header = bytes([0xA0, 0xF1, 0x04, 0x36, 0x88])
    payload = struct.pack("<BBH", soc_pct, soh_pct, raw_time) + bytes([0xFF, 0xFF, 0xFF, 0xFF])
    return RbusFrame.from_bytes(header + payload)


# ---------------------------------------------------------------------------
# F2:80  RBusPGNBatterySensorMeasurementsAveraged
# ---------------------------------------------------------------------------


class TestPgnF280:
    def test_session_a_net_current(self):
        # NOTIFY_A_CURRENT: raw_current=10005 → (10005-10000)*0.1 = +0.5 A
        frame = load_frame("notify_a_current.bin")
        assert frame.pdu_fmt == 0xF2
        assert frame.pdu_spec == 0x80
        assert frame.pgn_key == 0xF280
        assert frame.payload.raw_current == 10005
        assert frame.payload.net_current_a == pytest.approx(0.5)

    def test_session_a_voltage(self):
        # NOTIFY_A_CURRENT: raw_voltage=133 → 133*0.1 = 13.3 V
        frame = load_frame("notify_a_current.bin")
        assert frame.payload.raw_voltage == 133
        assert frame.payload.voltage_v == pytest.approx(13.3)

    def test_session_a_temp(self):
        # NOTIFY_A_CURRENT: raw_temp=0x43=67 → 67-60 = 7°C
        frame = load_frame("notify_a_current.bin")
        assert frame.payload.raw_temp == 0x43
        assert frame.payload.temp_c == 7

    def test_session_d_net_current(self):
        # NOTIFY_D_CHARGER: raw_current=9856 → (9856-10000)*0.1 = -14.4 A (app confirmed ~14A)
        frame = load_frame("notify_d_charger.bin")
        assert frame.payload.raw_current == 9856
        assert frame.payload.net_current_a == pytest.approx(-14.4)

    def test_session_d_voltage(self):
        # NOTIFY_D_CHARGER: raw_voltage=131 → 131*0.1 = 13.1 V
        frame = load_frame("notify_d_charger.bin")
        assert frame.payload.raw_voltage == 131
        assert frame.payload.voltage_v == pytest.approx(13.1)

    def test_session_d_temp(self):
        # NOTIFY_D_CHARGER: raw_temp=0x48=72 → 72-60 = 12°C
        frame = load_frame("notify_d_charger.bin")
        assert frame.payload.raw_temp == 0x48
        assert frame.payload.temp_c == 12

    def test_session_e_net_current(self):
        # NOTIFY_E_CURRENT: raw_current=9892 → (9892-10000)*0.1 = -10.8 A
        frame = load_frame("notify_e_current.bin")
        assert frame.payload.raw_current == 9892
        assert frame.payload.net_current_a == pytest.approx(-10.8)

    def test_session_e_voltage(self):
        # NOTIFY_E_CURRENT: raw_voltage=132 → 132*0.1 = 13.2 V
        frame = load_frame("notify_e_current.bin")
        assert frame.payload.raw_voltage == 132
        assert frame.payload.voltage_v == pytest.approx(13.2)

    def test_session_e_temp(self):
        # NOTIFY_E_CURRENT: raw_temp=0x4B=75 → 75-60 = 15°C (CONFIRMED vs app screenshot)
        frame = load_frame("notify_e_current.bin")
        assert frame.payload.raw_temp == 0x4B
        assert frame.payload.temp_c == 15

    def test_load_current_not_available(self):
        # Single-shunt BSEN500: raw_load_current always 0xFFFF
        frame = load_frame("notify_a_current.bin")
        assert frame.payload.raw_load_current == 0xFFFF

    def test_sentinel_current_returns_zero(self):
        # Sentinel: raw_current == 20000 → net_current_a returns 0.0
        frame = make_f2_80(raw_current=20000, raw_voltage=133, raw_load=0xFFFF, raw_temp=0x43)
        assert frame.payload.raw_current == 20000
        assert frame.payload.net_current_a == 0.0

    def test_sentinel_temp_returns_zero(self):
        # Sentinel: raw_temp == 0xFA → temp_c returns 0
        frame = make_f2_80(raw_current=10005, raw_voltage=133, raw_load=0xFFFF, raw_temp=0xFA)
        assert frame.payload.raw_temp == 0xFA
        assert frame.payload.temp_c == 0


# ---------------------------------------------------------------------------
# F1:04  RBusPGNBatteryChargeStatus
# ---------------------------------------------------------------------------


class TestPgnF104:
    def test_session_a_soc(self):
        # NOTIFY_A_SOC: payload[0]=0x63=99
        frame = load_frame("notify_a_soc.bin")
        assert frame.pdu_fmt == 0xF1
        assert frame.pdu_spec == 0x04
        assert frame.pgn_key == 0xF104
        assert frame.payload.soc_pct == 99

    def test_session_a_time_to_full(self):
        # NOTIFY_A_SOC: raw_time=0x7DC6=32198 → (32198-32127)*5 = 355 min (positive=charging)
        frame = load_frame("notify_a_soc.bin")
        assert frame.payload.raw_time == 32198
        assert frame.payload.time_until_fullflat_min == 355

    def test_session_a_soh_not_available(self):
        # SoH always 0xFF (not available) on BSEN500
        frame = load_frame("notify_a_soc.bin")
        assert frame.payload.state_of_health_pct == 0xFF

    def test_session_3_soc(self):
        # NOTIFY_3_MEASUREMENT: payload[0]=0x62=98
        frame = load_frame("notify_3_measurement.bin")
        assert frame.payload.soc_pct == 98

    def test_session_3_time_to_flat(self):
        # NOTIFY_3_MEASUREMENT: raw_time=0x7B8B=31627 → (31627-32127)*5 = -2500 min (discharging)
        frame = load_frame("notify_3_measurement.bin")
        assert frame.payload.raw_time == 31627
        assert frame.payload.time_until_fullflat_min == -2500

    def test_session_d_soc(self):
        # NOTIFY_D_MEASUREMENT: payload[0]=0x5D=93
        frame = load_frame("notify_d_measurement.bin")
        assert frame.payload.soc_pct == 93

    def test_session_d_time_to_flat(self):
        # NOTIFY_D_MEASUREMENT: raw_time=0x7CA5=31909 → (31909-32127)*5 = -1090 min
        frame = load_frame("notify_d_measurement.bin")
        assert frame.payload.raw_time == 31909
        assert frame.payload.time_until_fullflat_min == -1090

    def test_sentinel_time_returns_minus_one(self):
        # Sentinel: raw_time == 0xFFFA → time_until_fullflat_min returns -1
        frame = make_f1_04(soc_pct=99, soh_pct=0xFF, raw_time=0xFFFA)
        assert frame.payload.raw_time == 0xFFFA
        assert frame.payload.time_until_fullflat_min == -1


# ---------------------------------------------------------------------------
# F1:0A  RBusPGNLowBatteryAlarm
# ---------------------------------------------------------------------------


class TestPgnF10a:
    def test_alarm_flags_session_a(self):
        # NOTIFY_A_TEMP: alarm_flags=0xF0 → bits[1:0]=0 (SOC off), bits[3:2]=0 (volt off)
        frame = load_frame("notify_a_temp.bin")
        assert frame.pdu_fmt == 0xF1
        assert frame.pdu_spec == 0x0A
        assert frame.pgn_key == 0xF10A
        assert frame.payload.alarm_flags == 0xF0
        assert frame.payload.soc_alarm_active is False
        assert frame.payload.voltage_alarm_active is False

    def test_soc_setpoint_session_a(self):
        # NOTIFY_A_TEMP: soc_alarm_setpoint_pct=0x0E=14
        frame = load_frame("notify_a_temp.bin")
        assert frame.payload.soc_alarm_setpoint_pct == 14

    def test_voltage_setpoint_session_a(self):
        # NOTIFY_A_TEMP: raw_voltage_setpoint=0x2CEC=11500 → 11500*0.001 = 11.500 V
        frame = load_frame("notify_a_temp.bin")
        assert frame.payload.raw_voltage_setpoint == 11500
        assert frame.payload.voltage_alarm_setpoint_v == pytest.approx(11.5, abs=0.001)

    def test_alarm_flags_session_e(self):
        # NOTIFY_E_ALARM: same setpoints as session A
        frame = load_frame("notify_e_alarm.bin")
        assert frame.payload.soc_alarm_active is False
        assert frame.payload.voltage_alarm_active is False
        assert frame.payload.soc_alarm_setpoint_pct == 14
        assert frame.payload.voltage_alarm_setpoint_v == pytest.approx(11.5, abs=0.001)


# ---------------------------------------------------------------------------
# F1:02  RBusPGNBatterySensorMeasurements  (secondary voltage source)
# ---------------------------------------------------------------------------


class TestPgnF102:
    def test_session_a_voltage(self):
        # NOTIFY_A_VOLTAGE: raw_voltage_mv=13385 → 13385/1000.0 = 13.385 V
        frame = load_frame("notify_a_voltage.bin")
        assert frame.pdu_fmt == 0xF1
        assert frame.pdu_spec == 0x02
        assert frame.pgn_key == 0xF102
        assert frame.payload.raw_voltage_mv == 13385
        assert frame.payload.voltage_v == pytest.approx(13.385, abs=0.001)


# ---------------------------------------------------------------------------
# F1:00  RBusPGNBatteryProperties
# ---------------------------------------------------------------------------


class TestPgnF100:
    def test_charge_state_session_a(self):
        # NOTIFY_A_CHARGESTATE: charge_state=0x01 (always 1 across all sessions)
        frame = load_frame("notify_a_chargestate.bin")
        assert frame.pdu_fmt == 0xF1
        assert frame.pdu_spec == 0x00
        assert frame.pgn_key == 0xF100
        assert frame.payload.charge_state == 1

    def test_unknown_0_session_a(self):
        # NOTIFY_A_CHARGESTATE bytes[5-6]=04 18 → LE u16 = 0x1804 = 6148
        frame = load_frame("notify_a_chargestate.bin")
        assert frame.payload.unknown_0 == 0x1804


# ---------------------------------------------------------------------------
# F4:04  RBusPGNNodeSerialInformation
# ---------------------------------------------------------------------------


class TestPgnF404:
    def test_device_info_data(self):
        # NOTIFY_A_DEVICEINFO: constant payload 5F 6D 5B 8F 14 00 18 00
        frame = load_frame("notify_a_deviceinfo.bin")
        assert frame.pdu_fmt == 0xF4
        assert frame.pdu_spec == 0x04
        assert frame.pgn_key == 0xF404
        assert frame.payload.data == bytes.fromhex("5f6d5b8f14001800")


# ---------------------------------------------------------------------------
# F3:04  RBusPGNRealTimeClock — dispatch test (synthetic frame)
# ---------------------------------------------------------------------------


class TestPgnF304:
    def test_dispatch_parses_without_exception(self):
        # Construct a minimal F3:04 frame: day=1, month=6, year=2026, hour=14, min=8, sec=0
        # Layout: [unknown_0:1][month:1][year:2 LE][hour:1][minute:1][second:1] + 1 padding byte
        header = bytes([0xA0, 0xF3, 0x04, 0x36, 0x88])
        payload = struct.pack("<BBHBBBx", 0x01, 6, 2026, 14, 8, 0)
        frame = RbusFrame.from_bytes(header + payload)
        assert frame.pgn_key == 0xF304
        assert frame.payload.month == 6
        assert frame.payload.year == 2026
        assert frame.payload.hour == 14


# ---------------------------------------------------------------------------
# Frame header fields (shared across PGN types)
# ---------------------------------------------------------------------------


class TestFrameHeader:
    def test_flags_byte(self):
        frame = load_frame("notify_a_current.bin")
        assert frame.flags == 0xA0

    def test_src_addr(self):
        frame = load_frame("notify_a_current.bin")
        assert frame.src_addr == 0x36

    def test_data_len_from_len_byte(self):
        # len_byte=0x88 → data_len = 0x88 & 0x0F = 8
        frame = load_frame("notify_a_current.bin")
        assert frame.len_byte == 0x88
        assert frame.data_len == 8
