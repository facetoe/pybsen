"""ADB controller for REDARC Smart Battery Monitor app automation.

Wraps subprocess calls to the `adb` binary.

App constants:
    Package  : au.com.redarc.redvision.tvms.user
    Activity : com.redarc.redvision_flutter.MainActivity

UI facts (Flutter accessibility — content-desc, not text):
    SOC card   : "{soc}%\\n{time_remaining_str}"
    Status card: "Battery Status\\n{abs_current}A\\n{voltage}V\\n{temp}ºC"
    Note: degree char is U+00BA (MASCULINE ORDINAL INDICATOR), not U+00B0

Lock screen support:
    No lock / swipe-to-unlock : works without configuration.
    PIN lock                  : pass pin=<digits> to AdbController.__init__.
    Pattern / biometric       : not supported via ADB — device must be
                                configured with no lock, swipe, or PIN.
"""

import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

APP_PACKAGE = "au.com.redarc.redvision.tvms.user"
APP_ACTIVITY = "com.redarc.redvision_flutter.MainActivity"

_SOC_RE = re.compile(r"^(\d+)%\n(.+)$", re.MULTILINE)
# Matches lock-screen indicators across Android versions:
#   showing=          KeyguardServiceDelegate (Android 10+)
#   mIsShowing=       KeyguardStateMonitor (Android 10+)
#   mShowingLockscreen=  older AOSP
#   isStatusBarKeyguard= some OEM variants
_LOCK_RE = re.compile(r"(?:mShowingLockscreen|isStatusBarKeyguard|mIsShowing|showing)=(true|false)")
# U+00BA (º) and U+00B0 (°) both matched for robustness
_STATUS_RE = re.compile(
    r"^Battery Status\n([+-]?\d+\.?\d*)A\n(\d+\.?\d*)V\n([+-]?\d+\.?\d*)[º°]C$",
    re.MULTILINE,
)


class AdbError(Exception):
    """Raised when an adb command fails or returns unexpected output."""


class AdbController:
    """Synchronous ADB controller for the REDARC BSEN app.

    All methods block until the adb command completes.  The capture
    orchestrator calls these from a thread executor to avoid blocking
    the asyncio event loop.
    """

    def __init__(
        self,
        serial: str | None = None,
        timeout: float = 15.0,
        pin: str | None = None,
    ) -> None:
        """
        Args:
            serial:  ADB device serial (pass None to use the only connected device).
            timeout: Default subprocess timeout in seconds.
            pin:     Numeric PIN to enter after dismissing the lock screen.
                     Leave None for no-lock or swipe-to-unlock devices.
        """
        self._serial = serial
        self._timeout = timeout
        self._pin = pin

    # ── Public API ─────────────────────────────────────────────────────────

    def wake_screen(self) -> None:
        """Wake the display and dismiss the lock screen.

        Sends KEYCODE_WAKEUP, then a swipe gesture to dismiss the lock screen
        or bring the PIN entry field into focus.  If a PIN was provided at
        construction time it is entered and confirmed with KEYCODE_ENTER.
        """
        self._adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
        time.sleep(0.5)

        if not self._is_screen_locked():
            return

        # Swipe up to dismiss swipe-lock or reveal PIN entry field
        self._adb("shell", "input", "swipe", "540", "1800", "540", "900", "300")
        time.sleep(0.8)

        if self._pin and self._is_screen_locked():
            self._adb("shell", "input", "text", self._pin)
            time.sleep(0.3)
            self._adb("shell", "input", "keyevent", "KEYCODE_ENTER")
            time.sleep(0.5)

    def force_stop(self) -> None:
        """Force-stop the REDARC app."""
        self._adb("shell", "am", "force-stop", APP_PACKAGE)

    def launch_app(self) -> None:
        """Start the REDARC app main activity."""
        self._adb(
            "shell", "am", "start", "-n",
            f"{APP_PACKAGE}/{APP_ACTIVITY}",
        )

    def is_app_foreground(self) -> bool:
        """Return True if the REDARC app is the current foreground window."""
        result = self._adb_output("shell", "dumpsys", "window", "windows")
        return APP_PACKAGE in result

    def screenshot(self, path: Path) -> None:
        """Capture screenshot and save to path (PNG)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        png_bytes = self._adb_bytes("exec-out", "screencap", "-p")
        path.write_bytes(png_bytes)

    def uiautomator_dump(self) -> bytes:
        """Run uiautomator dump and return the XML bytes."""
        self._adb("shell", "uiautomator", "dump", "/sdcard/_bsen_uidump.xml")
        return self._adb_bytes("exec-out", "cat", "/sdcard/_bsen_uidump.xml")

    def wait_for_app_values(self, timeout: float = 30.0, poll_interval: float = 2.0) -> dict[str, Any]:
        """Poll uiautomator until the app shows live battery values.

        Returns an app_values dict once both the SOC card and Status card
        content-desc nodes are present and parseable.

        Raises:
            TimeoutError: if values do not appear within `timeout` seconds.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                xml_bytes = self.uiautomator_dump()
                values = self.parse_content_desc(xml_bytes)
                if _is_complete(values):
                    return values
            except Exception:
                pass
            time.sleep(poll_interval)
        raise TimeoutError(f"App values did not appear within {timeout:.0f}s")

    @staticmethod
    def parse_content_desc(xml_bytes: bytes) -> dict[str, Any]:
        """Parse uiautomator XML and extract app_values from content-desc attributes.

        Returns a dict with keys: soc_pct, time_remaining_str, abs_current_a,
        voltage_v, temp_c.  Missing fields are omitted (not None).
        """
        root = ET.fromstring(xml_bytes)
        result: dict[str, Any] = {}
        for node in root.iter("node"):
            cd = node.get("content-desc", "")
            if not cd:
                continue

            m = _SOC_RE.search(cd)
            if m:
                result["soc_pct"] = int(m.group(1))
                result["time_remaining_str"] = m.group(2).strip()
                continue

            m = _STATUS_RE.search(cd)
            if m:
                result["abs_current_a"] = float(m.group(1))
                result["voltage_v"] = float(m.group(2))
                result["temp_c"] = float(m.group(3))
        return result

    # ── Internal helpers ───────────────────────────────────────────────────

    def _is_screen_locked(self) -> bool:
        """Return True if the keyguard (lock screen) is currently showing.

        Tries ``dumpsys window policy`` first (reliable on Android 8+), then
        falls back to ``dumpsys deviceidle`` (available since Android M / 6.0).
        Returns False if neither source can determine the state.
        """
        output = self._adb_output("shell", "dumpsys", "window", "policy")
        m = _LOCK_RE.search(output)
        if m:
            return m.group(1) == "true"
        # Fallback for devices where window policy output format differs
        output = self._adb_output("shell", "dumpsys", "deviceidle")
        return "mScreenLocked=true" in output

    def _base_cmd(self) -> list[str]:
        cmd = ["adb"]
        if self._serial:
            cmd += ["-s", self._serial]
        return cmd

    def _adb(self, *args: str) -> None:
        cmd = self._base_cmd() + list(args)
        result = subprocess.run(cmd, capture_output=True, timeout=self._timeout)
        if result.returncode != 0:
            raise AdbError(
                f"adb {' '.join(args)} failed (rc={result.returncode}): "
                f"{result.stderr.decode(errors='replace').strip()}"
            )

    def _adb_output(self, *args: str) -> str:
        cmd = self._base_cmd() + list(args)
        result = subprocess.run(cmd, capture_output=True, timeout=self._timeout)
        return result.stdout.decode(errors="replace")

    def _adb_bytes(self, *args: str) -> bytes:
        cmd = self._base_cmd() + list(args)
        result = subprocess.run(cmd, capture_output=True, timeout=self._timeout)
        if result.returncode != 0:
            raise AdbError(
                f"adb {' '.join(args)} failed (rc={result.returncode})"
            )
        return result.stdout


def _is_complete(values: dict[str, Any]) -> bool:
    """Return True if all expected app_values keys are present."""
    return all(k in values for k in ("soc_pct", "abs_current_a", "voltage_v", "temp_c"))
