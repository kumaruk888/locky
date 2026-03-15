"""
System tray icon for BreakGuard.

Shows status, remaining time, and provides pause/resume/quit controls.
"""

import logging
import threading
from typing import Callable

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger("breakguard")


def _create_icon_image(color: str = "#16c79a") -> Image.Image:
    """Create a simple colored circle icon."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill=color, outline="#1a1a2e", width=2)
    # Draw a simple "play" triangle or pause bars in the center
    draw.polygon([(24, 18), (24, 46), (48, 32)], fill="white")
    return img


def _create_paused_icon() -> Image.Image:
    """Create icon indicating paused state."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill="#e94560", outline="#1a1a2e", width=2)
    # Pause bars
    draw.rectangle([22, 18, 28, 46], fill="white")
    draw.rectangle([36, 18, 42, 46], fill="white")
    return img


class TrayIcon:
    """Manages the system tray icon and menu."""

    def __init__(
        self,
        get_status: Callable[[], str],
        on_pause_resume: Callable[[], None],
        on_skip_break: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self.get_status = get_status
        self.on_pause_resume = on_pause_resume
        self.on_skip_break = on_skip_break
        self.on_quit = on_quit
        self._paused = False
        self._icon = None

    def _build_menu(self):
        """Build the right-click context menu."""
        status_text = self.get_status()
        pause_text = "Resume" if self._paused else "Pause"

        return pystray.Menu(
            pystray.MenuItem(status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(pause_text, self._toggle_pause),
            pystray.MenuItem("Take Break Now", self.on_skip_break),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit BreakGuard", self._quit),
        )

    def _toggle_pause(self, icon, item):
        self._paused = not self._paused
        self.on_pause_resume()
        # Update icon appearance
        if self._paused:
            self._icon.icon = _create_paused_icon()
        else:
            self._icon.icon = _create_icon_image()
        self._icon.update_menu()

    def _quit(self, icon, item):
        logger.info("Quit requested from tray")
        self._icon.visible = False
        self._icon.stop()
        self.on_quit()

    def run(self):
        """Run the tray icon. Blocks the calling thread."""
        self._icon = pystray.Icon(
            name="BreakGuard",
            icon=_create_icon_image(),
            title="BreakGuard",
            menu=self._build_menu(),
        )
        logger.info("System tray icon started")
        self._icon.run()

    def stop(self):
        """Stop the tray icon."""
        if self._icon:
            self._icon.stop()

    def update_title(self, title: str):
        """Update the hover tooltip text."""
        if self._icon:
            self._icon.title = title
