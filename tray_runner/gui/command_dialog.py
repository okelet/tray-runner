"""
tray_runner.gui.settings modules.
"""
import os
import uuid
from gettext import gettext
from typing import TYPE_CHECKING, Optional

import pytz
from babel.dates import format_datetime
from babel.numbers import format_decimal
from dateutil.tz import tzlocal
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QCheckBox, QDialog, QFileDialog, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTableView, QWidget
from slugify import slugify

from tray_runner.common_utils.common import get_simple_default_locale
from tray_runner.common_utils.qt import checkbox_tristate_from_val, checkbox_tristate_to_val, load_ui
from tray_runner.config import ConfigCommand, ConfigCommandEnvironmentVariable

if TYPE_CHECKING:
    from tray_runner.gui import TrayCmdRunnerApp


class CommandDialog(QDialog):
    """
    CommandDialog class.
    """

    id_text_box: QLineEdit
    name_text_box: QLineEdit
    description_text_box: QPlainTextEdit
    command_text_box: QLineEdit
    working_directory_choose_button: QPushButton
    working_directory_text_box: QLineEdit
    max_log_count_spin_box: QSpinBox
    seconds_between_executions_spin_box: QSpinBox
    disabled_checkbox: QCheckBox

    run_in_shell_checkbox: QCheckBox
    restart_on_exit_checkbox: QCheckBox
    restart_on_failure_checkbox: QCheckBox

    include_output_in_notifications_checkbox: QCheckBox
    show_complete_notifications_checkbox: QCheckBox
    show_error_notifications_checkbox: QCheckBox

    environment_table: QTableView

    total_runs_label: QLabel
    ok_runs_label: QLabel
    error_runs_label: QLabel
    failed_runs_label: QLabel
    last_run_dt_label: QLabel
    last_run_exit_code_label: QLabel
    last_successful_run_dt_label: QLabel
    last_duration_label: QLabel
    min_duration_label: QLabel
    max_duration_label: QLabel
    avg_duration_label: QLabel

    def __init__(self, parent: QWidget, app: "TrayCmdRunnerApp", command: ConfigCommand, is_new: Optional[bool] = False):  # pylint: disable=too-many-statements
        """
        CommandDialog constructor.
        """
        super().__init__(parent)
        self.app = app
        self.command = command
        self.is_new = is_new
        load_ui(os.path.join(os.path.dirname(__file__), "command_dialog.ui"), self)

        # Center relative to parent
        geo = self.geometry()
        geo.moveCenter(self.parentWidget().geometry().center())
        self.setGeometry(geo)

        self.id_text_box.setText(self.command.id)
        if is_new:
            self.id_text_box.setEnabled(True)
        self.name_text_box.setText(self.command.name)
        if self.command.description:
            self.description_text_box.setPlainText(self.command.description)
        self.command_text_box.setText(self.command.command)
        self.command_text_box.setText(self.command.command)
        self.working_directory_text_box.setText(self.command.working_directory)
        self.working_directory_choose_button.clicked.connect(self.working_directory_choose_button_clicked)
        self.max_log_count_spin_box.setValue(self.command.max_log_count)
        self.seconds_between_executions_spin_box.setValue(self.command.seconds_between_executions)
        self.disabled_checkbox.setChecked(self.command.disabled)

        self.run_in_shell_checkbox.setCheckState(checkbox_tristate_from_val(self.command.run_in_shell))
        self.restart_on_exit_checkbox.setCheckState(checkbox_tristate_from_val(self.command.restart_on_exit))
        self.restart_on_failure_checkbox.setCheckState(checkbox_tristate_from_val(self.command.restart_on_failure))
        self.include_output_in_notifications_checkbox.setCheckState(checkbox_tristate_from_val(self.command.include_output_in_notifications))
        self.show_complete_notifications_checkbox.setCheckState(checkbox_tristate_from_val(self.command.show_complete_notifications))
        self.show_error_notifications_checkbox.setCheckState(checkbox_tristate_from_val(self.command.show_error_notifications))

        self.environment_table_model = QStandardItemModel()
        self.environment_table_model.setHorizontalHeaderLabels([gettext("Key"), gettext("Value")])
        self.environment_table.setModel(self.environment_table_model)
        self.environment_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.environment_table.customContextMenuRequested.connect(self.environment_table_menu)
        for env in sorted(self.command.environment, key=lambda x: x.key.lower()):
            self.environment_table_model.appendRow((QStandardItem(env.key), QStandardItem(env.value)))

        header = self.environment_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        local_tz = tzlocal()
        self.total_runs_label.setText(format_decimal(self.command.total_runs, locale=get_simple_default_locale()))
        self.ok_runs_label.setText(format_decimal(self.command.ok_runs, locale=get_simple_default_locale()))
        self.error_runs_label.setText(format_decimal(self.command.error_runs, locale=get_simple_default_locale()))
        self.failed_runs_label.setText(format_decimal(self.command.failed_runs, locale=get_simple_default_locale()))
        self.last_run_dt_label.setText(format_datetime(self.command.last_run_dt.replace(tzinfo=pytz.UTC).astimezone(local_tz), locale=get_simple_default_locale()) if self.command.last_run_dt else gettext("Never"))
        self.last_run_exit_code_label.setText(str(self.command.last_run_exit_code) if self.command.last_run_exit_code is not None else gettext("Unknown"))
        self.last_successful_run_dt_label.setText(format_datetime(self.command.last_successful_run_dt.replace(tzinfo=pytz.UTC).astimezone(local_tz), locale=get_simple_default_locale()) if self.command.last_successful_run_dt else gettext("Never"))
        self.last_duration_label.setText(gettext("{seconds} seconds").format(seconds=format_decimal(self.command.last_duration, locale=get_simple_default_locale())) if self.command.last_duration is not None else gettext("Unknown"))
        self.min_duration_label.setText(gettext("{seconds} seconds").format(seconds=format_decimal(self.command.min_duration, locale=get_simple_default_locale())) if self.command.min_duration is not None else gettext("Unknown"))
        self.max_duration_label.setText(gettext("{seconds} seconds").format(seconds=format_decimal(self.command.max_duration, locale=get_simple_default_locale())) if self.command.max_duration is not None else gettext("Unknown"))
        self.avg_duration_label.setText(gettext("{seconds} seconds").format(seconds=format_decimal(self.command.avg_duration, locale=get_simple_default_locale())) if self.command.avg_duration is not None else gettext("Unknown"))

        if self.is_new:
            self.id_text_box.setFocus()
            self.setWindowTitle(gettext("Add new command"))
        else:
            self.name_text_box.setFocus()
            self.setWindowTitle(gettext("Edit command {command_name}").format(command_name=self.command.name))

    def working_directory_choose_button_clicked(self):
        """
        Shows a dialog to select the working directory.
        """
        current_dir = self.working_directory_text_box.text()
        if not current_dir:
            current_dir = os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(self, gettext("Select directory"), current_dir)
        if chosen:
            self.working_directory_text_box.setText(chosen)

    def environment_table_menu(self):
        """
        Displays the menu to add and remove rows in the environment variables table.
        """
        menu = QMenu()
        menu.addAction(gettext("Add variable"), self.environment_table_add_row)
        selected = self.environment_table.selectedIndexes()
        if selected:
            menu.addAction(gettext("Delete variable"), lambda: self.environment_table_remove_rows(selected))
        menu.exec_(QCursor.pos())

    def environment_table_remove_rows(self, indexes):
        """
        Removes the rows from the environment variables table.
        """
        rows = set(index.row() for index in indexes)
        for row in sorted(rows, reverse=True):
            self.environment_table_model.removeRow(row)

    def environment_table_add_row(self):
        """
        Adds a new row to the environment variables table.
        """
        self.environment_table_model.appendRow((QStandardItem(""), QStandardItem("")))

    def accept(self):  # pylint: disable=too-many-statements,too-many-branches,too-many-return-statements
        """
        Function executed when the OK button is clicked. Performs all data validation and updates command configuration according to the form.
        """
        # If the command is new, check that the ID is valid and not already being used
        new_id_val = None
        if self.is_new:
            id_val = self.id_text_box.text()
            if id_val:
                if slugify(id_val) != id_val:
                    QMessageBox.warning(self, gettext("Validation error"), gettext("The ID is not valid (can only contain lowercase numbers and letters, and hyphens)."))
                    self.id_text_box.setFocus()
                    return
                for command in self.app.config.commands:
                    if slugify(command.id) == slugify(id_val):
                        QMessageBox.warning(self, gettext("Validation error"), gettext("There is another command with the same ID."))
                        self.id_text_box.setFocus()
                        return
                new_id_val = id_val
            else:
                new_id_val = str(uuid.uuid4())

        # Check non-empty name
        if not self.name_text_box.text():
            QMessageBox.warning(self, gettext("Validation error"), gettext("Name can't be empty."))
            self.name_text_box.setFocus()
            return

        # Check if the name it is not already being used
        new_name = self.name_text_box.text()
        for loop_command in self.app.config.commands:
            if loop_command != self.command:
                if loop_command.name.lower() == new_name.lower():
                    QMessageBox.warning(self, gettext("Validation error"), gettext("There is another command with the same name."))
                    self.name_text_box.setFocus()
                    return

        # Check non-empty command
        if not self.command_text_box.text():
            QMessageBox.warning(self, gettext("Validation error"), gettext("Command can't be empty."))
            self.command_text_box.setFocus()
            return

        # Check working directory exists
        working_directory = self.working_directory_text_box.text()
        if working_directory:
            if not os.path.exists(working_directory):
                if QMessageBox.question(self, gettext("Validation error"), gettext("Directory {working_directory} doesn't exist. Are you sure you want to use it? During execution, if this directory doesn't exist, the current user home directory will be used.").format(working_directory=working_directory)) != QMessageBox.StandardButton.Yes:
                    return

        # Configure environment variables
        new_environment = []
        for index in range(self.environment_table_model.rowCount()):
            key = self.environment_table_model.item(index, 0).text()
            value = self.environment_table_model.item(index, 1).text()
            if key or value:
                if not key and value:
                    QMessageBox.warning(self, gettext("Validation error"), gettext("The key for the environment variable with ID {idx} is empty.").format(idx=index + 1))
                    return
                new_environment.append(ConfigCommandEnvironmentVariable(key=key, value=value))

        # Fill command object data
        if self.is_new:
            self.command.id = new_id_val
        self.command.name = new_name
        self.command.description = self.description_text_box.toPlainText().strip() if self.description_text_box.toPlainText().strip() else None
        self.command.command = self.command_text_box.text()
        self.command.working_directory = working_directory
        self.command.max_log_count = self.max_log_count_spin_box.value()
        self.command.seconds_between_executions = self.seconds_between_executions_spin_box.value()
        self.command.disabled = self.disabled_checkbox.isChecked()

        self.command.run_in_shell = checkbox_tristate_to_val(self.run_in_shell_checkbox.checkState())
        self.command.restart_on_exit = checkbox_tristate_to_val(self.restart_on_exit_checkbox.checkState())
        self.command.restart_on_failure = checkbox_tristate_to_val(self.restart_on_failure_checkbox.checkState())
        self.command.include_output_in_notifications = checkbox_tristate_to_val(self.include_output_in_notifications_checkbox.checkState())
        self.command.show_complete_notifications = checkbox_tristate_to_val(self.show_complete_notifications_checkbox.checkState())
        self.command.show_error_notifications = checkbox_tristate_to_val(self.show_error_notifications_checkbox.checkState())

        self.command.environment = new_environment

        super().accept()
