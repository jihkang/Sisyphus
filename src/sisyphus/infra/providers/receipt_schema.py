from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import re
import stat

from ...shared.digests import stable_json_hash


LOCAL_AGENT_RECEIPT_SCHEMA_VERSION = "sisyphus.local_agent_run.v1"
MAX_LOCAL_AGENT_RECEIPT_BYTES = 2_000_000
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


class InvalidLocalAgentReceipt(ValueError):
    pass


def read_local_agent_receipt(path: Path) -> dict[str, object]:
    try:
        file_fd = os.open(path, _READ_FLAGS)
    except OSError as exc:
        raise InvalidLocalAgentReceipt(f"cannot open local agent receipt: {exc}") from exc
    try:
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise InvalidLocalAgentReceipt("local agent receipt is not a regular file")
        if metadata.st_size > MAX_LOCAL_AGENT_RECEIPT_BYTES:
            raise InvalidLocalAgentReceipt(
                f"local agent receipt exceeds {MAX_LOCAL_AGENT_RECEIPT_BYTES} bytes"
            )
        payload = _read_bounded(file_fd)
    finally:
        os.close(file_fd)
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidLocalAgentReceipt("local agent receipt is not valid UTF-8 JSON") from exc
    return parse_local_agent_receipt(decoded)


def parse_local_agent_receipt(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidLocalAgentReceipt("local agent receipt must be a JSON object")
    receipt = {str(key): item for key, item in value.items()}
    if receipt.get("schema_version") != LOCAL_AGENT_RECEIPT_SCHEMA_VERSION:
        raise InvalidLocalAgentReceipt("local agent receipt has an unsupported schema version")
    status = receipt.get("status")
    if status not in {"completed", "blocked", "failed"}:
        raise InvalidLocalAgentReceipt("local agent receipt status is invalid")

    facts = receipt.get("completion_facts")
    if not isinstance(facts, Mapping):
        raise InvalidLocalAgentReceipt("local agent receipt completion_facts must be an object")
    if "completion_ready" in facts and type(facts["completion_ready"]) is not bool:
        raise InvalidLocalAgentReceipt("completion_ready must be a boolean")
    changed_files = facts.get("changed_files")
    if changed_files is not None and (
        not isinstance(changed_files, list)
        or any(not isinstance(path, str) for path in changed_files)
    ):
        raise InvalidLocalAgentReceipt("changed_files must be a string list")
    for field in (
        "baseline_test_step",
        "last_mutation_step",
        "last_successful_test_step",
    ):
        if field in facts and facts[field] is not None and type(facts[field]) is not int:
            raise InvalidLocalAgentReceipt(f"{field} must be an integer or null")

    events = receipt.get("events")
    if events is not None:
        if not isinstance(events, list) or any(not isinstance(event, Mapping) for event in events):
            raise InvalidLocalAgentReceipt("local agent receipt events must be an object list")
        if any(
            "action" in event and not isinstance(event.get("action"), str)
            for event in events
        ):
            raise InvalidLocalAgentReceipt("local agent receipt event actions must be strings")

    for field in ("request_digest", "receipt_digest"):
        digest = receipt.get(field)
        if digest is not None and (
            not isinstance(digest, str) or _DIGEST_PATTERN.fullmatch(digest) is None
        ):
            raise InvalidLocalAgentReceipt(f"{field} is invalid")
    claimed_digest = receipt.get("receipt_digest")
    if isinstance(claimed_digest, str):
        unsigned = dict(receipt)
        unsigned.pop("receipt_digest", None)
        if stable_json_hash(unsigned) != claimed_digest:
            raise InvalidLocalAgentReceipt("local agent receipt digest does not match its payload")
    return receipt


def sign_local_agent_receipt(payload: Mapping[str, object]) -> dict[str, object]:
    signed = dict(payload)
    signed.pop("receipt_digest", None)
    signed["receipt_digest"] = stable_json_hash(signed)
    return signed


def _read_bounded(file_fd: int) -> bytes:
    chunks: list[bytes] = []
    remaining = MAX_LOCAL_AGENT_RECEIPT_BYTES + 1
    while remaining > 0:
        chunk = os.read(file_fd, min(remaining, 64 * 1024))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    payload = b"".join(chunks)
    if len(payload) > MAX_LOCAL_AGENT_RECEIPT_BYTES:
        raise InvalidLocalAgentReceipt(
            f"local agent receipt exceeds {MAX_LOCAL_AGENT_RECEIPT_BYTES} bytes"
        )
    return payload


__all__ = [
    "InvalidLocalAgentReceipt",
    "LOCAL_AGENT_RECEIPT_SCHEMA_VERSION",
    "MAX_LOCAL_AGENT_RECEIPT_BYTES",
    "parse_local_agent_receipt",
    "read_local_agent_receipt",
    "sign_local_agent_receipt",
]
