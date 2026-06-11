"""Tests for pybsen.frame — RBUS wire-frame reassembly."""

from collections.abc import Callable

import pytest

from pybsen.frame import RawFrame, parse_rbus_frames
from tests.fixtures import (
    NOTIFY_EMPTY,
    NOTIFY_GW_ADDR_RESPONSE,
    NOTIFY_GW_MTU_RESPONSE,
    NOTIFY_STRAY_CONTINUATION,
    NOTIFY_TOO_SHORT,
)


class TestEdgeCases:
    def test_empty_returns_empty_list(self) -> None:
        assert parse_rbus_frames(NOTIFY_EMPTY) == []

    def test_too_short_returns_empty_list(self) -> None:
        # 4 bytes: header requires minimum 5
        assert parse_rbus_frames(NOTIFY_TOO_SHORT) == []

    def test_stray_continuation_returns_empty_list(self) -> None:
        # b0 = 0x40 sets bit6 → stray continuation, skipped
        assert parse_rbus_frames(NOTIFY_STRAY_CONTINUATION) == []

    def test_gw_mtu_response_returns_empty_list(self) -> None:
        # Gateway channel response [0x80, 0x02, 0x00] — 3 bytes, not an RBUS frame
        assert parse_rbus_frames(NOTIFY_GW_MTU_RESPONSE) == []

    def test_gw_addr_response_returns_empty_list(self) -> None:
        # Gateway channel response [0x80, 0x01, 0x01, 0x36] — 4 bytes, not an RBUS frame
        assert parse_rbus_frames(NOTIFY_GW_ADDR_RESPONSE) == []


class TestSingleFrameParse:
    """Verify correct field extraction from real binary fixtures."""

    def test_f280_pdu_fmt(self, load_bin: Callable[[str], bytes]) -> None:
        data = load_bin("notify_a_current.bin")
        frames = parse_rbus_frames(data)
        assert len(frames) == 1
        assert frames[0].pdu_fmt == 0xF2

    def test_f280_pdu_spec(self, load_bin: Callable[[str], bytes]) -> None:
        data = load_bin("notify_a_current.bin")
        frames = parse_rbus_frames(data)
        assert frames[0].pdu_spec == 0x80

    def test_f280_src_addr(self, load_bin: Callable[[str], bytes]) -> None:
        data = load_bin("notify_a_current.bin")
        frames = parse_rbus_frames(data)
        assert frames[0].src_addr == 0x36

    def test_f280_segment_count(self, load_bin: Callable[[str], bytes]) -> None:
        data = load_bin("notify_a_current.bin")
        frames = parse_rbus_frames(data)
        assert frames[0].segment_count == 1

    def test_f280_payload_length(self, load_bin: Callable[[str], bytes]) -> None:
        # len_byte = 0x88 → data_len = 8
        data = load_bin("notify_a_current.bin")
        frames = parse_rbus_frames(data)
        assert len(frames[0].payload) == 8

    def test_f280_payload_bytes(self, load_bin: Callable[[str], bytes]) -> None:
        # NOTIFY_A_CURRENT payload: 15 27 85 00 ff ff 43 ff
        # raw_current=0x2715=10005, raw_voltage=0x0085=133, raw_temp=0x43
        data = load_bin("notify_a_current.bin")
        frames = parse_rbus_frames(data)
        payload = frames[0].payload
        assert payload[0] == 0x15  # LSB of raw_current 10005
        assert payload[1] == 0x27  # MSB of raw_current 10005
        assert payload[6] == 0x43  # raw_temp = 67

    def test_f104_pdu_fmt_spec(self, load_bin: Callable[[str], bytes]) -> None:
        data = load_bin("notify_a_soc.bin")
        frames = parse_rbus_frames(data)
        assert len(frames) == 1
        assert frames[0].pdu_fmt == 0xF1
        assert frames[0].pdu_spec == 0x04

    def test_f104_payload_soc_byte(self, load_bin: Callable[[str], bytes]) -> None:
        # NOTIFY_A_SOC: payload[0] = 0x63 = 99 (SOC%)
        data = load_bin("notify_a_soc.bin")
        frames = parse_rbus_frames(data)
        assert frames[0].payload[0] == 0x63

    def test_f102_payload_voltage_bytes(self, load_bin: Callable[[str], bytes]) -> None:
        # NOTIFY_A_VOLTAGE: payload[4-5] = 0x49 0x34 = 13385 mV
        data = load_bin("notify_a_voltage.bin")
        frames = parse_rbus_frames(data)
        assert len(frames) == 1
        assert frames[0].pdu_fmt == 0xF1
        assert frames[0].pdu_spec == 0x02
        assert frames[0].payload[4] == 0x49
        assert frames[0].payload[5] == 0x34

    def test_f10a_payload_alarm_byte(self, load_bin: Callable[[str], bytes]) -> None:
        # NOTIFY_A_TEMP is actually F1:0A: payload[0] = 0xF0 → alarms inactive
        data = load_bin("notify_a_temp.bin")
        frames = parse_rbus_frames(data)
        assert len(frames) == 1
        assert frames[0].pdu_fmt == 0xF1
        assert frames[0].pdu_spec == 0x0A
        assert frames[0].payload[0] == 0xF0

    def test_f100_pdu_spec(self, load_bin: Callable[[str], bytes]) -> None:
        data = load_bin("notify_a_chargestate.bin")
        frames = parse_rbus_frames(data)
        assert len(frames) == 1
        assert frames[0].pdu_fmt == 0xF1
        assert frames[0].pdu_spec == 0x00

    def test_f404_pdu_spec(self, load_bin: Callable[[str], bytes]) -> None:
        data = load_bin("notify_a_deviceinfo.bin")
        frames = parse_rbus_frames(data)
        assert len(frames) == 1
        assert frames[0].pdu_fmt == 0xF4
        assert frames[0].pdu_spec == 0x04

    def test_parse_notify_fixture_consistent_with_direct_call(
        self, load_bin: Callable[[str], bytes], parse_notify: Callable[[bytes], list[RawFrame]]
    ) -> None:
        data = load_bin("notify_d_charger.bin")
        assert parse_notify(data) == parse_rbus_frames(data)


@pytest.mark.parametrize(
    "fixture_name",
    [
        "notify_a_current.bin",
        "notify_a_soc.bin",
        "notify_a_voltage.bin",
        "notify_a_temp.bin",
        "notify_a_chargestate.bin",
        "notify_b_current.bin",
        "notify_d_charger.bin",
        "notify_e_current.bin",
        "notify_e_soc.bin",
    ],
)
def test_single_frame_per_standard_fixture(fixture_name: str, load_bin: Callable[[str], bytes]) -> None:
    """All standard measurement fixtures should parse to exactly one frame."""
    data = load_bin(fixture_name)
    frames = parse_rbus_frames(data)
    assert len(frames) == 1
    assert frames[0].segment_count == 1


# ---------------------------------------------------------------------------
# Multi-segment reassembly
#
# The parser handles notifications where the first frame's payload starts with
# a segment-index byte and is followed by continuation chunks marked with
# bit6=1 in their first byte.  This path is used by FC:D0 (SOC log hourly)
# and similar long PGNs.  Layout per segment:
#
#   Header frag  : [flags(bit6=0), pduFmt, pduSpec, srcAddr, lenByte, segIdx, d0..d6]
#   Continuation : [0x40|x, segIdx, d0..d6]  (9 bytes)
#
# Assembled payload = first d0..d6 + each continuation's d0..d6.
# ---------------------------------------------------------------------------

_MULTISEG_HDR = bytes([0xA0, 0xFC, 0xD0, 0x36, 0x88])
_MULTISEG_SEG0 = bytes([0x00, 0x5F, 0x63, 0x63, 0x63, 0x63, 0x63, 0x63])  # segIdx=0, 7 data bytes
_MULTISEG_SEG1 = bytes([0x40, 0x01, 0x62, 0x61, 0x60, 0x5F, 0x5E, 0x5D, 0x5C])  # continuation seg1
_MULTISEG_SEG2 = bytes([0x40, 0x02, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])  # continuation seg2

_TWO_SEG = _MULTISEG_HDR + _MULTISEG_SEG0 + _MULTISEG_SEG1
_THREE_SEG = _MULTISEG_HDR + _MULTISEG_SEG0 + _MULTISEG_SEG1 + _MULTISEG_SEG2


class TestMultiSegment:
    def test_two_segment_produces_one_frame(self) -> None:
        assert len(parse_rbus_frames(_TWO_SEG)) == 1

    def test_two_segment_payload_length(self) -> None:
        # segIdx stripped from seg0; 7 bytes + 7 bytes from continuation = 14
        frames = parse_rbus_frames(_TWO_SEG)
        assert len(frames[0].payload) == 14

    def test_two_segment_payload_content(self) -> None:
        frames = parse_rbus_frames(_TWO_SEG)
        assert frames[0].payload[:7] == bytes([0x5F, 0x63, 0x63, 0x63, 0x63, 0x63, 0x63])
        assert frames[0].payload[7:] == bytes([0x62, 0x61, 0x60, 0x5F, 0x5E, 0x5D, 0x5C])

    def test_two_segment_segment_count(self) -> None:
        frames = parse_rbus_frames(_TWO_SEG)
        assert frames[0].segment_count == 2

    def test_two_segment_pdu_fields(self) -> None:
        frames = parse_rbus_frames(_TWO_SEG)
        assert frames[0].pdu_fmt == 0xFC
        assert frames[0].pdu_spec == 0xD0
        assert frames[0].src_addr == 0x36

    def test_three_segment_payload_length(self) -> None:
        # 7 + 7 + 7 = 21 bytes assembled
        frames = parse_rbus_frames(_THREE_SEG)
        assert len(frames[0].payload) == 21

    def test_three_segment_segment_count(self) -> None:
        frames = parse_rbus_frames(_THREE_SEG)
        assert frames[0].segment_count == 3

    def test_three_segment_third_chunk_appended(self) -> None:
        frames = parse_rbus_frames(_THREE_SEG)
        assert frames[0].payload[14:] == bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])

    def test_truncated_continuation_does_not_raise(self) -> None:
        # Continuation marker present but notification ends before the full 9-byte chunk
        data = _MULTISEG_HDR + _MULTISEG_SEG0 + bytes([0x40])
        frames = parse_rbus_frames(data)
        # Parser breaks out of the continuation loop rather than reading past end
        assert len(frames) == 1
        assert frames[0].payload == bytes([0x5F, 0x63, 0x63, 0x63, 0x63, 0x63, 0x63])
        assert frames[0].segment_count == 1


# ---------------------------------------------------------------------------
# Payload truncation
#
# If a notification ends before the data_len bytes declared in len_byte are
# all present, the parser clips silently via min(data_len, available).
# ---------------------------------------------------------------------------


class TestPayloadTruncation:
    def test_truncated_payload_does_not_raise(self) -> None:
        # len_byte=0x88 claims 8 payload bytes; only 3 follow the header
        data = bytes([0xA0, 0xF1, 0x04, 0x36, 0x88, 0x63, 0xFF, 0xC6])
        frames = parse_rbus_frames(data)
        assert len(frames) == 1

    def test_truncated_payload_length_clipped(self) -> None:
        data = bytes([0xA0, 0xF1, 0x04, 0x36, 0x88, 0x63, 0xFF, 0xC6])
        frames = parse_rbus_frames(data)
        assert len(frames[0].payload) == 3

    def test_truncated_payload_bytes_correct(self) -> None:
        data = bytes([0xA0, 0xF1, 0x04, 0x36, 0x88, 0x63, 0xFF, 0xC6])
        frames = parse_rbus_frames(data)
        assert frames[0].payload == bytes([0x63, 0xFF, 0xC6])
