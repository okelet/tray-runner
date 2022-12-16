"""
tray_runner.common_utils.common module.
"""
import locale
import logging
import os
import shlex
import subprocess
import sys
import threading
from datetime import datetime, tzinfo
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import click
import pytz
from babel.core import Locale
from dateutil.tz import tzlocal
from flask_babel import lazy_gettext
from pydantic import BaseModel
from slugify import slugify

from tray_runner.utils import PackagePathFilter

LOG = logging.getLogger(__name__)


class YesNoDefault(str, Enum):

    YES = "YES"
    NO = "NO"
    DEFAULT = "DEFAULT"

    def display_name(self):
        """
        Returns a friendly display name.
        """
        return {
            self.YES.value: lazy_gettext("Yes"),
            self.NO.value: lazy_gettext("No"),
            self.DEFAULT.value: lazy_gettext("By default"),
        }.get(self.value, self.value)

    def to_boolean(self) -> Optional[bool]:
        return {
            self.YES.value: True,
            self.NO.value: False,
            self.DEFAULT.value: None,
        }[self.value]


def run_command(command: Union[str, List[str]], environ: Optional[Dict[str, str]] = None, run_in_shell: Optional[bool] = True, working_directory: Optional[str] = None, stop_event: Optional[threading.Event] = None, poll_period_ms: Optional[int] = None) -> Tuple[int, int, Optional[str], Optional[str]]:  # pylint: disable=too-many-arguments
    """
    Runs a command using Powershell in Windows, or the current shell in Linux.

    If stdout or stderr is returned by the command, it is stripped before being returned by this function.
    """
    if poll_period_ms is None:
        poll_period_ms = 500
    cmd: Union[str, List[str]]
    if run_in_shell is None:
        run_in_shell = False
    if run_in_shell:
        # When running using a shell, we don't have to split the command
        if isinstance(command, str):
            cmd = command
        elif isinstance(command, list):
            cmd = shlex.join(command)
    else:
        if isinstance(command, str):
            cmd = shlex.split(command)
        elif isinstance(command, list):
            cmd = command

    new_env = os.environ.copy()
    if environ:
        new_env = {**new_env, **environ}

    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=new_env, cwd=working_directory, shell=run_in_shell) as process:
        LOG.debug("Waiting for command %s to finish...", command)
        while True:
            if stop_event and stop_event.is_set():
                LOG.info("Command %s, stop signal detected...", command)
                LOG.info("Command %s, sending terminate signal...", command)
                process.terminate()
                try:
                    LOG.info("Command %s, waiting for process to finish...", command)
                    stdout, stderr = process.communicate(timeout=3)
                    LOG.info("Command %s, process finished.", command)
                except subprocess.TimeoutExpired:
                    LOG.info("Command %s, timeout detected, sending kill signal...", command)
                    process.kill()
                    LOG.info("Command %s, closing streams...", command)
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                    LOG.info("Command %s, getting output data...", command)
                    stdout, stderr = process.communicate()
                pid = process.pid
                exit_code = process.returncode
                return pid, exit_code, stdout.strip() if stdout.strip() else None, stderr.strip() if stderr.strip() else None
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
                elif icon and isinstance(icon, str):
                    link.icon_location = (icon, 0)
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
            LOG.debug("Removing shortcut in %s...", link_filepath)
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
        LOG.debug("Removing shortcut in %s...", app_shortcut)
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


def get_local_datetime() -> datetime:
    """
    Returns a datetime object with the current system tzinfo set.
    """
    return datetime.now().replace(tzinfo=tzlocal())


def get_utc_datetime() -> datetime:
    """
    Returns a datetime object with the UTC tzinfo set.
    """
    return datetime.utcnow().replace(tzinfo=pytz.UTC)


def ensure_local_datetime(date_time: datetime, default_tz: Optional[tzinfo] = None):
    """
    Ensures that the datetime object passed as parameter has the current system tzinfo set.

    If the datetime doesn't have yet a time zone set, it is replaced with default_tz or UTC if empty.
    """
    if not date_time.tzinfo:
        if default_tz:
            date_time = date_time.replace(tzinfo=default_tz)
        else:
            date_time = date_time.replace(tzinfo=pytz.UTC)
    return date_time.astimezone(tzlocal())


def get_languages(current_locale: Locale, only_languages: Optional[List[str]] = None):
    """
    Returns the list of languages in the specified locale.
    """
    languages_data = []
    for language_id, language_data in current_locale.languages.items():
        if not only_languages or language_id in only_languages:
            languages_data.append([language_id, language_data])
    return sorted(languages_data, key=lambda x: x[1])


def copy_fields(src: BaseModel, dst: BaseModel) -> None:
    src_fields = src.__fields__
    dst_fields = dst.__fields__
    for field_name, field_data in src_fields.items():
        if field_name in dst_fields.keys():
            setattr(dst, field_name, getattr(src, field_name))

def init_logging(base_package: str, log_file: str, package_level: Optional[Union[int, str]] = None, default_level: Optional[Union[int, str]] = None, message_format: Optional[str] = None, max_file_size: Optional[int] = None, max_backup_files: Optional[int] = None):  # pylint: disable=too-many-arguments
    """
    Initializes the Python logging framework.
    """
    if package_level is None:
        package_level = logging.DEBUG
    if default_level is None:
        default_level = logging.WARNING
    if message_format is None:
        message_formatter = logging.Formatter("%(asctime)s - %(relativepath)s:%(lineno)s - %(name)s:%(funcName)s - %(levelname)s - %(message)s")
    else:
        message_formatter = logging.Formatter(message_format)
    if max_file_size is None:
        max_file_size = 5 * 1024 * 1024  # 5 MB
    if max_backup_files is None:
        max_backup_files = 10

    logging.getLogger("").setLevel(default_level)
    logging.getLogger(base_package).setLevel(package_level)

    # Configure rotating file handler
    rotating_file_handler = RotatingFileHandler(filename=log_file, maxBytes=max_file_size, backupCount=max_backup_files)
    rotating_file_handler.addFilter(PackagePathFilter())
    rotating_file_handler.setFormatter(message_formatter)
    logging.getLogger("").addHandler(rotating_file_handler)

    # Configure stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.addFilter(PackagePathFilter())
    stderr_handler.setFormatter(message_formatter)
    logging.getLogger("").addHandler(stderr_handler)
