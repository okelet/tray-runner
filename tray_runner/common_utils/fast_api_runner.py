"""
tray_runner.common_utils.flask_app_runner module.
"""
import logging
import threading
from typing import Optional, Tuple

from cheroot import wsgi
from fastapi import FastAPI


class FastApiRunner:
    """
    Class that allows to run Flask applications in a separate thread, without stopping the main thread, and allows to start and stop the application.
    """

    def __init__(self, app: FastAPI, bind_address: Optional[str] = None, bind_port: Optional[int] = None):
        """
        Class constructor.
        """
        self.logger = logging.Logger(__name__)
        self.address = "127.0.0.1"
        if bind_address is not None:
            self.address = bind_address
        self.port = 0
        if bind_port is not None:
            self.port = bind_port
        self.app = app
        self.server = wsgi.Server((self.address, self.port), wsgi.PathInfoDispatcher({"/": self.app}))
        self.thread = None

    def start(self) -> None:
        """
        Starts the process.
        """
        self.logger.debug("Starting HTTP server...")
        if self.thread and self.thread.is_alive():
            self.logger.warning("HTTP server already running")
        else:
            self.thread = threading.Thread(target=self.server.start)
            self.thread.start()

    def stop(self) -> None:
        """
        Stops the process.
        """
        self.logger.debug("Stopping HTTP server...")
        if self.thread and self.thread.is_alive():
            self.server.stop()
            self.thread.join()
        else:
            self.logger.warning("HTTP server NOT running")

    def join(self) -> None:
        """
        Waits for the thread to finish.
        """
        self.logger.debug("Joining thread...")
        if self.thread and self.thread.is_alive():
            self.thread.join()

    def get_address_and_port(self) -> Tuple[str, int]:
        """
        Returns a tuple containing the real address and port where the application is served.
        """
        return self.server.bind_addr

    def get_address(self) -> str:
        """
        Returns the actual address where the application is served.
        """
        return self.server.bind_addr[0]

    def get_port(self) -> int:
        """
        Returns the actual port where the application is served.
        """
        return self.server.bind_addr[1]

    def is_ready(self) -> bool:
        """
        Checks if the process is ready to accept requests.
        """
        return self.server.ready
