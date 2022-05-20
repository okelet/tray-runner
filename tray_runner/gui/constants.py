"""
tray_runner.gui.constants module.
"""
import os

MODULE_DIR = os.path.dirname(__file__)
ICON_PATH = os.path.join(MODULE_DIR, "icons", "terminal-medium.png")

REGULAR_ICON_PATH = ICON_PATH
WARNING_ICON_PATH = os.path.join(MODULE_DIR, "icons", "terminal--exclamation.png")

CIRCLE_ICON_PATH = os.path.join(MODULE_DIR, "icons", "ikonate", "circle.svg")
COMMAND_OK_ICON_PATH = os.path.join(MODULE_DIR, "icons", "ikonate", "ok-circle.svg")
COMMAND_ERROR_ICON_PATH = os.path.join(MODULE_DIR, "icons", "ikonate", "cancel.svg")
SETTINGS_ICON_PATH = os.path.join(MODULE_DIR, "icons", "ikonate", "settings.svg")
ABOUT_ICON_PATH = os.path.join(MODULE_DIR, "icons", "ikonate", "qr.svg")
EXIT_ICON_PATH = os.path.join(MODULE_DIR, "icons", "ikonate", "exit.svg")
