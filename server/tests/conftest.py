from __future__ import annotations

import os
import sys
from pathlib import Path


# Ensure `import app...` works no matter where pytest is launched from.
SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

# Keep tests independent from developer-local config.yaml defaults.
TEST_CONFIG_PATH = Path(__file__).resolve().parent / "config.test.yaml"
os.environ["MIDAS_CONFIG_PATH"] = str(TEST_CONFIG_PATH)
