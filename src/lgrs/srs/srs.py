# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

##############################################################################
# region> IMPORT
##############################################################################
import abc as _abc
import functools as _functools
import pyproj as _pyproj



# endregion
##############################################################################
# region> SPATIAL REFERENCE SYSTEMS
##############################################################################
class CRS(_pyproj.CRS):
    @_functools.wraps(_pyproj.CRS.__init__)
    def __init__(self, *args, **kwargs) -> None:
        # TODO: Add LTM support equivalent to existing UTM support. The
        #  expectation is that this `CRS` class could be dropped once
        #  LTM gains PROJ support.
        # Example: `CRS("IAU_2015:30100 / LTM zone 23N")
        # Example: `CRS(proj="ltm", zone=23, ellps="IAU_2015:30100")`
        # Note: My ideal would be that LPS would also be supported by
        # this syntactic sugar, but since UPS is not thusly supported,
        # that's probably unrealistic.
        # Fall back to `super().__init__(...)` if not LTM specific.
        ...

class GRS:
    """
    Class for gridded reference systems.
    """
    def __init__(self, *args, **kwargs) -> None:
        # Support instantiation by "LGRS:" and "ACC:", or maybe drop the
        # colons?
        # Note: Use of custom authorities is explicitly recommended in
        # the PROJ docs
        # (https://proj.org/en/stable/apps/projinfo.html#cmdoption-projinfo-output-id).
        # Note: We could test "LGRS" and "ACC" against
        # `pyproj.database.get_authorities()` at startup and issue a
        # warning if there is a collision, as future-proofing
        # precaution.
        ...

class BaseSRS(_abc.ABC):
    """
    Abstract base class for spatial reference systems.
    """
    ...
BaseSRS.register(_pyproj.CRS)
BaseSRS.register(GRS)



# endregion
