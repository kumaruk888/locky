"""
Detects if the user is currently in an active online meeting/call.

Detection method: scans window titles for keywords that indicate
an active call is happening (not just the app being open).
"""

import logging

import win32gui

logger = logging.getLogger("breakguard")

# Window title keywords that indicate an ACTIVE call/meeting
# These should only match when a call is in progress, not just app being open
ACTIVE_CALL_KEYWORDS = [
    "zoom meeting",
    "zoom webinar",
    "meeting | microsoft teams",
    "call | microsoft teams",
    " | call",
    "screen sharing",
    "meet.google.com",
    "webex meeting",
]


def _get_all_window_titles() -> list[str]:
    """Collect titles of all visible windows."""
    titles = []

    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                titles.append(title)

    win32gui.EnumWindows(enum_callback, None)
    return titles


def is_in_meeting() -> bool:
    """Return True if the user appears to be in an active call/meeting."""
    titles = _get_all_window_titles()
    for title in titles:
        title_lower = title.lower()
        for keyword in ACTIVE_CALL_KEYWORDS:
            if keyword in title_lower:
                logger.info(f"Active meeting detected: '{title}'")
                return True
    return False
