"""
BreakGuard — Forces healthy breaks by locking the workstation.

Dashboard → Floating Timer → Windows Lock Screen → Re-lock if needed.

Break types:
- "Take Break" button or scheduled break: enforced lock for full break
  duration, re-locks if user logs in early, resets work timer after.
- External lock (Win+L, etc.): pauses work timer, resumes on unlock.
"""

import ctypes
import ctypes.wintypes
import logging
import threading
import time
import tkinter as tk

from floating_widget import FloatingWidget

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("breakguard")

# ---------------------------------------------------------------------------
# Lock / unlock detection helpers
# ---------------------------------------------------------------------------
DESKTOP_SWITCHDESKTOP = 0x0100


def lock_workstation():
    """Lock the Windows workstation (same as Win+L)."""
    ctypes.windll.user32.LockWorkStation()


def is_workstation_locked() -> bool:
    """Check if the workstation is currently locked."""
    hDesktop = ctypes.windll.user32.OpenDesktopW(
        "Default", 0, False, DESKTOP_SWITCHDESKTOP
    )
    if hDesktop:
        result = ctypes.windll.user32.SwitchDesktop(hDesktop)
        ctypes.windll.user32.CloseDesktop(hDesktop)
        return not result
    return True


# ---------------------------------------------------------------------------
# Dashboard — initial setup screen
# ---------------------------------------------------------------------------
class Dashboard:
    """Startup screen where user sets screen time and break time."""

    def __init__(self):
        self.result = None

    def show(self):
        self.root = tk.Tk()
        self.root.title("BreakGuard")
        self.root.configure(bg="#1a1a2e")
        self.root.resizable(False, False)

        w, h = 380, 320
        sx = self.root.winfo_screenwidth() // 2 - w // 2
        sy = self.root.winfo_screenheight() // 2 - h // 2
        self.root.geometry(f"{w}x{h}+{sx}+{sy}")

        tk.Label(
            self.root, text="BreakGuard", font=("Segoe UI", 24, "bold"),
            fg="#e94560", bg="#1a1a2e",
        ).pack(pady=(25, 5))

        tk.Label(
            self.root, text="Set your work and break durations",
            font=("Segoe UI", 11), fg="#888888", bg="#1a1a2e",
        ).pack(pady=(0, 25))

        input_frame = tk.Frame(self.root, bg="#1a1a2e")
        input_frame.pack(pady=5)

        tk.Label(
            input_frame, text="Screen time (minutes):",
            font=("Segoe UI", 12), fg="#eaeaea", bg="#1a1a2e", anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(10, 15), pady=8)

        self.screen_time_var = tk.StringVar(value="45")
        screen_entry = tk.Entry(
            input_frame, textvariable=self.screen_time_var,
            font=("Consolas", 14), bg="#16213e", fg="#eaeaea",
            insertbackground="#eaeaea", relief="flat", width=8, justify="center",
        )
        screen_entry.grid(row=0, column=1, padx=(0, 10), pady=8)

        tk.Label(
            input_frame, text="Break time (minutes):",
            font=("Segoe UI", 12), fg="#eaeaea", bg="#1a1a2e", anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=(10, 15), pady=8)

        self.break_time_var = tk.StringVar(value="5")
        break_entry = tk.Entry(
            input_frame, textvariable=self.break_time_var,
            font=("Consolas", 14), bg="#16213e", fg="#eaeaea",
            insertbackground="#eaeaea", relief="flat", width=8, justify="center",
        )
        break_entry.grid(row=1, column=1, padx=(0, 10), pady=8)

        self.start_btn = tk.Button(
            self.root, text="Start", font=("Segoe UI", 14, "bold"),
            fg="#1a1a2e", bg="#16c79a", activebackground="#13a87e",
            activeforeground="#1a1a2e", relief="flat", padx=40, pady=8,
            cursor="hand2", command=self._on_start,
        )
        self.start_btn.pack(pady=(25, 0))

        self.error_label = tk.Label(
            self.root, text="", font=("Segoe UI", 9),
            fg="#e94560", bg="#1a1a2e",
        )
        self.error_label.pack(pady=(8, 0))

        screen_entry.focus_set()
        self.root.mainloop()
        return self.result

    def _on_start(self):
        try:
            screen_min = float(self.screen_time_var.get().strip())
            if screen_min <= 0:
                raise ValueError
            break_str = self.break_time_var.get().strip()
            if break_str == "":
                # Blank break time → 15 seconds (for testing)
                break_min = 0.25
            else:
                break_min = float(break_str)
                if break_min <= 0:
                    raise ValueError
            self.result = (screen_min, break_min)
            self.root.destroy()
        except ValueError:
            self.error_label.config(text="Please enter valid positive numbers")


# ---------------------------------------------------------------------------
# App controller
# ---------------------------------------------------------------------------
class BreakGuardApp:
    """Main app: manages timer, locking, and re-locking."""

    def __init__(self, screen_seconds: float, break_seconds: float):
        self.screen_seconds = screen_seconds
        self.break_seconds = break_seconds
        self.remaining = screen_seconds
        self._running = True
        self._in_break = False          # True during enforced break
        self._externally_locked = False  # True when user locked via Win+L etc.
        self._break_remaining = 0.0
        self._lock = threading.Lock()

    def get_remaining_seconds(self) -> float:
        return max(0, self.remaining)

    def is_on_break(self) -> bool:
        return self._in_break

    def is_paused(self) -> bool:
        return self._externally_locked

    def get_break_remaining(self) -> float:
        return max(0, self._break_remaining)

    def take_break_now(self):
        """User clicked 'Take Break' — enforced break with re-locking."""
        if self._in_break:
            return
        logger.info("User-initiated break requested")
        self._start_enforced_break()

    def _start_enforced_break(self):
        """Lock workstation and enforce full break duration."""
        with self._lock:
            if self._in_break:
                return
            self._in_break = True
            self._externally_locked = False
            self._break_remaining = self.break_seconds

        logger.info(f"Enforced break started — {self.break_seconds:.0f}s")
        lock_workstation()

        t = threading.Thread(target=self._enforced_break_loop, daemon=True)
        t.start()

    def _enforced_break_loop(self):
        """Monitor during enforced break: count down and re-lock if user logs in early."""
        poll_interval = 2

        while self._in_break and self._running:
            time.sleep(poll_interval)

            if not self._in_break:
                break

            self._break_remaining -= poll_interval

            if self._break_remaining <= 0:
                # Break time is over
                logger.info("Break time over — waiting for user to log back in")
                self._wait_for_login()
                self._end_enforced_break()
                break

            if not is_workstation_locked():
                # User logged in too early — re-lock!
                logger.info(
                    f"User logged in early — re-locking "
                    f"({self._break_remaining:.0f}s remaining)"
                )
                time.sleep(1)
                lock_workstation()

    def _wait_for_login(self):
        """Wait until the user actually logs back in."""
        while self._running:
            if not is_workstation_locked():
                return
            time.sleep(1)

    def _end_enforced_break(self):
        """Reset work timer after enforced break ends."""
        with self._lock:
            self._in_break = False
            self.remaining = self.screen_seconds
            self._break_remaining = 0
        logger.info(f"Work timer restarted — {self.screen_seconds:.0f}s")

    def timer_loop(self):
        """Background thread: counts down work timer and detects external locks."""
        was_locked = False

        while self._running:
            time.sleep(1)

            # Don't do anything during enforced breaks
            if self._in_break:
                was_locked = False
                continue

            locked = is_workstation_locked()

            if locked and not was_locked:
                # User just locked externally (Win+L, etc.)
                self._externally_locked = True
                logger.info("External lock detected — pausing work timer")

            if not locked and was_locked and self._externally_locked:
                # User unlocked after an external lock — resume timer
                self._externally_locked = False
                logger.info(
                    f"External unlock — resuming work timer "
                    f"({self.remaining:.0f}s remaining)"
                )

            was_locked = locked

            # Only count down when not locked and not on break
            if not locked and not self._externally_locked and not self._in_break:
                self.remaining -= 1

                if self.remaining <= 0:
                    self._start_enforced_break()

    def quit(self):
        logger.info("Shutting down BreakGuard")
        self._running = False
        import os
        os._exit(0)

    def run(self):
        """Start the app with floating widget."""
        logger.info(
            f"BreakGuard started — screen: {self.screen_seconds:.0f}s, "
            f"break: {self.break_seconds:.0f}s"
        )

        timer_thread = threading.Thread(target=self.timer_loop, daemon=True)
        timer_thread.start()

        self.widget = FloatingWidget(
            get_remaining_seconds=self.get_remaining_seconds,
            is_on_break=self.is_on_break,
            is_paused=self.is_paused,
            get_break_remaining=self.get_break_remaining,
            on_take_break=self.take_break_now,
            on_quit=self.quit,
        )
        self.widget.show()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    dashboard = Dashboard()
    result = dashboard.show()

    if result is None:
        exit(0)

    screen_minutes, break_minutes = result
    app = BreakGuardApp(
        screen_seconds=screen_minutes * 60,
        break_seconds=break_minutes * 60,
    )
    app.run()
