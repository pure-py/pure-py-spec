"""PurePy reference type checker package."""

from .check_module import check_file
from .check_program import check_program

__all__ = ["check_file", "check_program"]
