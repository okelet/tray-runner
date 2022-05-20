"""
tray_runner.tray_runner_utils module.
"""
import logging
import os
import shutil
import sys
from typing import Optional, Tuple, Union

import tray_runner
from tray_runner.common_utils.common import create_app_menu_shortcut
from tray_runner.constants import APP_NAME
from tray_runner.gui.constants import ICON_PATH, REGULAR_ICON_PATH


def resolve_app_exe_info() -> Tuple[str, Optional[str], Optional[str], Union[Optional[str], Tuple[str, int]]]:
    """
    Auxiliary function to guess the executable name, arguments, working dir and icon for the current execution method.
    """
    icon = None
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
        icon = REGULAR_ICON_PATH
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
    create_app_menu_shortcut(APP_NAME, command=exe, args=args, work_dir=work_dir, icon=icon, autostart=True)


class PackagePathFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """
    Logging filter to add relative path to log messages.

    Borrowed from: https://stackoverflow.com/a/52582536/576138
    """

    def filter(self, record):
        pathname = record.pathname
        record.relativepath = None
        abs_sys_paths = map(os.path.abspath, sys.path)
        for path in sorted(abs_sys_paths, key=len, reverse=True):  # longer paths first
            if not path.endswith(os.sep):
                path += os.sep
            if pathname.startswith(path):
                record.relativepath = os.path.relpath(pathname, path)
                break
        return True
