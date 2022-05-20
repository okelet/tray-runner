"""
tray_runner.gui.settings modules.
"""
import logging
import os
from gettext import gettext
from typing import TYPE_CHECKING, Optional

import click
from PySide6.QtGui import QIcon, QScreen
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QWidget

import tray_runner
from tray_runner.common_utils.common import remove_app_menu_shortcut
from tray_runner.common_utils.qt import load_ui, set_warning_style
from tray_runner.config import ConfigCommand, LogLevelEnum
from tray_runner.constants import APP_NAME
from tray_runner.gui.command_dialog import CommandDialog
from tray_runner.gui.constants import REGULAR_ICON_PATH
from tray_runner.utils import create_tray_runner_app_menu_launcher, create_tray_runner_autostart_shortcut

if TYPE_CHECKING:
    from tray_runner.gui import TrayCmdRunnerApp


class SettingsDialog(QDialog):
    """
    SettingsDialog class.
    """

    warning_label: QLabel

    log_level_combo_box: QComboBox
    create_app_menu_shortcut_checkbox: QCheckBox
    auto_start_checkbox: QCheckBox

    include_output_in_notifications_checkbox: QCheckBox
    show_complete_notifications_checkbox: QCheckBox
    show_error_notifications_checkbox: QCheckBox

    run_in_shell_checkbox: QCheckBox
    restart_on_exit_checkbox: QCheckBox
    restart_on_failure_checkbox: QCheckBox

    commands_list: QListWidget
    add_command_button: QPushButton
    edit_command_button: QPushButton
    show_command_logs_button: QPushButton
    delete_command_button: QPushButton

    def __init__(self, parent: QWidget, app: "TrayCmdRunnerApp", warning_style: Optional[int] = None, warning_text: Optional[str] = None):  # pylint: disable=too-many-statements
        """
        SettingsDialog constructor.
        """
        QDialog.__init__(self, parent)
        self.app = app
        load_ui(os.path.join(os.path.dirname(__file__), "settings_dialog.ui"), self)
        self.setWindowIcon(QIcon(REGULAR_ICON_PATH))
        self.setWindowTitle(gettext("{app_name} - Configuration").format(app_name=APP_NAME))
        if self.parentWidget().isVisible():
            # Center relative to parent
            geo = self.geometry()
            geo.moveCenter(self.parentWidget().geometry().center())
            self.setGeometry(geo)
        else:
            # Center in the screen
            center = QScreen.availableGeometry(QApplication.primaryScreen()).center()
            geo = self.frameGeometry()
            geo.moveCenter(center)
            self.setGeometry(geo)

        if warning_style:
            set_warning_style(self.warning_label, warning_style)

        if warning_text:
            self.warning_label.setText(warning_text)
        else:
            self.warning_label.hide()

        self.log_values = [
            ("DEBUG", "DEBUG"),
            ("INFO", "INFO"),
            ("WARNING", "WARNING"),
            ("ERROR", "ERROR"),
            ("CRITICAL", "CRITICAL"),
        ]
        for idx, (key, val) in enumerate(self.log_values):
            self.log_level_combo_box.addItem(val, key)
            if key == self.app.config.log_level.value:
                self.log_level_combo_box.setCurrentIndex(idx)
        self.log_level_combo_box.currentIndexChanged.connect(self.log_level_combo_box_changed)
        self.create_app_menu_shortcut_checkbox.setChecked(self.app.config.create_app_menu_shortcut)
        self.create_app_menu_shortcut_checkbox.stateChanged.connect(self.create_app_menu_shortcut_checkbox_changed)
        self.auto_start_checkbox.setChecked(self.app.config.auto_start)
        self.auto_start_checkbox.stateChanged.connect(self.auto_start_checkbox_changed)

        self.include_output_in_notifications_checkbox.setChecked(self.app.config.include_output_in_notifications)
        self.include_output_in_notifications_checkbox.stateChanged.connect(self.include_output_in_notifications_checkbox_changed)

        self.show_complete_notifications_checkbox.setChecked(self.app.config.show_complete_notifications)
        self.show_complete_notifications_checkbox.stateChanged.connect(self.show_complete_notifications_checkbox_changed)

        self.show_error_notifications_checkbox.setChecked(self.app.config.show_error_notifications)
        self.show_error_notifications_checkbox.stateChanged.connect(self.show_error_notifications_checkbox_changed)

        self.run_in_shell_checkbox.setChecked(self.app.config.run_in_shell)
        self.run_in_shell_checkbox.stateChanged.connect(self.run_in_shell_checkbox_changed)

        self.restart_on_exit_checkbox.setChecked(self.app.config.restart_on_exit)
        self.restart_on_exit_checkbox.stateChanged.connect(self.restart_on_exit_checkbox_changed)

        self.restart_on_failure_checkbox.setChecked(self.app.config.restart_on_failure)
        self.restart_on_failure_checkbox.stateChanged.connect(self.restart_on_failure_checkbox_changed)

        self.commands_list.currentItemChanged.connect(self.commands_list_item_changed)
        self.commands_list.itemDoubleClicked.connect(self.commands_list_item_double_clicked)
        self.update_commands_list()

        self.add_command_button.clicked.connect(self.add_command_button_clicked)
        self.edit_command_button.clicked.connect(self.edit_command_button_clicked)
        self.show_command_logs_button.clicked.connect(self.show_command_logs_button_clicked)
        self.delete_command_button.clicked.connect(self.delete_command_button_clicked)

        self.edit_command_button.setEnabled(False)
        self.show_command_logs_button.setEnabled(False)
        self.delete_command_button.setEnabled(False)

    def update_commands_list(self):
        """
        Function that clears and re-inserts the elements in the list.
        """
        self.commands_list.clear()
        for command in sorted(self.app.config.commands, key=lambda x: x.name.lower()):
            item = QListWidgetItem(command.name)
            font = item.font()
            if not command.disabled:
                font.setBold(True)
                item.setFont(font)
            self.commands_list.addItem(item)

    def log_level_combo_box_changed(self):
        """
        Saves the config for the log level option.
        """
        log_level_name = self.log_values[self.log_level_combo_box.currentIndex()][0]
        self.app.config.log_level = LogLevelEnum[log_level_name]
        self.app.save_config()
        logging.getLogger(tray_runner.__name__).setLevel(log_level_name)

    def create_app_menu_shortcut_checkbox_changed(self):
        """
        Saves the config for the create app menu shortcut option.
        """
        self.app.config.create_app_menu_shortcut = self.create_app_menu_shortcut_checkbox.isChecked()
        self.app.save_config()
        if self.app.config.create_app_menu_shortcut:
            create_tray_runner_app_menu_launcher()
        else:
            remove_app_menu_shortcut(APP_NAME)

    def auto_start_checkbox_changed(self):
        """
        Saves the config for the auto-start option.
        """
        self.app.config.auto_start = self.auto_start_checkbox.isChecked()
        self.app.save_config()
        if self.app.config.auto_start:
            create_tray_runner_autostart_shortcut()
        else:
            remove_app_menu_shortcut(APP_NAME, autostart=True)

    def include_output_in_notifications_checkbox_changed(self):
        """
        Function called when the checkbox changes its state.
        """
        self.app.config.include_output_in_notifications = self.include_output_in_notifications_checkbox.isChecked()
        self.app.save_config()

    def show_complete_notifications_checkbox_changed(self):
        """
        Function called when the checkbox changes its state.
        """
        self.app.config.show_complete_notifications = self.show_complete_notifications_checkbox.isChecked()
        self.app.save_config()

    def show_error_notifications_checkbox_changed(self):
        """
        Function called when the checkbox changes its state.
        """
        self.app.config.show_error_notifications = self.show_error_notifications_checkbox.isChecked()
        self.app.save_config()

    def run_in_shell_checkbox_changed(self):
        """
        Function called when the checkbox changes its state.
        """
        self.app.config.run_in_shell = self.run_in_shell_checkbox.isChecked()
        self.app.save_config()

    def restart_on_exit_checkbox_changed(self):
        """
        Function called when the checkbox changes its state.
        """
        self.app.config.restart_on_exit = self.restart_on_exit_checkbox.isChecked()
        self.app.save_config()

    def restart_on_failure_checkbox_changed(self):
        """
        Function called when the checkbox changes its state.
        """
        self.app.config.restart_on_failure = self.restart_on_failure_checkbox.isChecked()
        self.app.save_config()

    def commands_list_item_changed(self, current: QListWidgetItem, _previous: QListWidgetItem):
        """
        Function called when the selected item in the command list has changed.
        """
        self.edit_command_button.setEnabled(bool(current))
        self.show_command_logs_button.setEnabled(bool(current))
        self.delete_command_button.setEnabled(bool(current))

    def commands_list_item_double_clicked(self, item: QListWidgetItem):
        """
        Function called when an item in the command list is double-clicked, to edit it.
        """
        idx = self.commands_list.indexFromItem(item).row()
        command = self.app.config.get_command_by_name(item.text())
        if command:
            command_dialog = CommandDialog(self, self.app, command)
            if command_dialog.exec():
                # Start the process
                if command.disabled:
                    self.app.stop_command_thread(command)
                else:
                    self.app.start_command_thread(command)
                # Save the configuration
                self.app.save_config()
                # Update the list of commands in UI
                self.update_commands_list()
                # Restore the selected index
                self.commands_list.setCurrentRow(idx)
                # Update the application menu and status
                self.app.update_status()
            command_dialog.destroy()

    def add_command_button_clicked(self):
        """
        Function called when the add button is clicked.
        """
        command = ConfigCommand(id="", name="", command="")
        command_dialog = CommandDialog(self, self.app, command, True)
        if command_dialog.exec():
            # Start the process
            if not command.disabled:
                self.app.start_command_thread(command)
            # Add the new command to the configuration commands list
            self.app.config.commands.append(command)
            # Save the configuration
            self.app.save_config()
            # Update the list of commands in UI
            self.update_commands_list()
            # Restore the selected index
            self.commands_list.setCurrentRow(list(sorted(self.app.config.commands, key=lambda x: x.name.lower())).index(command))
            # Update the application menu and status
            self.app.update_status()
        command_dialog.destroy()

    def edit_command_button_clicked(self):
        """
        Function called when the edit button is clicked.
        """
        selected_items = self.commands_list.selectedItems()
        if selected_items:
            self.commands_list_item_double_clicked(selected_items[0])

    def show_command_logs_button_clicked(self):
        """
        Function called when the show logs button is clicked.
        """
        selected_items = self.commands_list.selectedItems()
        if selected_items:
            command = self.app.config.get_command_by_name(selected_items[0].text())
            log_path = command.get_log_file_path()
            if not os.path.exists(log_path):
                QMessageBox.warning(self, gettext("No logs available"), gettext("This command doesn't have generated logs yet."))
            else:
                click.launch(log_path)

    def delete_command_button_clicked(self):
        """
        Function called when the delete button is clicked.
        """

        selected_items = self.commands_list.selectedItems()
        if selected_items:

            command = self.app.config.get_command_by_name(selected_items[0].text())
            if QMessageBox.question(self, gettext("Delete command"), gettext('Are you sure that you want to delete the command "{command_name}"?').format(command_name=command.name)):

                # pylint: disable=pointless-string-statement
                """
                progress_dialog = QMessageBox(QMessageBox.Icon.NoIcon, gettext("Deleting command..."), gettext("Deleting command..."), buttons=QMessageBox.StandardButton.Ok, parent=self)
                progress_dialog.setIconPixmap(QPixmap(SPINNER_ICON_PATH))
                for button in progress_dialog.buttons():
                    progress_dialog.removeButton(button)
                progress_dialog.show()

                # Stop command thread
                progress_dialog.setText(gettext("Stopping command..."))
                self.app.stop_command_thread(command)
                time.sleep(2)

                # Remove command from configuration
                progress_dialog.setText(gettext("Removing from configuration..."))
                time.sleep(2)
                # TODO

                # Save configuration
                progress_dialog.setText(gettext("Saving configuration..."))
                self.app.save_config()
                time.sleep(2)

                progress_dialog.hide()
                progress_dialog.destroy()
                """
                # Stop command thread
                self.app.stop_command_thread(command)
                # Remove command from configuration
                self.app.config.commands.remove(command)
                # Save configuration
                self.app.save_config()
                # Update commands list
                self.update_commands_list()
                # Update the application menu and status
                self.app.update_status()
