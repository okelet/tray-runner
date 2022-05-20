"""
tray_runner.common_utils.common module.
"""
import locale
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import click
from PySide6.QtCore import QThread
from slugify import slugify

LOG = logging.getLogger(__name__)


class CommandAborted(Exception):
    """
    CommandAborted exception class.
    """


def run_command(command: str, environ: Optional[Dict[str, str]] = None, run_in_shell: Optional[bool] = True, working_directory: Optional[str] = None, thread: Optional[QThread] = None, poll_period_ms: Optional[int] = None) -> Tuple[int, int, Optional[str], Optional[str]]:  # pylint: disable=too-many-arguments
    """
    Runs a command using Powershell in Windows, or the current shell in Linux.

    If stdout or stderr is returned by the command, it is stripped before being returned by this function.
    """
    if poll_period_ms is None:
        poll_period_ms = 500
    cmd_run_in_shell = False
    cmd: Union[str, List[str]]
    if sys.platform == "win32":
        cmd = ["powershell", "-Command", command]
    else:
        if run_in_shell:
            # When running using a shell, we don't have to split the command
            cmd = command
            cmd_run_in_shell = True
        else:
            cmd = shlex.split(command)

    new_env = os.environ.copy()
    if environ:
        new_env = {**new_env, **environ}

    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=new_env, cwd=working_directory, shell=cmd_run_in_shell) as process:
        LOG.debug("Waiting for command %s to finish...", command)
        while True:
            if thread and thread.isInterruptionRequested():
                LOG.info("Command %s, stop signal detected; killing command and raising CommandAborted exception.", command)
                process.kill()
                raise CommandAborted()
            try:
                stdout, stderr = process.communicate(timeout=poll_period_ms / 1000)
                break
            except subprocess.TimeoutExpired:
                continue

        pid = process.pid
        exit_code = process.returncode
        return pid, exit_code, stdout.strip() if stdout.strip() else None, stderr.strip() if stderr.strip() else None


def create_app_menu_shortcut(name: str, command: str, args: Optional[str] = None, work_dir: Optional[str] = None, description: Optional[str] = None, icon: Optional[Union[str, Tuple[str, int]]] = None, autostart: Optional[bool] = False) -> None:  # pylint: disable=too-many-branches,too-many-arguments
    """
    Creates a shortcut to launch the application in the applications' menu.

    Support for Windows and Linux.
    """

    LOG.debug("Creating desktop shortcut with params: platform=%s, name=%s, command=%s, work_dir=%s, description=%s, icon=%s, autostart=%s...", sys.platform, name, command, work_dir, description, icon, autostart)
    if sys.platform == "win32":

        try:
            import winshell  # pylint: disable=import-error,import-outside-toplevel

            if autostart:
                link_filepath = str(Path(winshell.startup(common=False)) / f"{name}.lnk")
            else:
                link_filepath = str(Path(winshell.programs(common=False)) / f"{name}.lnk")
            LOG.debug("Creating shortcut in %s...", link_filepath)
            with winshell.shortcut(link_filepath) as link:
                link.path = command
                if description:
                    link.description = description
                if args:
                    link.arguments = args
                if work_dir:
                    link.working_directory = work_dir
                if icon and isinstance(icon, tuple):
                    link.icon_location = (icon[0], icon[1])
        except Exception as ex:  # pylint: disable=broad-except
            LOG.error("Error creating Windows Start Menu shortcut: %s", str(ex), exc_info=True)

    elif sys.platform == "linux":

        if autostart:
            app_dir = os.path.expanduser("~/.config/autostart")
        else:
            app_dir = os.path.expanduser("~/.local/share/applications")
        if not os.path.exists(app_dir):
            os.makedirs(app_dir)
        app_shortcut = os.path.join(app_dir, f"{slugify(name)}.desktop")
        LOG.debug("Creating shortcut in %s...", app_shortcut)
        with click.open_file(app_shortcut, "w") as shortcut:
            shortcut.write("[Desktop Entry]\n")
            shortcut.write("Version=1.0\n")
            shortcut.write("Type=Application\n")
            shortcut.write("Terminal=False\n")
            shortcut.write(f"Name={name}\n")
            if args:
                shortcut.write(f"Exec={command} {args}\n")
            else:
                shortcut.write(f"Exec={command}\n")
            if description:
                shortcut.write(f"Comment={description}\n")
            if icon and isinstance(icon, str):
                shortcut.write(f"Icon={icon}\n")

    else:

        # Platform not supported
        LOG.error("Error creating shortcut: platform not supported (%s).", sys.platform)


def remove_app_menu_shortcut(name: str, autostart: Optional[bool] = False) -> None:
    """
    Removes a shortcut to launch the application in the applications' menu.

    Support for Windows and Linux.
    """
    if sys.platform == "win32":

        try:
            import winshell  # pylint: disable=import-error,import-outside-toplevel

            if autostart:
                link_filepath = str(Path(winshell.startup(common=False)) / f"{name}.lnk")
            else:
                link_filepath = str(Path(winshell.programs(common=False)) / f"{name}.lnk")
            if os.path.exists(link_filepath):
                os.remove(link_filepath)
        except Exception as ex:  # pylint: disable=broad-except
            LOG.error("Error creating Windows Start Menu shortcut: %s", str(ex), exc_info=True)

    elif sys.platform == "linux":

        if autostart:
            app_dir = os.path.expanduser("~/.config/autostart")
        else:
            app_dir = os.path.expanduser("~/.local/share/applications")
        app_shortcut = os.path.join(app_dir, f"{slugify(name)}.desktop")
        if os.path.exists(app_shortcut):
            os.remove(app_shortcut)

    else:

        # Platform not supported
        LOG.error("Error removing shortcut: platform not supported (%s).", sys.platform)


def coalesce(*arg):
    """
    Returns the first non-None value from the arguments.
    """
    return next((a for a in arg if a is not None), None)


def get_simple_default_locale() -> str:
    """
    Returns the first part of the default locale.
    """
    lang, _lc = locale.getdefaultlocale()
    if lang:
        return lang
    return "en_US"
