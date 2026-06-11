meta:
  id: rbus_gateway
  title: REDARC BSEN500 Gateway Channel Frame (CHAR_2015_8003)
  license: MIT
  ks-version: 0.11
  endian: le

doc: |
  CHAR_2015_8003 gateway channel protocol.
  UUID: 09022015-5160-4000-8003-524544415243

  Two distinct frame formats share this characteristic:
    - Write frame (host → device): [key_hi, key_lo, data_len, ...data...]
    - Response frame (device → host): [0x80, key_lo, ...response_data...]

  This spec's top-level seq parses a WRITE frame (the typical analysis
  direction). To parse a response frame, use the embedded response_frame type.

  Disambiguation: response frames always begin with 0x80. Write frames with
  bit7 of key_hi set (i.e. key_hi = 0x80, meaning response is expected) are
  structurally identical in their first byte. Context (characteristic write vs
  notify callback) is the only reliable discriminator.

  Key dictionary:
    0x0001  Read device RBUS address. Write: [0x80, 0x01, 0x00].
            Response: [0x80, 0x01, 0x01, rbus_addr].
    0x0002  MTU negotiation. Write: [0x00, 0x02, 0x02, mtu_hi, mtu_lo].
            Response: [0x80, 0x02, 0x00].
    0xFFFF  Error / undefined.

  Source: PROTOCOL.md §Gateway Channel Protocol, AGENTS.md Initialization Sequence.
  Confirmed from btsnoop_hci.log init trace.

seq:
  - id: key_hi
    type: u1
    doc: |
      High byte of the 16-bit command key.
      Bit 7 (0x80) set = response expected from device.
      0x00 = no response expected; 0x80 = response expected.
      Source: PROTOCOL.md Gateway Channel Protocol.
    -confidence: high
    -evidence: MTU write key_hi=0x00 (no response bit), addr read key_hi=0x80

  - id: key_lo
    type: u1
    doc: |
      Low byte of the command key.
      0x01 = GW_RBUS_ADDR (read device RBUS source address).
      0x02 = GW_MTU (MTU negotiation, payload = 2-byte big-endian MTU value).
      0xFF (with key_hi=0xFF) = error / undefined.
      Source: PROTOCOL.md Gateway Channel Protocol.
    -confidence: high

  - id: data_len
    type: u1
    doc: |
      Number of data bytes following this field.
      0x00 for GW_RBUS_ADDR write (no payload).
      0x02 for GW_MTU write (2-byte MTU value).
      Source: PROTOCOL.md Gateway Channel Protocol.
    -confidence: high

  - id: data
    size: data_len
    doc: |
      Command payload, data_len bytes.
      GW_MTU: 2-byte big-endian MTU value. Example: [0x00, 0xA0] = 160 bytes MTU.
      GW_RBUS_ADDR: empty (data_len=0).
      Source: PROTOCOL.md §Initialization Sequence step 3.
    -confidence: high

instances:
  key:
    value: '(key_hi << 8) | key_lo'
    doc: Full 16-bit command key. 0x0001=addr read, 0x0002=MTU, 0xFFFF=error.

  response_expected:
    value: '(key_hi & 0x80) != 0'
    doc: True if bit 7 of key_hi is set, meaning device will send a response notification.

types:
  response_frame:
    doc: |
      Device → host response on CHAR_2015_8003 notify.
      Format: [0x80, key_lo, ...response_data...]
      The 0x80 prefix byte is always present on response frames.
      Source: PROTOCOL.md Gateway Channel Protocol.
    seq:
      - id: prefix
        contents: [0x80]
        doc: |
          Fixed prefix byte 0x80 identifying this as a gateway response.
          Using contents: validates the byte at parse time.
        -confidence: high

      - id: key_lo
        type: u1
        doc: |
          Echo of the command key low byte from the corresponding write.
          0x01 = GW_RBUS_ADDR response, 0x02 = GW_MTU response.
        -confidence: high

      - id: response_data
        size-eos: true
        doc: |
          Response payload bytes (variable length, read to end of notification).
          GW_RBUS_ADDR (key_lo=0x01): [data_len=0x01, rbus_addr]. Sample: [0x01, 0x36].
          GW_MTU (key_lo=0x02): [0x00] (empty acknowledgement).
          Source: PROTOCOL.md §Initialization Sequence, AGENTS.md step 5.
        -confidence: high
        -evidence: NOTIFY_GW_ADDR_RESPONSE=0x80,0x01,0x01,0x36; NOTIFY_GW_MTU_RESPONSE=0x80,0x02,0x00
