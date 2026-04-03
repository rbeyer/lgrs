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
import collections as _collections
import dataclasses as _dataclasses
import functools as _functools
import re as _re
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
    _pattern: _typing.ClassVar[_re.Pattern]

    @_functools.cached_property
    def _pattern_bytes(self) -> _re.Pattern:
        return _re.compile(self._pattern.pattern.encode())

    @classmethod
    def from_string(cls, string: str) -> _typing.Self:
        # Match to pattern.
        match = cls._pattern.search(string)
        if match is None:
            raise TypeError(
                f"`string` {string!r} is not in the supported format: "
                f"{cls._pattern.pattern!r}"
            )
        match_dict = match.groupdict()

        # Distinguish easting and northing, if necessary.
        e_and_n = match_dict.pop("e_and_n", None)
        if e_and_n is not None:
            if len(e_and_n) % 2:
                raise TypeError(
                    "`easting` and `northing` components must each "
                    "have the same number of digits"
                )
            digit_count = len(e_and_n) // 2
            match_dict["easting"] = e_and_n[:digit_count]
            match_dict["northing"] = e_and_n[digit_count:]

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
    _pattern = _re.compile(
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
    _pattern = _re.compile(
        "^"
        "(?P<longitudinal_band>[ABYZ])"
        "(?P<easting_area>[A-HJ-NP-Z])"
        "(?P<northing_area>[-A-HJ-NP-Z+])"
        "(?P<e_and_n>[0-9]+)?"  # TODO: Change to explicit `easting` and `northing` with |'d 1, 2, or 3 length
        "$"
    )
    longitudinal_band: str
    easting_area: str
    northing_area: str
    easting: str | None = None
    northing: str | None = None

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmAcc(_GriddedCoordinate):
    _pattern = _re.compile(
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
    _pattern = _re.compile(
        "^"
        "(?P<longitudinal_band>[0-9]{1,2})"
        "(?P<latitudinal_band>[C-HJ-NP-X])"
        "(?P<easting_area>[A-HJK])"
        "(?P<northing_area>[A-HJ-NP-V])"
        "(?P<e_and_n>[0-9]+)?"  # TODO: Change to explicit `easting` and `northing` with |'d 1, 2, or 3 length
        "$"
    )
    longitudinal_band: int  # LTM zone
    latitudinal_band: str
    easting_area: str
    northing_area: str
    easting: str | None = None
    northing: str | None = None



# endregion
