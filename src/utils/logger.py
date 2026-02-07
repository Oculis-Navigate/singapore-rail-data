"""Simple logging utility for MRT data pipeline."""
import sys
from typing import Optional


class Logger:
    """Simple logger with clean output formatting."""

    # ANSI color codes
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"

    def __init__(self, verbose: bool = True, use_colors: bool = True):
        self.verbose = verbose
        self.use_colors = use_colors
        self.indent_level = 0

    def _indent(self) -> str:
        """Get current indentation string."""
        return "  " * self.indent_level

    def _color(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if self.use_colors:
            return f"{color}{text}{self.END}"
        return text

    def info(self, message: str):
        """Log info message."""
        if self.verbose:
            print(f"{self._indent()}{message}")

    def success(self, message: str):
        """Log success message."""
        if self.verbose:
            print(f"{self._indent()}{self._color('✓', self.GREEN)} {message}")

    def warning(self, message: str):
        """Log warning message."""
        print(f"{self._indent()}{self._color('⚠', self.YELLOW)} {message}", file=sys.stderr)

    def error(self, message: str):
        """Log error message."""
        print(f"{self._indent()}{self._color('✗', self.RED)} {message}", file=sys.stderr)

    def section(self, title: str):
        """Log section header."""
        if self.verbose:
            print(f"\n{self._color('▶', self.BLUE)} {self._color(title, self.BOLD)}")
            self.indent_level = 1

    def subsection(self, title: str):
        """Log subsection header."""
        if self.verbose:
            print(f"\n{self._indent()}{self._color('→', self.BLUE)} {title}")
            self.indent_level = 2

    def item(self, message: str, status: Optional[str] = None):
        """Log an item with optional status."""
        if self.verbose:
            if status:
                print(f"{self._indent()}• {message} {self._color(f'[{status}]', self.YELLOW)}")
            else:
                print(f"{self._indent()}• {message}")

    def progress(self, current: int, total: int, message: str = "Processing"):
        """Show progress indicator."""
        if self.verbose:
            percent = (current / total) * 100 if total > 0 else 0
            bar_length = 30
            filled = int(bar_length * current / total) if total > 0 else 0
            bar = f"{'█' * filled}{'░' * (bar_length - filled)}"
            print(f"\r{self._indent()}{message}: {bar} {percent:.1f}% ({current}/{total})", end="", flush=True)
            if current == total:
                print()  # New line when complete

    def result(self, message: str):
        """Log a result/summary line."""
        print(f"\n{self._color('═', self.BLUE) * 50}")
        print(f"{self._color(message, self.BOLD)}")
        print(f"{self._color('═', self.BLUE) * 50}")

    def stats(self, label: str, value: str, unit: str = ""):
        """Log a statistic."""
        print(f"{self._indent()}{self._color(label + ':', self.BOLD)} {value} {unit}")

    def debug(self, message: str):
        """Log debug message (only in verbose mode)."""
        if self.verbose:
            print(f"{self._indent()}{self._color('[DEBUG]', self.YELLOW)} {message}")


# Global logger instance
logger = Logger()


def set_logger(new_logger: Logger):
    """Set the global logger instance."""
    global logger
    logger = new_logger
