import logging
import os
import shlex
import stat
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta
from gettext import gettext
from threading import Event, Thread
from typing import List, Optional

from tray_runner import PACKAGE_DIR
from tray_runner.base_app import BaseApp
from tray_runner.common_utils.common import coalesce, run_command
from tray_runner.config import ConfigCommand, ConfigCommandExecutionResult, ConfigCommandExecutionStatus, ConfigCommandRunMode, ConfigCommandScheduleMode

LOG = logging.getLogger(__name__)


class BaseCommandThread(Thread):
    def __init__(self, execution_manager: "BaseExecutionManager", command: ConfigCommand, is_startup: Optional[bool] = False) -> None:
        """
        Class constructor.
        """
        super().__init__(name=f"Command thread for command {command.id} - {command.name}")
        self.execution_manager = execution_manager
        self.command = command
        self.stop_event = Event()
        self.is_startup = is_startup

    def stop(self):
        """
        Notifies the thread to stop.
        """
        self.stop_event.set()

    def wait_startup_on_startup(self):

        if self.is_startup and self.command.startup_delay_seconds:
            end_delay = datetime.utcnow() + timedelta(seconds=self.command.startup_delay_seconds)
            while datetime.utcnow() < end_delay:
                if self.stop_event and self.stop_event.is_set():
                    return
                time.sleep(0.1)

    def execute_command(self, stop_event: Optional[Event] = None) -> None:

        script_path = None
        try:

            run_in_shell = coalesce(self.command.run_in_shell.to_boolean(), self.execution_manager.get_app().config.run_in_shell)
            include_output_in_notifications = coalesce(self.command.include_output_in_notifications.to_boolean(), self.execution_manager.get_app().config.include_output_in_notifications)
            show_complete_notifications = coalesce(self.command.show_complete_notifications.to_boolean(), self.execution_manager.get_app().config.show_complete_notifications)
            show_error_notifications = coalesce(self.command.show_error_notifications.to_boolean(), self.execution_manager.get_app().config.show_error_notifications)

            working_directory = self.command.working_directory
            if not working_directory or not os.path.exists(working_directory):
                working_directory = os.path.expanduser("~")

            cmd = None
            if self.command.run_mode == ConfigCommandRunMode.COMMAND and self.command.command:
                cmd = self.command.command
            elif self.command.run_mode == ConfigCommandRunMode.SCRIPT and self.command.script:
                run_in_shell = False
                if sys.platform == "win32":
                    # https://github.com/PowerShell/PowerShell/issues/3028
                    # Workaround using https://github.com/stax76/run-hidden
                    file_descriptor, script_path = tempfile.mkstemp(text=True)
                    run_hidden_path = os.path.join(PACKAGE_DIR, "helpers", "win", "run-hidden.exe")
                    cmd = shlex.split(f"{run_hidden_path} {self.command.script_interpreter} {script_path}")
                else:
                    file_descriptor, script_path = tempfile.mkstemp(text=True)
                    file_stat = os.stat(script_path)
                    os.chmod(script_path, file_stat.st_mode | stat.S_IEXEC)
                    cmd = script_path
                with os.fdopen(file_descriptor, "w") as script_file:
                    if sys.platform != "win32" and not self.command.script.startswith("#!"):
                        # Add shebang if not present and not Windows
                        script_file.write("#!/bin/sh\n")
                    script_file.write(self.command.script)
                LOG.debug("Command %s: generated file for script: %s", self.command.name, script_path)

            if cmd:

                LOG.info("Executing command %s - %s...", self.command.name, self.command.command)
                result = ConfigCommandExecutionResult(status=ConfigCommandExecutionStatus.RUNNING, start_time=datetime.utcnow())
                self.command.add_log(result)
                self.command.current_status = ConfigCommandExecutionStatus.RUNNING
                self.command.current_start_dt = result.start_time
                try:
                    pid, exit_code, stdout, stderr = run_command(command=cmd, environ=self.command.environment_as_dict(), run_in_shell=run_in_shell, working_directory=working_directory, stop_event=stop_event)
                    result.end_time = datetime.utcnow()
                    if exit_code:
                        result.status = ConfigCommandExecutionStatus.ERROR
                    else:
                        result.status = ConfigCommandExecutionStatus.SUCCESS
                    result.pid = pid
                    result.exit_code = exit_code
                    result.stdout = stdout
                    result.stderr = stderr
                    LOG.debug("Command %s exited with code %s (took %s seconds).", self.command.id, exit_code, f"{result.duration:.2f}")
                except Exception as ex:  # pylint: disable=broad-except
                    result.end_time = datetime.utcnow()
                    result.status = ConfigCommandExecutionStatus.FAILED
                    result.fail_message = str(ex)
                    result.stack_trace = traceback.format_exc()
                    LOG.warning("Error running command %s: %s.", self.command.id, result.fail_message)

                # Update statuses
                self.command.save_log(result)
                self.execution_manager.get_app().config.save()
                self.execution_manager.get_app().on_status_changed()

                if result.status == ConfigCommandExecutionStatus.FAILED:

                    # Failed to run
                    if show_error_notifications:
                        self.execution_manager.get_app().send_notification(self.command.name, gettext("Command failed to run ({error_message}).").format(error_message=result.fail_message))

                elif result.status == ConfigCommandExecutionStatus.ERROR:

                    # Exited with code > 0
                    if show_error_notifications:
                        if include_output_in_notifications and result.stdout and result.stderr:
                            self.execution_manager.get_app().send_notification(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nStandard output: {stdout}\n\nError output: {stderr}").format(exit_code=result.exit_code, elapsed_time=result.duration, stdout=result.stdout, stderr=result.stderr))
                        elif include_output_in_notifications and result.stdout:
                            self.execution_manager.get_app().send_notification(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nStandard output: {stdout}").format(exit_code=result.exit_code, elapsed_time=result.duration, stdout=result.stdout))
                        elif include_output_in_notifications and result.stderr:
                            self.execution_manager.get_app().send_notification(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nError output: {stderr}").format(exit_code=result.exit_code, elapsed_time=result.duration, stderr=result.stderr))
                        else:
                            self.execution_manager.get_app().send_notification(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).").format(exit_code=result.exit_code, elapsed_time=result.duration))

                elif result.status == ConfigCommandExecutionStatus.SUCCESS:

                    # Exited with code = 0
                    if show_complete_notifications:
                        if include_output_in_notifications and result.stdout and result.stderr:
                            self.execution_manager.get_app().send_notification(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nStandard output: {stdout}\n\nError output: {stderr}").format(exit_code=result.exit_code, elapsed_time=result.duration, stdout=result.stdout, stderr=result.stderr))
                        elif include_output_in_notifications and result.stdout:
                            self.execution_manager.get_app().send_notification(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nStandard output: {stdout}").format(exit_code=result.exit_code, elapsed_time=result.duration, stdout=result.stdout))
                        elif include_output_in_notifications and result.stderr:
                            self.execution_manager.get_app().send_notification(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).\n\nError output: {stderr}").format(exit_code=result.exit_code, elapsed_time=result.duration, stderr=result.stderr))
                        else:
                            self.execution_manager.get_app().send_notification(self.command.name, gettext("Command exited with code {exit_code} (took {elapsed_time:.2f} seconds).").format(exit_code=result.exit_code, elapsed_time=result.duration))

            else:
                LOG.critical("Command %s: no command or script set.", self.command.name)

        except Exception as ex:  # pylint: disable=broad-except
            LOG.error("Error during command execution: %s.", str(ex), exc_info=True)
        finally:
            if script_path and os.path.exists(script_path):
                os.remove(script_path)


class OneShotCommandThread(BaseCommandThread):  # pylint: disable=too-few-public-methods
    """
    OneShotCommandThread class.

    Thread responsible for running the commands defined in the configuration and emitting signals on change.
    """

    def run(self):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """
        Overridden method from parent class, implementing the logic of the thread.
        """
        # Initial delay
        self.wait_startup_on_startup()

        # Exit if stopped
        if self.stop_event.is_set():
            return

        # Run command
        self.execute_command(self.stop_event)

        # Remove self from running threads when finished
        self.execution_manager.remove_thread(self)


class ScheduledCommandThread(BaseCommandThread):  # pylint: disable=too-few-public-methods
    """
    ScheduledCommandThread class.

    Thread responsible for running the commands defined in the configuration and emitting signals on change.
    """

    def needs_to_run(self, is_first_loop: bool):

        if is_first_loop and self.command.run_at_startup:
            return True

        # TODO: Implement run_at_startup_if_missing_previous_run

        next_run_dt = self.command.next_run_dt
        if not next_run_dt:
            next_run_dt = self.command.get_next_execution_dt(self.command.last_status.start_time if self.command.last_status else None)
            self.command.next_run_dt = next_run_dt

        if next_run_dt < datetime.utcnow():
            return True

        return False

    def run(self):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """
        Overridden method from parent class, implementing the logic of the thread.
        """
        # Initial delay
        self.wait_startup_on_startup()

        is_first_loop = True
        while True:  # pylint: disable=too-many-nested-blocks

            if self.stop_event.is_set():
                break

            tmp_is_first_loop = is_first_loop
            is_first_loop = False

            if self.needs_to_run(is_first_loop=tmp_is_first_loop):

                # Run command
                self.execute_command(self.stop_event)

                # Calculate next run
                self.command.next_run_dt = self.command.get_next_execution_dt()

            else:
                time.sleep(1)
                continue

        self.execution_manager.remove_thread(self)


class BaseExecutionManager:
    def get_app(self) -> BaseApp:
        raise NotImplementedError()

    def get_running_jobs(self) -> List[BaseCommandThread]:
        raise NotImplementedError()

    def auto_start_jobs(self, is_system_autostart: bool, is_app_autostart: bool) -> None:
        raise NotImplementedError()

    def ensure_command_status(self, command: ConfigCommand, is_system_autostart: Optional[bool] = False, is_app_autostart: Optional[bool] = False) -> None:
        raise NotImplementedError()

    def start_command(self, command: ConfigCommand) -> None:
        raise NotImplementedError()

    def stop_command_thread(self, command: ConfigCommand) -> None:
        raise NotImplementedError()

    def remove_thread(self, t: BaseCommandThread):
        raise NotImplementedError()

    def stop_all_threads(self):
        raise NotImplementedError()


class ExecutionManager(BaseExecutionManager):
    def __init__(self, app: BaseApp):
        self.app = app
        self.running_threads: List[BaseCommandThread] = []

    def get_app(self) -> BaseApp:
        return self.app

    def get_running_jobs(self) -> List[BaseCommandThread]:
        return self.running_threads

    def auto_start_jobs(self, is_system_autostart: bool, is_app_autostart: bool) -> None:

        for command in self.app.config.commands:
            self.ensure_command_status(command=command, is_system_autostart=is_system_autostart, is_app_autostart=is_app_autostart)

    def ensure_command_status(self, command: ConfigCommand, is_system_autostart: Optional[bool] = False, is_app_autostart: Optional[bool] = False) -> None:

        self.stop_command_thread(command)

        if command.disabled:
            return

        if command.schedule_mode == ConfigCommandScheduleMode.SYSTEM_START and is_system_autostart:
            one_shot_command_thread = OneShotCommandThread(self, command=command, is_startup=True)
            self.running_threads.append(one_shot_command_thread)
            one_shot_command_thread.start()

        elif command.schedule_mode == ConfigCommandScheduleMode.APP_START and is_app_autostart:
            one_shot_command_thread = OneShotCommandThread(self, command=command, is_startup=True)
            self.running_threads.append(one_shot_command_thread)
            one_shot_command_thread.start()

        elif command.schedule_mode in [ConfigCommandScheduleMode.CRON, ConfigCommandScheduleMode.PERIOD]:
            scheduled_command_thread = ScheduledCommandThread(self, command=command, is_startup=True)
            self.running_threads.append(scheduled_command_thread)
            scheduled_command_thread.start()

        else:
            LOG.debug("Not running command %s on autostart because its schedule mode is %s.", command.name, command.schedule_mode)

    def start_command(self, command: ConfigCommand) -> None:
        t = OneShotCommandThread(self, command)
        self.running_threads.append(t)
        t.start()

    def stop_command_thread(self, command: ConfigCommand) -> None:
        LOG.debug("Trying to stop job thread for job %s (current number of threads running: %s)...", command.id, len(self.running_threads))
        for t in self.running_threads:
            if t.command == command:
                LOG.debug("Job thread for job %s found; signaling to stop and waiting...", command.id)
                t.stop()
                t.join()
                LOG.debug("Job thread for job %s stopped (current number of threads running: %s).", command.id, len(self.running_threads))
                self.remove_thread(t)
                break
        else:
            LOG.debug("Command thread for job %s not found; perhaps it wasn't running.", command.id)

    def remove_thread(self, t: BaseCommandThread):
        if t in self.running_threads:
            self.running_threads.remove(t)

    def stop_all_threads(self):
        for t in self.running_threads:
            LOG.debug("Signaling thread %s to stop...", t.name)
            if t.is_alive():
                t.stop()
        for t in self.running_threads:
            LOG.debug("Waiting for thread %s to stop...", t.name)
            t.join()
