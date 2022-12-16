"""
tray_runner.tray_runner_utils module.
"""
import logging
import os
import sys


class PackagePathFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """
    Logging filter to add relative path to log messages.

    Borrowed from: https://stackoverflow.com/a/52582536/576138
    """

    def filter(self, record):
        pathname = record.pathname
        record.relativepath = None
        abs_sys_paths = map(os.path.abspath, sys.path)
        for path in sorted(abs_sys_paths, key=len, reverse=True):  # longer paths first
            if not path.endswith(os.sep):
                path += os.sep
            if pathname.startswith(path):
                record.relativepath = os.path.relpath(pathname, path)
                break
        return True
