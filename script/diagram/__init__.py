"""Dependency diagram of the organisation's repositories, as SVG"""

import importlib
import pkgutil

ORG = "pure-py"


def register(package: str, path: list[str]) -> None:
    """Import every module of a package, so that each kind defined there registers itself"""
    for module in pkgutil.iter_modules(path):
        importlib.import_module(f"{package}.{module.name}")
