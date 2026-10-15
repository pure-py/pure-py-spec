"""PurePy reference checker package."""

from .check_module import check_file as check_module
from .check_program import check_program

__all__ = ["check_module", "check_program"]
