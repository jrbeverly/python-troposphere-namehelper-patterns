"""Single source of truth for the package version.

Kept in its own module so that submodules can read the version without
importing the package root (which would create an import cycle).
"""

__version__ = "0.0.0"
