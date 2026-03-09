# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

##############################################################################
# region> IMPORT
##############################################################################
import collections as _collections



# endregion
##############################################################################
# region> CACHING
##############################################################################
# TODO: Cache `CRS`, `SRS`, `pyproj.Transformer`, and
#  `GriddedTransformer` instances that are created via this library.

_CACHING_IS_ENABLED: bool = True

_cache: dict[_collections.abc.Callable, dict] = {}

def enable_caching(enable: bool = True, *, clear: bool = False) -> None:
    """
    Enable or disable caching, and optionally clear the cache.

    Parameters
    ----------
    enable : bool, default=True
        Whether to enable caching.
    clear : bool, default=False
        Whether to clear the cache.

    """
    global _CACHING_IS_ENABLED
    _CACHING_IS_ENABLED = enable
    if clear:
        _cache.clear()



# endregion
