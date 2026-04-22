"""
nginx-set-conf - A tool for managing Nginx configurations
"""

from . import config_templates as config_templates
from . import utils as utils
from . import validators as validators

__version__ = "1.11.0"

__all__ = [
    "__version__",
    "config_templates",
    "utils",
    "validators",
]
