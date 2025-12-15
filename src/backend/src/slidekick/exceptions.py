

class BaseSlidekickError(Exception):
    """Base exception for Slidekick errors."""

    def __init__(self, message: str, original_exception: Exception | None = None):
        super().__init__(message)
        self.original_exception = original_exception


class ToolExecutorError(BaseSlidekickError):
    """Exception for tool executor errors."""
    pass