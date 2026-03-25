# -*- coding: utf-8 -*-
# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

##############################################################################
# region> IMPORT
##############################################################################
from __future__ import annotations
import builtins as _builtins
import collections as _collections
import contextlib as _contextlib
import dataclasses as _dataclasses
import functools as _functools
import inspect as _inspect
import io as _io
import pathlib as _pathlib
import sys as _sys
import typing as _typing

from sphinx.ext.inheritance_diagram import latex_visit_inheritance_diagram

# endregion
##############################################################################
# region> READ SCRIPTS
##############################################################################
HOST_DIR_PATH = _pathlib.Path(__file__).parent
COORDINATE_CONVERSION_PATH = HOST_DIR_PATH / "LGRS_Coordinate_Conversion_edited.py"
COORDINATE_CONVERSION_CODE_STRING = COORDINATE_CONVERSION_PATH.read_text()



# endregion
##############################################################################
# region> UTILITIES
##############################################################################
def _coerce_to_int(string: str) -> int | None:
    try:
        float_val = float(string)
    except ValueError:
        return None
    if float_val.is_integer():
        return int(float_val)
    else:
        return None

def _execute_coordinate_conversion(
        method_name: str, value: _BaseLocus, trunc_val: int,
        return_type: type[_BaseLocus]
) -> _BaseLocus:
    # Set script parameters.
    explicit_globals = {
        "info": False,
        "trunc_val": trunc_val,
        "condensed": False,
    }
    _sys.argv = ["", method_name, *value.spaced.split(" ")]
    
    # Execute script, capturing stdout.
    f = _io.StringIO()
    with _contextlib.redirect_stdout(f):
        try:
            exec(COORDINATE_CONVERSION_CODE_STRING, globals=explicit_globals)
        except SystemExit as e:
            raise TypeError(f.getvalue())
    stdout_str = f.getvalue()

    # Create and return instance.
    new = return_type.from_string(stdout_str.strip())
    return new



# endregion
##############################################################################
# region> DATACLASSES
##############################################################################
@_dataclasses.dataclass(kw_only=True, frozen=True)
class _BaseLocus:

    def __iter__(self) -> _collections.abc.Iterable:
        return (getattr(self, field.name)
                for field in _dataclasses.fields(self))

    @classmethod
    def from_string(
            cls, string: str, *, coerce_to_int: bool = True
    ) -> _BaseLocus:
        # Note: `fields` and `parts` are mapped from last to first to
        # accommodate leading optional arguments for `*Acc`.
        fields = tuple(reversed(_dataclasses.fields(cls)))
        parts = tuple(reversed(string.split(" ")))
        if len(parts) > len(fields):
            raise TypeError(
                "`string` contains too many space-delimited "
                f"components: {string!r}"
            )
        init_kwargs = {}
        for field, part in zip(fields, parts):
            val_typ = getattr(_builtins, field.type)
            try:
                val = val_typ(part)
            except ValueError as e:
                if (not coerce_to_int) or (field.type != "int"):
                    raise e
                val = _coerce_to_int(part)
                if val is None:
                    raise e
            init_kwargs[field.name] = val
        return cls(**init_kwargs)

    @_functools.cached_property
    def condensed(self) -> str:
        return self.spaced.replace(" ", "")

    @_functools.cached_property
    def spaced(self) -> str:
        strings = []
        for val in self:
            if val is None:
                continue
            if isinstance(val, str):
                string = val
            else:
                string = repr(val)
            strings.append(string)
        return " ".join(strings)

    def is_equal_to(
            self, other: _typing.Self, *,
            max_float_difference: float | None = None,
            error: bool = False
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
class LpsAcc(_BaseLocus):
    longitudinal_band: str
    easting_area: str
    northing_area: str
    easting_1k: str
    easting: int
    northing_1k: str
    northing: int

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmAcc(_BaseLocus):
    longitudinal_band: int
    latitudinal_band: str
    easting_area: str
    northing_area: str
    easting_1k: str
    easting: int
    northing_1k: str
    northing: int

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LatLon(_BaseLocus):
    latitude: float
    longitude: float

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LpsLgrs(_BaseLocus):
    longitudinal_band: str
    easting_area: str
    northing_area: str
    easting: int
    northing: int

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmLgrs(_BaseLocus):
    longitudinal_band: int
    latitudinal_band: str
    easting_area: str
    northing_area: str
    easting: int
    northing: int

@_dataclasses.dataclass(kw_only=True, frozen=True)
class Lps(_BaseLocus):
    hemisphere: str
    easting: float
    northing: float

@_dataclasses.dataclass(kw_only=True, frozen=True)
class Ltm(_BaseLocus):
    zone_number: int
    hemisphere: str
    easting: float
    northing: float



# endregion
##############################################################################
# region> CONVERSION FUNCTIONS
##############################################################################
def LGRS2ACC(value: LtmLgrs, *, trunc_val: int = 0) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LGRS2ACC", value, trunc_val, LtmAcc
    )

def LGRS2LGRS_ACC(value: LtmLgrs, *, trunc_val: int = 0) -> LtmAcc:
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

def LGRS_ACC2LGRS(value: LtmAcc, *, trunc_val: int = 0) -> LtmLgrs:
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

def LPS2ACC(value: Lps, *, trunc_val: int = 0) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LPS2ACC", value, trunc_val, LtmAcc
    )

def LPS2LatLon(value: Lps, *, trunc_val: int = 0) -> LatLon:
    return _execute_coordinate_conversion(
        "LPS2LatLon", value, trunc_val, LatLon
    )

def LPS2PolarLGRS(value: Lps, *, trunc_val: int = 0) -> LpsLgrs:
    return _execute_coordinate_conversion(
        "LPS2PolarLGRS", value, trunc_val, LpsLgrs
    )

def LPS2PolarLGRS_ACC(value: Lps, *, trunc_val: int = 0) -> LpsAcc:
    return _execute_coordinate_conversion(
        "LPS2PolarLGRS_ACC", value, trunc_val, LpsAcc
    )

def LTM2ACC(value: Ltm, *, trunc_val: int = 0) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LTM2ACC", value, trunc_val, LtmAcc
    )

def LTM2LGRS(value: Ltm, *, trunc_val: int = 0) -> LtmLgrs:
    return _execute_coordinate_conversion(
        "LTM2LGRS", value, trunc_val, LtmLgrs
    )

def LTM2LGRS_ACC(value: Ltm, *, trunc_val: int = 0) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LTM2LGRS_ACC", value, trunc_val, LtmAcc
    )

def LTM2LatLon(value: Ltm, *, trunc_val: int = 0) -> LatLon:
    return _execute_coordinate_conversion(
        "LTM2LatLon", value, trunc_val, LatLon
    )

def LatLon2ACC(value: LatLon, *, trunc_val: int = 0) -> LtmAcc:
    return _execute_coordinate_conversion(
        "LatLon2ACC", value, trunc_val, LtmAcc
    )

def LatLon2LGRS(value: LatLon, *, trunc_val: int = 0) -> LtmLgrs:
    return _execute_coordinate_conversion(
        "LatLon2LGRS", value, trunc_val, LtmLgrs
    )

def LatLon2LGRS_ACC(value: LatLon, *, trunc_val: int = 0) -> LtmAcc:
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

def LatLon2PolarLGRS(value: LatLon, *, trunc_val: int = 0) -> LpsLgrs:
    return _execute_coordinate_conversion(
        "LatLon2PolarLGRS", value, trunc_val, LpsLgrs
    )

def LatLon2PolarLGRS_ACC(value: LatLon, *, trunc_val: int = 0) -> LpsAcc:
    return _execute_coordinate_conversion(
        "LatLon2PolarLGRS_ACC", value, trunc_val, LpsAcc
    )

def LatLon2Polar_ACC(value: LatLon, *, trunc_val: int = 0) -> LpsAcc:
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

def PolarLGRS2PolarLGRS_ACC(value: LpsLgrs, *, trunc_val: int = 0) -> LpsAcc:
    return _execute_coordinate_conversion(
        "PolarLGRS2PolarLGRS_ACC", value, trunc_val, LpsAcc
    )

def PolarLGRS2Polar_ACC(value: LpsLgrs, *, trunc_val: int = 0) -> LpsAcc:
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

def PolarLGRS_ACC2PolarLGRS(value: LpsAcc, *, trunc_val: int = 0) -> LpsLgrs:
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
    easting=13590, northing=8480
)
alt_lps_lgrs = LpsLgrs.from_string("A Z S 13590 08480")
alt_lps_lgrs.is_equal_to(lps_lgrs, max_float_difference=0, error=True)
lps_acc = PolarLGRS2PolarLGRS_ACC(lps_lgrs)
lps_lgrs_recovered = PolarLGRS_ACC2PolarLGRS(lps_acc)
lps_lgrs_recovered.is_equal_to(lps_lgrs)

# TODO: For `*LGRS` and `*ACC` types, change `int` -> `str`, to support
#  leading zeros.
# TODO: Extend `.from_string()` to support condensed strings (i.e.,
#  strings without space delimiters) wherever necessary.