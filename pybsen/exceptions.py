"""Custom exception hierarchy for pybsen library errors."""


class BsenError(Exception):
    """Base exception for all pybsen library errors."""


class BsenConnectionError(BsenError):
    """BLE connection failure (scan, connect, or disconnect errors)."""


class BsenProtocolError(BsenError):
    """Frame parsing failure or unexpected protocol state."""


class BsenTimeoutError(BsenConnectionError):
    """Connection or initialization timeout."""
