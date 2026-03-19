# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

##############################################################################
# region> IMPORT
##############################################################################
# External.
import abc as _abc
import functools as _functools
import pyproj as _pyproj
import re as _re

# Internal.
import lgrs.caching as _caching
import lgrs.srs.wkt as _wkt



# endregion
##############################################################################
# region> COORDINATE REFERENCE SYSTEMS
##############################################################################
_crs_name_pattern = _re.compile(
    "(?i)^"  # Case-insensitive. Match from start.
    "((?P<datum>.+?) ?/ ?)?"  # Datum is optional.
    "(?P<proj>LPS|LTM)"  # "LPS" or "LTM".
    "( zone)? "  # "zone" is optional.
    "(?P<num>[0-9]+)?"  # Zone number.
    "(?P<n_or_s>[NS])"  # "N" or "S" hemisphere.
    "$"  # Match to end.
)

class CRS(_pyproj.CRS, metaclass=_caching._MetaMultiton):
    """
    Equivalent to `pyproj.CRS` with caching support.

    Examples
    --------
    >>> import lgrs.CRS
    >>> crs_utm = CRS.from_user_input(32615)
    >>> crs_utm2 = CRS.from_user_input(32615)
    >>> crs_utm2 is crs_utm
    True
    # However, equivalent arguments are not guaranteed to cache identically.
    >>> crs_utm3 = CRS("WGS 84 / UTM zone 15N")
    >>> crs_utm3.is_exact_same(crs_utm)
    True
    >>> crs_utm3 is crs_utm
    False
    """

def make_lps_or_ltm_crs(
        name: str | None = None, *,
        proj: str | None = None, zone: int | None = None,
        south: bool | None = None, ellps: str | None = None,
        extended_ltm: bool = False,
) -> CRS:
    """
    Return LPS or LTM zone `CRS` using UTM-like `proj.CRS()` arguments.

    See Examples section below.

    Parameters
    ----------
    name : str, optional
        String name of `crs`. If specified, no additional argument may be
        specified, except for `extended_ltm`.
    proj : str, optional
        "LTM" or "LPS". Must be specified, unless `name` is specified.
    zone : int, optional
        The LTM zone. Should not be specified for LPS.
    south : bool, optional
        Whether `crs` is in the Southern Hemisphere. Must be specified,
        unless `name` is specified.
    ellps : str, default="IAU_2015:30100"
        The name of the `crs` ellipsoid.
    extended_ltm : bool, default=False
        Whether to use the extended LTM range of 80-82 degrees.

    Returns
    -------
    crs : CRS
        The LPS or LTM zone CRS instance.

    Examples
    --------
    >>> import pyproj
    >>> utm_crs = pyproj.CRS("WGS84 / UTM zone 23N")
    >>> ltm_crs = make_lps_or_ltm_crs("IAU_2015:30100 / LTM zone 23N")
    >>> utm_crs2 = CRS(proj="utm", zone=23, south=False, ellps="WGS84")
    >>> ltm_crs2 = make_lps_or_ltm_crs(
    ...    proj="ltm", zone=23, south=False, ellps="IAU_2015:30100"
    ...    )
    As a convenience, LPS is also supported.
    >>> lps_crs = make_lps_or_ltm_crs("IAU_2015:30100 / LPS S")
    >>> lps_crs2 = make_lps_or_ltm_crs(
    ...    proj="lps", south=True, ellps="IAU_2015:30100"
    ...    )
    As a further convenience, `ellps` defaults to "IAU_2015:30100" and,
    as with `pyproj.CRS` UTM support, the word "zone" is optional.
    >>> lps_crs3 = make_lps_or_ltm_crs("LPS S")
    >>> ltm_crs3 = make_lps_or_ltm_crs("LTM 23N")
    """
    # TODO: Should we also make `proj` optional, to support calls like
    #  `make_lps_or_ltm_crs("S")` and `make_lps_or_ltm_crs("23N")`?
    #  *Alternatively*, should we drop defaulting `ellps`, to more
    #  closely parallel `pyproj.CRS()` and what it (may) one day support
    #  for LTM? Likewise, drop LPS support for the same reason?
    # TODO: Determine whether to align `crs.name` with `name`. Instead,
    #  `crs.name` may be "Moon (2015) - Sphere / Ocentric..."
    # Parse `name`, is specified.
    if name is not None:
        if (proj, zone, south, ellps).count(None) != 4:
            raise TypeError(
                "If `name` is specified, `zone`, `south`, and `ellps` "
                "must be `None`."
            )
        match = _crs_name_pattern.search(name)
        if match is None:
            raise TypeError(f"`name` is not in a recognized form: {name!r}")
        ellps = match.group("datum")  # *REASSIGNMENT*
        proj = match.group("proj").upper()  # *REASSIGNMENT*
        num = match.group("num")
        if num is None:
            zone = None  # *REASSIGNMENT*
        else:
            zone = int(num)  # *REASSIGNMENT*
        south = (match.group("n_or_s").upper() == "S")  # *REASSIGNMENT*

    # Otherwise, ensure that required arguments are specified.
    # Note: PROJ defaults to `south=False` for UTM, but that default is
    # intentionally avoided here in preference of explicitness and
    # because `south=True` will likely be more used in practice.
    elif south is None:
        raise TypeError("Must specify `south` (or `name`).")
    elif proj is None:
        raise TypeError("Must specify `proj` (or `name`).")

    # Default `ellps`, if necessary.
    if ellps is None:
        ellps = "IAU_2015:30100"  # *REASSIGNMENT*

    # Determine projection type and test for consistency.
    proj = proj.upper()  # *REASSIGNMENT*
    match proj:
        case "LPS":
            type_ = _wkt.LpsZone
            if zone is not None:
                raise TypeError(
                    f"If `proj` is {proj!r}, `zone` cannot be specified."
                )
        case "LTM":
            type_ = _wkt.LtmZone
            if zone is None:
                raise TypeError(
                    f"If `proj` is {proj!r}, `zone` must be specified."
                )
        case _:
            raise TypeError(f"`proj` not recognized: {proj!r}")

    # Instantiate and return `CRS`.
    zone_instance = type_(
        number=zone, hemisphere=("S" if south else "N"),
        extended_ltm=extended_ltm, datum_name=ellps.upper()
    )
    crs = CRS.from_wkt(zone_instance.wkt)
    # TODO: Optionally, here, we could assign a `.ltm_zone` (or possibly
    #  a `.lps_zone`) to parallel `pyproj.CRS.utm_zone`.
    return crs

class GRS(metaclass=_caching._MetaMultiton):
    """
    Class for gridded reference systems, analogous to `pyproj.CRS`.
    """

    def __init__(self, ) -> None:
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
