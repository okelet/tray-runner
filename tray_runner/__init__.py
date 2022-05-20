"""
tray_runner module.
"""
import importlib.metadata
import os
import sys

import click

try:
    __version__ = importlib.metadata.version(__package__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "__DEVELOPMENT__"

PACKAGE_DIR = os.path.dirname(__file__)

if os.getenv("CMD_RUNNER_PORTABLE") == "1":
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running using Pyinstaller, so we take the dir where the executable is located
        # https://pyinstaller.org/en/stable/runtime-information.html#using-sys-executable-and-sys-argv-0
        APP_DIR = os.path.dirname(sys.argv[0])
    else:
        APP_DIR = os.getcwd()
else:
    APP_DIR = click.get_app_dir(__name__)
DEFAULT_CONFIG_FILE = os.path.join(APP_DIR, "config.json")
