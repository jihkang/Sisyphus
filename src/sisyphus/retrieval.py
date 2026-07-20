from __future__ import annotations

from .application.codecs.search import encode_retrieval_result
from .application.search.retrieval import *  # noqa: F403
from .application.search.retrieval import __all__
from .compat.serialization import install_serialization_compat


install_serialization_compat(RetrievalResult, encode_mapping=encode_retrieval_result)  # noqa: F405
