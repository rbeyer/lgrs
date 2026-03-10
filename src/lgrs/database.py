# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

##############################################################################
# region> IMPORT
##############################################################################
import collections as _collections
from pyproj import database as _pyproj_database
from pyproj import aoi as _pyproj_aoi



# endregion
##############################################################################
# region> INFO CLASSES
##############################################################################
# Note: Unfortunately, if we want to replicate
# `pyproj.query_utm_crs_info()` as closely as possible, we'd need to
# implement something like `pyproj.database.CRSInfo` (stub below) and
# `pyproj.database.PJType`, possibly more.
class SRSInfo(_pyproj_database.CRSInfo):
    ...



# endregion
##############################################################################
# region> QUERY FUNCTIONS
##############################################################################
# Conservative option, nearly identical to
# `pyproj.database.query_utm_crs_info()`. Note the necessary inclusion
# of `extended_ltm` to cover the 80-82 degrees LPS/LTM overlap.
def query_ltm_crs_info(
        datum_name: str | None = "IAU_2015:30100",
        area_of_interest: _pyproj_aoi.AreaOfInterest | None = None,
        contains: bool = False, *,
        extended_ltm: bool = False,
) -> list[SRSInfo]:
    ...

# Preferred option, which extends support to LPS and supports querying
# by point(s), which will be needed to support `GriddedTransform`
# (though `GriddedTransform` might use some intermediate `np.ndarray`
# form, for performance, rather than the final output of this function).
# Note: Might be preferable to instead return some subclass of `list`
# that has useful (but possibly empty) subsets accessible as `.lps`,
# `.ltm`, and `.ltm_extended`.
def query_lps_and_ltm_crs_info(
        datum_name: str | None = "IAU_2015:30100",
        area_of_interest: _pyproj_aoi.AreaOfInterest | None = None,
        contains: bool = False, *,
        extended_ltm: bool = False,
        latitude: float | _collections.abc.Iterable[float] | None = None,
        longitude: float | _collections.abc.Iterable[float] | None = None
) -> list[SRSInfo]:
    """
    Query for LPS and LTM CRS information.

    Parameters
    ----------
    datum_name : str, default="IAU_2015:30100"
        The name of the datum.
    area_of_interest : AreaOfInterest, optional
        Filter `infos` by `area_of_interest`. Not compatible with `latitude`
        and `longitude`.
    contains : bool, default=False
        If `True`, `infos` will only reference a CRS if its area of use entirely
        contains `area_of_interest`. If `False`, `infos` will only reference a
        CRS if its area of use intersects the specified `area_of_interest`.
        Ignored if `area_of_interest` is unspecified.
    extended_ltm : bool, default=False
        Whether to use extended LTM zones, which span from 80 to 82 degrees N
        and S.
    latitude : float or iterable of floats, optional
        The latitude(s) to query. Numpy arrays are preferred.
    longitude : float or array, optional
        The longitudes(s) to query. Numpy arrays are preferred.

    Returns
    -------
    infos : list[SRSInfo]
        List of LPS and/or LTM CRS information instances.

    Raises
    ------
    TypeError
        If the combination of `area_of_interest`, `latitude`, and `longitude`
        are under- or over-specified.

    Examples
    --------
    >>> query_lps_and_ltm_crs_info(latitude=0., longitude=0.)
    """
    match (latitude, longitude).count(None):
        case 1:
            raise TypeError(
                "Must specify both `latitude` and `longitude`, or "
                "neither."
            )
        case 2:
            if area_of_interest:
                raise TypeError("Cannot specify both `area_of_interest` and "
                                "`latitude`, `longitude`.")
    ...


# endregion