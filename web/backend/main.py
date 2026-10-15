"""Website Backend Server Entrypoint for Apex Fantasy Analytics.

Allows launching the backend server directly from the `web` namespace:
    python -m uvicorn web.backend.main:app --reload --port 8000
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.backend.main:app", host="127.0.0.1", port=8000, reload=True)
