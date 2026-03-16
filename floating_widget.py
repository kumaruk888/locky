"""
Floating timer widget — shows countdown to next break with a
'Take Break Now' button.
"""

import ctypes
import tkinter as tk

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000


class FloatingWidget:
    """Small always-on-top floating timer with Take Break button."""

    def __init__(
        self,
        get_remaining_seconds,
        is_on_break,
        is_paused,
        get_break_remaining,
        on_take_break,
        on_quit,
    ):
        self._get_remaining = get_remaining_seconds
        self._is_on_break = is_on_break
        self._is_paused = is_paused
        self._get_break_remaining = get_break_remaining
        self._on_take_break = on_take_break
        self._on_quit = on_quit

        # Drag state
        self._drag_x = 0
        self._drag_y = 0

    def show(self):
        """Build and run the widget. Blocks (tkinter mainloop)."""
        self.root = tk.Tk()
        self.root.title("BreakGuard Timer")
        self.root.overrideredirect(True)
        self.root.configure(bg="#1a1a2e")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.9)

        # Position top-right
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"+{sw - 220}+10")

        self._build_ui()

        self.root.update_idletasks()

        # Hide from taskbar
        hwnd = self.root.winfo_id()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        # Dragging
        for w in [self.root, self.container, self.timer_label, self.status_label]:
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        self._update()
        self.root.mainloop()

    def _build_ui(self):
        # Main container with border
        self.container = tk.Frame(
            self.root, bg="#1a1a2e", highlightbackground="#16c79a",
            highlightthickness=2, padx=10, pady=8,
        )
        self.container.pack(fill="both", expand=True)

        # Timer display
        self.timer_label = tk.Label(
            self.container, text="--:--", font=("Consolas", 22, "bold"),
            fg="#16c79a", bg="#1a1a2e",
        )
        self.timer_label.pack(pady=(2, 2))

        # Status label
        self.status_label = tk.Label(
            self.container, text="Working...", font=("Segoe UI", 9),
            fg="#888888", bg="#1a1a2e",
        )
        self.status_label.pack(pady=(0, 5))

        # Take Break button
        self.break_btn = tk.Button(
            self.container, text="Take Break", font=("Segoe UI", 9, "bold"),
            fg="#1a1a2e", bg="#e94560", activebackground="#c73850",
            activeforeground="#1a1a2e", relief="flat", padx=12, pady=2,
            cursor="hand2", command=self._on_take_break,
        )
        self.break_btn.pack(pady=(0, 2))


    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _update(self):
        try:
            if self._is_on_break():
                break_rem = self._get_break_remaining()
                if break_rem > 0:
                    mins, secs = divmod(int(break_rem), 60)
                    self.timer_label.config(
                        text=f"{mins:02d}:{secs:02d}",
                        fg="#e94560",
                    )
                    self.status_label.config(text="On break — screen locked")
                else:
                    self.timer_label.config(text="Break!", fg="#e94560")
                    self.status_label.config(text="Waiting for you to return...")
                self.container.config(highlightbackground="#e94560")
                self.break_btn.config(state="disabled")
            elif self._is_paused():
                remaining = self._get_remaining()
                mins, secs = divmod(int(remaining), 60)
                self.timer_label.config(text=f"{mins:02d}:{secs:02d}", fg="#ffbd69")
                self.status_label.config(text="Paused — screen locked")
                self.container.config(highlightbackground="#ffbd69")
                self.break_btn.config(state="disabled")
            else:
                remaining = self._get_remaining()
                mins, secs = divmod(int(remaining), 60)
                self.timer_label.config(text=f"{mins:02d}:{secs:02d}")
                self.break_btn.config(state="normal")

                if remaining > 300:
                    color = "#16c79a"  # Green
                    self.status_label.config(text="Working...")
                elif remaining > 120:
                    color = "#ffbd69"  # Orange
                    self.status_label.config(text="Break coming soon")
                else:
                    color = "#e94560"  # Red
                    self.status_label.config(text="Break very soon!")

                self.timer_label.config(fg=color)
                self.container.config(highlightbackground=color)

        except Exception:
            pass

        self.root.after(500, self._update)

    def stop(self):
        try:
            self.root.destroy()
        except Exception:
            pass
