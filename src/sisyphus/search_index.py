from __future__ import annotations

from .application.codecs.search import encode_search_index_rebuild_result
from .compat.serialization import install_serialization_compat
from .infra.search.index import *  # noqa: F403
from .infra.search.index import __all__


install_serialization_compat(  # noqa: F405
    SearchIndexRebuildResult,
    encode_mapping=encode_search_index_rebuild_result,
)
