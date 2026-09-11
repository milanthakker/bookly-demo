"""Bookly support agent.

Dependencies live only in the project-local .venv, so running with the system
interpreter fails partway through imports with a confusing ModuleNotFoundError.
Fail early instead, and say how to run it properly.
"""

import sys
from pathlib import Path

_VENV_PYTHON = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python"

# sys.prefix == sys.base_prefix means no virtualenv is active. Only complain if
# the project venv is actually there to point at -- this stays quiet for
# container or CI setups that install the dependencies globally on purpose.
if sys.prefix == sys.base_prefix and _VENV_PYTHON.exists():
    sys.exit(
        f"Bookly must run inside its virtualenv, but is running under "
        f"{sys.executable}.\n"
        f"  Use:  bash start.sh\n"
        f"  Or:   {_VENV_PYTHON} -m uvicorn app.main:app --reload"
    )
