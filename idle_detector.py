"""
Idle detection using Windows GetLastInputInfo API.
No keyboard/mouse hooks needed — just one lightweight API call.
"""

import ctypes
import ctypes.wintypes


class IdleDetector:
    """Detects user idle time using Windows native API."""

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.UINT),
            ("dwTime", ctypes.wintypes.DWORD),
        ]

    def __init__(self):
        self._lii = self.LASTINPUTINFO()
        self._lii.cbSize = ctypes.sizeof(self.LASTINPUTINFO)

    def get_idle_seconds(self) -> float:
        """Return how many seconds the user has been idle."""
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(self._lii))
        tick_count = ctypes.windll.kernel32.GetTickCount()
        idle_ms = tick_count - self._lii.dwTime
        return idle_ms / 1000.0

    def is_idle(self, threshold_seconds: float) -> bool:
        """Return True if user has been idle longer than threshold."""
        return self.get_idle_seconds() >= threshold_seconds
