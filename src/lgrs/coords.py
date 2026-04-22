"""
Coordinate types: geographic and projected, non-gridded and gridded.

Examples
--------
>>> lps_lgrs = LpsLgrs(
...     longitudinal_band="A", easting_area="Z", northing_area="S",
...     easting="13590", northing="08480"
... )
>>> alt_lps_lgrs = LpsLgrs.from_string("AZS1359008480")
>>> alt_lps_lgrs.is_equal_to(lps_lgrs, error=True)
"""

# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

###############################################################################
# region> IMPORT
###############################################################################
# External.
from __future__ import annotations
import abc as _abc
import builtins as _builtins
import collections as _collections
import dataclasses as _dataclasses
import functools as _functools
import math as _math
_floor = _math.floor
import pyproj as _pyproj
import regex as _regex
import types as _types
import typing as _typing

# Internal.
import lgrs.caching as _caching
import lgrs.database as _database
import lgrs.exceptions as _exceptions
import lgrs.srs.srs as _srs
import lgrs.srs.wkt as _wkt


# endregion
###############################################################################
# region> TYPE ALIASES
###############################################################################
type ToMethod = _collections.abc.Callable[..., BaseCoordinate]



# endregion
###############################################################################
# region> UTILITIES: REDIRECTION & CACHING
###############################################################################
def _cache(func: ToMethod) -> ToMethod:
    public_func = getattr(BaseCoordinate, func.__name__.removeprefix("_"))
    @_functools.wraps(public_func)
    def wrapped(self: BaseCoordinate, **kwargs) -> BaseCoordinate:
        new = func(self, **kwargs)
        self._register_cousin(new)
        return new
    return wrapped

def _calc_na_letterset(zone_number: int) -> int:
    na_letterset = (zone_number - 1) % 3  # Eq. 83
    return na_letterset

def _redirect(func: ToMethod) -> ToMethod:
    """
    Redirect `.to_*()` to the `._to_*()` of the best cousin instance.

    A method decorated with this function will never be called (and
    therefore can be empty). Rather, a "cousin" `BaseCoordinate` instance
    is found and its (hidden) `._to_*()` counterpart is called instead. The
    result of that call is returned. Specifically, that cousin is used whose
    `._to_*()` is the most performant among those of available cousins.

    A "cousin" is another `BaseCoordinate` whose location (after
    transformation) and constraints are the same as those of `self`. Cousins
    are often generated during intermediate calculations, whether internal
    or external (i.e., by the user), so caching them into cousin groups
    improves efficiency.

    Parameters
    ----------
    func : callable
        The public `.to_*()` method to be decorated. It will never be
        called.

    Returns
    -------
    coordinate : BaseCoordinate
        The output of the `._to_*(**kwargs)` call.
    """
    @_functools.wraps(func)
    def wrapped(self: BaseCoordinate) -> BaseCoordinate:
        # Note: `func` itself is only used for its return type and name.
        best_cousin, is_resolved = self._get_best_cousin(func)
        if is_resolved:
            return best_cousin
        new = getattr(best_cousin, f"_{func.__name__}")()
        return new
    return wrapped

@_functools.cache
def _resolve_out_types(func: _collections.abc.Callable) -> tuple[type, ...]:
    out_hint = _typing.get_type_hints(func)["return"]
    if isinstance(out_hint, _types.UnionType):
        out_types = _typing.get_args(out_hint)
    else:
        out_types = (out_hint,)
    return out_types

def _return_none(self: BaseCoordinate) -> None:
    return None



# endregion
###############################################################################
# region> UTILITIES: REGEX
###############################################################################
def _compile_regex_without_i_and_o(pattern: str) -> _regex.Pattern:
    clean_pattern = _regex.sub("[A-Z]-[A-Z]", _remove_i_and_o, pattern)
    return _regex.compile(clean_pattern)

def _expand_char_range(char_range: str) -> list[str]:
    start_char, end_char = char_range.split("-")
    chars = [chr(i)
             for i in range(ord(start_char), ord(end_char) + 1)]
    return chars

def _format_as_five_digit_int(n: float) -> str:
    return f"{_smart_truncate(n):05}"

def _index_char_set(
        pattern: _regex.Pattern | None = None, name: str | None = None, *,
        chars: str | None = None, start:int, **manual: int
) -> tuple[dict[str, int], dict[int, str]]:
    # Resolve `chars` from group pattern, if necessary.
    # Note: Not general (e.g., does not accommodate escaped ")").
    if chars is None:
        chars = _regex.search(
            rf"\(\?P<{name}>\[(?P<gpattern>.*?)]\)", pattern.pattern
        ).group("gpattern")

    # Convert to mappings.
    indices = range(start, len(chars) + start)
    idx_to_char = dict(zip(indices, chars))
    char_to_idx = dict(zip(chars, indices))
    # Note: Implementation details here are fit for purpose (e.g., Table
    # 6 in M2025).
    for char, idx in manual.items():
        if idx in idx_to_char:
            raise TypeError(f"Index cannot be duplicated: {idx!r}")
        idx_to_char[idx] = char
        char_to_idx.setdefault(char, idx)
    # TODO: This block is temporary, to remind me to test the case where
    #  the mapping cannot be inverted without loss.
    if len(char_to_idx) < len(idx_to_char):
        char_to_idx = None
    return (char_to_idx, idx_to_char)

def _make_en_pattern(*digit_count: int) -> str:
    pattern = "|".join(
        f"((?P<easting>[0-9]{{{i}}})(?P<northing>[0-9]{{{i}}}))"
        for i in sorted(digit_count, reverse=True)
    )
    return pattern

def _map_index_char_sets(
        *chars_tup: str, start:int
) -> tuple[dict[int, dict[str, int]], dict[int, dict[str, int]]]:
    i_to_char_to_idx = {}
    i_to_idx_to_char = {}
    for i, chars in enumerate(chars_tup):
        char_to_idx, idx_to_char = _index_char_set(chars=chars, start=start)
        i_to_char_to_idx[i] = char_to_idx
        i_to_idx_to_char[i] = idx_to_char
    return (i_to_char_to_idx, i_to_idx_to_char)

def _remove_i_and_o(match: _regex.Match) -> str:
    expanded = _expand_char_range(match.group())
    for char in ("I", "O"):
        try:
            expanded.remove(char)
        except ValueError:
            continue
    return "".join(expanded)



# endregion
###############################################################################
# region> UTILITIES: OTHER
###############################################################################
def _easy_dataclass(cls: type) -> type:
    # Isolate non-universal fields.
    naive_dataclass = _dataclasses.dataclass(cls, frozen=True, kw_only=True)
    univ_field_name_set = {
        field.name
        for field in _dataclasses.fields(_BaseCoordinate)
    }
    non_univ_fields = [
        field
        for field in _dataclasses.fields(naive_dataclass)
        if field.name not in univ_field_name_set
    ]

    # Insert "shadow" dataclass in inheritance, to push universal fields
    # to end.
    field_annotations = {
        field.name: field.type
        for field in non_univ_fields
    }
    shadow_cls = type(
        f"_Shadow{cls.__name__}", (_AbstractBaseCoordinate,),
        {"__annotations__": field_annotations}
    )
    shadow_dataclass = _dataclasses.dataclass(
        shadow_cls, kw_only=True, frozen=True
    )
    mro = (
        *cls.__mro__[:cls.__mro__.index(_AbstractBaseCoordinate)],
        *shadow_dataclass.__mro__,
    )
    twin_cls = type(cls.__name__, mro, {"__module__": cls.__module__})

    # Create and return outer dataclass.
    dataclass = _dataclasses.dataclass(kw_only=True, frozen=True)(twin_cls)
    return dataclass

def _smart_truncate(f: float, *, tolerance: float = 0.001) -> int:
    # TODO: Determine whether `tolerance` is a good choice. Code
    #  mimics `check_decimal_round()` of reference code and presumably
    #  mitigates undesirable results that arise due to floating-point
    #  precision.
    nearest_int = round(f)
    if abs(nearest_int - f) < tolerance:
        return nearest_int
    else:
        return _floor(f)



# endregion
###############################################################################
# region> COORDINATE BASE TYPES
###############################################################################
class _AbstractBaseCoordinate(_abc.ABC):
    pass

# Note: `_BaseCoordinate` is useful for defining behavior that depends
# on the class being a dataclass. Conversely, `BaseCoordinate` and its
# hidden subclasses are useful for defining all other behavior (without
# accidentally implying dataclass fields).
@_dataclasses.dataclass(frozen=True, kw_only=True)
class _BaseCoordinate(_AbstractBaseCoordinate):

    #* Fields and validation. -------------------------------------------------
    _fields_cached: _typing.ClassVar[tuple[_dataclasses.Field, ...]]
    polar_ltm: bool = False
    prefer_lps: bool = False
    extended_ltm: bool = False
    validate: _dataclasses.InitVar[bool] = True

    def _register_validation(self) -> None:
        object.__setattr__(self, "_was_validated", True)

    def _validate(self) -> None:
        for field in self._get_fields():
            result = getattr(self, f"_validate_{field.name}")()
            if result is not None:
                # Note: Cannot assign directly, because `self` is a
                # frozen dataclass.
                object.__setattr__(self, field.name, result)
        # Note: `._init_kwargs` effectively freezes values, which may
        # not be finalized until validation completes. It should not be
        # assigned until after validation.
        assert "_init_kwargs" not in self.__dict__
        self._register_validation()

    def _validate_polar_ltm(self) -> None:
        if self.polar_ltm:
            if (self.prefer_lps or self.extended_ltm):
                raise _exceptions.MalformedCoordinate(
                    "If `polar_ltm` is `True`, `prefer_lps` and `extended_ltm` "
                    "must be `False` (or `None`)."
                )

    _validate_prefer_lps = _return_none
    _validate_extended_ltm = _return_none

    #* Initialization. --------------------------------------------------------
    def __post_init__(self, validate: bool) -> None:
        if validate:  # TODO: Uncomment after testing.
        # if validate and False:  # TODO: Comment after testing.
            self._validate()

    @_functools.cached_property
    def _init_kwargs(self) -> dict[str, _typing.Any]:
        return {
            field.name: getattr(self, field.name)
            for field in self._get_fields()
        }

    def with_constraints(
            self, *,
            polar_ltm: bool | None = None, prefer_lps: bool | None = None,
            extended_ltm: bool | None = None, validate: bool = False,
            copy: bool = False
    ) -> _typing.Self:
        # Resolve new initialization kwargs.
        new_init_kwargs = self._init_kwargs.copy()
        if polar_ltm is not None:
            new_init_kwargs["polar_ltm"] = polar_ltm
        if prefer_lps is not None:
            new_init_kwargs["prefer_lps"] = prefer_lps
        if extended_ltm is not None:
            new_init_kwargs["extended_ltm"] = extended_ltm

        # Return `self`, if suitable and allowed.
        if (
            not copy
            and not validate
            and new_init_kwargs == self._init_kwargs
        ):
            return self

        # Create and return copy, constrained as specified.
        new = type(self)(**new_init_kwargs)
        return new

    #* Field support. ---------------------------------------------------------
    def __iter__(self) -> _collections.abc.Iterable:
        return iter(self._init_kwargs.values())

    @_functools.cached_property
    def _constraint_keys(self) -> tuple[str, ...]:
        # Note: Assumes that all fields of `_BaseCoordinate` are
        # constraints, consistent with `_easy_dataclass()`.
        constraint_keys = tuple(
            field.name
            for field in _BaseCoordinate._get_fields()
        )
        _BaseCoordinate._constraint_keys = constraint_keys
        return constraint_keys

    @classmethod
    @_functools.cache
    def _get_fields(cls) -> tuple[_dataclasses.Field, ...]:
        return _dataclasses.fields(cls)

    @classmethod
    @_functools.cache
    def _get_field_name_to_type(cls) -> dict[str, type]:
        name_to_type = {}
        field_name_set = {
            field.name
            for field in cls._get_fields()
        }
        for name, typ in _typing.get_type_hints(cls).items():
            if name not in field_name_set:
                continue
            if isinstance(typ, _types.UnionType):
                types = list(_typing.get_args(typ))
                types.remove(type(None))
                typ, = types  # *REASSIGNMENT*
            name_to_type[name] = typ
        return name_to_type

    @_functools.cached_property
    def _nonconstraint_kwargs(self) -> dict[str, _typing.Any]:
        return {
            field_name: field_val
            for field_name, field_val in self._init_kwargs.items()
            if field_name not in self._constraint_keys
        }


class BaseCoordinate(_BaseCoordinate):
    # TODO: Document that `MalformedCoordinate` may be raised.
    _idx: int
    _template: str | None = None
    _was_validated: bool = False

    #* Basic behavior. --------------------------------------------------------
    def __bytes__(self) -> _builtins.bytes:
        return self.bytes

    def __copy__(self) -> _typing.Self:
        return self.copy()

    def __str__(self) -> str:
        return self.string

    #* Instantiation. ---------------------------------------------------------
    @classmethod
    def _from_ref_string(cls, string: str) -> _typing.Self:
        # Note: Unlike `_GriddedCoordinate.from_string()`, this method
        # exists solely to support parsing values from
        # `LGRS_Coordinate_Conversion`.
        parts = tuple(string.split(" "))
        if len(parts) == 1:
            raise _exceptions.MalformedCoordinate(
                "`string` must be space-delimited"
            )
        field_name_to_type = cls._get_field_name_to_type()
        if len(parts) > len(field_name_to_type):
            raise _exceptions.MalformedCoordinate(
                "`string` contains too many space-delimited "
                f"components: {string!r}"
            )
        init_kwargs = {
            name: typ(part)
            for part, (name, typ) in zip(parts, field_name_to_type.items())
        }
        return cls(**init_kwargs)

    #* Validation. ------------------------------------------------------------
    @staticmethod
    def _expect_error(
            func: _collections.abc.Callable | None = None
    ) -> _typing.NoReturn:
        if func is not None:
            func()
        raise TypeError("An unknown error occurred.")

    def _raise_malformed_coordinate(
            self, middle: str, *,
            attr_name: str, if_attr_name: str | None = None,
    ) -> _typing.NoReturn:
        if if_attr_name is None:
            prefix = ""
        else:
            prefix = f"For `{if_attr_name}={getattr(self, if_attr_name)!r}`, "
        raise _exceptions.MalformedCoordinate(
            f"{prefix}"
            f"`{attr_name}` must be "
            f"{middle}"
            f", not: {getattr(self, attr_name)!r}"
        )

    def _validate_against_closed_interval(
        self, *, attr_name: str, minimum: _typing.Any, maximum: _typing.Any,
        if_attr_name: str | None = None, coerce_str: bool = False
    ) -> None:
        val = getattr(self, attr_name)
        if coerce_str:
            val = float(val)  # *REASSIGNMENT*
        if not (minimum <= val <= maximum):
            self._raise_malformed_coordinate(
                f"between {minimum} and {maximum}, inclusive",
                attr_name=attr_name, if_attr_name=if_attr_name
            )

    def _validate_against_sequence(
        self, *,
        attr_name: str, sequence: _collections.abc.Sequence,
        if_attr_name: str | None = None
    ) -> None:
        val = getattr(self, attr_name)
        if val not in sequence:
            if len(sequence) == 2:
                item_1, item_2 = sequence
                middle = f"{item_1!r} or {item_2!r}"
            else:
                middle = (
                    f"one of {', '.join(map(repr, sequence[:-1]))}, "
                    f"or {sequence[-1]!r}"
                )
            self._raise_malformed_coordinate(
                attr_name=attr_name, if_attr_name=if_attr_name
            )

    def _validate_hemisphere(self) -> None:
        self._validate_against_sequence(
            attr_name="hemisphere", sequence=("N", "S")
        )

    def validate(self, *, revalidate: bool = False) -> None:
        if not revalidate and self._was_validated:
            return
        new = self.copy(validate=False)
        try:
            new._validate()
        except _exceptions.MalformedCoordinate:
            self._unregister_cousins(*self._cousins)
            raise
        if new._init_kwargs == self._init_kwargs:
            self._register_validation()
            return
        self._unregister_cousins(*self._cousins)
        change_lines = []
        for k, new_v in new._init_kwargs.items():
            old_v = self._init_kwargs[k]
            if new_v != old_v:
                change_lines.append(
                    f"    {k}: {old_v!r} --> {new_v!r}"
                )
        raise _exceptions.MalformedCoordinate(
            "\n"
            "  Validation conformed the following value(s):\n"
            f"{'\n'.join(change_lines)}"
        )

    #* Public data. -----------------------------------------------------------
    @_functools.cached_property
    def bytes(self) -> _builtins.bytes:
        return self.string.encode()

    @_functools.cached_property
    def string(self) -> str:
        if self._template is None:
            string = "".join(self._iter_value_strings())
        else:
            string = self._template.format(**self.__dict__)
        return string

    #* General public methods. ------------------------------------------------
    def copy(self, *, validate: bool = False) -> _typing.Self:
        # Note: `self` can only exist if validated or explicitly not
        # validated. Either way, defaulting `validate` to `False` is
        # appropriate.
        new = type(self)(
            **self._init_kwargs, validate=(validate and not self._was_validated)
        )
        return new

    def is_equal_to(
            self, other: _typing.Self, *,
            max_float_difference: float | None = None, error: bool = False,
            constraints: bool = False
    ) -> bool:
        # Validate and resolve arguments.
        if not isinstance(other, type(self)):
            raise TypeError(
                f"`other` must be of type {type(self).__name__}, not: {other!r}"
            )
        if max_float_difference is None:
            # Note: Expected difference is "very small" but exact
            # default magnitudes are not rigorous.
            if isinstance(self, LatLon):
                max_float_difference = 1e-12
            else:
                max_float_difference = 1e-9

        # Compare.
        if constraints:
            field_names = self._constraint_keys
        else:
            field_names = self._init_kwargs.keys()
        field_name_to_type = self._get_field_name_to_type()
        for field_name in field_names:
            self_val = getattr(self, field_name)
            other_val = getattr(other, field_name)
            if self_val == other_val:
                continue
            field_type = field_name_to_type[field_name]
            if (
                    field_type == "float"
                    and abs(self_val - other_val) <= max_float_difference
            ):
                continue
            if not error:
                return False
            raise TypeError(
                f"{field_name!r} values differ:\n"
                f"    {self_val!r} vs. {other_val!r}"
           )
        return True

    def replace(
            self, *, validate: bool = True, copy: bool = True, **overrides
    ) -> _typing.Self:
        if not copy and not overrides:
            return self
        init_kwargs = self._init_kwargs.copy()
        init_kwargs.update(overrides)
        return type(self)(**init_kwargs, validate=validate)


    #* Transformation caching. ------------------------------------------------
    @property
    def _cousins(self) -> _collections.deque[BaseCoordinate]:
        cached_cousins = _caching._query_weak_cache(
            self._root, key="cousins", default=None
        )
        if cached_cousins is None:
            new_cousins = _collections.deque()
            new_cousins.appendleft(self)
            _caching._store_to_weak_cache(
                self._root, key="cousins", value=new_cousins
            )
            return new_cousins
        else:
            return cached_cousins

    def _get_best_cousin(self, func: ToMethod) -> tuple[BaseCoordinate, bool]:
        # TODO: Maybe simplify to return targeted type or `None`.
        #  (Current approach is unnecessarily general, because the chain
        #  will never skip a type nor (now) jump to the opposite side.)
        # Resolve out types.
        out_types = _resolve_out_types(func)

        # Find best starting point for conversion.
        # Note: `._idx` on each public `BaseCoordinate` subclass
        # indexes the processing chains:
        #   LatLon -> Lps --> LpsLgrs -> LpsAcc  (`._idx` <= 0)
        #   LatLon -> Ltm --> LtmLgrs -> LtmAcc  (`._idx` >= 0)
        # where index magnitudes are set so that interconversion
        # between LGRS and ACC is preferred over (slower)
        # interconversion between LPS/LTM and LGRS.
        min_abs_diff = float("inf")  # Initialize.
        closest_cousin = None  # Initialize.
        for out_type in out_types:
            targ_idx = out_type._idx
            abs_targ_idx = abs(targ_idx)
            for cousin in self._cousins:
                abs_diff = abs(targ_idx - cousin._idx)
                if abs_diff > min_abs_diff:
                    continue
                from_same_chain = (abs_diff <= abs_targ_idx)
                if not from_same_chain:
                    continue
                min_abs_diff = abs_diff
                closest_cousin = cousin
                if min_abs_diff == 0:
                    return (closest_cousin, True)

        # Characterize (or create) best cousin and return.
        if closest_cousin is None:
            best = self._to_latlon()
            is_resolved = isinstance(best, out_types)
        else:
            best = closest_cousin
            is_resolved = False
        return (best, is_resolved)

    def _register_cousin(self, cousin: BaseCoordinate) -> None:
        if _caching._CACHING_IS_ENABLED:
            object.__setattr__(cousin, "_root", self._root)
            self._cousins.appendleft(cousin)

    def _unregister_cousins(self, *cousins: BaseCoordinate) -> None:
        if _caching._CACHING_IS_ENABLED:
            for cousin in cousins:
                self._cousins.remove(cousin)

    @_functools.cached_property
    def _root(self) -> BaseCoordinate:
        # Note: Overridden when instantiated by transformation.
        return self

    @_functools.cached_property
    def constraints(self) -> _types.MappingProxyType[str, bool]:
        return _types.MappingProxyType(
            {
                key: self._init_kwargs[key]
                for key in self._constraint_keys
            }
        )

    #* Coordinate transformation. ---------------------------------------------
    @_redirect
    def to_acc(self) -> LpsAcc | LtmAcc:
        ...

    @_redirect
    def to_latlon(self) -> LatLon:
        ...

    @_redirect
    def to_lgrs(self) -> LpsLgrs | LtmLgrs:
        ...

    @_redirect
    def to_lps_or_ltm(self) -> Lps | Ltm:
        ...

    # TODO: Uncomment abstract methods after implementation.
    # @_abc.abstractmethod
    # def _to_acc(self, **kwargs) -> LpsAcc | LtmAcc:
    #     ...
    #
    # @_abc.abstractmethod
    # def _to_latlon(self, **kwargs) -> LatLon:
    #     ...
    #
    # @_abc.abstractmethod
    # def _to_lgrs(self, **kwargs) -> LpsLgrs | LtmLgrs:
    #     ...
    #
    # @_abc.abstractmethod
    # def _to_lps_or_ltm(self, **kwargs) -> Lps | Ltm:
    #     ...

    #* Utilities. -------------------------------------------------------------
    def _iter_value_strings(self) -> _typing.Iterator[str]:
        for value in self:
            match value:
                case str():
                    yield value
                case bool() | None:
                    continue
                case int() | float():
                    yield repr(value)
                case _:
                    self._expect_error()



# endregion
###############################################################################
# region> NON-GRIDDED COORDINATE TYPES
###############################################################################
class _NonGriddedCoordinate(BaseCoordinate):
    #* Coordinate transformation. ---------------------------------------------
    @_abc.abstractmethod
    def _get_proj_crs(self, **kwargs) -> _srs.CRS:
        ...

    @staticmethod
    @_caching._optionally_cache
    def _get_transformer(
            *, to_geographic: bool, proj_crs: _srs.CRS
    ) -> _pyproj.Transformer:
        geo_crs = _srs.make_lunar_crs()
        if to_geographic:
            crs_from = proj_crs
            crs_to = geo_crs
        else:
            crs_from = geo_crs
            crs_to = proj_crs
        transformer = _pyproj.Transformer.from_crs(crs_from, crs_to)
        return transformer


@_easy_dataclass
class LatLon(_NonGriddedCoordinate):
    # TODO: Should `._template` use N/S and E/W?

    #* Fields and validation. -------------------------------------------------
    _template = "{latitude!r}° {longitude!r}°"
    latitude: float
    longitude: float

    def _validate_latitude(self) -> float:
        conformed_lat, = _database._conform_latitudes((self.latitude,))
        return conformed_lat

    def _validate_longitude(self) -> float:
        conformed_lon, = _database._conform_longitudes((self.longitude,))
        return conformed_lon

    #* Coordinate transformation. ---------------------------------------------
    def _get_proj_crs(self, **kwargs) -> _srs.CRS:
        long_name, = _database._get_lunar_crs_long_names(
            conformed_latitudes=(self.latitude,),
            conformed_longitudes=(self.longitude,),
            **kwargs
        )
        crs_info = _database.LunarCrsInfo._from_long_name(long_name)
        crs = crs_info.get_crs()
        return crs

    @_cache
    def _to_lps_or_ltm(self, *, allow_lps: bool = True) -> Lps | Ltm:
        # Determine projected CRS.
        proj_crs = self._get_proj_crs(
            extended_ltm=self.extended_ltm,
            polar_ltm=self.polar_ltm
        )
        # TODO: Determine minimum absolute latitude for which conversion
        #  to LPS should be attempted.
        force_lps_attempt = (
                self.prefer_lps
                and allow_lps
                and proj_crs.lps_hemisphere is None
        )
        if force_lps_attempt:
            # *REASSIGNMENT*
            proj_crs = _srs.make_lunar_crs("S" if self.latitude < 0 else "N")

        # Transform.
        transformer = self._get_transformer(
            to_geographic=False, proj_crs=proj_crs
        )
        e, n = transformer.transform(self.latitude, self.longitude)

        # Create and return instance.
        if proj_crs.ltm_zone is None:
            try:
                lps = Lps(
                    hemisphere=proj_crs.lps_hemisphere, easting=e, northing=n,
                    **self._root.constraints, validate=force_lps_attempt
                )
            except _exceptions.MalformedCoordinate:
                if force_lps_attempt:
                    # Note: `Lps` instance was invalid, so resort to
                    # `Ltm`.
                    return self._to_lps_or_ltm(allow_lps=False)
                raise
            return lps
        else:
            zone = int(proj_crs.ltm_zone[:-1])
            hemi = proj_crs.ltm_zone[-1]
            ltm = Ltm(
                zone_number=zone, hemisphere=hemi, easting=e, northing=n,
                **self._root.constraints, validate=False
            )
            return ltm

    def _to_lgrs(self, **kwargs) -> LpsLgrs | LtmLgrs:
        lps_or_ltm = self._to_lps_or_ltm(**kwargs)
        lgrs = lps_or_ltm._to_lgrs(**kwargs)
        return lgrs


@_easy_dataclass
class Lps(_NonGriddedCoordinate):

    #* Fields and validation. -------------------------------------------------
    _template = "{hemisphere}{easting!r}E{northing!r}N"
    hemisphere: str
    easting: float
    northing: float

    # Note: `._validate_hemisphere()` is defined on base class.

    def _validate_easting(self) -> None:
        # TODO: Implement, with consideration of `.prefer_lps`, etc.
        # Note: Limits from reference code, adapted from p. 54 of M2025.
        return self._validate_against_closed_interval(
            attr_name="easting", minimum=197_000, maximum=805_000
        )

    def _validate_northing(self) -> None:
        # TODO: Implement, with consideration of `.prefer_lps`, etc.
        # Note: Limits from reference code, adapted from p. 54 of M2025.
        return self._validate_against_closed_interval(
            attr_name="northing", minimum=197_000, maximum=805_000
        )

    #* Coordinate transformation. ---------------------------------------------
    def _get_proj_crs(self) -> _srs.CRS:
        return _srs.make_lunar_crs(self.hemisphere)

    def _get_transformer(self, *, to_geographic: bool) -> _pyproj.Transformer:
        proj_crs = self._get_proj_crs()
        transformer = LatLon._get_transformer(
            to_geographic=to_geographic, proj_crs=proj_crs
        )
        return transformer

    @_cache
    def _to_latlon(self, **kwargs) -> LatLon:
        transformer = self._get_transformer(to_geographic=True)
        lat, lon = transformer.transform(self.easting, self.northing)
        latlon = LatLon(
            latitude=lat, longitude=lon,
            **self._root.constraints, validate=False
        )
        return latlon

    @_cache
    def _to_lgrs(self, **kwargs) -> LpsLgrs:
        is_in_west_half = self.easting < _wkt.LPS_FALSE_EASTING
        match (self.hemisphere, is_in_west_half):
            case ("S", True):  # Eq. 100
                lon_band = "A"
            case ("S", False):  # Eq. 101
                lon_band = "B"
            case ("N", True):  # Eq. 100
                lon_band = "Y"
            case ("N", False):  # Eq. 101
                lon_band = "Z"
            case _:
                self._expect_error(self._validate_hemisphere)
        e_adj = self.easting - _wkt.LPS_FALSE_EASTING  # Eq. 109
        n_adj = self.northing - _wkt.LPS_FALSE_NORTHING  # Eq. 110
        if is_in_west_half:
            # TODO: Check with Mark that abs() should instead be around
            #  around e_adj in Eq. 103, as it is on line 1646 of
            #  reference code.
            ea_idx = 24 - _floor(abs(e_adj) // 25_000)  # Eq. 103
        else:
            ea_idx = _floor(e_adj // 25_000)  # Eq. 102
        ea = LpsLgrs._easting_area__idx_to_char[ea_idx]  # Tables 13, 14
        na_idx = _floor(n_adj // 25_000) + 13  # Eq. 104
        na = LpsLgrs._northing_area__idx_to_char[na_idx]  # Tables 15, 16
        if is_in_west_half:
            e = 25_000 - (abs(e_adj) % 25_000)  # Eq. 105
        else:
            e = e_adj % 25_000  # Eq. 106
        n = n_adj % 25_000
        lps_lrgs = LpsLgrs(
            longitudinal_band=lon_band,
            easting_area=ea,
            northing_area=na,
            easting=_format_as_five_digit_int(e),
            northing=_format_as_five_digit_int(n),
            **self._root.constraints, validate=False
        )
        return lps_lrgs


@_easy_dataclass
class Ltm(_NonGriddedCoordinate):

    #* Fields and validation. -------------------------------------------------
    _template = "{zone_number}{hemisphere}{easting!r}E{northing!r}N"
    zone_number: int
    hemisphere: str
    easting: float
    northing: float

    def _validate_zone_number(self) -> None:
        return self._validate_against_closed_interval(
            attr_name="zone_number", minimum=1, maximum=45
        )

    _validate_hemisphere = Lps._validate_hemisphere

    def _validate_easting(self) -> None:
        # TODO: Confirm limits empirically.
        # Note: Limits from p. 47 of M2025.
        return self._validate_against_closed_interval(
            attr_name="easting", minimum=125_000, maximum=375_000
        )

    def _validate_northing(self) -> None:
        # TODO: Confirm limits empirically, including for extended and
        #  polar LTM. Note that reference code uses [0, 2_500_000].
        # Note: Limits from p. 47 of M2025.
        match self.hemisphere:
            case "N":
                minimum = 0
                maximum = 2_487_500
            case "S":
                minimum = 12_500
                maximum = 2_500_000
            case _:
                self._expect_error(self._validate_hemisphere)
        return self._validate_against_closed_interval(
            attr_name="northing", minimum=minimum, maximum=maximum
        )

    #* Coordinate transformation. ---------------------------------------------
    def _get_proj_crs(self) -> _srs.CRS:
        return _srs.make_lunar_crs(f"{self.zone_number}{self.hemisphere}")

    _get_transformer = Lps._get_transformer

    _to_latlon = Lps._to_latlon

    @_cache
    def _to_lgrs(self, **kwargs) -> LtmLgrs:
        lon_band = self.zone_number
        lat_lon = self.to_latlon()
        lat_band_idx = _floor(lat_lon.latitude // 8)  # Eq. 81
        lat_band = LtmLgrs._latitudinal_band__idx_to_char[lat_band_idx]  # Table 6
        ea_idx = _floor(self.easting // 25_000) - 5  # Eq. 82
        ea = LtmLgrs._easting_area__idx_to_char[ea_idx]  # Table 7
        # TODO: Determine if the "- 1" (which appears in the reference
        #  code but not in Eq. 83) is correct.
        na_letterset = _calc_na_letterset(self.zone_number)  # Eq. 83
        na_idx = _floor(self.northing // 25_000) % 20  # Eq. 84
        na = LtmLgrs._northing_area__letterset_to_idx_to_char[na_letterset][na_idx]  # Tables 8, 9, 10
        e = self.easting % 25_000  # Eq. 85
        n = self.northing % 25_000  # Eq. 86
        ltm_lgrs = LtmLgrs(
            longitudinal_band=lon_band,
            latitudinal_band=lat_band,
            easting_area=ea,
            northing_area=na,
            easting=_format_as_five_digit_int(e),
            northing=_format_as_five_digit_int(n),
            **self._root.constraints, validate=False
        )
        return ltm_lgrs



# endregion
###############################################################################
# region> GRIDDED COORDINATE BASE TYPES
###############################################################################
class _GriddedCoordinate(BaseCoordinate):
    # TODO: Add `.truncate_to()`.

    #* Fields and validation. -------------------------------------------------
    easting:  str | None
    northing: str | None

    def _validate(self) -> None:
        super()._validate()
        self._validate_against_pattern()

    def _validate_against_pattern(self) -> None:
        if self._pattern.search(self.string) is None:
            raise _exceptions.MalformedCoordinate(
                f"`.string` does not have the form: {self._pattern.pattern!r}"
            )

    #* Instantiation from string. ---------------------------------------------
    __pattern_bytes: _regex.Pattern
    _pattern: _regex.Pattern

    @classmethod
    def _get_pattern_bytes(cls) -> _regex.Pattern:
        try:
            return cls.__pattern_bytes
        except AttributeError:
            cls.__pattern_bytes = _regex.compile(cls._pattern.pattern.encode())
            return cls.__pattern_bytes

    @classmethod
    def from_string(
            cls, string: str | bytes, *, validate: bool = True
    ) -> _typing.Self:
        # Determine pattern.
        string_is_bytes = isinstance(string, bytes)
        if string_is_bytes:
            pattern = cls._get_pattern_bytes()
        else:
            pattern = cls._pattern

        # Match to pattern.
        match = pattern.search(string)
        if match is None:
            raise _exceptions.MalformedCoordinate(
                f"`string` {string!r} is not in the supported format: "
                f"{pattern.pattern!r}"
            )
        match_dict = match.groupdict()
        if string_is_bytes:
            # *REASSIGNMENT*
            match_dict = {k: v.decode()
                          for k, v in match_dict.items()}

        # Coerce each argument to the correct type.
        field_name_to_type = cls._get_field_name_to_type()
        init_kwargs = {
            name: field_name_to_type[name](value_string)
            for name, value_string in match_dict.items()
            if value_string is not None
        }
        return cls(**init_kwargs, validate=validate)

    #* Coordinate transformation. ---------------------------------------------
    @_functools.cached_property
    def _easting_int(self) -> int | None:
        if self.easting is None:
            return None
        else:
            return int(self.easting)

    @_functools.cached_property
    def _northing_int(self) -> int | None:
        if self.easting is None:
            return None
        else:
            return int(self.northing)



# endregion
###############################################################################
# region> GRIDDED COORDINATE TYPES
###############################################################################
@_easy_dataclass
class LpsAcc(_GriddedCoordinate):

    #* Fields and validation. -------------------------------------------------
    _pattern = _compile_regex_without_i_and_o(
        "^"
        "(?P<longitudinal_band>[ABYZ])"
        "(?P<easting_area>[A-Z])"
        "(?P<northing_area>[-A-Z+])"
        "((?P<easting_1k>[-A-Z])"
        "(?P<easting>[0-9]{1,3})?"
        "(?P<northing_1k>[-A-Z])"
        "(?P<northing>[0-9]{1,3})?)?"
        "$"
    )
    longitudinal_band: str
    easting_area: str
    northing_area: str
    easting_1k: str | None = None
    easting: str | None = None
    northing_1k: str | None = None
    northing: str | None = None

    _validate_longitudinal_band = _return_none  # `._pattern` is sufficient.

    def _validate_easting_area(self) -> None:
        match self.longitudinal_band:
            case "A" | "Y":
                minimum = "M"
                maximum = "Z"
            case "B" | "Z":
                minimum = "A"
                maximum = "N"
            case _:
                self._expect_error(self._validate_longitudinal_band)
        self._validate_against_closed_interval(
            attr_name="easting_area", minimum=minimum, maximum=maximum,
            if_attr_name="longitudinal_band"
        )

    _validate_northing_area = _return_none  # `._pattern` is sufficient.
    _validate_easting_1k = _return_none  # `._pattern` is sufficient.

    def _validate_easting(self) -> None:
        if (self.easting is None) != (self.northing is None):
            raise _exceptions.MalformedCoordinate(
                "`easting` and `northing` must both be specified "
                "or both be `None`."
            )

    _validate_northing_1k = _return_none  # `._pattern` is sufficient.
    _validate_northing = _return_none  # `._pattern` is sufficient.

    #* Coordinate transformation. ---------------------------------------------
    _easting_area__char_to_idx, _easting_area__idx_to_char = _index_char_set(
        _pattern, "easting_area", start=1
    )
    _northing_area__char_to_idx, _northing_area__idx_to_char = _index_char_set(
        _pattern, "northing_area", start=0
    )
    _easting_1k__char_to_idx, _easting_1k__idx_to_char = _index_char_set(
        _pattern, "easting_1k", start=0
    )
    _northing_1k__char_to_idx, _northing_1k__idx_to_char = _index_char_set(
        _pattern, "northing_1k", start=0
    )


@_easy_dataclass
class LpsLgrs(_GriddedCoordinate):
    #* Fields and validation. -------------------------------------------------
    _pattern = _compile_regex_without_i_and_o(
        "^"
        "(?P<longitudinal_band>[ABYZ])"
        "(?P<easting_area>[A-Z])"
        "(?P<northing_area>[-A-Z+])"
        f"({_make_en_pattern(5, 4, 3, 2)})?"
        "$"
    )
    longitudinal_band: str
    easting_area: str
    northing_area: str
    easting: str | None = None
    northing: str | None = None

    _validate_longitudinal_band = LpsAcc._validate_longitudinal_band
    _validate_easting_area = LpsAcc._validate_easting_area
    _validate_northing_area = LpsAcc._validate_northing_area

    def _validate_easting(self) -> None:
        # TODO: Implement, with consideration of `.prefer_lps`, etc.
        #  Should upper limit be 24_999?
        # Note: Limits from reference code.
        return self._validate_against_closed_interval(
            attr_name="easting", minimum=0, maximum=25_000, coerce_str=True
        )

    def _validate_northing(self) -> None:
        # TODO: Implement, with consideration of `.prefer_lps`, etc.
        #  Should upper limit be 24_999?
        return self._validate_against_closed_interval(
            attr_name="northing", minimum=0, maximum=25_000, coerce_str=True
        )

    def _validate_northing(self) -> None:
        # TODO: Implement, with consideration of `.prefer_lps`, etc.
        ...

    #* Coordinate transformation. ---------------------------------------------
    _easting_area__char_to_idx = LpsAcc._easting_area__char_to_idx
    _easting_area__idx_to_char = LpsAcc._easting_area__idx_to_char
    _northing_area__char_to_idx = LpsAcc._northing_area__char_to_idx
    _northing_area__idx_to_char = LpsAcc._northing_area__idx_to_char

    @_cache
    def _to_acc(self, **kwargs) -> LpsAcc | LtmAcc:
        init_kwargs = {
            "longitudinal_band": self.longitudinal_band,
            "easting_area": self.easting_area,
            "northing_area": self.northing_area,
        }
        if self.easting is not None:
            init_kwargs["easting_1k"] = LpsAcc._easting_1k__idx_to_char[
                int(self.easting[:2])
            ]
            init_kwargs["northing_1k"] = LpsAcc._northing_1k__idx_to_char[
                int(self.northing[:2])
            ]
            if len(self.easting) > 2:
                init_kwargs["easting"] = self.easting[2:]
                init_kwargs["northing"] = self.northing[2:]
        if isinstance(self, LpsLgrs):
            acc_type = LpsAcc
        else:
            acc_type = LtmAcc
        acc = acc_type(**init_kwargs, **self._root.constraints, validate=False)
        return acc


@_easy_dataclass
class LtmAcc(_GriddedCoordinate):

    #* Fields and validation. -------------------------------------------------
    _pattern = _compile_regex_without_i_and_o(
        "^"
        "(?P<longitudinal_band>[0-9]{1,2})"
        "(?P<latitudinal_band>[C-X])"
        "(?P<easting_area>[A-K])"
        "(?P<northing_area>[A-V])"
        "((?P<easting_1k>[-A-Z])"
        "(?P<easting>[0-9]{1,3})?"
        "(?P<northing_1k>[-A-Z])"
        "(?P<northing>[0-9]{1,3})?)?"
        "$"
    )
    longitudinal_band: int  # LTM zone
    latitudinal_band: str
    easting_area: str
    northing_area: str
    easting_1k: str
    easting: str | None = None
    northing_1k: str
    northing: str | None = None

    def _validate_longitudinal_band(self) -> None:
        return self._validate_against_closed_interval(
            attr_name="longitudinal_band", minimum=1, maximum=45
        )

    _validate_latitudinal_band = _return_none  # `._pattern` is sufficient.
    _validate_easting_area = _return_none  # `._pattern` is sufficient.

    def _validate_northing_area(self) -> None:
        na_letterset = _calc_na_letterset(self.longitudinal_band)  # Eq. 83
        na_chars = LtmLgrs._northing_area__letterset_to_char_to_idx[na_letterset]
        self._validate_against_sequence(
            attr_name="easting_area", sequence=na_chars,
            if_attr_name="longitudinal_band"
        )

    _validate_easting_1k = LpsAcc._validate_easting_1k
    _validate_easting = LpsAcc._validate_easting
    _validate_northing_1k = LpsAcc._validate_northing_1k
    _validate_northing = LpsAcc._validate_northing

    #* Coordinate transformation. ---------------------------------------------
    _latitudinal_band__char_to_idx, _latitudinal_band__idx_to_char = _index_char_set(
        _pattern, "latitudinal_band", start=-10, C=-11, X=10
    )
    _easting_area__char_to_idx, _easting_area__idx_to_char = _index_char_set(
        _pattern, "easting_area", start=0
    )
    (
        _northing_area__letterset_to_char_to_idx,
        _northing_area__letterset_to_idx_to_char
    ) = _map_index_char_sets(
        "ABCDEFGHJKLMNPQRSTUV", "FGHJKLMNPQRSTUVABCDE", "LMNPQRSTUVABCDEFGHJK",
        start=0
    )
    _easting_1k__char_to_idx, _easting_1k__idx_to_char = _index_char_set(
        _pattern, "easting_1k", start=0
    )
    _northing_1k__char_to_idx, _northing_1k__idx_to_char = _index_char_set(
        _pattern, "northing_1k", start=0
    )


@_easy_dataclass
class LtmLgrs(_GriddedCoordinate):

    #* Fields and validation. -------------------------------------------------
    _pattern = _compile_regex_without_i_and_o(
        "^"
        "(?P<longitudinal_band>[0-9]{1,2})"
        "(?P<latitudinal_band>[C-X])"
        "(?P<easting_area>[A-K])"
        "(?P<northing_area>[A-V])"
        f"({_make_en_pattern(5, 4, 3, 2)})?"
        "$"
    )
    longitudinal_band: int  # LTM zone
    latitudinal_band: str
    easting_area: str
    northing_area: str
    easting: str | None = None
    northing: str | None = None

    _validate_longitudinal_band = LtmAcc._validate_longitudinal_band
    _validate_latitudinal_band = LtmAcc._validate_latitudinal_band
    _validate_easting_area = LtmAcc._validate_easting_area
    _validate_northing_area = LtmAcc._validate_northing_area
    _validate_easting = LpsLgrs._validate_easting
    _validate_northing = LpsLgrs._validate_northing

    #* Coordinate transformation. ---------------------------------------------
    _latitudinal_band__char_to_idx = LtmAcc._latitudinal_band__char_to_idx
    _latitudinal_band__idx_to_char = LtmAcc._latitudinal_band__idx_to_char
    _easting_area__char_to_idx = LtmAcc._easting_area__char_to_idx
    _easting_area__idx_to_char = LtmAcc._easting_area__idx_to_char
    _northing_area__letterset_to_char_to_idx = LtmAcc._northing_area__letterset_to_char_to_idx
    _northing_area__letterset_to_idx_to_char = LtmAcc._northing_area__letterset_to_idx_to_char

    _to_acc = LpsLgrs._to_acc



# endregion
###############################################################################
# region> PROCESSING CHAIN INDICES
###############################################################################
# Note: Used by `_redirect()` (via `._get_best_cousin()`) to determine
# best related coordinate instance from which to start a transformation.

# `LatLon` is 0, because logical starting point for both LPS and LTM
# chains is `LatLon`.
LatLon._idx = 0

# LPS chain is increasingly negative.
Lps._idx = -1
LpsLgrs._idx = -3  # Not -2, to favor LGRS <--> ACC over LPS <--> LGRS.
LpsAcc._idx = -4

# LTM chain is increasingly positive.
Ltm._idx = +1
LtmLgrs._idx = +3  # Not +2, to favor LGRS <--> ACC over LTM <--> LGRS.
LtmAcc._idx = +4



# endregion


# TODO: Remove after testing.
_caching.enable_caching(False)

lat_lon = LatLon(latitude=-30.13048481, longitude=96.48515138)  # p. 45
lps_or_ltm = lat_lon.to_lps_or_ltm()
lgrs_ = lps_or_ltm.to_lgrs()
assert lgrs_.is_equal_to(LtmLgrs.from_string("35JFJ1271112229"))

lat_lon1 = LatLon(latitude=-81.13048481, longitude=96.48515138)
lps_or_ltm1 = lat_lon1.to_lps_or_ltm()
lgrs1 = lps_or_ltm1.to_lgrs()
assert isinstance(lgrs1, LpsLgrs)

lat_lon2 = lat_lon1.with_constraints(extended_ltm=True)
lps_or_ltm2 = lat_lon2.to_lps_or_ltm()
lgrs2 = lps_or_ltm2.to_lgrs()
assert isinstance(lgrs2, LtmLgrs)

lat_lon4 = LatLon(latitude=-86.38231380366628, longitude=-6.004331982958013)  # p. 53, 64
lps_or_ltm4 = lat_lon4.to_lps_or_ltm()
lgrs4 = lps_or_ltm4.to_lgrs()
assert lgrs4.is_equal_to(LpsLgrs.from_string("AZS1359008480"))

lat_lon5 = LatLon(latitude=-30.13048481, longitude=96.48515138)
lat_lon5.to_latlon()

lps = Lps(hemisphere="S", easting=197000, northing=197000)
lps.to_lgrs()