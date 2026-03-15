"""
BreakGuard — Forces healthy breaks every 45 minutes of active computer use.

Main entry point: orchestrates the timer, idle detection, meeting detection,
break screen, and system tray icon.
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time

from break_timer import BreakTimer
from idle_detector import IdleDetector
from meeting_detector import is_in_meeting
from floating_widget import FloatingWidget
from tray_icon import TrayIcon

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("breakguard")

# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# App class
# ---------------------------------------------------------------------------
class BreakGuardApp:
    """Main application controller."""

    def __init__(self):
        self.config = load_config()
        self.idle_detector = IdleDetector()
        self.timer = BreakTimer(
            work_interval_seconds=self.config["work_interval_minutes"] * 60,
            meeting_delay_seconds=self.config["meeting_delay_minutes"] * 60,
        )
        self.check_interval = self.config["check_interval_seconds"]
        self.idle_threshold = self.config["idle_timeout_minutes"] * 60
        self.break_duration = self.config["break_duration_minutes"] * 60
        self.exercises = self.config["exercises"]

        self._running = True
        self._paused = False
        self._in_break = False
        self._monitor_thread = None
        self._widget = None

    # -- Status for tray icon --
    def get_status(self) -> str:
        if self._in_break:
            return "On break..."
        if self._paused:
            return "Paused"
        remaining = self.timer.get_remaining_minutes()
        return f"Next break in {remaining:.0f} min"

    # -- Tray callbacks --
    def toggle_pause(self):
        self._paused = not self._paused
        state = "paused" if self._paused else "resumed"
        logger.info(f"Timer {state}")

    def skip_to_break(self):
        if not self._in_break:
            logger.info("Manual break requested")
            self._trigger_break()

    def quit_app(self):
        logger.info("Shutting down BreakGuard")
        self._running = False
        try:
            if self._widget:
                self._widget.stop()
        except Exception:
            pass
        # Force exit to ensure no orphan processes
        os._exit(0)

    # -- Widget helpers --
    def _get_remaining_seconds(self) -> float:
        return self.timer.get_remaining_minutes() * 60

    def _is_paused(self) -> bool:
        return self._paused

    def _is_on_break(self) -> bool:
        return self._in_break

    @staticmethod
    def _find_python() -> str:
        """Find the system Python executable when running as a frozen exe."""
        import shutil
        # Try pythonw first (no console window), then python
        for name in ["pythonw", "python"]:
            path = shutil.which(name)
            if path:
                return path
        # Fallback to known location
        return r"C:\Users\user\AppData\Local\Programs\Python\Python313\pythonw.exe"

    # -- Core loop --
    def _monitor_loop(self):
        """Background thread: checks idle/meeting status and triggers breaks."""
        logger.info("Work timer started")

        while self._running:
            time.sleep(self.check_interval)

            if self._paused or self._in_break:
                continue

            is_idle = self.idle_detector.is_idle(self.idle_threshold)
            self.timer.tick(is_idle, self.check_interval)

            # Update tray tooltip
            if hasattr(self, "tray"):
                remaining = self.timer.get_remaining_minutes()
                self.tray.update_title(f"BreakGuard — {remaining:.0f} min to break")

            if self.timer.is_break_due():
                # Check meeting before interrupting
                if is_in_meeting():
                    self.timer.delay_for_meeting()
                    continue

                self._trigger_break()

    def _trigger_break(self):
        """Launch break screen as a separate process."""
        self._in_break = True
        logger.info("Break triggered — locking screen")

        password = self.config.get("emergency_password", "exit")
        # When running as exe, look for break_screen.py next to the exe
        # When running as script, look next to main.py
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        break_script = os.path.join(base_dir, "break_screen.py")

        def run_break():
            try:
                # Find Python interpreter — sys.executable is the exe when frozen
                if getattr(sys, 'frozen', False):
                    python_exe = self._find_python()
                else:
                    python_exe = sys.executable

                logger.info(f"Launching break screen: {python_exe} {break_script}")
                proc = subprocess.run(
                    [python_exe, break_script, str(self.break_duration), password],
                    timeout=self.break_duration + 60,
                )
            except Exception as e:
                logger.error(f"Break screen error: {e}")
            finally:
                self._on_break_complete()

        t = threading.Thread(target=run_break, daemon=True)
        t.start()

    def _on_break_complete(self):
        """Called when the break screen closes."""
        self._in_break = False
        self.timer.reset()
        logger.info("Break complete — work timer restarted")

    # -- Entry point --
    def run(self):
        """Start BreakGuard."""
        logger.info("BreakGuard starting")

        # Start background monitor thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self._monitor_thread.start()

        # Start floating timer widget in its own thread
        self._widget = FloatingWidget(
            get_remaining_seconds=self._get_remaining_seconds,
            get_active_minutes=self.timer.get_active_minutes,
            is_paused=self._is_paused,
            is_on_break=self._is_on_break,
            on_take_break=self.skip_to_break,
        )
        widget_thread = threading.Thread(target=self._widget.show, daemon=True)
        widget_thread.start()

        # Run tray icon on the main thread (blocks until quit)
        self.tray = TrayIcon(
            get_status=self.get_status,
            on_pause_resume=self.toggle_pause,
            on_skip_break=self.skip_to_break,
            on_quit=self.quit_app,
        )
        self.tray.run()

        # After tray exits, clean up
        self._running = False
        logger.info("BreakGuard stopped")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = BreakGuardApp()
    app.run()
