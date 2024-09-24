"""App Metadata."""

from __future__ import annotations

import importlib.metadata

__all__ = ("__version__", "__project__")

__version__ = importlib.metadata.version("gobuddy")
"""Version of the app."""
__project__ = importlib.metadata.metadata("gobuddy")["Name"]
"""Name of the app."""
