"""
tray_runner.gui module
"""
import imp
import logging
import os.path
import signal
import sys
from gettext import gettext
from typing import Optional

import click
from filelock import FileLock, Timeout

import tray_runner
from tray_runner import DEFAULT_CONFIG_FILE, __version__
from tray_runner.common_utils.common import init_logging
from tray_runner.config import Config
from tray_runner.constants import APP_ID
from tray_runner.gui.app import TrayRunnerGuiApp

LOG = logging.getLogger(__name__)


@click.command()
@click.option("--config", "-c", "config_path", type=click.Path(exists=True, dir_okay=False, resolve_path=True), required=False, help="Path to configuration file.")
@click.option("--bind", "-b", "bind_address", required=False, help="Address to bind.")
@click.option("--port", "-p", "bind_port", type=int, required=False, help="Port to bind.")
@click.option("--log-level", type=click.Choice([logging.getLevelName(x) for x in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]], case_sensitive=False), show_default=True)
@click.option("--system-start", is_flag=True, default=False)
@click.option("--show-config", is_flag=True, default=False)
@click.version_option(__version__)
def run(config_path: Optional[str], bind_address: Optional[str], bind_port: Optional[int], log_level: Optional[str], system_start: bool, show_config: bool) -> None:
    """
    Main command for the tray_runner package.
    """

    # Init logging
    if not os.path.exists(tray_runner.APP_DIR):
        os.makedirs(tray_runner.APP_DIR)
    init_logging(tray_runner.__name__, os.path.join(tray_runner.APP_DIR, f"{APP_ID}.log"), log_level)

    if not config_path:
        config_path = DEFAULT_CONFIG_FILE
        config_path_dir = os.path.dirname(config_path)
        if not os.path.exists(config_path_dir):
            os.makedirs(config_path_dir)

    lock_file_path = config_path + ".lock"
    lock_file = FileLock(lock_file_path)
    try:
        lock_file.acquire(timeout=0)
    except Timeout:
        print(gettext("The application is already running."))
        sys.exit(1)

    try:
        LOG.debug("Loading configuration from file %s...", config_path)
        config = Config.load_from_file(file_path=config_path)
        config.app_runs += 1
        config.save()
    except Exception as ex:  # pylint: disable=broad-except
        LOG.exception("Error loading configuration from file %s: %s.", config_path, str(ex))
        sys.exit(1)

    app = TrayRunnerGuiApp(config=config, bind_address=bind_address, bind_port=bind_port, system_start=system_start, show_config=show_config)

    #################################################################################################################################
    # Signal handling
    #################################################################################################################################

    def exit_gracefully(_signum, _frame):
        """
        Function executed when Control-C pressed.
        """
        LOG.info("Detected Control-C; performing application stop...")

        # Stop the application
        app.stop()

    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)

    #################################################################################################################################
    # Run application
    #################################################################################################################################

    try:
        sys.exit(app.run())
    finally:
        lock_file.release()


if __name__ == "__main__":
    run()  # pylint: disable=no-value-for-parameter
