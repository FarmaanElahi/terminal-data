from enum import StrEnum


class TerminalEnum(StrEnum):
    """Base class for all terminal enums."""

    pass


class LogLevels(TerminalEnum):
    info = "INFO"
    warn = "WARN"
    error = "ERROR"
    debug = "DEBUG"
