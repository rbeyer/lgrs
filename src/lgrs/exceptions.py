# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

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