from __future__ import annotations

from .compat.serialization import install_serialization_compat
from .interfaces.inbox.mapper import (
    changed_file_to_record,
    conversation_payload_to_record,
    inbox_event_to_record,
    pull_request_merged_payload_to_record,
)
from .interfaces.inbox.parser import (
    ChangedFile,
    ConversationPayload,
    InboxEvent,
    PullRequestMergedPayload,
    parse_changed_file,
    parse_conversation_payload,
    parse_inbox_event,
    parse_pull_request_merged_payload,
)


install_serialization_compat(
    ChangedFile,
    encode_mapping=changed_file_to_record,
    decode_mapping=parse_changed_file,
)
install_serialization_compat(
    ConversationPayload,
    encode_mapping=conversation_payload_to_record,
    decode_mapping=parse_conversation_payload,
)
install_serialization_compat(
    PullRequestMergedPayload,
    encode_mapping=pull_request_merged_payload_to_record,
    decode_mapping=parse_pull_request_merged_payload,
)
install_serialization_compat(
    InboxEvent,
    encode_mapping=inbox_event_to_record,
    decode_mapping=parse_inbox_event,
)


__all__ = [
    "ChangedFile",
    "ConversationPayload",
    "InboxEvent",
    "PullRequestMergedPayload",
]
