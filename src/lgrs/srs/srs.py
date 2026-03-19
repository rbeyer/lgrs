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
import dataclasses as _dataclasses
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
    "((?P<proj>LPS|LTM) )?"  # "LPS" or "LTM" is optional.
    "(zone )?"  # "zone" is optional.
    "(?P<num>[0-9]+)?"  # Zone number.
    "(?P<n_or_s>[NS])"  # "N" or "S" hemisphere.
    "$"  # Match to end.
)

# Note: Parsing of arguments to `make_lunar_crs()` is delegated to this
# class to improve code organization and caching of equivalent calls.
@_dataclasses.dataclass(kw_only=True, unsafe_hash=True)
class _CrsParameters:
    name: _dataclasses.InitVar[str | None] = None
    proj: str | None = None
    zone: int | None = None
    south: bool | None = None
    ellps: str | None = None
    extended_ltm: bool = False

    def __post_init__(self, name: str | None) -> None:
        # Parse `name`, if specified.
        if name is not None:
            if (self.proj, self.zone, self.south, self.ellps).count(None) != 4:
                raise TypeError(
                    "If `name` is specified, all other arguments "
                    "except for `extended_ltm` must be `None`"
                )
            self._parse_name(name)

        # Resolve and validate compatibility for all arguments.
        self._resolve_and_validate()

    def _parse_name(self, name: str) -> None:
        match = _crs_name_pattern.search(name)
        if match is None:
            raise TypeError(f"`name` is not in a recognized form: {name!r}")
        self.ellps = match.group("datum")
        self.proj = match.group("proj")
        num = match.group("num")
        if num is None:
            self.zone = None
        else:
            self.zone = int(num)
        self.south = (match.group("n_or_s").upper() == "S")

    def _resolve_and_validate(self) -> None:
        # Check for required parameters.
        # Note: PROJ defaults to `south=False` for UTM, but that default
        # is intentionally avoided here in preference of explicitness
        # and because `south=True` will likely be more used in practice.
        if self.south is None:
            raise TypeError("Must specify `south` (or `name`).")

        # Apply defaults and standardize.
        if self.ellps is None:
            self.ellps = "IAU_2015:30100"
        else:
            self.ellps = self.ellps.upper()
        if self.proj is None:
            if self.zone is None:
                self.proj = "LPS"
            else:
                self.proj = "LTM"
        else:
            self.proj = self.proj.upper()

        # Check compatibility.
        if self.proj == "LPS" and self.zone is not None:
            raise TypeError(
                f"If `proj` is {self.proj!r}, `zone` must be `None`, not: "
                f"{self.zone!r}"
            )
        elif self.proj == "LTM" and self.zone is None:
            raise TypeError(
                f"If `proj` is {self.proj!r}, `zone` must be specified."
            )

    # Note: Caching this method ensures that equivalent `_CrsParameters`
    # instances return the same `CRS` instance.
    @_caching._optionally_cache
    def make_crs(self) -> CRS:
        match self.proj:
            case "LPS":
                type_ = _wkt.LpsZone
            case "LTM":
                type_ = _wkt.LtmZone
            case _:
                raise TypeError(f"`proj` not recognized: {self.proj!r}")
        hemisphere = ("S" if self.south else "N")
        zone_instance = type_(
            number=self.zone, hemisphere=hemisphere,
            extended_ltm=self.extended_ltm, datum_name=self.ellps
        )
        crs = CRS.from_wkt(zone_instance.wkt)
        # TODO: Retain? Document?
        if self.proj == "LPS":
            crs.lps_hemisphere = hemisphere
        else:
            # Note: Parallels `CRS.utm_zone`.
            crs.ltm_zone = f"{self.zone}{hemisphere}"
        return crs

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

# Note: Only identical calls are cached here. Compare:
# `_CrsParameters.make_crs()`.
@_caching._optionally_cache
def make_lunar_crs(
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
        String name of `crs`. If specified, all remaining arguments, except
        for `extended_ltm`, are interpreted from `name` and cannot be
        independently specified.
    proj : str, optional
        "LTM" or "LPS". If not specified, `proj` is inferred from `zone`.
        That is, `zone=None` implies `proj="LPS"`, otherwise `proj="LTM"`.
    zone : int, optional
        The LTM zone. Should not be specified for LPS.
    south : bool, optional
        Whether `crs` is in the Southern Hemisphere. Must be specified,
        unless `name` is specified.
    ellps : str, default="IAU_2015:30100"
        The name of the `crs` ellipsoid. Only "IAU_2015:30100" is supported.
    extended_ltm : bool, default=False
        Whether to use the extended LTM range of 80-82 degrees.

    Returns
    -------
    crs : CRS
        The LPS or LTM zone `CRS` instance.

    Examples
    --------
    >>> import pyproj
    >>> utm_crs = pyproj.CRS("WGS84 / UTM zone 23N")
    >>> ltm_crs = make_lunar_crs("IAU_2015:30100 / LTM zone 23N")
    >>> utm_crs2 = CRS(proj="utm", zone=23, south=False, ellps="WGS84")
    >>> ltm_crs2 = make_lunar_crs(
    ...    proj="ltm", zone=23, south=False, ellps="IAU_2015:30100"
    ...    )
    As a convenience, LPS is also supported.
    >>> lps_crs = make_lunar_crs("IAU_2015:30100 / LPS S")
    >>> lps_crs2 = make_lunar_crs(
    ...    proj="lps", south=True, ellps="IAU_2015:30100"
    ...    )
    As a further convenience, `ellps` defaults to "IAU_2015:30100" and,
    as with `pyproj.CRS` UTM support, the word "zone" is optional.
    >>> lps_crs3 = make_lunar_crs("LPS S")
    >>> ltm_crs3 = make_lunar_crs("LTM 23N")
    Additionally, `proj` will be inferred if not specified.
    >>> lps_crs4 = make_lunar_crs("S")
    >>> ltm_crs4 = make_lunar_crs("23N")
    >>> lps_crs4.is_exact_same(lps_crs)
    >>> ltm_crs4.is_exact_same(lps_crs)
    """
    # TODO: Determine whether to align `crs.name` with `name`. Instead,
    #  `crs.name` may be "Moon (2015) - Sphere / Ocentric..."
    params = _CrsParameters(**locals())
    crs = params.make_crs()
    return crs



# endregion