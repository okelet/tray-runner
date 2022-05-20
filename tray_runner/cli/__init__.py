"""
Module tray_runner.cli
"""
import logging
import textwrap
import time
from gettext import gettext
from typing import Optional

import click

import tray_runner.config
from tray_runner.common_utils.common import run_command

LOG = logging.getLogger(__name__)


class CliCmdRunnerApp:  # pylint: disable=too-few-public-methods
    """
    CliCmdRunnerApp class.
    """

    def __init__(self, command: str, show_notifications: Optional[bool] = None, restart_on_exit: Optional[bool] = None, restart_on_failure: Optional[bool] = None, seconds_between_executions: Optional[int] = None, show_output: Optional[bool] = None):  # pylint: disable=too-many-arguments
        self.command: str = command
        self.show_notifications: bool = show_notifications if show_notifications is not None else True
        self.restart_on_exit: bool = restart_on_exit if restart_on_exit is not None else True
        self.restart_on_failure: bool = restart_on_failure if restart_on_failure is not None else True
        self.seconds_between_executions: int = seconds_between_executions if seconds_between_executions is not None else 1000
        self.show_output = show_output if show_output is not None else True

    def run(self) -> None:  # pylint: disable=too-many-branches,too-many-statements
        """
        Run method, executes the command, restaring and sending notifications if needed.
        """

        while True:

            LOG.info("Executing command %s...", self.command)
            exit_code = None
            error_message = None
            elapsed_time = None
            try:
                start_time = time.perf_counter()
                _pid, exit_code, stdout, stderr = run_command(self.command)
                end_time = time.perf_counter()
                elapsed_time = end_time - start_time
                LOG.debug("Command exited with code %s.", exit_code)
            except Exception as ex:  # pylint: disable=broad-except
                error_message = str(ex)
                LOG.warning("Error running command %s.", error_message)

            if exit_code is None:
                # Failed to run
                if self.show_notifications:
                    click.echo(f"Command {self.command} failed to run ({error_message}).")
            elif exit_code:
                # Exited with code > 0
                if not self.restart_on_failure:
                    if self.show_notifications:
                        click.echo(f"Command {self.command} exited with code {exit_code} (took {elapsed_time:.2f} seconds).")
                    if self.show_output:
                        if stdout:
                            click.echo(gettext("Standard output:"))
                            click.echo(textwrap.indent(stdout, "  "))
                        if stderr:
                            click.echo(gettext("Error output:"))
                            click.echo(textwrap.indent(stderr, "  "))
                    break
            else:
                # Exited with code = 0
                if not self.restart_on_exit:
                    if self.show_notifications:
                        click.echo(f"Command {self.command} exited with code {exit_code} (took {elapsed_time:.2f} seconds).")
                    if self.show_output:
                        if stdout:
                            click.echo(gettext("Standard output:"))
                            click.echo(textwrap.indent(stdout, "  "))
                        if stderr:
                            click.echo(gettext("Error output:"))
                            click.echo(textwrap.indent(stderr, "  "))
                    break

            if self.show_notifications:
                if exit_code is None:
                    click.echo(f"Command {self.command} failed to run ({error_message}); restarting after {self.seconds_between_executions/1000:.2f} seconds...")
                else:
                    click.echo(f"Command {self.command} exited with code {exit_code} (took {elapsed_time:.2f} seconds); restarting after {self.seconds_between_executions/1000:.2f} seconds...")
            if self.show_output:
                if stdout:
                    click.echo(gettext("Standard output:"))
                    click.echo(textwrap.indent(stdout, "  "))
                if stderr:
                    click.echo(gettext("Error output:"))
                    click.echo(textwrap.indent(stderr, "  "))
            time.sleep(self.seconds_between_executions)


@click.command()
@click.option("--command", required=True, help="Command to execute.")
@click.option("--log-level", type=click.Choice([logging.getLevelName(x) for x in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]], case_sensitive=False), default=logging.getLevelName(logging.ERROR), show_default=True)
@click.version_option(tray_runner.__version__)
def run(command: str, log_level: str) -> None:
    """
    Tool to run and restart commands, so they can be continuously executed.
    """
    logging.basicConfig(level=logging.getLevelName(log_level))

    app = CliCmdRunnerApp(command, True, True, True)
    app.run()
