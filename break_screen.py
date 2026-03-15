"""
Fullscreen break overlay that locks the user out for the break duration.

Features:
- Fullscreen, always-on-top, no close button
- Countdown timer
- Random exercise suggestions
- Intercepts Alt+F4 and other close attempts
- Re-focuses itself if user tries to switch away
"""

import logging
import random
import threading
import tkinter as tk
from typing import Callable

logger = logging.getLogger("breakguard")


class BreakScreen:
    """Creates and manages the fullscreen break overlay."""

    def __init__(
        self,
        duration_seconds: int,
        exercises: list[str],
        on_break_complete: Callable[[], None],
        emergency_password: str = "exit",
    ):
        self.duration_seconds = duration_seconds
        self.exercises = exercises
        self.on_break_complete = on_break_complete
        self.emergency_password = emergency_password
        self.remaining = duration_seconds
        self.root = None
        self._closed = False
        self._refocus_job = None

    def show(self):
        """Show the break screen. Must be called from the main thread."""
        self.root = tk.Tk()
        self.root.title("BreakGuard - Time for a Break!")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1a1a2e")
        self.root.overrideredirect(True)

        # Block close attempts
        self.root.protocol("WM_DELETE_WINDOW", self._block_close)
        self.root.bind("<Alt-F4>", self._block_close)
        self.root.bind("<Escape>", self._block_close)
        self.root.bind("<Alt-Tab>", self._block_close)

        # Pick 3 random exercises
        selected_exercises = random.sample(
            self.exercises, min(3, len(self.exercises))
        )

        # Main container
        frame = tk.Frame(self.root, bg="#1a1a2e")
        frame.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        tk.Label(
            frame,
            text="Time for a Break!",
            font=("Segoe UI", 48, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
        ).pack(pady=(0, 20))

        # Subtitle
        tk.Label(
            frame,
            text="You've been working for 45 minutes.\nStand up and move!",
            font=("Segoe UI", 18),
            fg="#eaeaea",
            bg="#1a1a2e",
            justify="center",
        ).pack(pady=(0, 40))

        # Exercise suggestions
        tk.Label(
            frame,
            text="Try one of these:",
            font=("Segoe UI", 16, "bold"),
            fg="#0f3460",
            bg="#1a1a2e",
        ).pack(pady=(0, 10))

        for exercise in selected_exercises:
            tk.Label(
                frame,
                text=f"  \u2713  {exercise}",
                font=("Segoe UI", 16),
                fg="#16c79a",
                bg="#1a1a2e",
                anchor="w",
            ).pack(pady=3)

        # Countdown timer
        self.timer_label = tk.Label(
            frame,
            text="",
            font=("Segoe UI", 36, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
        )
        self.timer_label.pack(pady=(50, 10))

        # Progress bar
        self.progress_canvas = tk.Canvas(
            frame, width=400, height=12, bg="#16213e", highlightthickness=0
        )
        self.progress_canvas.pack(pady=(0, 20))

        # Emergency exit section
        emergency_frame = tk.Frame(frame, bg="#1a1a2e")
        emergency_frame.pack(pady=(30, 0))

        self.emergency_btn = tk.Button(
            emergency_frame,
            text="Emergency Exit",
            font=("Segoe UI", 10),
            fg="#888888",
            bg="#2a2a3e",
            activebackground="#3a3a4e",
            activeforeground="#cccccc",
            relief="flat",
            padx=16,
            pady=4,
            cursor="hand2",
            command=self._show_password_prompt,
        )
        self.emergency_btn.pack()

        # Password prompt (hidden until emergency button clicked)
        self.password_frame = tk.Frame(frame, bg="#1a1a2e")

        self.password_label = tk.Label(
            self.password_frame,
            text="Type password to exit:",
            font=("Segoe UI", 10),
            fg="#888888",
            bg="#1a1a2e",
        )
        self.password_label.pack(pady=(5, 2))

        self.password_entry = tk.Entry(
            self.password_frame,
            font=("Consolas", 12),
            show="*",
            bg="#16213e",
            fg="#eaeaea",
            insertbackground="#eaeaea",
            relief="flat",
            width=15,
            justify="center",
        )
        self.password_entry.pack(pady=(0, 5))
        self.password_entry.bind("<Return>", self._check_password)

        self.password_error = tk.Label(
            self.password_frame,
            text="",
            font=("Segoe UI", 9),
            fg="#e94560",
            bg="#1a1a2e",
        )
        self.password_error.pack()

        # Hint
        tk.Label(
            frame,
            text="Screen will unlock automatically when the break ends",
            font=("Segoe UI", 11),
            fg="#555577",
            bg="#1a1a2e",
        ).pack(pady=(10, 0))

        # Start countdown and refocus loop
        self._update_timer()
        self._refocus_loop()

        self.root.mainloop()

    def _block_close(self, event=None):
        """Prevent closing the break screen."""
        return "break"

    def _show_password_prompt(self):
        """Show the password entry field."""
        self.emergency_btn.pack_forget()
        self.password_frame.pack(pady=(10, 0))
        self.password_entry.focus_set()

    def _check_password(self, event=None):
        """Validate the emergency password."""
        entered = self.password_entry.get().strip()
        if entered == self.emergency_password:
            logger.info("Emergency exit — password accepted")
            self._close()
        else:
            self.password_error.config(text="Wrong password")
            self.password_entry.delete(0, tk.END)
            # Clear error after 2 seconds
            self.root.after(2000, lambda: self.password_error.config(text=""))

    def _refocus_loop(self):
        """Periodically bring the window back to front."""
        if self._closed or self.root is None:
            return
        try:
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.root.lift()
            self._refocus_job = self.root.after(500, self._refocus_loop)
        except tk.TclError:
            pass

    def _update_timer(self):
        """Update the countdown display."""
        if self._closed or self.root is None:
            return

        minutes, seconds = divmod(self.remaining, 60)
        self.timer_label.config(text=f"Break ends in: {minutes:02d}:{seconds:02d}")

        # Update progress bar
        progress = 1.0 - (self.remaining / self.duration_seconds)
        self.progress_canvas.delete("all")
        self.progress_canvas.create_rectangle(
            0, 0, 400, 12, fill="#16213e", outline=""
        )
        self.progress_canvas.create_rectangle(
            0, 0, int(400 * progress), 12, fill="#16c79a", outline=""
        )

        if self.remaining <= 0:
            self._close()
            return

        self.remaining -= 1
        self.root.after(1000, self._update_timer)

    def _close(self):
        """Close the break screen and notify completion."""
        if self._closed:
            return
        self._closed = True
        logger.info("Break complete — unlocking screen")
        try:
            if self._refocus_job:
                self.root.after_cancel(self._refocus_job)
            self.root.destroy()
        except tk.TclError:
            pass
        self.on_break_complete()
