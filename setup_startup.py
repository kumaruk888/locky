"""
Adds BreakGuard to Windows startup so it runs automatically on boot.

Run this script once:
    python setup_startup.py

It creates a shortcut in the Windows Startup folder pointing to main.py
using pythonw.exe (no console window).
"""

import os
import sys

try:
    import win32com.client
except ImportError:
    print("ERROR: pywin32 is required. Run: pip install pywin32")
    sys.exit(1)


def get_startup_folder() -> str:
    """Get the Windows Startup folder path."""
    return os.path.join(
        os.environ["APPDATA"],
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )


def create_shortcut():
    """Create a .lnk shortcut in the Startup folder."""
    startup_folder = get_startup_folder()
    shortcut_path = os.path.join(startup_folder, "BreakGuard.lnk")

    # Use pythonw.exe to avoid showing a console window
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable  # Fallback to python.exe

    main_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "main.py"
    )
    working_dir = os.path.dirname(main_script)

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = pythonw
    shortcut.Arguments = f'"{main_script}"'
    shortcut.WorkingDirectory = working_dir
    shortcut.Description = "BreakGuard — Healthy break enforcer"
    shortcut.save()

    print(f"Startup shortcut created at:\n  {shortcut_path}")
    print(f"\nBreakGuard will now start automatically when you log in.")
    print(f"To remove, delete the shortcut from:\n  {startup_folder}")


def remove_shortcut():
    """Remove the startup shortcut."""
    shortcut_path = os.path.join(get_startup_folder(), "BreakGuard.lnk")
    if os.path.exists(shortcut_path):
        os.remove(shortcut_path)
        print("Startup shortcut removed.")
    else:
        print("No startup shortcut found.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--remove":
        remove_shortcut()
    else:
        create_shortcut()
