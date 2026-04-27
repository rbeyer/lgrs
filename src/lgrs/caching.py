"""Support for caching across `lgrs` library."""

# Copyright © 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

##############################################################################
# region> IMPORT
##############################################################################
import abc as _abc
import collections as _collections
import functools as _functools
import typing as _typing
import weakref as _weakref



# endregion
##############################################################################
# region> INTRA-MODULE USE
##############################################################################
_CACHING_IS_ENABLED: bool = True
_NOT_FOUND = object()

_cache: dict = {}
_weak_cache: _weakref.WeakKeyDictionary[_typing.Any, dict[str, _typing.Any]] = _weakref.WeakKeyDictionary()

def _query_cache(
        func_or_cls: _collections.abc.Callable | type, *args, **kwargs
) -> tuple[_collections.abc.Hashable, _typing.Any]:
    # Abort if caching is disabled.
    default_result = (None, _NOT_FOUND)
    if not _CACHING_IS_ENABLED:
        return default_result

    # Generate cache key.
    kwargs_list = list(kwargs.items())
    kwargs_list.sort()
    kwargs_tuple = tuple(kwargs_list)
    key = (func_or_cls, args, kwargs_tuple)

    # Return cached instance or `None`.
    try:
        cached = _cache.get(key, _NOT_FOUND)
    except TypeError as e:
        # Note: If `key` is unhashable, return as though caching were
        # disabled.
        try:
            hash(key)
        except TypeError:
            return default_result
        else:
            raise e
    return (key, cached)

def _query_weak_cache(
        instance: _collections.abc.Hashable, *,
        key: str, default: _typing.Any = _NOT_FOUND
) -> _typing.Any:
    if _CACHING_IS_ENABLED:
        cached_dict = _weak_cache.get(instance, default)
        if cached_dict is default:
            return default
        cached_val = cached_dict.get(key, default)
        return cached_val
    else:
        return default

def _store_to_cache(key: _collections.abc.Hashable, value: _typing.Any) -> None:
    if key is not None:
        _cache[key] = value

def _store_to_weak_cache(
        instance: _collections.abc.Hashable, *,
        key: str, value: _typing.Any
) -> None:
    if not _CACHING_IS_ENABLED:
        return
    cached_dict = _weak_cache.get(instance)
    if cached_dict is None:
        cached_dict = {}
        _weak_cache[instance] = cached_dict
    cached_dict[key] = value



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
        _weak_cache.clear()



# endregion