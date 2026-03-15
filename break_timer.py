"""
Core timer logic that tracks active work time and triggers breaks.
"""

import logging
import time

logger = logging.getLogger("breakguard")


class BreakTimer:
    """Tracks cumulative active work time and determines when a break is due."""

    def __init__(self, work_interval_seconds: int, meeting_delay_seconds: int):
        self.work_interval = work_interval_seconds
        self.meeting_delay = meeting_delay_seconds
        self.active_seconds = 0.0
        self._last_tick = time.time()
        self._paused = False
        self._meeting_delayed = False

    def tick(self, is_idle: bool, check_interval: float):
        """
        Called periodically. Accumulates active time if user is not idle.
        Returns nothing — use is_break_due() to check.
        """
        now = time.time()

        if is_idle:
            if not self._paused:
                logger.debug("User idle — timer paused")
                self._paused = True
        else:
            if self._paused:
                logger.debug("User active — timer resumed")
                self._paused = False
            self.active_seconds += check_interval

        self._last_tick = now

    def is_break_due(self) -> bool:
        """Return True if enough active time has passed for a break."""
        threshold = self.work_interval
        if self._meeting_delayed:
            threshold += self.meeting_delay
        return self.active_seconds >= threshold

    def delay_for_meeting(self):
        """Extend the threshold because user is in a meeting."""
        if not self._meeting_delayed:
            logger.info(
                f"Meeting detected — delaying break by {self.meeting_delay // 60} minutes"
            )
            self._meeting_delayed = True

    def reset(self):
        """Reset the timer after a break is taken."""
        self.active_seconds = 0.0
        self._paused = False
        self._meeting_delayed = False
        self._last_tick = time.time()
        logger.info("Work timer reset")

    def get_remaining_minutes(self) -> float:
        """Return approximate minutes until next break."""
        threshold = self.work_interval
        if self._meeting_delayed:
            threshold += self.meeting_delay
        remaining = max(0, threshold - self.active_seconds)
        return remaining / 60.0

    def get_active_minutes(self) -> float:
        """Return minutes of active work since last break."""
        return self.active_seconds / 60.0
