class Logger:
    """Simple logger with prefix and optional verbosity.

    The logger can be configured with a prefix (e.g. module name) and a
    `verbose` flag. Normal logs are always printed, while verbose logs are
    printed only when `verbose` is True.
    """

    def __init__(self, prefix: str, verbose: bool = False) -> None:
        self.prefix = prefix
        self.verbose = verbose

    def log(self, msg: str, *, is_verbose: bool = False) -> None:
        """Log a message.

        :param msg: Message to log.
        :param is_verbose: If True, the message is printed only when
            `self.verbose` is True. If False, the message is always printed.
        """
        if is_verbose and not self.verbose:
            return
        print(f"[{self.prefix}] {msg}", flush=True)
__all__ = ["Logger"]
