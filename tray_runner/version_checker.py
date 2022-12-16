"""
Module that includes a class for application version checks using PyPi.
"""
import logging
import time
from datetime import datetime, timedelta
from threading import Event, Thread
from typing import Optional

import requests

LOG = logging.getLogger(__name__)


class VersionChecker(Thread):
    """
    Class that implements a thread for periodic checks of new versions in PyPi.
    """

    def __init__(self, app_name: str, current_version: str, check_interval_seconds: int):
        super().__init__()
        self.app_name = app_name
        self.current_version = current_version
        self.check_interval_seconds = check_interval_seconds
        self.remote_version: Optional[str] = None
        self.stop_signal = Event()

    def stop(self):
        """
        Signal the current thread to stop.
        """
        self.stop_signal.set()

    def run(self):
        """
        Runs the thread main logic.
        """

        while True:

            try:
                resp = requests.get(f"https://pypi.org/pypi/{self.app_name}/json", timeout=3.0).json()
                self.remote_version = resp.get("info").get("version")
                if self.remote_version and self.current_version != self.remote_version:
                    LOG.info("New version detected for %s: %s (current is %s).", self.app_name, self.remote_version, self.current_version)
            except Exception as ex:  # pylint: disable=broad-except
                LOG.exception("Error checking version: %s", str(ex))

            next_run = datetime.utcnow() + timedelta(seconds=self.check_interval_seconds)
            while True:
                if self.stop_signal.is_set():
                    return
                if datetime.utcnow() < next_run:
                    time.sleep(0.5)
