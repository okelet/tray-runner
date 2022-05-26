"""
tray_runner.config module.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum
from gettext import gettext
from typing import Dict, List, Optional

import click
import pytz
from croniter import croniter
from pydantic import BaseModel, Field
from slugify import slugify

from tray_runner import APP_DIR, DEFAULT_CONFIG_FILE
from tray_runner.common_utils.common import ensure_local_datetime

LOG = logging.getLogger(__name__)


class ConfigCommandLogItem(BaseModel):  # pylint: disable=too-few-public-methods
    """
    ConfigCommandLog class.
    """

    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime
    end_time: datetime
    duration: float
    aborted: Optional[bool] = Field(default=False)
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error_message: Optional[str] = None


class ConfigCommandLog(BaseModel):  # pylint: disable=too-few-public-methods
    """
    Class to store command logs.
    """

    items: List[ConfigCommandLogItem] = Field(default=[])


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

    PERIOD = "PERIOD"
    CRON = "CRON"

    def display_name(self):
        """
        Returns a friendly display name.
        """
        return {
            self.PERIOD.value: gettext("Period"),
            self.CRON.value: gettext("Cron"),
        }.get(self.value, self.value)


class ConfigCommand(BaseModel):
    """
    ConfigCommand class.
    """

    id: str = Field()
    name: str = Field()
    command: Optional[str] = Field()
    script: Optional[str] = Field()
    run_script_powershell: bool = Field(default=False)
    working_directory: str = Field(default=os.path.expanduser("~"))
    environment: List[ConfigCommandEnvironmentVariable] = Field(default=[])
    description: Optional[str]
    disabled: bool = Field(default=False)
    max_log_count: int = Field(default=100)

    run_at_startup: bool = Field(default=False)
    run_at_startup_if_missing_previous_run: bool = Field(default=False)
    run_mode: ConfigCommandRunMode = Field(default=ConfigCommandRunMode.PERIOD)
    seconds_between_executions: int = Field(default=600)
    cron_expr: Optional[str]

    run_in_shell: Optional[bool]
    restart_on_exit: Optional[bool]
    restart_on_failure: Optional[bool]

    include_output_in_notifications: Optional[bool]
    show_complete_notifications: Optional[bool]
    show_error_notifications: Optional[bool]

    total_runs: int = Field(default=0)
    ok_runs: int = Field(default=0, description="When a run has returned an exit code 0.")
    error_runs: int = Field(default=0, description="When a run was OK, but returned an exit code different that 0.")
    failed_runs: int = Field(default=0, description="When a run threw an error.")

    last_run_dt: Optional[datetime]
    next_run_dt: Optional[datetime]
    last_run_exit_code: Optional[int]
    last_run_error_message: Optional[str]

    last_successful_run_dt: Optional[datetime]

    last_duration: Optional[float]
    min_duration: Optional[float]
    max_duration: Optional[float]
    avg_duration: Optional[float]

    def get_next_execution_dt(self, start_date: Optional[datetime] = None) -> Optional[datetime]:
        """
        Get the command's next execution date/time, according to its status and run mode.
        """
        now = datetime.utcnow()
        if start_date is None:
            start_date = self.last_run_dt
        if self.disabled:
            return None
        if self.run_mode == ConfigCommandRunMode.PERIOD:
            if start_date is None:
                return now
            next_dt = start_date + timedelta(seconds=self.seconds_between_executions)
            while next_dt < now:
                # Find a moment in the future
                next_dt = next_dt + timedelta(seconds=self.seconds_between_executions)
            return next_dt
        if self.run_mode == ConfigCommandRunMode.CRON:
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
            raise Exception(f"Command run mode is {self.run_mode.value}, but no cron_expr set.")
        raise Exception(f"Invalid run mode: {self.run_mode}.")

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

    def add_log(self, item: ConfigCommandLogItem):
        """
        Add a log to the log history of the command.
        """

        # List of current logs, empty if no log file exists yet
        logs = ConfigCommandLog()

        # Read current logs
        if os.path.exists(self.get_log_file_path()):
            try:
                with click.open_file(self.get_log_file_path(), "r") as file_obj:
                    json_object = json.load(file_obj)
                    if json_object:
                        logs = ConfigCommandLog(**json_object)
            except Exception as ex:  # pylint: disable=broad-except
                backup_file = self.get_log_file_path() + "-" + str(uuid.uuid4())
                LOG.error("Failed to load logs file %s: %s; backing up the file to %s...", self.get_log_file_path(), str(ex), backup_file, exc_info=True)
                try:
                    os.rename(self.get_log_file_path(), backup_file)
                except Exception as move_ex:  # pylint: disable=broad-except
                    LOG.error("Failed to move file %s to %s: %s; expect an abnormal behaviour.", self.get_log_file_path(), backup_file, str(move_ex), exc_info=True)

        # Create the folder where the logs will be stored, if it doesn't exist yet
        if not os.path.exists(os.path.dirname(self.get_log_file_path())):
            os.makedirs(os.path.dirname(self.get_log_file_path()))

        # Add the current log message
        logs.items.append(item)

        # Keep only the latest N messages
        if len(logs.items) > self.max_log_count:
            logs.items = logs.items[-self.max_log_count :]

        # Save the logs
        with click.open_file(self.get_log_file_path(), "w", atomic=True) as file_obj:
            try:
                file_obj.write(logs.json(exclude_defaults=True, exclude_none=True, indent=2))
            except Exception as ex:  # pylint: disable=broad-except
                LOG.error("Error saving logs for command in file %s: %s.", self.get_log_file_path(), str(ex), exc_info=True)


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
            self.DEBUG.value: gettext("Debug"),
            self.INFO.value: gettext("Info"),
            self.WARNING.value: gettext("Warning"),
            self.ERROR.value: gettext("Error"),
            self.CRITICAL.value: gettext("Critical"),
        }.get(self.value, self.value)


class Config(BaseModel):
    """
    Config class.
    """

    log_level: LogLevelEnum = Field(default=LogLevelEnum.ERROR)
    create_app_menu_shortcut: bool = Field(default=True)
    auto_start: bool = Field(default=True)

    run_in_shell: bool = Field(default=False)
    restart_on_exit: bool = Field(default=True)
    restart_on_failure: bool = Field(default=True)

    include_output_in_notifications: bool = Field(default=True)
    show_complete_notifications: bool = Field(default=False)
    show_error_notifications: bool = Field(default=True)

    commands: List[ConfigCommand] = Field(default=[])

    app_runs: int = Field(default=0)

    def get_command_by_name(self, command_name: str) -> Optional[ConfigCommand]:
        """
        Finds a command in the configuration by its name.
        """
        for command in self.commands:
            if command.name == command_name:
                return command
        return None

    def get_command_by_id(self, command_id: str) -> Optional[ConfigCommand]:
        """
        Finds a command in the configuration by its id.
        """
        for command in self.commands:
            if command.id == command_id:
                return command
        return None

    def save_to_file(self, file_path: Optional[str] = None):
        """
        Writes the configuration to the file.
        """
        config_file = file_path or DEFAULT_CONFIG_FILE
        if not os.path.exists(os.path.dirname(config_file)):
            os.makedirs(os.path.dirname(config_file))
        try:
            with click.open_file(config_file, mode="w", atomic=True) as file_obj:
                file_obj.write(self.json(exclude_defaults=True, exclude_none=True, indent=2))
        except Exception as ex:  # pylint: disable=broad-except
            LOG.error("Error saving configuration file %s: %s.", file_path or DEFAULT_CONFIG_FILE, str(ex), exc_info=True)

    @staticmethod
    def load_from_file(file_path: str, raise_if_missing: Optional[bool] = False) -> "Config":
        """
        Loads the configuration from the file specified.
        """
        if not os.path.exists(file_path):
            if raise_if_missing:
                raise Exception(f"Configuration file {file_path} doesn't exist.")
            return Config()

        if not os.path.isfile(file_path):
            raise Exception(f"Configuration file {file_path} is not a file.")

        try:
            with click.open_file(file_path) as file_obj:
                json_object = json.load(file_obj)
                if json_object:
                    return Config(**json_object)
                return Config()
        except Exception as ex:  # pylint: disable=broad-except
            backup_file = file_path + "-" + str(uuid.uuid4())
            LOG.error("Failed to load configuration file %s: %s; backing up the file to %s...", file_path, str(ex), backup_file, exc_info=True)
            try:
                os.rename(file_path, backup_file)
            except Exception as move_ex:  # pylint: disable=broad-except
                LOG.error("Failed to move file %s to %s: %s; expect an abnormal behaviour.", file_path, backup_file, str(move_ex), exc_info=True)
            return Config()
