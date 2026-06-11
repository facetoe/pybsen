# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class RbusFilter(KaitaiStruct):
    """12-byte PGN filter subscription entry written to CHAR_2015_8002
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
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(RbusFilter, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.slot_idx = self._io.read_u1()
        self.fixed_2a = self._io.read_u1()
        self.flags = self._io.read_u1()
        self.mask_hi = self._io.read_u1()
        self.mask_lo = self._io.read_u1()
        self.zero_0 = self._io.read_u2le()
        self.pdu_fmt = self._io.read_u1()
        self.pdu_spec = self._io.read_u1()
        self.zero_1 = self._io.read_u1()
        self.rate_limit_ms = self._io.read_u2le()


    def _fetch_instances(self):
        pass

    @property
    def pgn_key(self):
        """16-bit PGN key encoded in this filter entry.
        Matches pgn_key in rbus_frame.ksy for cross-referencing.
        """
        if hasattr(self, '_m_pgn_key'):
            return self._m_pgn_key

        self._m_pgn_key = self.pdu_fmt << 8 | self.pdu_spec
        return getattr(self, '_m_pgn_key', None)


