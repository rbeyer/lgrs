"""Exceptions used across the `lgrs` library."""

# Copyright © 2026, Ethan I. Schaefer (eschaefer@seti.org)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.


###############################################################################
# region> IMPORT
###############################################################################
# Standard.
import warnings as _warnings


# endregion
###############################################################################
# region> EXCEPTIONS
###############################################################################
class CoordinateError(ValueError):
    """
    Raised when a coordinate is malformed or invalid.
    """

    pass


class GeospatialFileError(ValueError):
    """
    Raised when a geospatial file cannot be read as vector or raster data.

    The file exists and can be opened for reading. A missing file raises
    `FileNotFoundError` instead, and a file that cannot be opened raises
    `PermissionError`.
    """

    pass


# endregion
###############################################################################
# region> DEPRECATED NAMES
###############################################################################
def __getattr__(name: str) -> type:
    # Note: Python calls a module-level `__getattr__()` only for a name
    # that the module does not define (PEP 562). Resolve the name used
    # through 0.3.0, `MalformedCoordinate`, to its renamed class, with a
    # warning, so that code written for 0.3.0 keeps working.
    if name == "MalformedCoordinate":
        _warnings.warn(
            "`MalformedCoordinate` is deprecated; use `CoordinateError`.",
            DeprecationWarning,
            stacklevel=2,
        )
        return CoordinateError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# endregion
