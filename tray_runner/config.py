"""
tray_runner.config module.
"""
import json
import logging
import os
import shlex
import shutil
import sys
import uuid
from datetime import datetime, timedelta
from enum import Enum
from gettext import gettext
from typing import Dict, List, Optional, Tuple

import click
import pytz
from croniter import croniter
from flask_babel import lazy_gettext
from pydantic import BaseModel, Field
from slugify import slugify

from tray_runner import APP_DIR, DEFAULT_CONFIG_FILE
from tray_runner.common_utils.common import YesNoDefault, ensure_local_datetime

LOG = logging.getLogger(__name__)


class ConfigCommandExecutionStatus(str, Enum):

    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    RUN = "RUN"

    def display_name(self):
        """
        Returns a friendly display name.
        """
        return {
            self.RUNNING.value: lazy_gettext("Running"),
            self.STOPPED.value: lazy_gettext("Stopped"),
            self.FAILED.value: lazy_gettext("Failed"),
            self.RUN.value: lazy_gettext("Run"),
        }.get(self.value, self.value)


class ConfigCommandExecutionResult(BaseModel):  # pylint: disable=too-few-public-methods
    """
    ConfigCommandLog class.
    """

    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: ConfigCommandExecutionStatus
    start_time: datetime
    end_time: Optional[datetime]
    pid: Optional[int]
    exit_code: Optional[int]
    stdout: Optional[str]
    stderr: Optional[str]
    fail_message: Optional[str]
    stack_trace: Optional[str]

    @property
    def duration(self):
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def status_color(self) -> str:
        if self.status == ConfigCommandExecutionStatus.RUNNING:
            return "info"
        if self.status == ConfigCommandExecutionStatus.FAILED:
            return "danger"
        if self.status in [ConfigCommandExecutionStatus.STOPPED, ConfigCommandExecutionStatus.RUN]:
            if self.exit_code == 0:
                return "success"
            return "danger"
        return "default"


class ConfigCommandLog(BaseModel):  # pylint: disable=too-few-public-methods
    """
    Class to store command logs.
    """

    version: Optional[int]
    items: List[ConfigCommandExecutionResult] = Field(default=[])


class ConfigCommandEnvironmentVariable(BaseModel):  # pylint: disable=too-few-public-methods
    """
    Class to store command environment variables.
    """

    key: str
    value: str


class ConfigCommandRunMode(str, Enum):
    """
    Class to enumerate the log levels.
    """

    COMMAND = "COMMAND"
    SCRIPT = "SCRIPT"

    def display_name(self):
        """
        Returns a friendly display name.
        """
        return {
            self.COMMAND.value: lazy_gettext("Command"),
            self.SCRIPT.value: lazy_gettext("Script"),
        }.get(self.value, self.value)


class ConfigCommandScheduleMode(str, Enum):
    """
    Class to enumerate the log levels.
    """

    PERIOD = "PERIOD"
    CRON = "CRON"
    APP_START = "APP_START"
    SYSTEM_START = "SYSTEM_START"
    MANUAL = "MANUAL"

    def display_name(self):
        """
        Returns a friendly display name.
        """
        return {
            self.PERIOD.value: lazy_gettext("Period"),
            self.CRON.value: lazy_gettext("Cron"),
            self.APP_START.value: lazy_gettext("Application startup"),
            self.SYSTEM_START.value: lazy_gettext("System startup"),
            self.MANUAL.value: lazy_gettext("Manual"),
        }.get(self.value, self.value)


class MessageCategory(str, Enum):
    """
    Class to enumerate the log levels.
    """

    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


class CommandWarning(BaseModel):
    category: MessageCategory
    message: str


class ConfigCommandInput(BaseModel):
    """
    ConfigCommandInput class.
    """
    name: str = Field()
    description: Optional[str] = Field(default="")
    disabled: bool = Field(default=False)
    max_log_count: int = Field(default=100)

    working_directory: str = Field(default=os.path.expanduser("~"))
    run_mode: ConfigCommandRunMode = Field(default=ConfigCommandRunMode.COMMAND)
    command: Optional[str] = Field(default="")
    script_interpreter: str = Field(default="powershell")
    script: Optional[str] = Field(default="")

    run_at_startup: bool = Field(default=False)
    run_at_startup_if_missing_previous_run: bool = Field(default=False)
    schedule_mode: ConfigCommandScheduleMode = Field(default=ConfigCommandScheduleMode.PERIOD)
    period_seconds: int = Field(default=600)
    cron_expr: Optional[str] = Field(default="")
    startup_delay_seconds: int = Field(default=0)

    run_in_shell: YesNoDefault = Field(default=YesNoDefault.DEFAULT)
    include_output_in_notifications: YesNoDefault = Field(default=YesNoDefault.DEFAULT)
    show_complete_notifications: YesNoDefault = Field(default=YesNoDefault.DEFAULT)
    show_error_notifications: YesNoDefault = Field(default=YesNoDefault.DEFAULT)

    environment: List[ConfigCommandEnvironmentVariable] = Field(default=[])


class ConfigCommand(ConfigCommandInput):
    """
    ConfigCommand class.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    total_runs: int = Field(default=0)
    ok_runs: int = Field(default=0, description="When a run has returned an exit code 0.")
    error_runs: int = Field(default=0, description="When a run was OK, but returned an exit code different that 0.")
    failed_runs: int = Field(default=0, description="When a run threw an error.")

    last_successful_run_dt: Optional[datetime]
    last_error_run_dt: Optional[datetime]
    last_fail_run_dt: Optional[datetime]

    min_duration: Optional[float]
    max_duration: Optional[float]
    avg_duration: Optional[float]

    next_run_dt: Optional[datetime] = Field(exclude=True)

    @property
    def last_status(self) -> Optional[ConfigCommandExecutionResult]:
        logs = self.get_logs()
        if logs.items:
            logs = sorted(logs.items, key=lambda x: x.start_dt, reverse=True)
            return logs[0]
        return None

    @property
    def current_status(self) -> Optional[ConfigCommandExecutionResult]:
        logs = self.get_logs()
        if logs.items:
            logs = sorted(logs.items, key=lambda x: x.start_dt, reverse=True)
            last_log = logs[0]
            if last_log.status == ConfigCommandExecutionStatus.RUNNING:
                return last_log
        return None

    @property
    def status_color(self) -> str:
        if self.current_status:
            return self.current_status.status_color
        elif self.last_status:
            return self.last_status.status_color
        else:
            return "default"

    def get_next_execution_dt(self, start_date: Optional[datetime] = None) -> Optional[datetime]:
        """
        Get the command's next execution date/time, according to its status and schedule mode.
        """
        if self.disabled:
            return None

        now = datetime.utcnow()
        if start_date is None and self.last_status:
            start_date = self.last_status.start_time

        if self.schedule_mode == ConfigCommandScheduleMode.PERIOD:
            if start_date is None:
                return now
            next_dt = start_date + timedelta(seconds=self.period_seconds)
            while next_dt < now:
                # Find a moment in the future
                next_dt = next_dt + timedelta(seconds=self.period_seconds)
            return next_dt

        if self.schedule_mode == ConfigCommandScheduleMode.CRON:

            # Get the next cron schedule based on the system timezone (offset-aware)
            # But return it as UTC, removing the timezone info (offset-naive) so it can be compared using datetime.utcnow()
            if self.cron_expr:
                if start_date is None:
                    start_date = now
                next_dt = croniter(self.cron_expr).get_next(ret_type=datetime, start_time=ensure_local_datetime(start_date)).astimezone(pytz.UTC).replace(tzinfo=None)
                while next_dt < now:
                    # Find a moment in the future
                    next_dt = croniter(self.cron_expr).get_next(ret_type=datetime, start_time=ensure_local_datetime(next_dt)).astimezone(pytz.UTC).replace(tzinfo=None)
                return next_dt
            raise Exception(f"Command schedule mode is {self.schedule_mode.value}, but no cron_expr set.")

        raise Exception(f"Invalid schedule mode: {self.schedule_mode}.")

    def environment_as_dict(self) -> Dict[str, str]:
        """
        Converts the command environment variables object to a dictionary.
        """
        env = {}
        if self.environment:
            for item in self.environment:
                env[item.key] = item.value
        return env

    def get_log_file_path(self):
        """
        Returns the path to the log file corresponding to this command.
        """
        return os.path.join(APP_DIR, "logs", f"{slugify(self.id)}.log.json")

    def set_execution_results(self, item: ConfigCommandExecutionResult):
        """
        Set the command variables to the last execution result.
        """
        # Set command status
        self.total_runs += 1
        if item.status == ConfigCommandExecutionStatus.FAILED:
            self.failed_runs += 1
            self.last_fail_run_dt = item.start_time
        elif item.status == ConfigCommandExecutionStatus.RUN:
            if item.exit_code == 0:
                self.ok_runs += 1
                self.last_successful_run_dt = item.start_time
                if self.max_duration is None or item.duration > self.max_duration:
                    self.max_duration = item.duration
                if self.min_duration is None or item.duration < self.min_duration:
                    self.min_duration = item.duration
                if self.avg_duration is not None:
                    self.avg_duration = ((self.avg_duration * self.ok_runs) + item.duration) / (self.ok_runs + 1)
                else:
                    self.avg_duration = item.duration
            else:
                self.error_runs += 1
                self.last_error_run_dt = item.start_time

    def get_logs(self) -> ConfigCommandLog:

        # List of current logs, empty if no log file exists yet
        logs = ConfigCommandLog()

        # Read current logs
        if os.path.exists(self.get_log_file_path()):
            try:
                with click.open_file(self.get_log_file_path(), "r") as file_obj:
                    json_object = json.load(file_obj)
                    if json_object:
                        # Migrate from v0 to v1:
                        if not json_object.get("version"):
                            json_object["version"] = 1
                            if json_object.get("items"):
                                for log in json_object.get("items"):
                                    if log.get("duration"):
                                        del log["duration"]
                                    if log.get("fail_message"):
                                        log["status"] = ConfigCommandExecutionStatus.FAILED.value
                                    elif log.get("aborted"):
                                        del log["aborted"]
                                        log["status"] = ConfigCommandExecutionStatus.FAILED.value
                                        log["fail_message"] = "Aborted"
                                    else:
                                        log["status"] = ConfigCommandExecutionStatus.RUN.value
                        logs = ConfigCommandLog(**json_object)
            except Exception as ex:  # pylint: disable=broad-except
                backup_file = self.get_log_file_path() + "-" + str(uuid.uuid4())
                LOG.error("Failed to load logs file %s: %s; backing up the file to %s...", self.get_log_file_path(), str(ex), backup_file, exc_info=True)
                try:
                    os.rename(self.get_log_file_path(), backup_file)
                except Exception as move_ex:  # pylint: disable=broad-except
                    LOG.error("Failed to move file %s to %s: %s; expect an abnormal behaviour.", self.get_log_file_path(), backup_file, str(move_ex), exc_info=True)

        return logs

    def save_log(self, item: ConfigCommandExecutionResult):
        """
        Add a log to the log history of the command.
        """

        self.set_execution_results(item)

        logs = self.get_logs()

        # Update/Insert the log
        for log in logs.items:
            if log.uuid == item.uuid:
                log.start_time = item.start_time
                log.end_time = item.end_time
                log.status = item.status
                log.pid = item.pid
                log.exit_code = item.exit_code
                log.stdout = item.stdout
                log.stderr = item.stderr
                log.fail_message = item.fail_message
                log.stack_trace = item.stack_trace
                break
        else:
            logs.items.append(item)

        # Save logs
        self.save_logs(logs)

    def save_logs(self, logs: ConfigCommandLog):

        # Keep only the latest N messages
        if len(logs.items) > self.max_log_count:
            logs.items = logs.items[-self.max_log_count :]

        # Create the folder where the logs will be stored, if it doesn't exist yet
        if not os.path.exists(os.path.dirname(self.get_log_file_path())):
            os.makedirs(os.path.dirname(self.get_log_file_path()))

        # Save the logs
        with click.open_file(self.get_log_file_path(), "w", atomic=True) as file_obj:
            try:
                file_obj.write(logs.json(exclude_defaults=True, exclude_none=True, indent=2))
            except Exception as ex:  # pylint: disable=broad-except
                LOG.error("Error saving logs for command in file %s: %s.", self.get_log_file_path(), str(ex), exc_info=True)

    def get_warnings(self) -> List[CommandWarning]:

        warnings: List[CommandWarning] = []

        # Check command
        if self.run_mode == ConfigCommandRunMode.COMMAND and self.command:
            parts = shlex.split(self.command)
            command_exec = parts[0]
            if not shutil.which(command_exec):
                warnings.append(CommandWarning(category=MessageCategory.WARNING, message=gettext("Command {command_exec} hasn't been found. The execution will likely fail.").format(command_exec=command_exec)))

        # Check script interpreter exists
        if self.run_mode == ConfigCommandRunMode.SCRIPT and sys.platform == "win32" and self.script_interpreter:
            parts = shlex.split(self.script_interpreter)
            command_interpreter = parts[0]
            if not shutil.which(command_interpreter):
                warnings.append(CommandWarning(category=MessageCategory.WARNING, message=gettext("Command {command} for the interpreter {interpreter} doesn't exist. Are you sure you want to use it? During execution, if this directory doesn't exist, the current user home directory will be used.").format(command=command_interpreter, interpreter=self.script_interpreter)))

        # Check working directory exists
        if self.working_directory:
            if not os.path.exists(self.working_directory):
                warnings.append(CommandWarning(category=MessageCategory.WARNING, message=lazy_gettext("Directory {working_directory} doesn't exist. Are you sure you want to use it? During execution, if this directory doesn't exist, the current user home directory will be used.").format(working_directory=self.working_directory)))

        return warnings

    def get_warnings_as_tuples(self) -> List[Tuple[str, str]]:
        return [(str(x.category.value), x.message) for x in self.get_warnings()]


class LogLevelEnum(str, Enum):
    """
    Class to enumerate the log levels.
    """

    DEBUG = logging.getLevelName(logging.DEBUG)
    INFO = logging.getLevelName(logging.INFO)
    WARNING = logging.getLevelName(logging.WARNING)
    ERROR = logging.getLevelName(logging.ERROR)
    CRITICAL = logging.getLevelName(logging.CRITICAL)

    def display_name(self):
        """
        Returns a friendly display name.
        """
        return {
            self.DEBUG.value: lazy_gettext("Debug"),
            self.INFO.value: lazy_gettext("Info"),
            self.WARNING.value: lazy_gettext("Warning"),
            self.ERROR.value: lazy_gettext("Error"),
            self.CRITICAL.value: lazy_gettext("Critical"),
        }.get(self.value, self.value)


class Config(BaseModel):
    """
    Config class.
    """

    # TODO: By Pydantic, set this field to read only or set only during creation
    file_path: str = Field(exclude=True)

    version: Optional[int]
    language: Optional[str]
    first_run: bool = Field(default=True)

    log_level: LogLevelEnum = Field(default=LogLevelEnum.ERROR)
    create_app_menu_shortcut: bool = Field(default=True)
    auto_start: bool = Field(default=True)

    run_in_shell: bool = Field(default=False)

    include_output_in_notifications: bool = Field(default=True)
    show_complete_notifications: bool = Field(default=False)
    show_error_notifications: bool = Field(default=True)

    commands: List[ConfigCommand] = Field(default=[])

    app_runs: int = Field(default=0)
    app_version_check_enabled: bool = Field(default=True)
    app_version_check_interval_seconds: int = Field(default=3600)

    def get_command_by_id(self, command_id: str) -> Optional[ConfigCommand]:
        """
        Finds a command in the configuration by its id.
        """
        for command in self.commands:
            if command.id == command_id:
                return command
        return None

    def save(self):
        """
        Writes the configuration to the file.
        """
        if not os.path.exists(os.path.dirname(self.file_path)):
            os.makedirs(os.path.dirname(self.file_path))
        try:
            with click.open_file(self.file_path, mode="w", atomic=True) as file_obj:
                file_obj.write(self.json(exclude_defaults=True, exclude_none=True, indent=2))
        except Exception as ex:  # pylint: disable=broad-except
            LOG.error("Error saving configuration file %s: %s.", self.file_path, str(ex), exc_info=True)

    @staticmethod
    def load_from_file(file_path: str, raise_if_missing: Optional[bool] = False) -> "Config":
        """
        Loads the configuration from the file specified.
        """
        if not os.path.exists(file_path):
            if raise_if_missing:
                raise Exception(f"Configuration file {file_path} doesn't exist.")
            return Config(file_path=DEFAULT_CONFIG_FILE)

        if not os.path.isfile(file_path):
            raise Exception(f"Configuration file {file_path} is not a file.")

        try:
            with click.open_file(file_path) as file_obj:
                json_object = json.load(file_obj)
                if json_object:
                    # Migrate from v0 to v1:
                    if not json_object.get("version"):
                        json_object["version"] = 1
                        if json_object.get("commands"):
                            for command in json_object.get("commands"):
                                if command.get("next_run_dt"):
                                    del command["next_run_dt"]
                                if command.get("run_mode"):
                                    command["schedule_mode"] = command["run_mode"]
                                if command.get("script"):
                                    command["run_mode"] = ConfigCommandRunMode.SCRIPT.value
                                else:
                                    command["run_mode"] = ConfigCommandRunMode.COMMAND.value
                                if command.get("last_run_fail_message"):
                                    command["last_run_status"] = ConfigCommandExecutionStatus.FAILED.value
                                elif command.get("last_run_exit_code") is not None:
                                    command["last_run_status"] = ConfigCommandExecutionStatus.SUCCESS.value
                    # Migrate from v1 to v2
                    if json_object.get("version") == 1:
                        json_object["version"] = 2
                        if json_object.get("commands"):
                            for command in json_object.get("commands"):
                                for attr in ["run_in_shell", "include_output_in_notifications", "show_complete_notifications", "show_error_notifications"]:
                                    if command.get(attr) == True:
                                        command[attr] = YesNoDefault.YES.value
                                    elif command.get(attr) == False:
                                        command[attr] = YesNoDefault.NO.value
                                    else:
                                        command[attr] = YesNoDefault.DEFAULT.value
                    return Config(file_path=file_path, **json_object)
                return Config(file_path=file_path)
        except Exception as ex:  # pylint: disable=broad-except
            raise ex
            backup_file = file_path + "-" + str(uuid.uuid4())
            LOG.error("Failed to load configuration file %s: %s; backing up the file to %s...", file_path, str(ex), backup_file, exc_info=True)
            try:
                os.rename(file_path, backup_file)
            except Exception as move_ex:  # pylint: disable=broad-except
                LOG.error("Failed to move file %s to %s: %s; expect an abnormal behaviour.", file_path, backup_file, str(move_ex), exc_info=True)
            return Config(file_path=file_path)
