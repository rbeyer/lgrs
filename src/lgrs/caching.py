# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

##############################################################################
# region> IMPORT
##############################################################################
import abc as _abc
import collections as _collections
import functools as _functools
import typing as _typing



# endregion
##############################################################################
# region> INTRA-MODULE USE
##############################################################################
_CACHING_IS_ENABLED: bool = True
_NOT_FOUND = object()

_cache: dict = {}

def _query_cache(
        func_or_cls: _collections.abc.Callable | type, *args, **kwargs
) -> tuple[_collections.abc.Hashable, _typing.Any]:
    # Abort if caching is disabled.
    if not _CACHING_IS_ENABLED:
        return (None, _NOT_FOUND)

    # Generate cache key.
    kwargs_list = list(kwargs.items())
    kwargs_list.sort()
    kwargs_tuple = tuple(kwargs_list)
    key = (func_or_cls, args, kwargs_tuple)

    # Return cached instance or `None`.
    cached = _cache.get(key, _NOT_FOUND)
    return (key, cached)

def _store_to_cache(key: _collections.abc.Hashable, value: _typing.Any) -> None:
    if key is not None:
        _cache[key] = value



# endregion
##############################################################################
# region> INTRA-PACKAGE USE
##############################################################################
class _MetaMultiton(type):
    """
    Metaclass to support optional caching.

    Caching is controlled by `enable_caching()`.

    Examples
    --------
    >>> class MyClass(metaclass=_MetaMultiton):
    ...     def __init__(self, string: str) -> None:
    ...         pass
    >>> enable_caching()
    >>> x = MyClass("spam")
    >>> y = MyClass("spam")
    >>> y is x
    True
    >>> z = MyClass("pram")
    >>> z is x
    False
    """
    def __call__(cls, *args, **kwargs) -> _typing.Any:
        key, cached = _query_cache(cls, *args, **kwargs)
        if cached is not _NOT_FOUND:
            return cached
        new = cls.__new__(cls, *args, **kwargs)
        cls.__init__(new, *args, **kwargs)
        _store_to_cache(key, new)
        return new

class _AbstractMetaMultiton(_abc.ABCMeta):
    """
    Metaclass to support optional caching, that inherits from `abc.ABCMeta`.

    Caching is controlled by `enable_caching()`.

    See Also
    --------
    _MetaMultiton : Concrete equivalent, with examples.
    """
    __call__ = _MetaMultiton.__call__

def _optionally_cache(
        func: _collections.abc.Callable
) -> _collections.abc.Callable:
    """
    Decorate a function to optionally cache its results.

    Caching is controlled by `enable_caching()`.

    Parameters
    ----------
    func : callable
        The callable to optionally cache.

    Returns
    -------
    wrapped : callable
        A wrapped version of `func`.

    Examples
    --------
    >>> @_optionally_cache
    ... def my_func(string: str) -> list:
    ...     return []
    >>> enable_caching()
    >>> x = my_func("spam")
    >>> y = my_func("spam")
    >>> y is x
    True
    >>> z = my_func("pram")
    >>> z is x
    False
    """
    @_functools.wraps(func)
    def wrapped(*args, **kwargs) -> _typing.Any:
        key, cached = _query_cache(func, *args, **kwargs)
        if cached is not _NOT_FOUND:
            return cached
        result = func(*args, **kwargs)
        _store_to_cache(key, result)
        return result
    return wrapped



# endregion
##############################################################################
# region> PUBLIC USE
##############################################################################
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