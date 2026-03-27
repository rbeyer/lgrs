"""
Code to wrap reference scripts.

Examples
--------
>>> import lgrs.srs.coords as coords
>>> polar_latlon = coords.LatLon(latitude=85, longitude=1)
>>> polar_lps = LatLon2LPS(polar_latlon)
>>> polar_latlon_recovered = LPS2LatLon(polar_lps)
>>> polar_latlon_recovered.is_equal_to(polar_latlon, error=True)
Note: Below call would error because recovery is not exact:
strict_result = polar_latlon_recovered.is_equal_to(
    polar_latlon, error=True, max_float_difference=0.
)
>>> lps_lgrs = coords.LpsLgrs(
...     longitudinal_band="A", easting_area="Z", northing_area="S",
...     easting="13590", northing="08480"
... )
>>> lps_acc = PolarLGRS2PolarLGRS_ACC(lps_lgrs)
>>> lps_lgrs_recovered = PolarLGRS_ACC2PolarLGRS(lps_acc)
>>> lps_lgrs_recovered.is_equal_to(lps_lgrs, error=True)
"""

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
import contextlib as _contextlib
import io as _io
import sys as _sys

# Internal.
import lgrs.srs.coords as _coords
import lgrs.reference.LGRS_Coordinate_Conversion as _cconv
_cconv.initialize_LGRS_function_globals()



# endregion
##############################################################################
# region> UTILITIES
##############################################################################
def _execute_coordinate_conversion(
        method_name: str, value: _coords._BaseCoordinate, trunc_val: int,
        return_type: type[_coords._BaseCoordinate]
) -> _coords._BaseCoordinate:
    # Execute script, capturing stdout.
    orig_sys_argv = _sys.argv
    string_components = (v if isinstance(v, str) else repr(v) for v in value)
    _sys.argv = ["", method_name, *string_components]
    f = _io.StringIO()
    with _contextlib.redirect_stdout(f):
        try:
            _cconv.main(method_name, trunc_val, False)
        except SystemExit:
            raise TypeError(f.getvalue())
    _sys.argv = orig_sys_argv
    stdout_str = f.getvalue()

    # Create and return instance.
    if issubclass(return_type, _coords._GriddedCoordinate):
        string = stdout_str.strip().replace(" ", "")
        new = return_type.from_string(string)
    else:
        string = stdout_str.strip()
        new = return_type._from_ref_string(string)
    return new



# endregion
##############################################################################
# region> CONVERSION FUNCTIONS
##############################################################################
def LGRS2ACC(value: _coords.LtmLgrs, *, trunc_val: int = 1) -> _coords.LtmAcc:
    return _execute_coordinate_conversion(
        "LGRS2ACC", value, trunc_val, _coords.LtmAcc
    )

def LGRS2LGRS_ACC(value: _coords.LtmLgrs, *, trunc_val: int = 1) -> _coords.LtmAcc:
    return _execute_coordinate_conversion(
        "LGRS2LGRS_ACC", value, trunc_val, _coords.LtmAcc
    )

def LGRS2LTM(value: _coords.LtmLgrs, *, trunc_val: int = 0) -> _coords.Ltm:
    return _execute_coordinate_conversion(
        "LGRS2LTM", value, trunc_val, _coords.Ltm
    )

def LGRS2LatLon(value: _coords.LtmLgrs, *, trunc_val: int = 0) -> _coords.LatLon:
    return _execute_coordinate_conversion(
        "LGRS2LatLon", value, trunc_val, _coords.LatLon
    )

def LGRS_ACC2LGRS(value: _coords.LtmAcc, *, trunc_val: int = 1) -> _coords.LtmLgrs:
    return _execute_coordinate_conversion(
        "LGRS_ACC2LGRS", value, trunc_val, _coords.LtmLgrs
    )

def LGRS_ACC2LTM(value: _coords.LtmAcc, *, trunc_val: int = 0) -> _coords.Ltm:
    return _execute_coordinate_conversion(
        "LGRS_ACC2LTM", value, trunc_val, _coords.Ltm
    )

def LGRS_ACC2LatLon(value: _coords.LtmAcc, *, trunc_val: int = 0) -> _coords.LatLon:
    return _execute_coordinate_conversion(
        "LGRS_ACC2LatLon", value, trunc_val, _coords.LatLon
    )

def LPS2ACC(value: _coords.Lps, *, trunc_val: int = 1) -> _coords.LtmAcc:
    return _execute_coordinate_conversion(
        "LPS2ACC", value, trunc_val, _coords.LtmAcc
    )

def LPS2LatLon(value: _coords.Lps, *, trunc_val: int = 0) -> _coords.LatLon:
    return _execute_coordinate_conversion(
        "LPS2LatLon", value, trunc_val, _coords.LatLon
    )

def LPS2PolarLGRS(value: _coords.Lps, *, trunc_val: int = 1) -> _coords.LpsLgrs:
    return _execute_coordinate_conversion(
        "LPS2PolarLGRS", value, trunc_val, _coords.LpsLgrs
    )

def LPS2PolarLGRS_ACC(value: _coords.Lps, *, trunc_val: int = 1) -> _coords.LpsAcc:
    return _execute_coordinate_conversion(
        "LPS2PolarLGRS_ACC", value, trunc_val, _coords.LpsAcc
    )

def LTM2ACC(value: _coords.Ltm, *, trunc_val: int = 1) -> _coords.LtmAcc:
    return _execute_coordinate_conversion(
        "LTM2ACC", value, trunc_val, _coords.LtmAcc
    )

def LTM2LGRS(value: _coords.Ltm, *, trunc_val: int = 1) -> _coords.LtmLgrs:
    return _execute_coordinate_conversion(
        "LTM2LGRS", value, trunc_val, _coords.LtmLgrs
    )

def LTM2LGRS_ACC(value: _coords.Ltm, *, trunc_val: int = 1) -> _coords.LtmAcc:
    return _execute_coordinate_conversion(
        "LTM2LGRS_ACC", value, trunc_val, _coords.LtmAcc
    )

def LTM2LatLon(value: _coords.Ltm, *, trunc_val: int = 0) -> _coords.LatLon:
    return _execute_coordinate_conversion(
        "LTM2LatLon", value, trunc_val, _coords.LatLon
    )

def LatLon2ACC(value: _coords.LatLon, *, trunc_val: int = 1) -> _coords.LtmAcc:
    return _execute_coordinate_conversion(
        "LatLon2ACC", value, trunc_val, _coords.LtmAcc
    )

def LatLon2LGRS(value: _coords.LatLon, *, trunc_val: int = 1) -> _coords.LtmLgrs:
    return _execute_coordinate_conversion(
        "LatLon2LGRS", value, trunc_val, _coords.LtmLgrs
    )

def LatLon2LGRS_ACC(value: _coords.LatLon, *, trunc_val: int = 1) -> _coords.LtmAcc:
    return _execute_coordinate_conversion(
        "LatLon2LGRS_ACC", value, trunc_val, _coords.LtmAcc
    )

def LatLon2LPS(value: _coords.LatLon, *, trunc_val: int = 0) -> _coords.Lps:
    return _execute_coordinate_conversion(
        "LatLon2LPS", value, trunc_val, _coords.Lps
    )

def LatLon2LTM(value: _coords.LatLon, *, trunc_val: int = 0) -> _coords.Ltm:
    return _execute_coordinate_conversion(
        "LatLon2LTM", value, trunc_val, _coords.Ltm
    )

def LatLon2PolarLGRS(value: _coords.LatLon, *, trunc_val: int = 1) -> _coords.LpsLgrs:
    return _execute_coordinate_conversion(
        "LatLon2PolarLGRS", value, trunc_val, _coords.LpsLgrs
    )

def LatLon2PolarLGRS_ACC(value: _coords.LatLon, *, trunc_val: int = 1) -> _coords.LpsAcc:
    return _execute_coordinate_conversion(
        "LatLon2PolarLGRS_ACC", value, trunc_val, _coords.LpsAcc
    )

def LatLon2Polar_ACC(value: _coords.LatLon, *, trunc_val: int = 1) -> _coords.LpsAcc:
    return _execute_coordinate_conversion(
        "LatLon2Polar_ACC", value, trunc_val, _coords.LpsAcc
    )

def PolarLGRS2LPS(value: _coords.LpsLgrs, *, trunc_val: int = 0) -> _coords.Lps:
    return _execute_coordinate_conversion(
        "PolarLGRS2LPS", value, trunc_val, _coords.Lps
    )

def PolarLGRS2LatLon(value: _coords.LpsLgrs, *, trunc_val: int = 0) -> _coords.LatLon:
    return _execute_coordinate_conversion(
        "PolarLGRS2LatLon", value, trunc_val, _coords.LatLon
    )

def PolarLGRS2PolarLGRS_ACC(value: _coords.LpsLgrs, *, trunc_val: int = 1) -> _coords.LpsAcc:
    return _execute_coordinate_conversion(
        "PolarLGRS2PolarLGRS_ACC", value, trunc_val, _coords.LpsAcc
    )

def PolarLGRS2Polar_ACC(value: _coords.LpsLgrs, *, trunc_val: int = 1) -> _coords.LpsAcc:
    return _execute_coordinate_conversion(
        "PolarLGRS2Polar_ACC", value, trunc_val, _coords.LpsAcc
    )

def PolarLGRS_ACC2LPS(value: _coords.LpsAcc, *, trunc_val: int = 0) -> _coords.Lps:
    return _execute_coordinate_conversion(
        "PolarLGRS_ACC2LPS", value, trunc_val, _coords.Lps
    )

def PolarLGRS_ACC2LatLon(value: _coords.LpsAcc, *, trunc_val: int = 0) -> _coords.LatLon:
    return _execute_coordinate_conversion(
        "PolarLGRS_ACC2LatLon", value, trunc_val, _coords.LatLon
    )

def PolarLGRS_ACC2PolarLGRS(value: _coords.LpsAcc, *, trunc_val: int = 1) -> _coords.LpsLgrs:
    return _execute_coordinate_conversion(
        "PolarLGRS_ACC2PolarLGRS", value, trunc_val, _coords.LpsLgrs
    )



# endregion