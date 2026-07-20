from __future__ import annotations

from .application.codecs.episode_trace import encode_episode_step
from .compat.serialization import install_serialization_compat
from .composition.episode_trace import *  # noqa: F403
from .composition.episode_trace import __all__


install_serialization_compat(EpisodeStep, encode_mapping=encode_episode_step)  # noqa: F405
