"""
tray_runner.gui.utils module.
"""
import os
import shutil
import sys
from typing import Optional, Tuple, Union

import tray_runner
from tray_runner.common_utils.common import create_app_menu_shortcut
from tray_runner.constants import APP_NAME
from tray_runner.gui.constants import ICON_PATH, ICON_PATH_ICO


def resolve_app_exe_info() -> Tuple[str, Optional[str], Optional[str], Union[Optional[str], Tuple[str, int]]]:
    """
    Auxiliary function to guess the executable name, arguments, working dir and icon for the current execution method.
    """
    icon: Union[Optional[str], Tuple[str, int]] = None
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        exe = os.path.abspath(sys.argv[0])
        args = None
        work_dir = os.path.expanduser("~")
        if sys.platform == "win32":
            icon = (exe, 0)
        else:
            # Copy icon to app dir
            icon = os.path.join(tray_runner.APP_DIR, "icon.png")
            if not os.path.exists(tray_runner.APP_DIR):
                os.makedirs(tray_runner.APP_DIR)
            shutil.copyfile(ICON_PATH, icon)
    else:
        exe = sys.executable
        exe_dir = os.path.dirname(os.path.abspath(exe))
        if sys.platform == "win32":
            if os.path.exists(os.path.join(exe_dir, "pythonw.exe")):
                exe = os.path.join(exe_dir, "pythonw.exe")
        args = "-m tray_runner.gui"
        work_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(tray_runner.__file__)), ".."))
        if sys.platform == "win32":
            icon = ICON_PATH_ICO
        else:
            icon = ICON_PATH
    return exe, args, work_dir, icon


def create_tray_runner_app_menu_launcher():
    """
    Auxiliary function to create the app menu launcher shortcut.
    """
    exe, args, work_dir, icon = resolve_app_exe_info()
    create_app_menu_shortcut(APP_NAME, command=exe, args=args, work_dir=work_dir, icon=icon)


def create_tray_runner_autostart_shortcut():
    """
    Auxiliary function to create the auto-start shortcut.
    """
    exe, args, work_dir, icon = resolve_app_exe_info()
    create_app_menu_shortcut(APP_NAME, command=exe, args=args + " --system-start", work_dir=work_dir, icon=icon, autostart=True)
