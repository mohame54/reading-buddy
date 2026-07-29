import logging
import time
from typing import Any, Dict, Literal, Optional

LOGGER = logging.getLogger(__name__)

DurationUnit = Literal["s", "ms"]


class Timer:
    def __init__(
        self,
        operation_name: str,
        logger: Optional[logging.Logger] = None,
        extra: Optional[Dict[str, Any]] = None,
        level: int = logging.INFO,
        duration_unit: DurationUnit = "s",
    ):
        self.operation_name = operation_name
        self.logger = logger or LOGGER
        self.extra = extra if extra is not None else {}
        self.level = level
        self.duration_unit = duration_unit
        self.start_time: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> "Timer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.elapsed = time.perf_counter() - self.start_time
        if self.duration_unit == "ms":
            duration = self.elapsed * 1000
            duration_key = "duration_ms"
            duration_fmt = f"{duration:.1f}"
        else:
            duration = self.elapsed
            duration_key = "duration_s"
            duration_fmt = f"{duration:.3f}"

        context_parts = [f"{k}={v}" for k, v in self.extra.items()]
        context_parts.append(f"{duration_key}={duration_fmt}")
        suffix = f" ({' '.join(context_parts)})" if context_parts else ""
        if exc_type is not None:
            self.logger.log(
                self.level,
                "%s failed%s",
                self.operation_name,
                suffix,
            )
        else:
            self.logger.log(
                self.level,
                "%s completed%s",
                self.operation_name,
                suffix,
            )
