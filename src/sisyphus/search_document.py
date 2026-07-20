from __future__ import annotations

from .application.codecs.search import decode_search_document, encode_search_document
from .application.search.models import (
    SEARCH_DOCUMENT_SCHEMA_VERSION,
    SearchDocument,
    fingerprint_search_document_payload,
)
from .infra.search.documents import (
    project_repo_search_documents,
    project_task_search_documents,
)
from .compat.serialization import install_serialization_compat


install_serialization_compat(
    SearchDocument,
    encode_mapping=encode_search_document,
    decode_mapping=decode_search_document,
)

__all__ = [
    "SEARCH_DOCUMENT_SCHEMA_VERSION",
    "SearchDocument",
    "fingerprint_search_document_payload",
    "project_repo_search_documents",
    "project_task_search_documents",
]
