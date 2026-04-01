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
import functools as _functools
import pyproj as _pyproj
import re as _re
import typing as _typing

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
    polar_ltm: bool = False

    def __post_init__(self, name: str | None) -> None:
        # Parse `name`, if specified.
        if name is not None:
            if self._spec_count:
                raise TypeError(
                    "If `name` is specified, all other arguments, except for "
                    "`extended_ltm` and `polar_ltm`, must be `None`"
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
        del self._spec_count  # Force recalculation.

    def _resolve_and_validate(self) -> None:
        # In special, minimal-call case, return immediately.
        if not self._spec_count:
            return

        # Check for required parameters.
        # Note: PROJ defaults to `south=False` for UTM, but that default
        # is intentionally avoided here in preference of explicitness
        # and because `south=True` will likely be more used in practice.
        if self.south is None:
            raise TypeError("Must specify `south` (or `name`).")

        # Apply defaults and standardize.
        if self.ellps is None:
            self.ellps = _wkt.DATUM_NAME
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
        if self.proj == "LPS":
            if self.zone is not None:
                raise TypeError(
                    f"If `proj` is {self.proj!r}, `zone` must be `None`, not: "
                    f"{self.zone!r}"
                )
            if self.polar_ltm:
                raise TypeError(
                    f"If `proj` is {self.proj!r}, `polar_ltm` must be `False`."
                )
        elif self.zone is None:
            raise TypeError(
                f"If `proj` is {self.proj!r}, `zone` must be specified."
            )

    @_functools.cached_property
    def _spec_count(self) -> int:
        spec_vals = (self.proj, self.zone, self.south, self.ellps)
        unspec_count = spec_vals.count(None)
        spec_count = len(spec_vals) - unspec_count
        return spec_count

    # Note: Caching this method ensures that equivalent `_CrsParameters`
    # instances return the same `CRS` instance.
    @_caching._optionally_cache
    def make_crs(self) -> CRS:
        if not self._spec_count:
            return _pyproj.CRS(_wkt.DATUM_NAME)
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
            extended_ltm=self.extended_ltm, polar_ltm=self.polar_ltm,
            datum_name=self.ellps
        )
        crs = CRS.from_wkt(zone_instance.wkt)
        # TODO: Retain? Document? Or `CRS` -> `LunarCrs` and share
        #  convenience attribute generation (from `._short_name`) with
        #  `database.LunarCrsInfo`?
        if self.proj == "LPS":
            crs.lps_hemisphere = hemisphere
            crs.ltm_zone = None
        else:
            crs.lps_hemisphere = None
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

# Note: Only identical calls are cached here. Compare:
# `_CrsParameters.make_crs()`.
@_caching._optionally_cache
def make_lunar_crs(
        name: str | None = None, *,
        proj: str | None = None, zone: int | None = None,
        south: bool | None = None, ellps: str | None = None,
        extended_ltm: bool = False, polar_ltm: bool = False
) -> CRS:
    """
    Return LPS or LTM zone `CRS` using UTM-like `proj.CRS()` arguments.

    As a convenience, `make_lunar_crs()` returns the underlying geographic
    `CRS`. See Examples section below.

    Parameters
    ----------
    name : str, optional
        String name of `crs`. If specified, all remaining arguments, except
        for `extended_ltm` and `polar_ltm`, are interpreted from `name` and
        cannot be independently specified.
    proj : str, optional
        "LTM" or "LPS". If not specified, `proj` is inferred from `zone`.
        That is, `zone=None` implies `proj="LPS"`, otherwise `proj="LTM"`.
    zone : int, optional
        The LTM zone. Should not be specified for LPS.
    south : bool, optional
        Whether `crs` is in the Southern Hemisphere. Must be specified,
        unless `name` is specified or all arguments are defaulted.
    ellps : str, default="IAU_2015:30100"
        The name of the `crs` ellipsoid. Only "IAU_2015:30100" is supported.
    extended_ltm : bool, default=False
        Whether to extend the LTM/LPS boundary to 82 degrees N or S.
    polar_ltm : bool, default=False
        Whether to extend LTM zones to 90 degrees N or S.

    Returns
    -------
    crs : CRS
        The LPS or LTM zone `CRS` instance.

    Raises
    ------
    TypeError
        If CRS is under- or over-specified, or if `proj` is "LPS" but
        `polar_ltm` is `True`.

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
    Finally, as a convenience, a default call returns the underlying
    geographic `CRS`.
    >>> geo_crs = make_lunar_crs()
    >>> geo_crs2 = pyproj.CRS("IAU_2015:30100")
    >>> geo_crs.is_exact_same(geo_crs2)
    True
    >>> geo_crs.is_exact_same(ltm_crs4.geodetic_crs)
    True
    """
    # TODO: Determine whether to align `crs.name` with `name`. Instead,
    #  `crs.name` may be "Moon (2015) - Sphere / Ocentric..."
    params = _CrsParameters(**locals())
    crs = params.make_crs()
    return crs



# endregion
##############################################################################
# region> GRIDDED REFERENCE SYSTEMS
##############################################################################
@_dataclasses.dataclass(frozen=True, kw_only=True)
class GRS:
    """
    Class for gridded reference systems, analogous to `pyproj.CRS`.

    Instances are not especially useful on their own. They are primarily
    intended as inputs to `LunarTransformer.from_srs()`.
    """
    form: _typing.Literal["ACC", "ACC_FULL", "LGRS"]
    domain: _typing.Literal["LPS", "LTM", "BOTH", "INFER"] = "INFER"
    multi_zone: bool = False
    extended_ltm: bool = False
    prefix: str = ""

    @classmethod
    def from_user_input(cls, *args, **kwargs) -> _typing.Self:
        """
        Create a representation of a gridded reference system.

        Parameters
        ----------
        form : {"LGRS", "ACC", "ACC_FULL"}
            The form of the gridded reference. "ACC_FULL" includes the LGRS
            prefix, that is, the first 3-5 characters of an LGRS coordinate
            which identifies the 25-km-grid area.
        domain : {"LPS", "LTM", "BOTH", "INFER"}, default="INFER"
            Whether the GRS supports the LPS or LTM domain, or both. If
            "INFER", `LunarTransformer.transform()` infers "LPS" or "LTM" on
            each call, from the first coordinate.
        multi_zone : bool, default=False
            Whether to support multiple zones, where a zone is an LTM zone or
            an LPS-LGRS zone, which spans half of either pole. If `False`, on
            each call of `LunarTransformer.transform()`, the single zone used is
            determined by the first coordinate.
        extended_ltm : bool, default=False
            Whether to extend the LTM/LPS boundary to 82 degrees N and S.
        prefix : str, default=""
            Any number of characters that are guaranteed to start each
            coordinate. For example, for `form="LGRS"`, `prefix="S"` would
            constrain coordinates to the Southern Hemisphere. For `form="ACC"`,
            `prefix` is required and must identify the 25-km-grid area, which is
            the first 3-5 characters of an LGRS coordinate.

        Returns
        -------
        transformer : LunarTransformer
            A new transformer, with the useful `.transform()` method.
        """
        # TODO: Revisit and finalize these arguments. (The current
        #  arguments and docs above are initial ideas only. These will
        #  likely change and some may be moved to `LunarTransformer`.)
        return cls(*args, **kwargs)


# endregion
