"""
Floating timer widget — shows countdown to next break with a
'Take Break Now' button.

Also hooks into Windows session notifications (WTS_SESSION_LOCK /
WTS_SESSION_UNLOCK) via the tkinter window to reliably detect
lock/unlock events.
"""

import ctypes
import ctypes.wintypes
import platform
import tkinter as tk

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

# WTS session notification constants
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0

GWLP_WNDPROC = -4

# Properly typed SetWindowLongPtrW / GetWindowLongPtrW for 64-bit pointers
if platform.architecture()[0] == "64bit":
    _SetWindowLongPtr = ctypes.windll.user32.SetWindowLongPtrW
    _SetWindowLongPtr.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    _SetWindowLongPtr.restype = ctypes.c_void_p

    _GetWindowLongPtr = ctypes.windll.user32.GetWindowLongPtrW
    _GetWindowLongPtr.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
    _GetWindowLongPtr.restype = ctypes.c_void_p
else:
    _SetWindowLongPtr = ctypes.windll.user32.SetWindowLongW
    _SetWindowLongPtr.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    _SetWindowLongPtr.restype = ctypes.c_void_p

    _GetWindowLongPtr = ctypes.windll.user32.GetWindowLongW
    _GetWindowLongPtr.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
    _GetWindowLongPtr.restype = ctypes.c_void_p

_CallWindowProc = ctypes.windll.user32.CallWindowProcW
_CallWindowProc.argtypes = [
    ctypes.c_void_p, ctypes.wintypes.HWND, ctypes.c_uint,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
_CallWindowProc.restype = ctypes.c_long

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long,
    ctypes.wintypes.HWND,
    ctypes.c_uint,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)


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
        on_session_lock=None,
        on_session_unlock=None,
    ):
        self._get_remaining = get_remaining_seconds
        self._is_on_break = is_on_break
        self._is_paused = is_paused
        self._get_break_remaining = get_break_remaining
        self._on_take_break = on_take_break
        self._on_quit = on_quit
        self._on_session_lock = on_session_lock
        self._on_session_unlock = on_session_unlock

        # Drag state
        self._drag_x = 0
        self._drag_y = 0

        # Keep references to prevent garbage collection
        self._new_wndproc = None
        self._old_wndproc = None

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

        # Get the real top-level HWND (parent of the tkinter frame widget)
        frame_hwnd = self.root.winfo_id()
        self._hwnd = ctypes.windll.user32.GetParent(frame_hwnd) or frame_hwnd

        # Hide from taskbar
        style = ctypes.windll.user32.GetWindowLongW(frame_hwnd, GWL_EXSTYLE)
        style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(frame_hwnd, GWL_EXSTYLE, style)

        # Register for WTS session notifications on the top-level HWND
        result = ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
            self._hwnd, NOTIFY_FOR_THIS_SESSION
        )
        if result:
            # Subclass the window to intercept WM_WTSSESSION_CHANGE
            self._install_wndproc_hook()

        # Dragging
        for w in [self.root, self.container, self.timer_label, self.status_label]:
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        self._update()
        self.root.mainloop()

    def _install_wndproc_hook(self):
        """Subclass the window procedure to catch WTS session messages."""
        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_WTSSESSION_CHANGE:
                if wparam == WTS_SESSION_LOCK and self._on_session_lock:
                    self._on_session_lock()
                elif wparam == WTS_SESSION_UNLOCK and self._on_session_unlock:
                    self._on_session_unlock()
            return _CallWindowProc(
                self._old_wndproc, hwnd, msg, wparam, lparam
            )

        self._new_wndproc = WNDPROC(wndproc)
        self._old_wndproc = _GetWindowLongPtr(self._hwnd, GWLP_WNDPROC)
        _SetWindowLongPtr(self._hwnd, GWLP_WNDPROC, self._new_wndproc)

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
