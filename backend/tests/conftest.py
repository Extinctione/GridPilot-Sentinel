"""
Shared pytest fixtures/setup.

Ensures the `backend` directory (the parent of this `tests` folder and of
the `app` package) is on sys.path, so `import app...` resolves the same
way whether pytest is invoked from `backend/`, from the repo root, or
from an IDE's own working directory.
"""

from __future__ import annotations

import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
