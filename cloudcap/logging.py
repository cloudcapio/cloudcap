import logging
from typing import Any


FORMAT = "(%(asctime)s)\t%(levelname)s\t%(message)s (%(name)s, %(filename)s:%(lineno)d)"  # type: ignore


class CloudcapLogFormatter(logging.Formatter):
    """Custom Formatter to colorize log messages."""

    COLORS = {
        "DEBUG": "\033[94m",  # Blue
        "INFO": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[95m",  # Purple
    }
    RESET = "\033[0m"

    def format(self, record: Any):
        log_level = record.levelname
        if log_level in self.COLORS:
            # record.msg = f"{self.COLORS[log_level]}{record.msg}{self.RESET}"
            message = super().format(record)
            return f"{self.COLORS[log_level]}{message}{self.RESET}"
        else:
            return super().format(record)


def setup_logging(level: Any = logging.WARNING):
    # logging.basicConfig(level=level)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    colored_formatter = CloudcapLogFormatter(fmt=FORMAT)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(colored_formatter)
    root_logger.addHandler(console_handler)
