"""
Fullscreen break overlay — runs as a separate process for reliable
multi-monitor support and proper keyboard focus.

When run directly (python break_screen.py), it shows the break screen.
Main app launches this as a subprocess.
"""

import ctypes
import ctypes.wintypes
import json
import logging
import os
import random
import sys
import tkinter as tk

logger = logging.getLogger("breakguard")

HWND_TOPMOST = -1
SWP_SHOWWINDOW = 0x0040


def _get_virtual_screen() -> dict:
    user32 = ctypes.windll.user32
    return {
        "x": user32.GetSystemMetrics(76),
        "y": user32.GetSystemMetrics(77),
        "width": user32.GetSystemMetrics(78),
        "height": user32.GetSystemMetrics(79),
    }


class BreakScreenApp:
    """Fullscreen break overlay spanning all monitors."""

    def __init__(self, duration_seconds, exercises, emergency_password="exit"):
        self.duration_seconds = duration_seconds
        self.exercises = exercises
        self.emergency_password = emergency_password
        self.remaining = duration_seconds
        self._closed = False
        self._password_active = False
        self._vs = _get_virtual_screen()

    def run(self):
        """Show break screen. Blocks until break is done. Runs on main thread."""
        vs = self._vs

        self.root = tk.Tk()
        self.root.title("BreakGuard")
        self.root.overrideredirect(True)
        self.root.configure(bg="#1a1a2e")
        self.root.geometry(f"{vs['width']}x{vs['height']}+{vs['x']}+{vs['y']}")
        self.root.update_idletasks()

        # Force span all monitors via Win32
        hwnd = self.root.winfo_id()
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_TOPMOST, vs['x'], vs['y'], vs['width'], vs['height'], SWP_SHOWWINDOW
        )

        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        self._build_content()
        self.root.update_idletasks()

        # Force size again after content
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_TOPMOST, vs['x'], vs['y'], vs['width'], vs['height'], SWP_SHOWWINDOW
        )

        self._hwnd = hwnd
        self._update_timer()
        self._refocus_loop()

        self.root.mainloop()

    def _build_content(self):
        selected_exercises = random.sample(
            self.exercises, min(3, len(self.exercises))
        )

        frame = tk.Frame(self.root, bg="#1a1a2e")
        frame.place(x=960, rely=0.5, anchor="center")

        tk.Label(
            frame, text="Time for a Break!",
            font=("Segoe UI", 48, "bold"), fg="#e94560", bg="#1a1a2e",
        ).pack(pady=(0, 20))

        tk.Label(
            frame, text="You've been working hard.\nStand up and move!",
            font=("Segoe UI", 18), fg="#eaeaea", bg="#1a1a2e", justify="center",
        ).pack(pady=(0, 40))

        tk.Label(
            frame, text="Try one of these:",
            font=("Segoe UI", 16, "bold"), fg="#0f3460", bg="#1a1a2e",
        ).pack(pady=(0, 10))

        for exercise in selected_exercises:
            tk.Label(
                frame, text=f"  \u2713  {exercise}",
                font=("Segoe UI", 16), fg="#16c79a", bg="#1a1a2e", anchor="w",
            ).pack(pady=3)

        self.timer_label = tk.Label(
            frame, text="", font=("Segoe UI", 36, "bold"),
            fg="#e94560", bg="#1a1a2e",
        )
        self.timer_label.pack(pady=(50, 10))

        self.progress_canvas = tk.Canvas(
            frame, width=400, height=12, bg="#16213e", highlightthickness=0
        )
        self.progress_canvas.pack(pady=(0, 20))

        # Emergency exit
        self.emergency_btn = tk.Button(
            frame, text="Emergency Exit", font=("Segoe UI", 10),
            fg="#888888", bg="#2a2a3e", activebackground="#3a3a4e",
            activeforeground="#cccccc", relief="flat", padx=16, pady=4,
            cursor="hand2", command=self._show_password_prompt,
        )
        self.emergency_btn.pack(pady=(30, 0))

        # Password prompt (hidden)
        self.password_frame = tk.Frame(frame, bg="#1a1a2e")

        tk.Label(
            self.password_frame, text="Type password to exit:",
            font=("Segoe UI", 10), fg="#888888", bg="#1a1a2e",
        ).pack(pady=(5, 2))

        self.password_entry = tk.Entry(
            self.password_frame, font=("Consolas", 12), show="*",
            bg="#16213e", fg="#eaeaea", insertbackground="#eaeaea",
            relief="flat", width=15, justify="center",
        )
        self.password_entry.pack(pady=(0, 5))
        self.password_entry.bind("<Return>", self._check_password)

        self.password_error = tk.Label(
            self.password_frame, text="",
            font=("Segoe UI", 9), fg="#e94560", bg="#1a1a2e",
        )
        self.password_error.pack()

        tk.Label(
            frame, text="Screen will unlock automatically when the break ends",
            font=("Segoe UI", 11), fg="#555577", bg="#1a1a2e",
        ).pack(pady=(10, 0))

    def _show_password_prompt(self):
        self._password_active = True
        self.emergency_btn.pack_forget()
        self.password_frame.pack(pady=(10, 0))
        self.root.after(100, lambda: self.password_entry.focus_set())

    def _check_password(self, event=None):
        entered = self.password_entry.get().strip()
        if entered == self.emergency_password:
            self._close()
        else:
            self.password_error.config(text="Wrong password")
            self.password_entry.delete(0, tk.END)
            self.root.after(2000, lambda: self.password_error.config(text=""))

    def _refocus_loop(self):
        if self._closed:
            return
        try:
            vs = self._vs
            ctypes.windll.user32.SetWindowPos(
                self._hwnd, HWND_TOPMOST,
                vs['x'], vs['y'], vs['width'], vs['height'], SWP_SHOWWINDOW
            )

            if self._password_active:
                self.password_entry.focus_set()

            self.root.after(500, self._refocus_loop)
        except Exception:
            pass

    def _update_timer(self):
        if self._closed:
            return
        try:
            minutes, seconds = divmod(self.remaining, 60)
            self.timer_label.config(text=f"Break ends in: {minutes:02d}:{seconds:02d}")

            progress = 1.0 - (self.remaining / self.duration_seconds)
            self.progress_canvas.delete("all")
            self.progress_canvas.create_rectangle(0, 0, 400, 12, fill="#16213e", outline="")
            self.progress_canvas.create_rectangle(0, 0, int(400 * progress), 12, fill="#16c79a", outline="")

            if self.remaining <= 0:
                self._close()
                return

            self.remaining -= 1
            self.root.after(1000, self._update_timer)
        except Exception:
            pass

    def _close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.root.destroy()
        except Exception:
            pass


# When run as a subprocess, read config from command line args
if __name__ == "__main__":
    duration = int(float(sys.argv[1])) if len(sys.argv) > 1 else 300
    password = sys.argv[2] if len(sys.argv) > 2 else "exit"

    # Read exercises from config.json next to this script
    config_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "config.json")
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

    exercises = [
        "Walk around the room",
        "Stretch your arms and back",
        "Do 10 squats",
        "Drink a glass of water",
    ]
    try:
        with open(config_path) as f:
            cfg = json.load(f)
            exercises = cfg.get("exercises", exercises)
    except Exception:
        pass

    app = BreakScreenApp(duration, exercises, password)
    app.run()
