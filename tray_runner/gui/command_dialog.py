"""
tray_runner.gui.settings modules.
"""
import os
import uuid
from gettext import gettext
from typing import TYPE_CHECKING, Optional

from babel.dates import format_datetime
from babel.numbers import format_decimal
from croniter import croniter
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFileDialog, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTableView, QTabWidget, QWidget
from slugify import slugify

from tray_runner.common_utils.common import ensure_local_datetime, get_simple_default_locale
from tray_runner.common_utils.qt import checkbox_tristate_from_val, checkbox_tristate_to_val, load_ui
from tray_runner.config import ConfigCommand, ConfigCommandEnvironmentVariable, ConfigCommandRunMode

if TYPE_CHECKING:
    from tray_runner.gui import TrayCmdRunnerApp


class CommandDialog(QDialog):
    """
    CommandDialog class.
    """

    tabs: QTabWidget

    id_text_box: QLineEdit
    name_text_box: QLineEdit
    description_text_box: QPlainTextEdit
    command_text_box: QLineEdit
    working_directory_choose_button: QPushButton
    working_directory_text_box: QLineEdit
    max_log_count_spin_box: QSpinBox
    disabled_checkbox: QCheckBox

    run_at_startup_check_box: QCheckBox
    run_at_startup_if_missing_previous_run_check_box: QCheckBox
    run_mode_combo_box: QComboBox
    seconds_between_executions_label: QLabel
    seconds_between_executions_spin_box: QSpinBox
    cron_expr_label: QLabel
    cron_expr_text_box: QLineEdit

    run_in_shell_checkbox: QCheckBox
    restart_on_exit_checkbox: QCheckBox
    restart_on_failure_checkbox: QCheckBox

    include_output_in_notifications_checkbox: QCheckBox
    show_complete_notifications_checkbox: QCheckBox
    show_error_notifications_checkbox: QCheckBox

    environment_table: QTableView

    script_text_box: QPlainTextEdit
    run_script_powershell_check_box: QCheckBox

    total_runs_label: QLabel
    ok_runs_label: QLabel
    error_runs_label: QLabel
    failed_runs_label: QLabel
    last_run_dt_label: QLabel
    next_run_dt_label: QLabel
    last_run_exit_code_label: QLabel
    last_successful_run_dt_label: QLabel
    last_duration_label: QLabel
    min_duration_label: QLabel
    max_duration_label: QLabel
    avg_duration_label: QLabel

    def __init__(self, parent: QWidget, app: "TrayCmdRunnerApp", command: ConfigCommand, is_new: Optional[bool] = False):  # pylint: disable=too-many-statements,too-many-branches
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
        if self.command.command:
            self.command_text_box.setText(self.command.command)
        if self.command.script:
            self.script_text_box.setPlainText(self.command.script)
        self.run_script_powershell_check_box.setChecked(self.command.run_script_powershell)
        self.working_directory_text_box.setText(self.command.working_directory)
        self.working_directory_choose_button.clicked.connect(self.working_directory_choose_button_clicked)
        self.max_log_count_spin_box.setValue(self.command.max_log_count)
        self.disabled_checkbox.setChecked(self.command.disabled)

        self.run_at_startup_check_box.setChecked(self.command.run_at_startup)
        self.run_at_startup_if_missing_previous_run_check_box.setChecked(self.command.run_at_startup_if_missing_previous_run)
        self.run_mode_combo_box.currentIndexChanged.connect(self.on_run_mode_combo_box_currentIndexChanged)
        for idx, data in enumerate(ConfigCommandRunMode):
            self.run_mode_combo_box.addItem(data.display_name(), data.value)
            if data.value == self.command.run_mode.value:
                self.run_mode_combo_box.setCurrentIndex(idx)
        self.run_mode_combo_box.currentIndexChanged.connect(self.on_run_mode_combo_box_currentIndexChanged)
        self.seconds_between_executions_spin_box.setValue(self.command.seconds_between_executions)
        if self.command.cron_expr:
            self.cron_expr_text_box.setText(self.command.cron_expr)

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

        self.total_runs_label.setText(format_decimal(self.command.total_runs, locale=get_simple_default_locale()))
        self.ok_runs_label.setText(format_decimal(self.command.ok_runs, locale=get_simple_default_locale()))
        self.error_runs_label.setText(format_decimal(self.command.error_runs, locale=get_simple_default_locale()))
        self.failed_runs_label.setText(format_decimal(self.command.failed_runs, locale=get_simple_default_locale()))
        self.last_run_dt_label.setText(format_datetime(ensure_local_datetime(self.command.last_run_dt), locale=get_simple_default_locale()) if self.command.last_run_dt else gettext("Never"))
        if self.is_new:
            self.next_run_dt_label.setText(gettext("Unknown"))
        elif self.command.disabled:
            self.next_run_dt_label.setText(gettext("Never (command disabled)"))
        else:
            next_run_dt = self.command.get_next_execution_dt()
            if next_run_dt:
                self.next_run_dt_label.setText(format_datetime(ensure_local_datetime(next_run_dt), locale=get_simple_default_locale()))
            else:
                self.next_run_dt_label.setText(gettext("Unknown"))
        self.last_run_exit_code_label.setText(str(self.command.last_run_exit_code) if self.command.last_run_exit_code is not None else gettext("Unknown"))
        self.last_successful_run_dt_label.setText(format_datetime(ensure_local_datetime(self.command.last_successful_run_dt), locale=get_simple_default_locale()) if self.command.last_successful_run_dt else gettext("Never"))
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

    def on_run_mode_combo_box_currentIndexChanged(self):
        """
        Hides/SHows related fields when the run mode combo box changes.
        """
        self.seconds_between_executions_label.hide()
        self.seconds_between_executions_spin_box.hide()
        self.cron_expr_label.hide()
        self.cron_expr_text_box.hide()
        if ConfigCommandRunMode[self.run_mode_combo_box.currentData()] == ConfigCommandRunMode.PERIOD:
            self.seconds_between_executions_label.show()
            self.seconds_between_executions_spin_box.show()
        elif ConfigCommandRunMode[self.run_mode_combo_box.currentData()] == ConfigCommandRunMode.CRON:
            self.cron_expr_label.show()
            self.cron_expr_text_box.show()

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
                    self.tabs.setCurrentIndex(0)
                    self.id_text_box.setFocus()
                    return
                for command in self.app.config.commands:
                    if slugify(command.id) == slugify(id_val):
                        QMessageBox.warning(self, gettext("Validation error"), gettext("There is another command with the same ID."))
                        self.tabs.setCurrentIndex(0)
                        self.id_text_box.setFocus()
                        return
                new_id_val = id_val
            else:
                new_id_val = str(uuid.uuid4())

        # Check non-empty name
        if not self.name_text_box.text():
            QMessageBox.warning(self, gettext("Validation error"), gettext("Name can't be empty."))
            self.tabs.setCurrentIndex(0)
            self.name_text_box.setFocus()
            return

        # Check if the name it is not already being used
        new_name = self.name_text_box.text()
        for loop_command in self.app.config.commands:
            if loop_command != self.command:
                if loop_command.name.lower() == new_name.lower():
                    QMessageBox.warning(self, gettext("Validation error"), gettext("There is another command with the same name."))
                    self.tabs.setCurrentIndex(0)
                    self.name_text_box.setFocus()
                    return

        command = self.command_text_box.text()
        script = self.script_text_box.toPlainText()
        if command and script:
            QMessageBox.warning(self, gettext("Validation error"), gettext("Only the command or the script can be set."))
            self.tabs.setCurrentIndex(0)
            self.command_text_box.setFocus()
            return

        if not command and not script:
            QMessageBox.warning(self, gettext("Validation error"), gettext("Command or script must be set."))
            self.tabs.setCurrentIndex(0)
            self.command_text_box.setFocus()
            return

        # Check working directory exists
        working_directory = self.working_directory_text_box.text()
        if working_directory:
            if not os.path.exists(working_directory):
                if QMessageBox.question(self, gettext("Validation error"), gettext("Directory {working_directory} doesn't exist. Are you sure you want to use it? During execution, if this directory doesn't exist, the current user home directory will be used.").format(working_directory=working_directory)) != QMessageBox.StandardButton.Yes:
                    return

        # Check cron expr
        run_mode = ConfigCommandRunMode[self.run_mode_combo_box.currentData()]
        period = self.seconds_between_executions_spin_box.value()
        cron_expr = self.cron_expr_text_box.text()
        if run_mode == ConfigCommandRunMode.CRON:
            if not cron_expr:
                QMessageBox.warning(self, gettext("Validation error"), gettext("The cron expression can't be empty."))
                self.tabs.setCurrentIndex(0)
                self.cron_expr_text_box.setFocus()
                return
            if not croniter.is_valid(cron_expr):
                QMessageBox.warning(self, gettext("Validation error"), gettext("The cron expression is not valid."))
                self.tabs.setCurrentIndex(0)
                self.cron_expr_text_box.setFocus()
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
        if command:
            self.command.command = command
        if script:
            self.command.script = script
        self.command.run_script_powershell = self.run_script_powershell_check_box.isChecked()
        self.command.working_directory = working_directory
        self.command.max_log_count = self.max_log_count_spin_box.value()
        self.command.disabled = self.disabled_checkbox.isChecked()

        self.command.run_at_startup = self.run_at_startup_check_box.isChecked()
        self.command.run_at_startup_if_missing_previous_run = self.run_at_startup_if_missing_previous_run_check_box.isChecked()
        self.command.run_mode = run_mode
        self.command.seconds_between_executions = period
        self.command.cron_expr = cron_expr
        self.command.next_run_dt = self.command.get_next_execution_dt()

        self.command.run_in_shell = checkbox_tristate_to_val(self.run_in_shell_checkbox.checkState())
        self.command.restart_on_exit = checkbox_tristate_to_val(self.restart_on_exit_checkbox.checkState())
        self.command.restart_on_failure = checkbox_tristate_to_val(self.restart_on_failure_checkbox.checkState())
        self.command.include_output_in_notifications = checkbox_tristate_to_val(self.include_output_in_notifications_checkbox.checkState())
        self.command.show_complete_notifications = checkbox_tristate_to_val(self.show_complete_notifications_checkbox.checkState())
        self.command.show_error_notifications = checkbox_tristate_to_val(self.show_error_notifications_checkbox.checkState())

        self.command.environment = new_environment

        super().accept()
