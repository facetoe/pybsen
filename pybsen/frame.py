"""RBUS wire-frame reassembly.

Parses one BLE notification value (bytes from the bleak on_notify callback)
into a list of RawFrame objects.  Multi-segment reassembly for FC:D0 and
similar long PGNs is handled but has not been validated against live captures
(see docs/protocol.md §7 known limitation 5).
"""

from dataclasses import dataclass, field


@dataclass
class RawFrame:
    """Single reassembled RBUS CAN frame, pre-Kaitai parse artifact."""

    pdu_fmt: int
    pdu_spec: int
    src_addr: int
    payload: bytes
    segment_count: int = field(default=1)


def parse_rbus_frames(data: bytes) -> list[RawFrame]:
    """
    Parse one BLE notification value into a list of RBUS CAN frames.

    Single-segment frame (13 B):
      [flags, pduFmt, pduSpec, srcAddr, lenByte, d0..d7]
      lenByte bits[3:0] = data_len (typically 8)

    Multi-segment frame: a normal header frame is followed by ≥1 continuation
    bytes in the SAME notification buffer.
      First frag : [flags(bit6=0), pduFmt, pduSpec, srcAddr, lenByte, segIdx, d0..d6]
      Continuation: [0x40|any, segIdx, d0..d6]  (9 bytes each)

    Dispatch rule: treat payload[0] as segIdx (and true data = payload[1:]) only
    when the immediately following byte has bit6=1 (indicating a continuation).
    """
    frames: list[RawFrame] = []
    pos = 0

    while pos < len(data):
        if pos + 5 > len(data):
            break

        b0 = data[pos]
        if b0 & 0x40:
            # Stray continuation with no preceding header — skip it
            pos += min(9, len(data) - pos)
            continue

        pdu_fmt = data[pos + 1]
        pdu_spec = data[pos + 2]
        src_addr = data[pos + 3]
        len_byte = data[pos + 4]
        data_len = len_byte & 0x0F
        pos += 5

        available = len(data) - pos
        data_len = min(data_len, available)
        raw_payload = data[pos : pos + data_len]
        pos += data_len

        # Look ahead: is the next byte a continuation marker?
        if pos < len(data) and (data[pos] & 0x40):
            # Multi-segment: payload[0] = segIdx, payload[1:] = first chunk
            chunk = raw_payload[1:] if len(raw_payload) > 1 else b""
            seg_count = 1
            while pos < len(data) and (data[pos] & 0x40):
                if pos + 2 > len(data):
                    break
                # seg_idx = data[pos + 1]  (not used for reassembly here)
                cont_chunk = data[pos + 2 : pos + 9]
                chunk += cont_chunk
                pos += 9
                seg_count += 1
            frames.append(RawFrame(pdu_fmt, pdu_spec, src_addr, chunk, seg_count))
        else:
            frames.append(RawFrame(pdu_fmt, pdu_spec, src_addr, raw_payload))

    return frames
