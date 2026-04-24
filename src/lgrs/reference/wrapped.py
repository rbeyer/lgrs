"""
Code to wrap reference scripts.

Examples
--------
>>> import lgrs.coords as coords
>>> polar_latlon = coords.LatLonPoint(latitude=85, longitude=1)
>>> polar_lps = LatLon2LPS(polar_latlon)
>>> polar_latlon_recovered = LPS2LatLon(polar_lps)
>>> polar_latlon_recovered.is_close_to(polar_latlon, error=True)

Note: Below call would error because recovery is not exact:
strict_result = polar_latlon_recovered.is_equal_to(
    polar_latlon, error=True, max_float_difference=0.
)

>>> lps_lgrs = coords.LpsLgrsBox.from_string("AZS1359008480")
>>> lps_acc = PolarLGRS2PolarLGRS_ACC(lps_lgrs)
>>> lps_lgrs_recovered = PolarLGRS_ACC2PolarLGRS(lps_acc)
>>> lps_lgrs_recovered.is_close_to(lps_lgrs, error=True)
"""

# Copyright © 2026, Ethan I. Schafer (eschaefer@seti.org) and
# Ross A. Beyer (rbeyer@seti.org)
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
# External.
from __future__ import annotations
import contextlib as _contextlib
import io as _io
import sys as _sys

# Internal.
import lgrs.coords as _coords
import lgrs.reference.LGRS_Coordinate_Conversion as _cconv
_cconv.initialize_LGRS_function_globals()



# endregion
##############################################################################
# region> UTILITIES
##############################################################################
def _execute_coordinate_conversion(
        method_name: str, value: _coords.BaseCoordinate, trunc_val: int,
        return_type: type[_coords.BaseCoordinate]
) -> _coords.BaseCoordinate:
    # Execute script, capturing stdout.
    orig_sys_argv = _sys.argv
    _sys.argv = ["", method_name, *value._iter_value_strings()]
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
def LGRS2ACC(value: _coords.LtmLgrsBox, *, trunc_val: int = 1) -> _coords.LtmAccBox:
    return _execute_coordinate_conversion(
        "LGRS2ACC", value, trunc_val, _coords.LtmAccBox
    )

def LGRS2LGRS_ACC(value: _coords.LtmLgrsBox, *, trunc_val: int = 1) -> _coords.LtmAccBox:
    return _execute_coordinate_conversion(
        "LGRS2LGRS_ACC", value, trunc_val, _coords.LtmAccBox
    )

def LGRS2LTM(value: _coords.LtmLgrsBox, *, trunc_val: int = 0) -> _coords.LtmPoint:
    return _execute_coordinate_conversion(
        "LGRS2LTM", value, trunc_val, _coords.LtmPoint
    )

def LGRS2LatLon(value: _coords.LtmLgrsBox, *, trunc_val: int = 0) -> _coords.LatLonPoint:
    return _execute_coordinate_conversion(
        "LGRS2LatLon", value, trunc_val, _coords.LatLonPoint
    )

def LGRS_ACC2LGRS(value: _coords.LtmAccBox, *, trunc_val: int = 1) -> _coords.LtmLgrsBox:
    return _execute_coordinate_conversion(
        "LGRS_ACC2LGRS", value, trunc_val, _coords.LtmLgrsBox
    )

def LGRS_ACC2LTM(value: _coords.LtmAccBox, *, trunc_val: int = 0) -> _coords.LtmPoint:
    return _execute_coordinate_conversion(
        "LGRS_ACC2LTM", value, trunc_val, _coords.LtmPoint
    )

def LGRS_ACC2LatLon(value: _coords.LtmAccBox, *, trunc_val: int = 0) -> _coords.LatLonPoint:
    return _execute_coordinate_conversion(
        "LGRS_ACC2LatLon", value, trunc_val, _coords.LatLonPoint
    )

def LPS2ACC(value: _coords.LpsPoint, *, trunc_val: int = 1) -> _coords.LtmAccBox:
    return _execute_coordinate_conversion(
        "LPS2ACC", value, trunc_val, _coords.LtmAccBox
    )

def LPS2LatLon(value: _coords.LpsPoint, *, trunc_val: int = 0) -> _coords.LatLonPoint:
    return _execute_coordinate_conversion(
        "LPS2LatLon", value, trunc_val, _coords.LatLonPoint
    )

def LPS2PolarLGRS(value: _coords.LpsPoint, *, trunc_val: int = 1) -> _coords.LpsLgrsBox:
    return _execute_coordinate_conversion(
        "LPS2PolarLGRS", value, trunc_val, _coords.LpsLgrsBox
    )

def LPS2PolarLGRS_ACC(value: _coords.LpsPoint, *, trunc_val: int = 1) -> _coords.LpsAccBox:
    return _execute_coordinate_conversion(
        "LPS2PolarLGRS_ACC", value, trunc_val, _coords.LpsAccBox
    )

def LTM2ACC(value: _coords.LtmPoint, *, trunc_val: int = 1) -> _coords.LtmAccBox:
    return _execute_coordinate_conversion(
        "LTM2ACC", value, trunc_val, _coords.LtmAccBox
    )

def LTM2LGRS(value: _coords.LtmPoint, *, trunc_val: int = 1) -> _coords.LtmLgrsBox:
    return _execute_coordinate_conversion(
        "LTM2LGRS", value, trunc_val, _coords.LtmLgrsBox
    )

def LTM2LGRS_ACC(value: _coords.LtmPoint, *, trunc_val: int = 1) -> _coords.LtmAccBox:
    return _execute_coordinate_conversion(
        "LTM2LGRS_ACC", value, trunc_val, _coords.LtmAccBox
    )

def LTM2LatLon(value: _coords.LtmPoint, *, trunc_val: int = 0) -> _coords.LatLonPoint:
    return _execute_coordinate_conversion(
        "LTM2LatLon", value, trunc_val, _coords.LatLonPoint
    )

def LatLon2ACC(value: _coords.LatLonPoint, *, trunc_val: int = 1) -> _coords.LtmAccBox:
    return _execute_coordinate_conversion(
        "LatLon2ACC", value, trunc_val, _coords.LtmAccBox
    )

def LatLon2LGRS(value: _coords.LatLonPoint, *, trunc_val: int = 1) -> _coords.LtmLgrsBox:
    return _execute_coordinate_conversion(
        "LatLon2LGRS", value, trunc_val, _coords.LtmLgrsBox
    )

def LatLon2LGRS_ACC(value: _coords.LatLonPoint, *, trunc_val: int = 1) -> _coords.LtmAccBox:
    return _execute_coordinate_conversion(
        "LatLon2LGRS_ACC", value, trunc_val, _coords.LtmAccBox
    )

def LatLon2LPS(value: _coords.LatLonPoint, *, trunc_val: int = 0) -> _coords.LpsPoint:
    return _execute_coordinate_conversion(
        "LatLon2LPS", value, trunc_val, _coords.LpsPoint
    )

def LatLon2LTM(value: _coords.LatLonPoint, *, trunc_val: int = 0) -> _coords.LtmPoint:
    return _execute_coordinate_conversion(
        "LatLon2LTM", value, trunc_val, _coords.LtmPoint
    )

def LatLon2PolarLGRS(value: _coords.LatLonPoint, *, trunc_val: int = 1) -> _coords.LpsLgrsBox:
    return _execute_coordinate_conversion(
        "LatLon2PolarLGRS", value, trunc_val, _coords.LpsLgrsBox
    )

def LatLon2PolarLGRS_ACC(value: _coords.LatLonPoint, *, trunc_val: int = 1) -> _coords.LpsAccBox:
    return _execute_coordinate_conversion(
        "LatLon2PolarLGRS_ACC", value, trunc_val, _coords.LpsAccBox
    )

def LatLon2Polar_ACC(value: _coords.LatLonPoint, *, trunc_val: int = 1) -> _coords.LpsAccBox:
    return _execute_coordinate_conversion(
        "LatLon2Polar_ACC", value, trunc_val, _coords.LpsAccBox
    )

def PolarLGRS2LPS(value: _coords.LpsLgrsBox, *, trunc_val: int = 0) -> _coords.LpsPoint:
    return _execute_coordinate_conversion(
        "PolarLGRS2LPS", value, trunc_val, _coords.LpsPoint
    )

def PolarLGRS2LatLon(value: _coords.LpsLgrsBox, *, trunc_val: int = 0) -> _coords.LatLonPoint:
    return _execute_coordinate_conversion(
        "PolarLGRS2LatLon", value, trunc_val, _coords.LatLonPoint
    )

def PolarLGRS2PolarLGRS_ACC(value: _coords.LpsLgrsBox, *, trunc_val: int = 1) -> _coords.LpsAccBox:
    return _execute_coordinate_conversion(
        "PolarLGRS2PolarLGRS_ACC", value, trunc_val, _coords.LpsAccBox
    )

def PolarLGRS2Polar_ACC(value: _coords.LpsLgrsBox, *, trunc_val: int = 1) -> _coords.LpsAccBox:
    return _execute_coordinate_conversion(
        "PolarLGRS2Polar_ACC", value, trunc_val, _coords.LpsAccBox
    )

def PolarLGRS_ACC2LPS(value: _coords.LpsAccBox, *, trunc_val: int = 0) -> _coords.LpsPoint:
    return _execute_coordinate_conversion(
        "PolarLGRS_ACC2LPS", value, trunc_val, _coords.LpsPoint
    )

def PolarLGRS_ACC2LatLon(value: _coords.LpsAccBox, *, trunc_val: int = 0) -> _coords.LatLonPoint:
    return _execute_coordinate_conversion(
        "PolarLGRS_ACC2LatLon", value, trunc_val, _coords.LatLonPoint
    )

def PolarLGRS_ACC2PolarLGRS(value: _coords.LpsAccBox, *, trunc_val: int = 1) -> _coords.LpsLgrsBox:
    return _execute_coordinate_conversion(
        "PolarLGRS_ACC2PolarLGRS", value, trunc_val, _coords.LpsLgrsBox
    )



# endregion