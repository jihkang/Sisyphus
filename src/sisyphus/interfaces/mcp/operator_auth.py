from __future__ import annotations

from collections.abc import Mapping
import hmac
import os


OPERATOR_CAPABILITY_ENV = "SISYPHUS_OPERATOR_CAPABILITY"


def require_operator_capability(
    provided: object,
    *,
    environ: Mapping[str, str] | None = None,
) -> None:
    environment = os.environ if environ is None else environ
    expected = str(environment.get(OPERATOR_CAPABILITY_ENV) or "")
    candidate = provided if isinstance(provided, str) else ""
    if not expected:
        raise PermissionError(
            f"operator capability is not configured; set {OPERATOR_CAPABILITY_ENV}"
        )
    if not candidate or not hmac.compare_digest(candidate.encode(), expected.encode()):
        raise PermissionError("invalid operator capability")


__all__ = ["OPERATOR_CAPABILITY_ENV", "require_operator_capability"]
