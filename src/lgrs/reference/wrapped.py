# -*- coding: utf-8 -*-
# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

##############################################################################
# region> IMPORT
##############################################################################
# External.
from __future__ import annotations
import collections as _collections
import contextlib as _contextlib
import dataclasses as _dataclasses
import functools as _functools
import io as _io
import re as _re
import sys as _sys
import types as _types
import typing as _typing

# Internal.
import lgrs.reference.LGRS_Coordinate_Conversion as _cconv
_cconv.initialize_LGRS_function_globals()



# endregion
##############################################################################
# region> UTILITIES
##############################################################################
def _execute_coordinate_conversion(
        method_name: str, value: _BaseCoordinate, trunc_val: int,
        return_type: type[_BaseCoordinate]
) -> _BaseCoordinate:
    # Execute script, capturing stdout.
    orig_sys_argv = _sys.argv
    string_components = (v if isinstance(v, str) else repr(v) for v in value)
    _sys.argv = ["", method_name, *string_components]
    f = _io.StringIO()
    with _contextlib.redirect_stdout(f):
        try:
            _cconv.main(method_name, trunc_val, False)
        except SystemExit as e:
            raise TypeError(f.getvalue())
    _sys.argv = orig_sys_argv
    stdout_str = f.getvalue()

    # Create and return instance.
    if issubclass(return_type, _GriddedCoordinate):
        string = stdout_str.strip().replace(" ", "")
        new = return_type.from_string(string)
    else:
        string = stdout_str.strip()
        new = return_type._from_ref_string(string)
    return new

@_functools.cache
def _get_name_to_type(typ: type) -> dict[str, type]:
    name_to_type = {}
    for name, typ in _typing.get_type_hints(typ).items():
        if isinstance(typ, _types.UnionType):
            types = list(_typing.get_args(typ))
            types.remove(type(None))
            typ, = types  # *REASSIGNMENT*
        name_to_type[name] = typ
    return name_to_type



# endregion
##############################################################################
# region> DATACLASSES
##############################################################################
@_dataclasses.dataclass(kw_only=True, frozen=True)
class _BaseCoordinate:
    # TODO: Add `.__str__()`.

    def __iter__(self) -> _collections.abc.Iterable:
        return (getattr(self, field.name)
                for field in _dataclasses.fields(self))

    @classmethod
    def _from_ref_string(cls, string: str) -> _typing.Self:
        # Note: Unlike `_GriddedCoordinate.from_string()`, this method
        # exists solely to support parsing values from
        # `LGRS_Coordinate_Conversion`.
        parts = tuple(string.split(" "))
        if len(parts) == 1:
            raise TypeError("`string` must be space-delimited")
        name_to_type = _get_name_to_type(cls)
        if len(parts) > len(name_to_type):
            raise TypeError(
                "`string` contains too many space-delimited "
                f"components: {string!r}"
            )
        init_kwargs = {
            name: typ(part)
            for part, (name, typ) in zip(parts, name_to_type.items())
        }
        return cls(**init_kwargs)

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
class _GriddedCoordinate(_BaseCoordinate):
    # TODO: Add `.truncate_to()`.
    _pattern: _typing.ClassVar[_re.Pattern]

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
        name_to_type = _get_name_to_type(cls)
        init_kwargs = {
            name: name_to_type[name](value_string)
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
class LatLon(_BaseCoordinate):
    latitude: float
    longitude: float

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LpsLgrs(_GriddedCoordinate):
    _pattern = _re.compile(
        "^"
        "(?P<longitudinal_band>[ABYZ])"
        "(?P<easting_area>[A-HJ-NP-Z])"
        "(?P<northing_area>[-A-HJ-NP-Z+])"
        "(?P<e_and_n>[0-9]+)?"
        "$"
    )
    longitudinal_band: str
    easting_area: str
    northing_area: str
    easting: str | None = None
    northing: str | None = None

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmLgrs(_GriddedCoordinate):
    _pattern = _re.compile(
        "^"
        "(?P<longitudinal_band>[0-9]{1,2})"
        "(?P<latitudinal_band>[C-HJ-NP-X])"
        "(?P<easting_area>[A-HJK])"
        "(?P<northing_area>[A-HJ-NP-V])"
        "(?P<e_and_n>[0-9]+)?"
        "$"
    )
    longitudinal_band: int  # LTM zone
    latitudinal_band: str
    easting_area: str
    northing_area: str
    easting: str | None = None
    northing: str | None = None

@_dataclasses.dataclass(kw_only=True, frozen=True)
class Lps(_BaseCoordinate):
    hemisphere: str
    easting: float
    northing: float

@_dataclasses.dataclass(kw_only=True, frozen=True)
class Ltm(_BaseCoordinate):
    zone_number: int
    hemisphere: str
    easting: float
    northing: float



# endregion
##############################################################################
# region> CONVERSION FUNCTIONS
##############################################################################
def LGRS2ACC(value: LtmLgrs, *, trunc_val: int = 1) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LGRS2ACC", value, trunc_val, LtmAcc
    )

def LGRS2LGRS_ACC(value: LtmLgrs, *, trunc_val: int = 1) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LGRS2LGRS_ACC", value, trunc_val, LtmAcc
    )

def LGRS2LTM(value: LtmLgrs, *, trunc_val: int = 0) -> Ltm:
    return _execute_coordinate_conversion(
        "LGRS2LTM", value, trunc_val, Ltm
    )

def LGRS2LatLon(value: LtmLgrs, *, trunc_val: int = 0) -> LatLon:
    return _execute_coordinate_conversion(
        "LGRS2LatLon", value, trunc_val, LatLon
    )

def LGRS_ACC2LGRS(value: LtmAcc, *, trunc_val: int = 1) -> LtmLgrs:
    return _execute_coordinate_conversion(
        "LGRS_ACC2LGRS", value, trunc_val, LtmLgrs
    )

def LGRS_ACC2LTM(value: LtmAcc, *, trunc_val: int = 0) -> Ltm:
    return _execute_coordinate_conversion(
        "LGRS_ACC2LTM", value, trunc_val, Ltm
    )

def LGRS_ACC2LatLon(value: LtmAcc, *, trunc_val: int = 0) -> LatLon:
    return _execute_coordinate_conversion(
        "LGRS_ACC2LatLon", value, trunc_val, LatLon
    )

def LPS2ACC(value: Lps, *, trunc_val: int = 1) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LPS2ACC", value, trunc_val, LtmAcc
    )

def LPS2LatLon(value: Lps, *, trunc_val: int = 0) -> LatLon:
    return _execute_coordinate_conversion(
        "LPS2LatLon", value, trunc_val, LatLon
    )

def LPS2PolarLGRS(value: Lps, *, trunc_val: int = 1) -> LpsLgrs:
    return _execute_coordinate_conversion(
        "LPS2PolarLGRS", value, trunc_val, LpsLgrs
    )

def LPS2PolarLGRS_ACC(value: Lps, *, trunc_val: int = 1) -> LpsAcc:
    return _execute_coordinate_conversion(
        "LPS2PolarLGRS_ACC", value, trunc_val, LpsAcc
    )

def LTM2ACC(value: Ltm, *, trunc_val: int = 1) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LTM2ACC", value, trunc_val, LtmAcc
    )

def LTM2LGRS(value: Ltm, *, trunc_val: int = 1) -> LtmLgrs:
    return _execute_coordinate_conversion(
        "LTM2LGRS", value, trunc_val, LtmLgrs
    )

def LTM2LGRS_ACC(value: Ltm, *, trunc_val: int = 1) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LTM2LGRS_ACC", value, trunc_val, LtmAcc
    )

def LTM2LatLon(value: Ltm, *, trunc_val: int = 0) -> LatLon:
    return _execute_coordinate_conversion(
        "LTM2LatLon", value, trunc_val, LatLon
    )

def LatLon2ACC(value: LatLon, *, trunc_val: int = 1) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LatLon2ACC", value, trunc_val, LtmAcc
    )

def LatLon2LGRS(value: LatLon, *, trunc_val: int = 1) -> LtmLgrs:
    return _execute_coordinate_conversion(
        "LatLon2LGRS", value, trunc_val, LtmLgrs
    )

def LatLon2LGRS_ACC(value: LatLon, *, trunc_val: int = 1) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LatLon2LGRS_ACC", value, trunc_val, LtmAcc
    )

def LatLon2LPS(value: LatLon, *, trunc_val: int = 0) -> Lps:
    return _execute_coordinate_conversion(
        "LatLon2LPS", value, trunc_val, Lps
    )

def LatLon2LTM(value: LatLon, *, trunc_val: int = 0) -> Ltm:
    return _execute_coordinate_conversion(
        "LatLon2LTM", value, trunc_val, Ltm
    )

def LatLon2PolarLGRS(value: LatLon, *, trunc_val: int = 1) -> LpsLgrs:
    return _execute_coordinate_conversion(
        "LatLon2PolarLGRS", value, trunc_val, LpsLgrs
    )

def LatLon2PolarLGRS_ACC(value: LatLon, *, trunc_val: int = 1) -> LpsAcc:
    return _execute_coordinate_conversion(
        "LatLon2PolarLGRS_ACC", value, trunc_val, LpsAcc
    )

def LatLon2Polar_ACC(value: LatLon, *, trunc_val: int = 1) -> LpsAcc:
    return _execute_coordinate_conversion(
        "LatLon2Polar_ACC", value, trunc_val, LpsAcc
    )

def PolarLGRS2LPS(value: LpsLgrs, *, trunc_val: int = 0) -> Lps:
    return _execute_coordinate_conversion(
        "PolarLGRS2LPS", value, trunc_val, Lps
    )

def PolarLGRS2LatLon(value: LpsLgrs, *, trunc_val: int = 0) -> LatLon:
    return _execute_coordinate_conversion(
        "PolarLGRS2LatLon", value, trunc_val, LatLon
    )

def PolarLGRS2PolarLGRS_ACC(value: LpsLgrs, *, trunc_val: int = 1) -> LpsAcc:
    return _execute_coordinate_conversion(
        "PolarLGRS2PolarLGRS_ACC", value, trunc_val, LpsAcc
    )

def PolarLGRS2Polar_ACC(value: LpsLgrs, *, trunc_val: int = 1) -> LpsAcc:
    return _execute_coordinate_conversion(
        "PolarLGRS2Polar_ACC", value, trunc_val, LpsAcc
    )

def PolarLGRS_ACC2LPS(value: LpsAcc, *, trunc_val: int = 0) -> Lps:
    return _execute_coordinate_conversion(
        "PolarLGRS_ACC2LPS", value, trunc_val, Lps
    )

def PolarLGRS_ACC2LatLon(value: LpsAcc, *, trunc_val: int = 0) -> LatLon:
    return _execute_coordinate_conversion(
        "PolarLGRS_ACC2LatLon", value, trunc_val, LatLon
    )

def PolarLGRS_ACC2PolarLGRS(value: LpsAcc, *, trunc_val: int = 1) -> LpsLgrs:
    return _execute_coordinate_conversion(
        "PolarLGRS_ACC2PolarLGRS", value, trunc_val, LpsLgrs
    )



# endregion

polar_latlon = LatLon(latitude=85, longitude=1)
polar_lps = LatLon2LPS(polar_latlon)
polar_lps_recovered = LPS2LatLon(polar_lps)
polar_lps_recovered.is_equal_to(polar_latlon, error=True)
# Note: Below call will error because recovery is not exact.
# strict_result = polar_lps_recovered.is_equal_to(
#     polar_latlon, max_float_difference=0., error=True
# )
lps_lgrs = LpsLgrs(
    longitudinal_band="A", easting_area="Z", northing_area="S",
    easting="13590", northing="08480"
)
alt_lps_lgrs = LpsLgrs.from_string("AZS1359008480")
alt_lps_lgrs.is_equal_to(lps_lgrs, max_float_difference=0, error=True)
lps_acc = PolarLGRS2PolarLGRS_ACC(lps_lgrs)
lps_lgrs_recovered = PolarLGRS_ACC2PolarLGRS(lps_acc)
lps_lgrs_recovered.is_equal_to(lps_lgrs)
