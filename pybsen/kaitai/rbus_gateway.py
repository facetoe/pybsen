# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class RbusGateway(KaitaiStruct):
    """CHAR_2015_8003 gateway channel protocol.
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
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(RbusGateway, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.key_hi = self._io.read_u1()
        self.key_lo = self._io.read_u1()
        self.data_len = self._io.read_u1()
        self.data = self._io.read_bytes(self.data_len)


    def _fetch_instances(self):
        pass

    class ResponseFrame(KaitaiStruct):
        """Device → host response on CHAR_2015_8003 notify.
        Format: [0x80, key_lo, ...response_data...]
        The 0x80 prefix byte is always present on response frames.
        Source: PROTOCOL.md Gateway Channel Protocol.
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(RbusGateway.ResponseFrame, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.prefix = self._io.read_bytes(1)
            if not self.prefix == b"\x80":
                raise kaitaistruct.ValidationNotEqualError(b"\x80", self.prefix, self._io, u"/types/response_frame/seq/0")
            self.key_lo = self._io.read_u1()
            self.response_data = self._io.read_bytes_full()


        def _fetch_instances(self):
            pass


    @property
    def key(self):
        """Full 16-bit command key. 0x0001=addr read, 0x0002=MTU, 0xFFFF=error."""
        if hasattr(self, '_m_key'):
            return self._m_key

        self._m_key = self.key_hi << 8 | self.key_lo
        return getattr(self, '_m_key', None)

    @property
    def response_expected(self):
        """True if bit 7 of key_hi is set, meaning device will send a response notification."""
        if hasattr(self, '_m_response_expected'):
            return self._m_response_expected

        self._m_response_expected = self.key_hi & 128 != 0
        return getattr(self, '_m_response_expected', None)


