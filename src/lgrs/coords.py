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

def _redirect(func: ToMethod) -> ToMethod:
    """
    Redirect `.to_*()` to the `._to_*()` of the best cousin instance.

    A method decorated with this function will never be called (and
    therefore can be empty). Rather, a "cousin" `BaseCoordinate` instance
    is found and its (hidden) `._to_*()` counterpart is called instead, with
    the same keyword arguments. The result of that call is returned.
    Specifically, that cousin is used whose `._to_*()` is the most
    performant among those of available cousins.

    A "cousin" is another `BaseCoordinate` whose constraints are a (non-
    strict) subset of those that apply to `self`. For example, if an
    `LtmLgrs` instance was created (by transformation) with the constraint
    that it use extended LTM zones, then any cousin of that instance must
    also be compatible with this constraint and cannot add new constraints.
    Cousins are often generated during intermediate calculations, whether
    internal or external (i.e., by the user), so caching them into
    cousin groups improves efficiency.

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
    def wrapped(self: BaseCoordinate, **kwargs) -> BaseCoordinate:
        # Note: `func` itself is only used for its return type and name.
        best_cousin, is_resolved = self._get_best_cousin(func, **kwargs)
        if is_resolved:
            return best_cousin
        new = getattr(best_cousin, f"_{func.__name__}")(**kwargs)
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
@_functools.cache
def _get_field_name_to_type(typ: type) -> dict[str, type]:
    name_to_type = {}
    for name, typ in _typing.get_type_hints(typ).items():
        if name[0] == "_":
            continue
        if isinstance(typ, _types.UnionType):
            types = list(_typing.get_args(typ))
            types.remove(type(None))
            typ, = types  # *REASSIGNMENT*
        name_to_type[name] = typ
    return name_to_type

def _iter_value_strings(coords: BaseCoordinate) -> _typing.Iterator[str]:
    for value in coords:
        match value:
            case None:
                continue
            case str():
                yield value
            case _:
                yield repr(value)

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
# Note: `_BaseCoordinate` is useful for defining behavior that depends
# on the class being a dataclass. Conversely, `BaseCoordinate` and its
# hidden subclasses are useful for defining all other behavior (without
# accidentally implying dataclass fields).
@_dataclasses.dataclass(kw_only=True, frozen=True)
class _BaseCoordinate(_abc.ABC):
    validate: _dataclasses.InitVar[bool] = True

    def __post_init__(self, validate: bool) -> None:
        if validate:
            self._validate()

    def __iter__(self) -> _collections.abc.Iterable:
        return (getattr(self, field.name)
                for field in _dataclasses.fields(self))

    @_functools.cached_property
    def _init_kwargs(self) -> dict[str, _typing.Any]:
        return {field.name: getattr(self, field.name)
                for field in _dataclasses.fields(self)}

    @_abc.abstractmethod
    def _validate(self) -> None:
        # TODO: Document what errors may be raised on invalid arguments.
        ...


class BaseCoordinate(_BaseCoordinate):
    _idx: int
    _template: _typing.ClassVar[str | None] = None

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
            raise TypeError("`string` must be space-delimited")
        field_name_to_type = _get_field_name_to_type(cls)
        if len(parts) > len(field_name_to_type):
            raise TypeError(
                "`string` contains too many space-delimited "
                f"components: {string!r}"
            )
        init_kwargs = {
            name: typ(part)
            for part, (name, typ) in zip(parts, field_name_to_type.items())
        }
        return cls(**init_kwargs)

    #* Public data. -----------------------------------------------------------
    @_functools.cached_property
    def bytes(self) -> _builtins.bytes:
        return self.string.encode()

    @_functools.cached_property
    def string(self) -> str:
        if self._template is None:
            string = "".join(_iter_value_strings(self))
        else:
            string = self._template.format(**self.__dict__)
        return string

    #* General public methods. --------------------------------------------------------
    def copy(self) -> _typing.Self:
        return type(self)(**self._init_kwargs)

    def is_equal_to(
            self, other: _typing.Self, *,
            max_float_difference: float | None = None, error: bool = False
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
        for field, self_val, other_val in zip(
                _dataclasses.fields(self), self, other, strict=True
        ):
            if self_val == other_val:
                continue
            if (field.type == "float"
                and abs(self_val - other_val) <= max_float_difference):
                continue
            if not error:
                return False
            raise TypeError(
                f"{field.name!r} values differ:\n"
                f"    {self_val!r} vs. {other_val!r}"
           )
        return True

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

    def _get_best_cousin(
            self, func: ToMethod, **kwargs: bool | None
    ) -> tuple[BaseCoordinate, bool]:
        # Resolve root and out types.
        root = self._get_compatible_root()
        out_types = _resolve_out_types(func)

        # Find best starting point for conversion.
        # Note: `._idx` on each public `BaseCoordinate` subclass indexes
        # the processing chains:
        #   LatLon -> Lps --> LpsLgrs -> LpsAcc  (`._idx` <= 0)
        #   LatLon -> Ltm --> LtmLgrs -> LtmAcc  (`._idx` >= 0)
        # where index magnitudes are set so that interconversion between
        # LGRS and ACC is preferred over (slower) interconversion
        # between LPS/LTM and LGRS.
        min_abs_diff = float("inf")  # Initialize.
        closest_cousin = None  # Initialize.
        for out_type in out_types:
            targ_idx = out_type._idx
            abs_targ_idx = abs(targ_idx)
            for cousin in root._cousins:
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
        if closest_cousin is None:
            best = root._to_latlon(**kwargs)
            is_resolved = isinstance(best, out_types)
        else:
            best = closest_cousin
            is_resolved = False
        return (best, is_resolved)

    def _get_compatible_root(self, **kwargs: bool | None) -> BaseCoordinate:
        if not _caching._CACHING_IS_ENABLED:
            return self._to_latlon(**kwargs)
        cur_root = self._root
        kwarg_set = {(k, v)
                     for k, v in kwargs.items()
                     if v is not None}
        if cur_root._constraint_kwarg_set is None:
            # Note: Special `LatLon` case where root is universally
            # compatible. However, with this call, its constraints will
            # be resolved and set. (`LatLon.to_latlon()` does not call
            # the current method.)
            new_root = cur_root
        elif kwarg_set.issubset(cur_root._constraint_kwarg_set):
            # Note: `cur_root` satisfies all specified constraints.
            return cur_root
        else:
            new_root = self._to_latlon(**kwargs).copy()
        object.__setattr__(new_root, "_constraint_kwarg_set", kwarg_set)
        return new_root

    def _register_cousin(self, cousin: BaseCoordinate) -> None:
        if _caching._CACHING_IS_ENABLED:
            _caching._store_to_weak_cache(cousin, key="root", value=self._root)
            self._root._cousins.appendleft(cousin)

    @property
    def _root(self) -> BaseCoordinate:
        # Note: When an instance is the result of transformation, this
        # attribute is overwritten to point to the known root.
        # Otherwise, when instantiation is direct, `self` is its own
        # root.
        cached = _caching._query_weak_cache(self, key="root", default=None)
        if cached is None:
            _caching._store_to_weak_cache(self, key="root", value=self)
            return self
        else:
            return cached

    @_functools.cached_property
    def _constraint_kwarg_set(self) -> set[tuple[str, bool]] | None:
        # Note: When an instance is created by transformation, this
        # value is overwritten (on the root) to represent the explicit
        # constraints. Otherwise, when instantiation is direct, the
        # default empty set indicates that the constraints on the
        # instance are unknown (but may exist). For example, an
        # `LtmLgrs` instance from the extended LTM region is not
        # equivalent to an `LtmLgrs` with no (non-defaulted)
        # constraints, since the extended LTM region is a constraint.
        # See also `LatLon._constraint_kwarg_set()`, which returns
        # `None`.
        assert _caching._CACHING_IS_ENABLED
        return set()

    #* Coordinate transformation. ---------------------------------------------
    @_redirect
    def to_acc(self, *, extended_ltm: bool | None = None) -> LpsAcc | LtmAcc:
        ...

    @_redirect
    def to_latlon(self) -> LatLon:
        ...

    @_redirect
    def to_lgrs(self, *, extended_ltm: bool | None = None) -> LpsLgrs | LtmLgrs:
        ...

    @_redirect
    def to_lps_or_ltm(
            self, *,
            extended_ltm: bool | None = None, polar_ltm: bool | None = None
    ) -> Lps | Ltm:
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


@_dataclasses.dataclass(kw_only=True, frozen=True)
class LatLon(_NonGriddedCoordinate):
    # TODO: Should `._template` use N/S and E/W?

    #* Fields, initialization, and related. -----------------------------------
    _template = "{latitude!r}° {longitude!r}°"
    latitude: float
    longitude: float

    def _validate(self) -> None:
        conformed_lat, = _database._conform_latitudes((self.latitude,))
        object.__setattr__(self, "latitude", conformed_lat)
        conformed_lon, = _database._conform_longitudes((self.longitude,))
        object.__setattr__(self, "longitude",conformed_lon)

    #* Transformation caching. ------------------------------------------------
    @_functools.cached_property
    def _constraint_kwarg_set(self) -> set[tuple[str, bool]] | None:
        # Note: `LatLon` is a special case for which no constraints can
        # be applied. Therefore, if `LatLon` is the root, treat its
        # constraints as unknown but universally compatible, using the
        # special value `None`.
        return None

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

    # Note: Simplifies code in non-caching case. Generally, identity
    # "transformation" methods need not be defined, whether caching or
    # not.
    def _to_latlon(self, **kwargs) -> LatLon:
        return self

    @_cache
    def _to_lps_or_ltm(self, **kwargs) -> Lps | Ltm:
        proj_crs = self._get_proj_crs(**kwargs)
        transformer = self._get_transformer(
            to_geographic=False, proj_crs=proj_crs
        )
        e, n = transformer.transform(self.latitude, self.longitude)
        if proj_crs.ltm_zone is None:
            lps = Lps(hemisphere=proj_crs.lps_hemisphere, easting=e, northing=n)
            return lps
        else:
            zone = int(proj_crs.ltm_zone[:-1])
            hemi = proj_crs.ltm_zone[-1]
            ltm = Ltm(zone_number=zone, hemisphere=hemi, easting=e, northing=n)
            return ltm

    def _to_lgrs(self, **kwargs) -> LpsLgrs | LtmLgrs:
        lps_or_ltm = self._to_lps_or_ltm(**kwargs)
        lgrs = lps_or_ltm._to_lgrs(**kwargs)
        return lgrs

    # Note: Required to retain `._constrain_kwarg_set` as `None`.
    def to_latlon(self) -> LatLon:
        return self


class _LpsAndLtm(_NonGriddedCoordinate):
    easting: float
    northing: float

    def _get_transformer(self, *, to_geographic: bool) -> _pyproj.Transformer:
        proj_crs = self._get_proj_crs()
        transformer = super()._get_transformer(
            to_geographic=to_geographic, proj_crs=proj_crs
        )
        return transformer

    @_cache
    def _to_latlon(self, **kwargs) -> LatLon:
        transformer = self._get_transformer(to_geographic=True)
        lat, lon = transformer.transform(self.easting, self.northing)
        latlon = LatLon(latitude=lat, longitude=lon)
        return latlon


@_dataclasses.dataclass(kw_only=True, frozen=True)
class Lps(_LpsAndLtm):

    #* Fields, initialization, and related. -----------------------------------
    _template = "{hemisphere}{easting!r}E{northing!r}N"
    hemisphere: str
    easting: float
    northing: float

    def _validate(self) -> None:
        # TODO: Implement.
        ...

    #* Coordinate transformation. ---------------------------------------------
    def _get_proj_crs(self) -> _srs.CRS:
        return _srs.make_lunar_crs(self.hemisphere)

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
                raise TypeError(
                    f"`.hemisphere` is not recognized: {self.hemisphere}"
                )
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
            northing=_format_as_five_digit_int(n)
        )
        return lps_lrgs


@_dataclasses.dataclass(kw_only=True, frozen=True)
class Ltm(_LpsAndLtm):

    #* Fields, initialization, and related. -----------------------------------
    _template = "{zone_number}{hemisphere}{easting!r}E{northing!r}N"
    zone_number: int
    hemisphere: str
    easting: float
    northing: float

    def _validate(self) -> None:
        # TODO: Implement.
        ...

    #* Coordinate transformation. ---------------------------------------------
    def _get_proj_crs(self) -> _srs.CRS:
        return _srs.make_lunar_crs(f"{self.zone_number}{self.hemisphere}")

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
        na_letterset = (self.zone_number - 1) % 3  # Eq. 83
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
            northing=_format_as_five_digit_int(n)
        )
        return ltm_lgrs



# endregion
###############################################################################
# region> GRIDDED COORDINATE BASE TYPES
###############################################################################
class _GriddedCoordinate(BaseCoordinate):
    # TODO: Add `.truncate_to()`.

    easting:  str | None
    northing: str | None

    #* Instantiation from string. ---------------------------------------------
    __pattern_bytes: _typing.ClassVar[_regex.Pattern]
    _pattern: _typing.ClassVar[_regex.Pattern]

    @classmethod
    def _get_pattern_bytes(cls) -> _regex.Pattern:
        try:
            return cls.__pattern_bytes
        except AttributeError:
            cls.__pattern_bytes = _regex.compile(cls._pattern.pattern.encode())
            return cls.__pattern_bytes

    @classmethod
    def from_string(cls, string: str | bytes) -> _typing.Self:
        # Determine pattern.
        string_is_bytes = isinstance(string, bytes)
        if string_is_bytes:
            pattern = cls._get_pattern_bytes()
        else:
            pattern = cls._pattern

        # Match to pattern.
        match = pattern.search(string)
        if match is None:
            raise TypeError(
                f"`string` {string!r} is not in the supported format: "
                f"{pattern.pattern!r}"
            )
        match_dict = match.groupdict()
        if string_is_bytes:
            # *REASSIGNMENT*
            match_dict = {k: v.decode()
                          for k, v in match_dict.items()}

        # Coerce each argument to the correct type.
        field_name_to_type = _get_field_name_to_type(cls)
        init_kwargs = {
            name: field_name_to_type[name](value_string)
            for name, value_string in match_dict.items()
            if value_string is not None
        }
        return cls(**init_kwargs)

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


@_dataclasses.dataclass(kw_only=True, frozen=True)
class _LpsLgrs(_GriddedCoordinate):
    #* Fields, initialization, and related. -----------------------------------
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

    #* Coordinate transformation. ---------------------------------------------
    _easting_area__char_to_idx, _easting_area__idx_to_char = _index_char_set(
        _pattern, "easting_area", start=1
    )
    _northing_area__char_to_idx, _northing_area__idx_to_char = _index_char_set(
        _pattern, "northing_area", start=0
    )


@_dataclasses.dataclass(kw_only=True, frozen=True)
class _LtmLgrs(_GriddedCoordinate):
    #* Fields, initialization, and related. -----------------------------------
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



# endregion
###############################################################################
# region> GRIDDED COORDINATE TYPES
###############################################################################
@_dataclasses.dataclass(kw_only=True, frozen=True)
class LpsAcc(_LpsLgrs):

    #* Fields, initialization, and related. -----------------------------------
    _pattern = _compile_regex_without_i_and_o(
        "^"
        "(?P<longitudinal_band>[ABYZ])"
        "(?P<easting_area>[A-Z])"
        "(?P<northing_area>[-A-Z+])"
        "(?P<easting_1k>[-A-Z])"
        "(?P<easting>[0-9]{1,3})?"
        "(?P<northing_1k>[-A-Z])"
        "(?P<northing>[0-9]{1,3})?"
        "$"
    )
    longitudinal_band: str
    easting_area: str
    northing_area: str
    easting_1k: str
    easting: str | None = None
    northing_1k: str
    northing: str | None = None

    def _validate(self) -> None:
        # TODO: Implement.
        ...

    #* Coordinate transformation. ---------------------------------------------
    _easting_1k__char_to_idx, _easting_1k__idx_to_char = _index_char_set(
        _pattern, "easting_1k", start=0
    )
    _northing_1k__char_to_idx, _northing_1k__idx_to_char = _index_char_set(
        _pattern, "northing_1k", start=0
    )


@_dataclasses.dataclass(kw_only=True, frozen=True)
class LpsLgrs(_LpsLgrs):
    pass

    #* Validation. ------------------------------------------------------------
    def _validate(self) -> None:
        # TODO: Implement.
        ...


@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmAcc(_LtmLgrs):

    #* Fields, initialization, and related. -----------------------------------
    _pattern = _compile_regex_without_i_and_o(
        "^"
        "(?P<longitudinal_band>[0-9]{1,2})"
        "(?P<latitudinal_band>[C-X])"
        "(?P<easting_area>[A-K])"
        "(?P<northing_area>[A-V])"
        "(?P<easting_1k>[-A-Z])"
        "(?P<easting>[0-9]{1,3})?"
        "(?P<northing_1k>[-A-Z])"
        "(?P<northing>[0-9]{1,3})?"
        "$"
    )
    longitudinal_band: int
    latitudinal_band: str
    easting_area: str
    northing_area: str
    easting_1k: str
    easting: str | None = None
    northing_1k: str
    northing: str | None = None

    def _validate(self) -> None:
        # TODO: Implement.
        ...

    #* Coordinate transformation. ---------------------------------------------
    _easting_1k__char_to_idx, _easting_1k__idx_to_char = _index_char_set(
        _pattern, "easting_1k", start=0
    )
    _northing_1k__char_to_idx, _northing_1k__idx_to_char = _index_char_set(
        _pattern, "northing_1k", start=0
    )


@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmLgrs(_LtmLgrs):

    def _validate(self) -> None:
        # TODO: Implement.
        ...



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
_caching.enable_caching(False)  ####

lat_lon = LatLon(latitude=-30.13048481, longitude=96.48515138)  # p. 45
lps_or_ltm = lat_lon.to_lps_or_ltm()
lgrs_ = lps_or_ltm.to_lgrs()

lat_lon1 = LatLon(latitude=-81.13048481, longitude=96.48515138)
lps_or_ltm1 = lat_lon1.to_lps_or_ltm()
lgrs1 = lps_or_ltm1.to_lgrs()

lat_lon2 = LatLon(latitude=-81.13048481, longitude=96.48515138)
lps_or_ltm2 = lat_lon2.to_lps_or_ltm(extended_ltm=True)
lgrs2 = lps_or_ltm2.to_lgrs()

lat_lon3 = LatLon(latitude=-81.13048481, longitude=96.48515138)
lps_or_ltm3 = lat_lon3.to_lps_or_ltm(extended_ltm=False)
lgrs3 = lps_or_ltm3.to_lgrs()

lat_lon4 = LatLon(latitude=-86.38231380366628, longitude=-6.004331982958013)  # p. 53
lps_or_ltm4 = lat_lon4.to_lps_or_ltm()
lgrs4 = lps_or_ltm4.to_lgrs()

lat_lon5 = LatLon(latitude=-30.13048481, longitude=96.48515138)
lat_lon5.to_latlon()