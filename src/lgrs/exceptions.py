"""Exceptions used across the `lgrs` library."""

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
import pyproj as _pyproj



# endregion
##############################################################################
# region> EXCEPTIONS
##############################################################################
# TODO: Delete unused exception classes.
class MalformedCoordinate(Exception):
    """
    Raised when a coordinate is malformed.
    """
    pass

class NonGriddedError(_pyproj.exceptions.CRSError):
    """
    Raised when a non-gridded object is unexpectedly encountered.

    For example, when a `pyproj.CRS` is encountered but a `GRS` is
    expected, or when a `pyproj.Transformer` is encountered but a
    `GriddedTransformer` is expected.
    """
    pass

class NonPolarError(_pyproj.exceptions.ProjError):
    """
    Raised when the non-polar region is unexpectedly referenced.
    """
    pass

class PolarError(_pyproj.exceptions.ProjError):
    """
    Raised when the polar region is unexpectedly referenced.
    """
    pass



# endregion