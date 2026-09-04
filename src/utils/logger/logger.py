from __future__ import annotations

import sys
from datetime import datetime
from typing import Final


class Logger:
    """
    Standardized ANSI-colored logger for automation pipelines.
    Provides clean, professional terminal output without file persistence.
    """

    # ANSI Escape Sequences for Terminal Formatting
    _HEADER: Final[str] = "\033[95m"
    _BLUE: Final[str] = "\033[94m"
    _GREEN: Final[str] = "\033[92m"
    _WARNING: Final[str] = "\033[93m"
    _FAIL: Final[str] = "\033[91m"
    _ENDC: Final[str] = "\033[0m"
    _BOLD: Final[str] = "\033[1m"

    def __init__(self) -> None:
        """Initializes the logger instance. No file I/O setup."""
        pass

    @staticmethod
    def _get_timestamp() -> str:
        """Returns current timestamp in YYYY-MM-DD HH:MM:SS format."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def info(self, message: str) -> None:
        """Standard informational message."""
        print(f"[INFO: {self._get_timestamp()}] {message}")

    def success(self, message: str) -> None:
        """Success message highlighted in green."""
        print(f"[{self._GREEN}SUCCESS: {self._get_timestamp()}]{self._ENDC} {message}")

    def warning(self, message: str) -> None:
        """Warning alert highlighted in yellow."""
        print(
            f"[{self._WARNING}WARNING:{self._get_timestamp()}]{self._ENDC} {message}"
        )

    def error(self, message: str, exception: Exception | None = None) -> None:
        """
        Error message in red to stderr.
        Optionally logs the exception details for debugging.
        """
        error_msg: str = f"{message} | Error: {exception}" if exception else message
        print(
            f"[{self._FAIL}ERROR:{self._get_timestamp()}]{self._ENDC} {error_msg}",
            file=sys.stderr,
        )

    def section(self, title: str) -> None:
        """Major structural header for the log output."""
        print(
            f"[{self._get_timestamp()}] "
            f"{self._BOLD}{self._HEADER}{title.upper()}{self._ENDC}"
        )

    def subsection(self, message: str) -> None:
        """Bold informational message to distinguish sub-tasks within a section."""
        print(f"[{self._get_timestamp()}] {self._BOLD}{message}{self._ENDC}")

    def print(self, message: str, color: str | None = None) -> None:
        """
        Direct replacement for the built-in print command.
        Bypasses timestamp and prefixes for raw data output.
        """
        c: str = color if color else ""
        end: str = self._ENDC if color else ""
        print(f"{c}{message}{end}")


# Global instance for project-wide use
logger: Logger = Logger()
