from __future__ import annotations


SPEC_VALIDATION_GATE_CODES = frozenset(
    {
        "SPEC_VALIDATION_FAILED",
        "SPEC_VALIDATION_MISSING",
        "SPEC_VALIDATION_STALE",
    }
)
SPEC_VALIDATION_SOURCES = frozenset({"spec_validation"})


__all__ = ["SPEC_VALIDATION_GATE_CODES", "SPEC_VALIDATION_SOURCES"]
