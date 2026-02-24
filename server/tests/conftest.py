from __future__ import annotations

import sys
from pathlib import Path


# Ensure `import app...` works no matter where pytest is launched from.
SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))
