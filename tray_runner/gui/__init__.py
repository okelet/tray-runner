"""
tray_runner.gui module
"""
import logging
import os.path
import signal
import sys
import tempfile
import webbrowser
from datetime import datetime
from functools import partial
from gettext import gettext
from logging.handlers import RotatingFileHandler
from typing import List, Optional

import click
from PySide6.QtCore import QLockFile, QThread, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QMessageBox, QStyle, QSystemTrayIcon

import tray_runner
from tray_runner import DEFAULT_CONFIG_FILE, __version__
from tray_runner.common_utils.common import CommandAborted, coalesce, remove_app_menu_shortcut, run_command
from tray_runner.config import Config, ConfigCommand, ConfigCommandLogItem
from tray_runner.constants import APP_ID, APP_NAME, APP_URL
from tray_runner.gui.constants import ABOUT_ICON_PATH, CIRCLE_ICON_PATH, COMMAND_ERROR_ICON_PATH, COMMAND_OK_ICON_PATH, EXIT_ICON_PATH, ICON_PATH, REGULAR_ICON_PATH, SETTINGS_ICON_PATH, WARNING_ICON_PATH
from tray_runner.gui.settings_dialog import SettingsDialog
from tray_runner.utils import PackagePathFilter, create_tray_runner_app_menu_launcher, create_tray_runner_autostart_shortcut

LOG = logging.getLogger(__name__)


class CommandThread(QThread):  # pylint: disable=too-few-public-methods
    """
    CommandThread class.

    Thread responsible for running the commands defined in the configuration and emitting signals on change.
    """

    notification_signal = Signal(str, str)
    update_menu_signal = Signal()

    def __init__(self, app: "TrayCmdRunnerApp", command: ConfigCommand) -> None:
        QThread.__init__(self)
        self.app = app
        self.command = command
        self.update_menu_signal.connect(self.app.update_status)  # type: ignore[attr-defined]
        self.notification_signal.connect(self.app.show_notification)  # type: ignore[attr-defined]
        self.last_run_dt = None
        self.last_status = None
        self.last_error_message = None

    def run(self):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """
        Overridden method from parent class, implementing the logic of the thread.
        """

        last_run_dt = None
        while True:

            if self.isInterruptionRequested():
                break

            if last_run_dt and (datetime.utcnow() - last_run_dt).total_seconds() < self.command.seconds_between_executions:
                QThread.sleep(1)
                continue

            include_output_in_notifications = coalesce(self.command.include_output_in_notifications, self.app.config.include_output_in_notifications)
            show_complete_notifications = coalesce(self.command.show_complete_notifications, self.app.config.show_complete_notifications)
            show_error_notifications = coalesce(self.command.show_error_notifications, self.app.config.show_error_notifications)

            run_in_shell = coalesce(self.command.run_in_shell, self.app.config.run_in_shell)
            restart_on_failure = coalesce(self.command.restart_on_failure, self.app.config.restart_on_failure)
            restart_on_exit = coalesce(self.command.restart_on_exit, self.app.config.restart_on_exit)

            working_directory = self.command.working_directory
            if not os.path.exists(working_directory):
                working_directory = os.path.expanduser("~")

            last_run_dt = datetime.utcnow()

            LOG.info("Executing command %s - %s...", self.command.name, self.command.command)
            start_time = datetime.utcnow()
            self.command.total_runs += 1
            self.command.last_run_dt = start_time
            self.last_run_dt = start_time
            self.last_status = None
            self.last_error_message = None
            exit_code = None
            error_message = None
            elapsed_time = None
            aborted = False
            stdout = None
            stderr = None
            try:
                pid, exit_code, stdout, stderr = run_command(self.command.command, environ=self.command.environment_as_dict(), run_in_shell=run_in_shell, working_directory=working_directory, thread=self)
                end_time = datetime.utcnow()
                elapsed_time = (end_time - start_time).total_seconds()
                LOG.debug("Command %s - %s exited with code %s (took %s seconds).", self.command.name, self.command.command, exit_code, f"{elapsed_time:.2f}")
                self.command.add_log(ConfigCommandLogItem(start_time=start_time, end_time=end_time, duration=elapsed_time, pid=pid, exit_code=exit_code, stdout=stdout, stderr=stderr))
                self.command.last_run_exit_code = exit_code
                self.last_status = exit_code
                if exit_code == 0:
                    self.command.last_successful_run_dt = start_time
                    self.command.last_duration = elapsed_time
                    if self.command.max_duration is None or elapsed_time > self.command.max_duration:
                        self.command.max_duration = elapsed_time
                    if self.command.min_duration is None or elapsed_time < self.command.min_duration:
                        self.command.min_duration = elapsed_time
                    if self.command.avg_duration is not None:
                        self.command.avg_duration = ((self.command.avg_duration * self.command.ok_runs) + elapsed_time) / (self.command.ok_runs + 1)
                    else:
                        self.command.avg_duration = elapsed_time
                    self.command.ok_runs += 1
                else:
                    self.command.error_runs += 1
            except CommandAborted:
                # This happens when the command runner thread has been signaled to stop (because the program is being closed).
                # So we don't want to generate alerts/notifications when this happens, as this is because the user has initiated the action.
                end_time = datetime.utcnow()
                elapsed_time = (end_time - start_time).total_seconds()
                error_message = "Command aborted"
                aborted = True
                LOG.warning("Command %s - %s aborted.", self.command.name, self.command.command)
                self.command.add_log(ConfigCommandLogItem(start_time=start_time, end_time=end_time, duration=elapsed_time, aborted=True))
            except Exception as ex:  # pylint: disable=broad-except
                end_time = datetime.utcnow()
                elapsed_time = (end_time - start_time).total_seconds()
                error_message = str(ex)
                LOG.warning("Error running command %s - %s : %s.", self.command.name, self.command.command, error_message)
                self.command.add_log(ConfigCommandLogItem(start_time=start_time, end_time=end_time, duration=elapsed_time, error_message=error_message))
                self.command.failed_runs += 1
                self.last_error_message = str(ex)

            # Save command run statistics
            self.app.save_config()

            # Update statuses
            self.update_menu_signal.emit()

            if aborted:
                return

            if exit_code is None:
                # Failed to run
                if not restart_on_failure:
                    if show_error_notifications:
                        self.notification_signal.emit(self.command.name, gettext("Command failed to run ({error_message}).").format(error_message=error_message))
                    break
                if show_error_notifications:
                    self.notification_signal.emit(self.command.name, gettext("Command failed to run ({error_message}); restarting after {seconds_between_executions} seconds...").format(error_message=error_message, seconds_between_executions=self.command.seconds_between_executions))
            elif exit_code:
                # Exited with code > 0
                if not restart_on_failure:
                    if show_error_notifications:
                        if include_output_in_notifications and stdout and stderr:
                            self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nStandard output: {stdout}\n\nError output: {stderr}").format(exit_code=exit_code, elapsed_time=elapsed_time, stdout=stdout, stderr=stderr))
                        elif include_output_in_notifications and stdout:
                            self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nStandard output: {stdout}").format(exit_code=exit_code, elapsed_time=elapsed_time, stdout=stdout))
                        elif include_output_in_notifications and stderr:
                            self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nError output: {stderr}").format(exit_code=exit_code, elapsed_time=elapsed_time, stderr=stderr))
                        else:
                            self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).").format(exit_code=exit_code, elapsed_time=elapsed_time))
                    break
                if show_error_notifications:
                    if include_output_in_notifications and stdout and stderr:
                        self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds); restarting after {seconds_between_executions} seconds...\n\nStandard output: {stdout}\n\nError output: {stderr}").format(exit_code=exit_code, elapsed_time=elapsed_time, seconds_between_executions=self.command.seconds_between_executions, stdout=stdout, stderr=stderr))
                    elif include_output_in_notifications and stdout:
                        self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds); restarting after {seconds_between_executions} seconds...\n\nStandard output: {stdout}").format(exit_code=exit_code, elapsed_time=elapsed_time, seconds_between_executions=self.command.seconds_between_executions, stdout=stdout))
                    elif include_output_in_notifications and stderr:
                        self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds); restarting after {seconds_between_executions} seconds...\n\nError output: {stderr}").format(exit_code=exit_code, elapsed_time=elapsed_time, seconds_between_executions=self.command.seconds_between_executions, stderr=stderr))
                    else:
                        self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds); restarting after {seconds_between_executions} seconds...").format(exit_code=exit_code, elapsed_time=elapsed_time, seconds_between_executions=self.command.seconds_between_executions))
            else:
                # Exited with code = 0
                if not restart_on_exit:
                    if show_complete_notifications:
                        if include_output_in_notifications and stdout and stderr:
                            self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nStandard output: {stdout}\n\nError output: {stderr}").format(exit_code=exit_code, elapsed_time=elapsed_time, stdout=stdout, stderr=stderr))
                        elif include_output_in_notifications and stdout:
                            self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nStandard output: {stdout}").format(exit_code=exit_code, elapsed_time=elapsed_time, stdout=stdout))
                        elif include_output_in_notifications and stderr:
                            self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nError output: {stderr}").format(exit_code=exit_code, elapsed_time=elapsed_time, stderr=stderr))
                        else:
                            self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).").format(exit_code=exit_code, elapsed_time=elapsed_time))
                    break
                if show_complete_notifications:
                    if include_output_in_notifications and stdout and stderr:
                        self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds); restarting after {seconds_between_executions} seconds...\n\nStandard output: {stdout}\n\nError output: {stderr}").format(exit_code=exit_code, elapsed_time=elapsed_time, seconds_between_executions=self.command.seconds_between_executions, stdout=stdout, stderr=stderr))
                    elif include_output_in_notifications and stdout:
                        self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds); restarting after {seconds_between_executions} seconds...\n\nStandard output: {stdout}").format(exit_code=exit_code, elapsed_time=elapsed_time, seconds_between_executions=self.command.seconds_between_executions, stdout=stdout))
                    elif include_output_in_notifications and stderr:
                        self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds); restarting after {seconds_between_executions} seconds...\n\nError output: {stderr}").format(exit_code=exit_code, elapsed_time=elapsed_time, seconds_between_executions=self.command.seconds_between_executions, stderr=stderr))
                    else:
                        self.notification_signal.emit(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds); restarting after {seconds_between_executions} seconds...").format(exit_code=exit_code, elapsed_time=elapsed_time, seconds_between_executions=self.command.seconds_between_executions))


class TrayCmdRunnerApp:  # pylint: disable=too-many-instance-attributes
    """
    TrayCmdRunnerApp application.
    """

    def __init__(self, qt_app: QApplication, main_window: QMainWindow, config_path: Optional[str] = None, log_level_already_set: Optional[bool] = False, show_config: Optional[bool] = False):  # pylint: disable=too-many-arguments

        self.qt_app = qt_app
        self.main_window = main_window
        self.config_path = config_path
        self.config: Config = Config.load_from_file(self.config_path)
        if not log_level_already_set:
            logging.getLogger(tray_runner.__name__).setLevel(logging.getLevelName(self.config.log_level))

        self.config_dialog: Optional[SettingsDialog] = None

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

        self._tray = QSystemTrayIcon(icon=QIcon(ICON_PATH))
        self._tray.setToolTip(APP_NAME)
        self._tray.setVisible(True)

        # Init the list of command threads
        self.command_threads: List[CommandThread] = []

        # Create the menu
        self._menu = QMenu()
        self.rebuild_menu()

        # Add the menu to the tray
        self._tray.setContextMenu(self._menu)

        # Init command threads
        for command in self.config.commands:
            if not command.disabled:
                command_thread = CommandThread(self, command)
                command_thread.start()
                self.command_threads.append(command_thread)
        LOG.info("Current number of threads running: %s", len(self.command_threads))

        if show_config:
            self.edit_configuration()
        elif not os.path.exists(self.config_path or DEFAULT_CONFIG_FILE):
            self.save_config()
            if QMessageBox.question(self.main_window, gettext("Welcome"), gettext("Welcome! This is the first time you run the application. Do you want to configure it?")) == QMessageBox.StandardButton.Yes:
                self.edit_configuration()

    def save_config(self):
        """
        Saves the configuration.
        """
        self.config.save_to_file(self.config_path)

    def rebuild_menu(self) -> None:
        """
        Rebuilds the tray menu when the status of some objects changes. Usually fired by the signals from the command threads.
        """

        # Remove previous elements
        self._menu.clear()

        # Sample action
        for command in sorted(self.config.commands, key=lambda x: x.name.lower()):
            command_thread = self.get_command_thread(command)
            if command_thread:
                if command_thread.last_error_message or command_thread.last_status:
                    icon = COMMAND_ERROR_ICON_PATH
                else:
                    icon = COMMAND_OK_ICON_PATH
            else:
                icon = CIRCLE_ICON_PATH
            self._menu.addAction(QIcon(icon), command.name, partial(click.launch, command.get_log_file_path()))

        # Separator
        self._menu.addSeparator()

        # Configuration edit
        self._menu.addAction(QIcon(SETTINGS_ICON_PATH), gettext("Configuration"), self.edit_configuration)
        # self._menu.addAction(QIcon(SETTINGS_ICON_PATH), gettext("Edit configuration"), self.edit_configuration_file)

        # Add a About and Quit options to the menu.
        self._menu.addAction(QIcon(ABOUT_ICON_PATH), gettext("About"), self.about)
        self._menu.addAction(QIcon(EXIT_ICON_PATH), gettext("Quit"), self.quit)

    def edit_configuration(self, warning_style: Optional[int] = None, warning_text: Optional[str] = None):
        """
        Opens the configuration dialog.
        """
        if self.config_dialog:
            self.config_dialog.show()
            self.config_dialog.raise_()
            self.config_dialog.activateWindow()
        else:
            self.config_dialog = SettingsDialog(self.main_window, self, warning_style, warning_text)
            self.config_dialog.exec()
            self.config_dialog = None

    def edit_configuration_file(self):
        """
        Calls the OS functions to open the configuration file and edit it.
        """
        self._tray.showMessage(gettext("Edit configuration"), gettext("The configuration file will be opened in the default editor."), self.get_icon(QStyle.SP_DriveFDIcon))
        click.launch(self.config_path or DEFAULT_CONFIG_FILE)

    def get_icon(self, icon: QStyle.StandardPixmap) -> QIcon:
        """
        Gets an icon from the current application style.
        """
        return self.qt_app.style().standardIcon(icon)

    def update_status(self):
        """
        Function that updates tray icon and tooltip, according to the commands' status. Usually fired by the signals from the command threads.
        """
        has_error = False
        for command in self.command_threads:
            if command.last_error_message or command.last_status:
                has_error = True
                break
        if has_error:
            self._tray.setIcon(QIcon(WARNING_ICON_PATH))
            self._tray.setToolTip(gettext("{app_name}: One or more commands have errors.").format(app_name=APP_NAME))
        else:
            self._tray.setIcon(QIcon(REGULAR_ICON_PATH))
            self._tray.setToolTip(gettext("{app_name}: Everything is OK.").format(app_name=APP_NAME))
        self.rebuild_menu()

    def show_notification(self, title, message, icon=None):
        """
        Shows a notification provided by the tray. Usually fired by the signals from the command threads.
        """
        if icon:
            self._tray.showMessage(title, message, self.get_icon(icon))
        else:
            self._tray.showMessage(title, message)

    def stop_command_thread(self, command: ConfigCommand):
        """
        Finds and stops the thread associated with the command.
        """
        LOG.debug("Searching for command %s - %s and stopping it...", command.name, command.command)
        for i in self.command_threads:
            if i.command == command:
                LOG.debug("Command %s - %s found; stopping it...", command.name, command.command)
                i.requestInterruption()
                i.wait()
                self.command_threads.remove(i)
                self.update_status()
                break
        else:
            LOG.debug("Command %s - %s NOT found; perhaps it was disabled or not running before.", command.name, command.command)
        LOG.info("Current number of threads running: %s", len(self.command_threads))

    def get_command_thread(self, command: ConfigCommand) -> Optional[CommandThread]:
        """
        Finds the thread associated to the command.
        """
        for command_thread in self.command_threads:
            if command_thread.command == command:
                return command_thread
        return None

    def start_command_thread(self, command: ConfigCommand):
        """
        Starts a thread associated to the command, checking before if the command is enabled and not already running.
        """
        if command.disabled:
            LOG.warning("Trying to start the command %s - %s, that is disabled; skipping...", command.name, command.command)
            return
        for command_thread in self.command_threads:
            if command_thread.command == command:
                LOG.warning("Command %s - %s is already running; skipping...", command.name, command.command)
                break
        else:
            command_thread = CommandThread(self, command)
            command_thread.start()
            self.command_threads.append(command_thread)
        LOG.info("Current number of threads running: %s", len(self.command_threads))

    def about(self):  # pylint: disable=no-self-use
        """
        Displays the application's about dialog.
        """
        webbrowser.open(APP_URL)

    def quit(self):
        """
        Performs the operations needed to stop the application (stop command threads, etc.).
        """
        LOG.info("Closing existing dialogs...")
        if self.config_dialog:
            QMessageBox.warning(self.config_dialog, gettext("Quit"), gettext("The settings dialog is open; save the changes and close it before quitting."))
            return

        LOG.info("Stopping threads...")
        for i in self.command_threads:
            if i.isRunning():
                i.requestInterruption()

        LOG.info("Waiting for threads to stop...")
        for i in self.command_threads:
            if i.isRunning():
                i.wait()

        self.qt_app.quit()


@click.command()
@click.option("--config", "-c", "config_path", type=click.Path(exists=True, dir_okay=False, resolve_path=True), required=False, help="Path to configuration file.")
@click.option("--log-level", type=click.Choice([logging.getLevelName(x) for x in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]], case_sensitive=False), show_default=True)
@click.option("--show-config", is_flag=True, default=False)
@click.version_option(__version__)
def run(config_path: str | None, log_level: str | None, show_config: bool) -> None:
    """
    Main command for the tray_runner package.
    """

    # Init logging
    formatter = logging.Formatter("%(asctime)s - %(relativepath)s:%(lineno)s - %(name)s:%(funcName)s - %(levelname)s - %(message)s")
    logging.getLogger("").setLevel(logging.NOTSET)
    if log_level:
        logging.getLogger(tray_runner.__name__).setLevel(logging.getLevelName(log_level))

    # Configure rotating file handler
    if not os.path.exists(tray_runner.APP_DIR):
        os.makedirs(tray_runner.APP_DIR)
    rotating_file_handler = RotatingFileHandler(filename=os.path.join(tray_runner.APP_DIR, f"{APP_ID}.log"), maxBytes=5 * 1024 * 1025, backupCount=10)  # 10 files of 5 MB
    rotating_file_handler.addFilter(PackagePathFilter())
    rotating_file_handler.setFormatter(formatter)
    logging.getLogger("").addHandler(rotating_file_handler)

    # Configure stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.addFilter(PackagePathFilter())
    stderr_handler.setFormatter(formatter)
    logging.getLogger("").addHandler(stderr_handler)

    # Init application
    qt_app = QApplication([])
    qt_app.setQuitOnLastWindowClosed(False)
    # qt_app.setApplicationDisplayName("Command runner")

    main_window = QMainWindow()
    main_window.setWindowIcon(QIcon(ICON_PATH))

    lock_file_path = os.path.join(tempfile.gettempdir(), "tray-runner-gui.lock")
    lock_file = QLockFile(lock_file_path)
    if not lock_file.tryLock():
        QMessageBox.critical(main_window, gettext("Application already running"), gettext("The application is already running."))
        sys.exit(1)

    # Create the application
    app = TrayCmdRunnerApp(qt_app, main_window, config_path, log_level_already_set=bool(log_level), show_config=show_config)

    # Control-C handler
    # https://stackoverflow.com/a/4939113/576138
    signal.signal(signal.SIGINT, lambda *_a: app.quit())
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)  # type: ignore[attr-defined] # pylint: disable=no-member

    try:
        sys.exit(qt_app.exec())
    finally:
        lock_file.unlock()
