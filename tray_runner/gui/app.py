"""
tray_runner.gui module
"""
import logging
import os.path
import signal
import sys
import tempfile
import time
import webbrowser
from gettext import gettext
from typing import Optional

import click
from filelock import FileLock, Timeout
from flask import url_for
from PIL import Image
from pystray import Icon, Menu, MenuItem

import tray_runner
from tray_runner import DEFAULT_CONFIG_FILE, __version__, flask_app
from tray_runner.base_app import BaseApp
from tray_runner.common_utils.common import init_logging, remove_app_menu_shortcut
from tray_runner.common_utils.flask_app_runner import FlaskAppRunner
from tray_runner.config import Config
from tray_runner.constants import APP_ID, APP_NAME
from tray_runner.execution_manager import ExecutionManager
from tray_runner.gui.constants import ABOUT_ICON_PATH, CIRCLE_ICON_PATH, COMMAND_ERROR_ICON_PATH, COMMAND_OK_ICON_PATH, EXIT_ICON_PATH, ICON_PATH, REGULAR_ICON_PATH, SETTINGS_ICON_PATH, WARNING_ICON_PATH
from tray_runner.gui.utils import create_tray_runner_app_menu_launcher, create_tray_runner_autostart_shortcut

LOG = logging.getLogger(__name__)


class TrayRunnerGuiApp(BaseApp):  # pylint: disable=too-many-instance-attributes
    """
    Main GUI class to run the application.
    """

    def __init__(self, config: Config, bind_address: Optional[str] = None, bind_port: Optional[int] = None, system_start: bool = False, show_config: bool = False):

        ####################################################################################################################
        # Init variables
        ####################################################################################################################

        super().__init__(config)
        if show_config is None:
            show_config = False

        self.system_start = system_start
        self.show_config = show_config

        ####################################################################################################################
        # Init execution manager
        ####################################################################################################################

        self.execution_manager = ExecutionManager(self)

        ####################################################################################################################
        # Init Flask app
        ####################################################################################################################

        LOG.debug("Creating Flask application...")
        self.flask_app_instance = flask_app.create_app(base_app=self, execution_manager=self.execution_manager)
        self.flask_app_runner = FlaskAppRunner(app=self.flask_app_instance, bind_address=bind_address, bind_port=bind_port)

        ####################################################################################################################
        # Init GUI app
        ####################################################################################################################

        LOG.debug("Creating tray icon...")
        self.icon = Icon(
            name=APP_ID,
            icon=Image.open(ICON_PATH),
            title=APP_NAME,
            menu=Menu(
                MenuItem(gettext("Configuration"), lambda _icon, _item: self.open_configuration()),
                MenuItem(gettext("Quit"), self.on_menu_item_quit_clicked),
            ),
        )

        LOG.debug("Using psystray backend: %s.", self.icon.__module__ + "." + self.icon.__class__.__name__)

        ####################################################################################################################
        # Shortcuts
        ####################################################################################################################

        # Create shortcut
        if self.config.create_app_menu_shortcut:
            create_tray_runner_app_menu_launcher()
        else:
            remove_app_menu_shortcut(APP_NAME)

        # Create autostart
        if self.config.auto_start:
            create_tray_runner_autostart_shortcut()
        else:
            remove_app_menu_shortcut(APP_NAME, autostart=True)

    def stop(self) -> None:
        """
        Stop process and exit application.
        """
        self.icon.stop()

    def send_notification(self, title: str, message: str) -> None:
        self.icon.remove_notification()
        self.icon.notify(message, title)

    def on_status_changed(self) -> None:
        # TODO
        pass

    def open_configuration(self):
        """
        Opens the configuration page in the browser, after generating a login token.
        """
        # Generate the URL and open the browser
        with self.flask_app_instance.app_context():
            url = url_for("login", token=self.add_token().value, _external=True)
        LOG.debug("Opening URL %s...", url)
        webbrowser.open(url)

    def on_menu_item_quit_clicked(self, icon: Icon, _item: MenuItem):
        """
        Method called when the Quit menu option is clicked.
        """
        icon.stop()

    def run(self) -> int:
        """
        Runs the application.
        """

        ####################################################################################################################
        # Init Flask app
        ####################################################################################################################

        LOG.debug("Starting Flask application...")
        self.flask_app_runner.start()

        LOG.debug("Waiting fot the Flask application to be ready...")
        while not self.flask_app_runner.is_ready():
            time.sleep(0.1)

        (addr, port) = self.flask_app_runner.get_address_and_port()
        if addr == "127.0.0.1":
            addr = "localhost"
        # TODO: Avoid use of nip.io
        server_name = f"""{APP_ID.replace("_", "-")}.127-0-0-1.nip.io:{port}"""
        LOG.debug("Setting Flask SERVER_NAME to %s...", server_name)
        self.flask_app_instance.config["SERVER_NAME"] = server_name

        ####################################################################################################################
        # Start execution manager
        ####################################################################################################################

        self.execution_manager.auto_start_jobs(is_system_autostart=self.system_start, is_app_autostart=True)

        ####################################################################################################################
        # Start version check
        ####################################################################################################################

        if self.config.app_version_check_enabled:
            self.version_checker.start()

        ####################################################################################################################
        # Init GUI app
        ####################################################################################################################

        if self.show_config:
            LOG.debug("Opening configuration page...")
            self.open_configuration()

        LOG.debug("Running tray icon...")
        self.icon.run()
        LOG.debug("Tray icon finished.")

        ####################################################################################################################
        # Cleanup
        ####################################################################################################################

        LOG.debug("Stopping Flask application...")
        self.flask_app_runner.stop()

        LOG.debug("Stopping version checker...")
        if self.version_checker.is_alive():
            self.version_checker.stop()
            self.version_checker.join()

        LOG.debug("Waiting for threads to stop...")
        self.execution_manager.stop_all_threads()

        return 0
