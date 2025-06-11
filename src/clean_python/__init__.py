"""Clean Python package with best practices."""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .actions.build import build
from .core import calculate_sum, greet

__all__ = ["greet", "calculate_sum", "build"]
