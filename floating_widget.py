"""
Small floating timer widget that sits on the desktop.

Features:
- Always on top, draggable, semi-transparent
- Shows countdown to next break as MM:SS
- Turns red when break is imminent (< 2 min)
- Click to expand/collapse
- Double-click to trigger break now
"""

import tkinter as tk
from typing import Callable


class FloatingWidget:
    """A small draggable countdown timer that floats on the desktop."""

    def __init__(
        self,
        get_remaining_seconds: Callable[[], float],
        get_active_minutes: Callable[[], float],
        is_paused: Callable[[], bool],
        is_on_break: Callable[[], bool],
        on_take_break: Callable[[], None],
    ):
        self.get_remaining_seconds = get_remaining_seconds
        self.get_active_minutes = get_active_minutes
        self.is_paused = is_paused
        self.is_on_break = is_on_break
        self.on_take_break = on_take_break

        self.root = None
        self._drag_x = 0
        self._drag_y = 0
        self._expanded = False

    def show(self):
        """Create and show the widget. Must run in its own thread."""
        self.root = tk.Tk()
        self.root.title("BreakGuard")
        self.root.overrideredirect(True)  # No title bar
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        self.root.configure(bg="#1a1a2e")

        # Position at top-right of screen
        screen_w = self.root.winfo_screenwidth()
        self.root.geometry(f"+{screen_w - 180}+10")

        # Main frame
        self.frame = tk.Frame(self.root, bg="#1a1a2e", padx=8, pady=4)
        self.frame.pack()

        # Timer row
        timer_row = tk.Frame(self.frame, bg="#1a1a2e")
        timer_row.pack()

        self.icon_label = tk.Label(
            timer_row,
            text="\u23f1",
            font=("Segoe UI Emoji", 14),
            fg="#16c79a",
            bg="#1a1a2e",
        )
        self.icon_label.pack(side="left", padx=(0, 6))

        self.timer_label = tk.Label(
            timer_row,
            text="45:00",
            font=("Consolas", 18, "bold"),
            fg="#16c79a",
            bg="#1a1a2e",
        )
        self.timer_label.pack(side="left")

        # Status label (shown when expanded)
        self.status_label = tk.Label(
            self.frame,
            text="",
            font=("Segoe UI", 9),
            fg="#8888aa",
            bg="#1a1a2e",
        )

        # Drag bindings
        for widget in [self.root, self.frame, self.timer_label, self.icon_label]:
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<Double-Button-1>", self._on_double_click)
            widget.bind("<Button-3>", self._toggle_expand)  # Right-click

        # Rounded border effect
        self.root.configure(highlightbackground="#16c79a", highlightthickness=1)

        self._update()
        self.root.mainloop()

    def _start_drag(self, event):
        """Start dragging the widget."""
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        """Move the widget as user drags."""
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _on_double_click(self, event):
        """Double-click to take a break now."""
        self.on_take_break()

    def _toggle_expand(self, event):
        """Right-click to show/hide extra info."""
        self._expanded = not self._expanded
        if self._expanded:
            self.status_label.pack(pady=(2, 0))
        else:
            self.status_label.pack_forget()

    def _update(self):
        """Update the timer display every second."""
        if self.root is None:
            return

        try:
            if self.is_on_break():
                self.timer_label.config(text="BREAK", fg="#e94560")
                self.icon_label.config(text="\U0001f6b6", fg="#e94560")
                self.root.configure(highlightbackground="#e94560")
                self.status_label.config(text="Take a walk!")
            elif self.is_paused():
                self.timer_label.config(text="PAUSED", fg="#ffbd69")
                self.icon_label.config(text="\u23f8", fg="#ffbd69")
                self.root.configure(highlightbackground="#ffbd69")
                self.status_label.config(text="Timer paused")
            else:
                remaining = self.get_remaining_seconds()
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")

                # Color based on urgency
                if remaining < 120:  # Less than 2 minutes
                    color = "#e94560"
                elif remaining < 300:  # Less than 5 minutes
                    color = "#ffbd69"
                else:
                    color = "#16c79a"

                self.timer_label.config(fg=color)
                self.icon_label.config(text="\u23f1", fg=color)
                self.root.configure(highlightbackground=color)

                active = self.get_active_minutes()
                self.status_label.config(
                    text=f"Active: {active:.0f} min | Double-click for break"
                )

            self.root.after(1000, self._update)
        except tk.TclError:
            pass  # Widget was destroyed

    def stop(self):
        """Close the widget."""
        if self.root:
            try:
                self.root.destroy()
            except tk.TclError:
                pass
