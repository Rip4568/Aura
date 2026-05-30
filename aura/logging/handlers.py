"""Custom handlers for the logging system."""

from __future__ import annotations

import logging
import os
import threading
from datetime import date
from pathlib import Path
from typing import Any


class DailyRotatingFileHandler(logging.Handler):
    """Logs to a daily file with optional rotation by line count.

    Creates files in the format: storage/logs/2026-05-29.log
    When max_lines is reached: renames to 2026-05-29.1.log and opens new 2026-05-29.log
    When day changes: opens a new file for the new day.

    **WARNING**: This handler uses `threading.Lock` and is **single-process-safe only**.
    For multi-worker deployments (e.g., uvicorn --workers N), use console logging
    (stdout) or implement a centralized logging service.

    Args:
        log_dir: Directory where log files are stored (can be path or str).
        filename: Alternative parameter name for log_dir (for compatibility).
        max_lines: Maximum lines per file before rotation. None for no rotation.
        warn_multiprocess: If True, emit a logging.warning when multiple processes
                          are detected (via os.getpid).
        encoding: File encoding (default: utf-8).

    Example::

        handler = DailyRotatingFileHandler(
            log_dir="logs",
            max_lines=10000,
            warn_multiprocess=True
        )
        logger.addHandler(handler)
    """

    def __init__(
        self,
        log_dir: str | None = None,
        filename: str | None = None,
        max_lines: int | None = None,
        warn_multiprocess: bool = True,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__()
        # Support both log_dir and filename parameter names
        dir_path = filename if filename is not None else log_dir
        if dir_path is None:
            dir_path = "logs"

        self._dir = Path(dir_path)
        self._max_lines = max_lines
        self._encoding = encoding
        self._lock = threading.Lock()
        self._current_date: date | None = None
        self._current_file: Any = None
        self._line_count: int = 0
        self._process_id = os.getpid()
        self._warn_multiprocess = warn_multiprocess
        self._dir.mkdir(parents=True, exist_ok=True)

        # Check for multiprocess on initialization
        if warn_multiprocess:
            self._check_multiprocess()

    def _check_multiprocess(self) -> None:
        """Check if multiple processes are running and warn if so."""
        current_pid = os.getpid()
        if current_pid != self._process_id:
            logging.warning(
                "DailyRotatingFileHandler detected process change (PID %d → %d). "
                "This handler is single-process-safe. Consider using console logging "
                "or a centralized logging service for multi-worker deployments.",
                self._process_id,
                current_pid,
            )
            self._process_id = current_pid

    def _get_log_path(self, d: date) -> Path:
        """Get the main log file path for a given date.

        Args:
            d: The date for which to get the log path.

        Returns:
            Path like storage/logs/2026-05-29.log
        """
        return self._dir / f"{d.isoformat()}.log"

    def _rotate(self, d: date) -> None:
        """Rotate the current log file by renaming it with a numeric suffix.

        Closes the current file, finds the next available suffix, renames
        the file, and opens a new file for the day.

        Args:
            d: The current date.
        """
        if self._current_file:
            self._current_file.close()

        log_path = self._get_log_path(d)

        # Find next available suffix
        suffix = 1
        while True:
            rotated_path = self._dir / f"{d.isoformat()}.{suffix}.log"
            if not rotated_path.exists():
                break
            suffix += 1

        # Rename current file
        if log_path.exists():
            log_path.rename(rotated_path)

        # Open new file
        self._open_file(d)
        self._line_count = 0

    def _open_file(self, d: date) -> None:
        """Open the log file for the given date in append mode.

        Args:
            d: The date for which to open the log file.
        """
        log_path = self._get_log_path(d)
        self._current_file = open(log_path, "a", encoding=self._encoding)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to file with thread-safe rotation handling.

        Args:
            record: The log record to emit.
        """
        with self._lock:
            # Check for multiprocess issues on each emit
            if self._warn_multiprocess:
                self._check_multiprocess()

            today = date.today()

            # If day changed, close current file and open new one
            if today != self._current_date:
                if self._current_file:
                    self._current_file.close()
                self._current_date = today
                self._open_file(today)
                self._line_count = 0

            # If max_lines reached, rotate
            if self._max_lines is not None and self._line_count >= self._max_lines:
                self._rotate(today)

            # Write the log record
            try:
                msg = self.format(record) + "\n"
                self._current_file.write(msg)
                self._current_file.flush()
                self._line_count += 1
            except Exception:
                self.handleError(record)

    def close(self) -> None:
        """Close the file handle and cleanup.

        Overrides the base class close method to ensure the file is closed.
        """
        with self._lock:
            if self._current_file:
                self._current_file.close()
                self._current_file = None
        super().close()
