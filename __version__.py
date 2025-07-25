"""Version information for kivra-sync."""

import os

def get_version():
    """Get the version from the VERSION file."""
    version_file = os.path.join(os.path.dirname(__file__), 'VERSION')
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return 'unknown'

__version__ = get_version()
