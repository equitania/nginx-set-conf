"""
nginx-set-conf - A tool for managing Nginx configurations
"""

from . import utils as utils
from . import validators as validators

__version__ = "1.18.0"

__all__ = [
    "__version__",
    "utils",
    "validators",
]
