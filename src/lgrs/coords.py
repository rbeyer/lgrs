"""
Coordinate types: geographic and projected, non-gridded and gridded.

Examples
--------
>>> lps_lgrs = LpsLgrs(
...     longitudinal_band="A", easting_area="Z", northing_area="S",
...     easting="13590", northing="08480"
... )
>>> alt_lps_lgrs = LpsLgrs.from_string("AZS1359008480")
>>> alt_lps_lgrs.is_equal_to(lps_lgrs, error=True))
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
import builtins as _builtins
import collections as _collections
import dataclasses as _dataclasses
import functools as _functools
import regex as _regex
import types as _types
import typing as _typing



# endregion
###############################################################################
# region> UTILITIES
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

def _make_ne_pattern(*digit_count: int) -> str:
    pattern = "|".join(
        f"((?P<northing>[0-9]{{{i}}})(?P<easting>[0-9]{{{i}}}))"
        for i in sorted(digit_count, reverse=True)
    )
    return pattern



# endregion
###############################################################################
# region> NON-GRIDDED COORDINATE TYPES
###############################################################################
@_dataclasses.dataclass(kw_only=True, frozen=True)
class BaseCoordinate:
    _template: _typing.ClassVar[str | None] = None

    def __iter__(self) -> _collections.abc.Iterable:
        return (getattr(self, field.name)
                for field in _dataclasses.fields(self))

    def __bytes__(self) -> _builtins.bytes:
        return self.bytes

    def __str__(self) -> str:
        return self.string

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

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LatLon(BaseCoordinate):
    # TODO: Should `._template` use N/S and E/W?
    _template = "{latitude!r}° {longitude!r}°"
    latitude: float
    longitude: float

@_dataclasses.dataclass(kw_only=True, frozen=True)
class Lps(BaseCoordinate):
    _template = "{hemisphere}{easting!r}E{northing!r}N"
    hemisphere: str
    easting: float
    northing: float

@_dataclasses.dataclass(kw_only=True, frozen=True)
class Ltm(BaseCoordinate):
    _template = "{zone_number}{hemisphere}{easting!r}E{northing!r}N"
    zone_number: int
    hemisphere: str
    easting: float
    northing: float



# endregion
###############################################################################
# region> GRIDDED COORDINATE TYPES
###############################################################################
@_dataclasses.dataclass(kw_only=True, frozen=True)
class _GriddedCoordinate(BaseCoordinate):
    # TODO: Add `.truncate_to()`.
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

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LpsAcc(_GriddedCoordinate):
    _pattern = _regex.compile(
        "^"
        "(?P<longitudinal_band>[ABYZ])"
        "(?P<easting_area>[A-HJ-NP-Z])"
        "(?P<northing_area>[-A-HJ-NP-Z+])"
        "(?P<easting_1k>[A-Z-])"
        "(?P<easting>[0-9]{1,3})?"
        "(?P<northing_1k>[A-HJ-NP-Z-])"
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

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LpsLgrs(_GriddedCoordinate):
    _pattern = _regex.compile(
        "^"
        "(?P<longitudinal_band>[ABYZ])"
        "(?P<easting_area>[A-HJ-NP-Z])"
        "(?P<northing_area>[-A-HJ-NP-Z+])"
        f"({_make_ne_pattern(5, 4, 3, 2)})?"
        "$"
    )
    longitudinal_band: str
    easting_area: str
    northing_area: str
    easting: str | None = None
    northing: str | None = None

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmAcc(_GriddedCoordinate):
    _pattern = _regex.compile(
        "^"
        "(?P<longitudinal_band>[0-9]{1,2})"
        "(?P<latitudinal_band>[C-HJ-NP-X])"
        "(?P<easting_area>[A-HJK])"
        "(?P<northing_area>[A-HJ-NP-V])"
        "(?P<easting_1k>[A-Z-])"
        "(?P<easting>[0-9]{1,3})?"
        "(?P<northing_1k>[A-HJ-NP-Z-])"
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

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmLgrs(_GriddedCoordinate):
    _pattern = _regex.compile(
        "^"
        "(?P<longitudinal_band>[0-9]{1,2})"
        "(?P<latitudinal_band>[C-HJ-NP-X])"
        "(?P<easting_area>[A-HJK])"
        "(?P<northing_area>[A-HJ-NP-V])"
        f"({_make_ne_pattern(5, 4, 3, 2)})?"
        "$"
    )
    longitudinal_band: int  # LTM zone
    latitudinal_band: str
    easting_area: str
    northing_area: str
    easting: str | None = None
    northing: str | None = None



# endregion
