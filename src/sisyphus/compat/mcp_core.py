from __future__ import annotations

import sys as _sys

from ..interfaces.mcp import service as _service

_sys.modules[__name__] = _service
