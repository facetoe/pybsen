meta:
  id: rbus_filter
  title: REDARC BSEN500 PGN Filter Entry (CHAR_2015_8002)
  license: MIT
  ks-version: 0.11
  endian: le

doc: |
  12-byte PGN filter subscription entry written to CHAR_2015_8002
  (UUID 09022015-5160-4000-8002-524544415243).

  The host writes one filter entry per PGN it wants to receive. The device
  uses the filter list to determine which PGNs to include in CHAR_2015_8001
  notifications, and at what rate. Without filter writes, the device streams
  nothing (confirmed empirically).

  Wire format (12 bytes):
    04 2A A0 FF FF 00 00 <pdu_fmt> <pdu_spec> 00 <period_lo> <period_hi>

  The first 7 bytes appear constant across all filter writes in the init
  sequence. The first byte (slot_idx=0x04 in all observed writes) may be a
  fixed magic value rather than a per-slot index; this is UNCONFIRMED.

  Sample filter writes from discover.py STANDARD_FILTERS:
    04 2A A0 FF FF 00 00 F2 80 00 E8 03  →  F2:80 @ 1000 ms
    04 2A A0 FF FF 00 00 F1 04 00 2C 01  →  F1:04 @ 300 ms
    04 2A A0 FF FF 00 00 F1 02 00 D0 07  →  F1:02 @ 2000 ms
    04 2A A0 FF FF 00 00 F1 0A 00 E8 03  →  F1:0A @ 1000 ms
    04 2A A0 FF FF 00 00 F1 00 00 88 13  →  F1:00 @ 5000 ms

  Source: PROTOCOL.md §2 Filter write format, §10 FILTER_WRITES, btsnoop_hci.log.

seq:
  - id: slot_idx
    type: u1
    doc: |
      Byte [0]. Always 0x04 in all observed filter writes. Meaning UNCONFIRMED —
      may be a magic prefix byte rather than a per-slot index.
      Source: PROTOCOL.md §2, §10.
    -confidence: low
    -evidence: all 30 filter writes in STANDARD_FILTERS have byte[0]=0x04

  - id: fixed_2a
    type: u1
    doc: |
      Byte [1]. Always 0x2A in observed frames; meaning unknown.
      Field semantics are UNCONFIRMED (confidence: low); using a plain u1
      instead of contents-validation to tolerate any firmware variation.
      Source: PROTOCOL.md §2 filter preamble.
    -confidence: low

  - id: flags
    type: u1
    doc: |
      Byte [2]. Always 0xA0 in all observed filter writes.
      Likely a frame-type/flags field matching the RBUS wire frame flags byte.
      Source: PROTOCOL.md §2.
    -confidence: medium

  - id: mask_hi
    type: u1
    doc: |
      Byte [3]. Always 0xFF in all observed writes. Likely a PGN acceptance
      mask high byte; 0xFF = accept any source address (wildcard).
      Source: PROTOCOL.md §2 preamble bytes 3-4.
    -confidence: low

  - id: mask_lo
    type: u1
    doc: |
      Byte [4]. Always 0xFF in all observed writes. Likely a PGN acceptance
      mask low byte; 0xFF = wildcard.
      Source: PROTOCOL.md §2.
    -confidence: low

  - id: zero_0
    type: u2
    doc: |
      Bytes [5-6]. Always 0x0000 (LE) in all observed filter writes.
      Purpose UNKNOWN. Padding or reserved field.
      Source: PROTOCOL.md §2 preamble bytes 5-6.
    -confidence: low

  - id: pdu_fmt
    type: u1
    doc: |
      Byte [7]. PGN high byte — matches the pdu_fmt field in RBUS CAN frames
      from the subscribed PGN. Example: 0xF2 for F2:80.
      Source: PROTOCOL.md §2.
    -confidence: high

  - id: pdu_spec
    type: u1
    doc: |
      Byte [8]. PGN low byte — matches the pdu_spec field in RBUS CAN frames.
      Example: 0x80 for F2:80 (averaged measurements).
      Source: PROTOCOL.md §2.
    -confidence: high

  - id: zero_1
    type: u1
    doc: |
      Byte [9]. Always 0x00 in all observed filter writes.
      Purpose UNKNOWN. Padding or reserved field.
      Source: PROTOCOL.md §2.
    -confidence: low

  - id: rate_limit_ms
    type: u2
    doc: |
      Bytes [10-11]. Notification period in milliseconds, little-endian.
      The device will not send this PGN more frequently than this interval.
      Examples: 0x012C = 300 ms (F1:04), 0x03E8 = 1000 ms (F2:80, F1:0A),
                0x07D0 = 2000 ms (F1:02), 0x1388 = 5000 ms (F1:00).
      Source: PROTOCOL.md §2, §10.
    -confidence: high
    -evidence: btsnoop_hci.log filter writes, confirmed by observed notification cadence

instances:
  pgn_key:
    value: '(pdu_fmt << 8) | pdu_spec'
    doc: |
      16-bit PGN key encoded in this filter entry.
      Matches pgn_key in rbus_frame.ksy for cross-referencing.
