from __future__ import annotations

import sys as _sys

from .compat import cli as _cli

if __name__ == "__main__":
    raise SystemExit(_cli.main())

_sys.modules[__name__] = _cli
