"""Support for spatial reference systems: coordinate-point and gridded."""

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
# External.
from __future__ import annotations

import dataclasses as _dataclasses
import functools as _functools
import re as _re
import typing as _typing
import warnings as _warnings

import numpy as _numpy
import pyproj as _pyproj

# Internal.
import lgrs.caching as _caching
import lgrs.srs.wkt as _wkt
import lgrs.util as _util


# endregion
###############################################################################
# region> UTILITIES
###############################################################################
@_caching._optionally_cache
def get_transformer(
    crs_from: _pyproj.CRS, crs_to: _pyproj.CRS, always_xy: bool, **kwargs
) -> _pyproj.Transformer:
    transformer = _pyproj.Transformer.from_crs(
        crs_from, crs_to, always_xy=always_xy, **kwargs
    )
    exact = _ExactSphericalTmTransformer.wrap(
        transformer, crs_from, crs_to, always_xy
    )
    return transformer if exact is None else exact


def _sincosd(degrees: _typing.Any) -> tuple[_typing.Any, _typing.Any]:
    """Return (sin, cos) of angles in degrees, exact at multiples of 90.

    The angle is reduced to [-45, 45] degrees by whole quarter turns before
    converting to radians, so sin(180) is exactly 0 rather than ~1.2e-16.
    """
    x = _numpy.fmod(_numpy.asarray(degrees, dtype=float), 360.0)
    q = _numpy.round(x / 90.0)
    r = _numpy.radians(x - 90.0 * q)
    s, c = _numpy.sin(r), _numpy.cos(r)
    q = _numpy.mod(q, 4)
    sin = _numpy.select([q == 0, q == 1, q == 2], [s, c, -s], -c)
    cos = _numpy.select([q == 0, q == 1, q == 2], [c, -s, -c], s)
    return sin + 0.0, cos + 0.0  # + 0.0 turns -0.0 into 0.0


class _ExactSphericalTmTransformer:
    """Closed-form LTM and LPS projections on a sphere.

    PROJ's spherical ``tmerc`` computes the northing through ``acos()``,
    which loses up to ~3 cm within ~1e-6 degrees of the equator, and its
    spherical polar ``stere`` inverse loses up to a few millimetres within
    a few centimetres of the pole. These closed forms are exact to
    floating-point precision. Only ``transform()`` between a geographic CRS
    and a spherical ``tmerc`` (LTM) or polar ``stere`` (LPS) CRS is
    replaced; every other attribute (e.g., ``transform_bounds()``) is
    delegated to the wrapped pyproj transformer.
    """

    def __init__(
        self,
        transformer: _pyproj.Transformer,
        *,
        forward: bool,
        polar: int,
        geo_lon_first: bool,
        radius: float,
        k0: float,
        lon0: float,
        x0: float,
        y0: float,
    ) -> None:
        self._transformer = transformer
        self._forward = forward  # geographic -> projected
        self._polar = polar  # 0: tmerc; +1 / -1: north / south polar stere
        self._geo_lon_first = geo_lon_first
        self._k0r = k0 * radius
        self._lon0_deg = lon0
        self._lon0 = _numpy.radians(lon0)
        self._x0 = x0
        self._y0 = y0

    @classmethod
    def wrap(
        cls,
        transformer: _pyproj.Transformer,
        crs_from: _pyproj.CRS,
        crs_to: _pyproj.CRS,
        always_xy: bool,
    ) -> _ExactSphericalTmTransformer | None:
        crs_from = _pyproj.CRS(crs_from)
        crs_to = _pyproj.CRS(crs_to)
        if crs_from.is_geographic and crs_to.is_projected:
            geo, proj, forward = crs_from, crs_to, True
        elif crs_from.is_projected and crs_to.is_geographic:
            geo, proj, forward = crs_to, crs_from, False
        else:
            return None
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            params = proj.to_dict()
        ellipsoid = proj.ellipsoid
        if params.get("proj") == "tmerc" and params.get("lat_0", 0) == 0:
            polar = 0
        elif params.get("proj") == "stere" and params.get("lat_0") in (
            90,
            -90,
        ):
            polar = 1 if params["lat_0"] == 90 else -1
        else:
            return None
        if (
            ellipsoid is None
            or ellipsoid.semi_major_metre != ellipsoid.semi_minor_metre
            or proj.geodetic_crs != geo
            or (
                [a.direction for a in proj.axis_info] != ["east", "north"]
                and not (
                    polar and [a.abbrev for a in proj.axis_info] == ["X", "Y"]
                )
            )
        ):
            return None
        if always_xy:
            geo_lon_first = True
        else:
            directions = [a.direction for a in geo.axis_info][:2]
            if directions == ["north", "east"]:
                geo_lon_first = False
            elif directions == ["east", "north"]:
                geo_lon_first = True
            else:
                return None
        return cls(
            transformer,
            forward=forward,
            polar=polar,
            geo_lon_first=geo_lon_first,
            radius=ellipsoid.semi_major_metre,
            k0=float(params.get("k", params.get("k_0", 1))),
            lon0=float(params.get("lon_0", 0)),
            x0=float(params.get("x_0", 0)),
            y0=float(params.get("y_0", 0)),
        )

    def __getattr__(self, name: str) -> _typing.Any:
        return getattr(self._transformer, name)

    def transform(
        self, xx: _typing.Any, yy: _typing.Any, *args, **kwargs
    ) -> tuple[_typing.Any, _typing.Any]:
        if args or kwargs:
            return self._transformer.transform(xx, yy, *args, **kwargs)
        scalar = _numpy.isscalar(xx) and _numpy.isscalar(yy)
        a = _numpy.asarray(xx, dtype=float)
        b = _numpy.asarray(yy, dtype=float)
        with _numpy.errstate(divide="ignore", invalid="ignore"):
            if self._polar:
                out1, out2 = self._polar_stere(a, b)
            elif self._forward:
                lon, lat = (a, b) if self._geo_lon_first else (b, a)
                sin_phi, cos_phi = _sincosd(lat)
                sin_dlam, cos_dlam = _sincosd(lon - self._lon0_deg)
                u = cos_phi * cos_dlam
                x = self._k0r * _numpy.arcsinh(
                    cos_phi * sin_dlam / _numpy.hypot(sin_phi, u)
                )
                y = self._k0r * _numpy.arctan2(sin_phi, u)
                out1, out2 = x + self._x0, y + self._y0
            else:
                xs = (a - self._x0) / self._k0r
                d = (b - self._y0) / self._k0r
                sinh_x = _numpy.sinh(xs)
                cos_d = _numpy.cos(d)
                lat = _numpy.degrees(
                    _numpy.arctan2(_numpy.sin(d), _numpy.hypot(sinh_x, cos_d))
                )
                lon = _numpy.degrees(
                    self._lon0 + _numpy.arctan2(sinh_x, cos_d)
                )
                lon = _numpy.where(lon >= 180, lon - 360, lon)
                lon = _numpy.where(lon < -180, lon + 360, lon)
                out1, out2 = (lon, lat) if self._geo_lon_first else (lat, lon)
        if scalar:
            return float(out1), float(out2)
        return out1, out2

    def _polar_stere(self, a, b):  # type: ignore[no-untyped-def]
        s = self._polar
        two_k0r = 2 * self._k0r
        if self._forward:
            lon, lat = (a, b) if self._geo_lon_first else (b, a)
            sin_h, cos_h = _sincosd(45.0 - s * lat / 2.0)
            rho = two_k0r * sin_h / cos_h
            sin_dlam, cos_dlam = _sincosd(lon - self._lon0_deg)
            return (
                self._x0 + rho * sin_dlam,
                self._y0 - s * rho * cos_dlam,
            )
        dx = a - self._x0
        dy = b - self._y0
        rho = _numpy.hypot(dx, dy)
        lat = s * (90 - _numpy.degrees(2 * _numpy.arctan(rho / two_k0r)))
        dlam = _numpy.where(rho == 0, 0.0, _numpy.arctan2(dx, -s * dy))
        lon = _numpy.degrees(self._lon0 + dlam)
        lon = _numpy.where(lon >= 180, lon - 360, lon)
        lon = _numpy.where(lon < -180, lon + 360, lon)
        return (lon, lat) if self._geo_lon_first else (lat, lon)


# endregion
###############################################################################
# region> COORDINATE REFERENCE SYSTEMS
###############################################################################
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
    global_lps: bool = False
    global_ltm: bool = False

    def __post_init__(self, name: str | None) -> None:
        # Parse `name`, if specified.
        if name is not None:
            if self._spec_count:
                raise ValueError(
                    "If `name` is specified, all other arguments, except for "
                    "`extended_ltm`, `global_lps`, and `global_ltm`, must be "
                    "`None`"
                )
            self._parse_name(name)

        # Resolve and validate compatibility for all arguments.
        self._resolve_and_validate()

    def _parse_name(self, name: str) -> None:
        match = _crs_name_pattern.search(name)
        if match is None:
            raise ValueError(f"`name` is not in a recognized form: {name!r}")
        self.ellps = match.group("datum")
        self.proj = match.group("proj")
        num = match.group("num")
        if num is None:
            self.zone = None
        else:
            self.zone = int(num)
        self.south = match.group("n_or_s").upper() == "S"
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
                raise ValueError(
                    f"If `proj` is {self.proj!r}, `zone` must be `None`, not: "
                    f"{self.zone!r}"
                )
            if self.global_ltm:
                raise ValueError(
                    f"If `proj` is {self.proj!r}, "
                    "`global_ltm` must be `False`."
                )
        else:
            if self.zone is None:
                raise TypeError(
                    f"If `proj` is {self.proj!r}, `zone` must be specified."
                )
            if self.global_lps:
                raise ValueError(
                    f"If `proj` is {self.proj!r}, "
                    "`global_lps` must be `False`."
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
            return CRS(_wkt.DATUM_NAME)
        wkt = self.make_wkt()
        crs = CRS(wkt)
        return crs

    # Note: Caching this method ensures that equivalent `_CrsParameters`
    # instances return the same WKT string instance.
    @_caching._optionally_cache
    def make_wkt(self) -> str:
        if not self._spec_count:
            crs = self.make_crs()
            return crs.to_wkt(pretty=True)
        match self.proj:
            case "LPS":
                type_ = _wkt.LpsZone
            case "LTM":
                type_ = _wkt.LtmZone
            case _:
                raise ValueError(f"`proj` not recognized: {self.proj!r}")
        hemisphere = "S" if self.south else "N"
        zone_instance = type_(
            number=self.zone,
            hemisphere=hemisphere,
            extended_ltm=self.extended_ltm,
            global_lps=self.global_lps,
            global_ltm=self.global_ltm,
            datum_name=self.ellps,
        )
        return zone_instance.wkt


class CRS(_pyproj.CRS, metaclass=_caching._MetaMultiton):
    """
    Equivalent to `pyproj.CRS` with caching support.

    Notes
    -----
    `.srs`, inherited from `pyproj.CRS`, holds the input that created
    the CRS, exactly as given. For an LPS or LTM CRS from
    `make_lunar_crs()`, that input is the WKT from `make_lunar_wkt()`,
    which is the WKT that `lgrs` defines for the CRS. `.to_wkt()`
    instead returns `pyproj`'s rendering of the CRS, which can differ
    from `.srs` in layout or content.

    Examples
    --------
    >>> from lgrs import CRS
    >>> crs_utm = CRS.from_user_input(32615)
    >>> crs_utm2 = CRS.from_user_input(32615)
    >>> crs_utm2 is crs_utm
    True

    However, equivalent arguments are not guaranteed to cache identically.

    >>> crs_utm3 = CRS("WGS 84 / UTM zone 15N")
    >>> crs_utm3.is_exact_same(crs_utm)
    True
    >>> crs_utm3 is crs_utm
    False

    For an LPS or LTM CRS, `.srs` is the WKT that `lgrs` defines, while
    `.to_wkt()` differs from it.

    >>> from lgrs import make_lunar_crs, make_lunar_wkt
    >>> crs_ltm = make_lunar_crs("LTM 23N")
    >>> crs_ltm.srs == make_lunar_wkt("LTM 23N")
    True
    >>> crs_ltm.to_wkt() == crs_ltm.srs
    False
    """

    # Note: Hashing a `pyproj.CRS` exports it as WKT on every call, so
    # where a `CRS` is hashed repeatedly (as when it keys a cache),
    # caching the hash can significantly improve performance. Caching
    # is valid because a `CRS` is not modified after creation.
    def __hash__(self) -> int:
        return self._hash

    def _extract(self, regex: _re.Pattern) -> str | None:
        if self.coordinate_operation is None:
            return None
        match = regex.search(self.coordinate_operation.name)
        if match is None:
            return None
        return match.group(1)

    @_functools.cached_property
    def _hash(self) -> int:
        return super().__hash__()

    @_functools.cached_property
    def lps_hemisphere(self) -> _typing.Literal["N", "S", None]:
        return self._extract(_wkt._lps_regex)

    @_functools.cached_property
    def ltm_zone(self) -> str | None:
        return self._extract(_wkt._ltm_regex)


# Note: Only identical calls are cached here. Compare:
# `_CrsParameters.make_crs()`.
@_caching._optionally_cache
def make_lunar_crs(
    name: str | None = None,
    *,
    proj: str | None = None,
    zone: int | None = None,
    south: bool | None = None,
    ellps: str | None = None,
    extended_ltm: bool = False,
    global_lps: bool = False,
    global_ltm: bool = False,
) -> CRS:
    """
    Return LPS or LTM zone `CRS` using UTM-like `pyproj.CRS()` arguments.

    As a convenience, `make_lunar_crs()` returns the underlying geographic
    `CRS`. See Examples section below.

    Parameters
    ----------
    name : str, optional
        String name of CRS. If specified, all remaining arguments, except
        for `extended_ltm`, `global_lps`, and `global_ltm`, are interpreted
        from `name` and cannot be independently specified.
    proj : str, optional
        "LTM" or "LPS". If not specified, `proj` is inferred from `zone`.
        That is, `zone=None` implies `proj="LPS"`, otherwise `proj="LTM"`.
    zone : int, optional
        The LTM zone. Should not be specified for LPS.
    south : bool, optional
        Whether CRS is in the Southern Hemisphere. Must be specified,
        unless `name` is specified or all arguments are defaulted.
    ellps : str, default="IAU_2015:30100"
        The name of the CRS ellipsoid. Only "IAU_2015:30100" is supported.
    extended_ltm : bool, default=False
        Whether to use the extended LTM region. If `True`, the nominal
        poleward extent of the LTM region is 82° N/S instead of 80° N/S.
    global_lps : bool, default=False
        Whether to extend the LPS region globally. If `True`, there is no
        LTM region.
    global_ltm : bool, default=False
        Whether to extend the LTM region globally. If `True`, there is no
        LPS region.

    Returns
    -------
    crs : CRS
        The LPS/LTM zone or geographic `CRS` instance.

    Raises
    ------
    TypeError
        If a required argument is missing: `south`, when `name` is not
        specified, or `zone`, when `proj` is `"LTM"`.
    ValueError
        If CRS cannot be interpreted, or if `proj` is `"LPS"`/`"LTM"`
        but `global_ltm`/`global_lps` is `True`.

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
    True
    >>> ltm_crs4.is_exact_same(lps_crs)
    False

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


# Note: Only identical calls are cached here. Compare:
# `_CrsParameters.make_crs()`.
@_caching._optionally_cache
@_util.partially_wraps(make_lunar_crs, exclude=(1, "Raises"))
def make_lunar_wkt(name: str | None = None, **kwargs) -> str:
    """
    Return LPS or LTM zone WKT using UTM-like `pyproj.CRS()` arguments.

    Returns
    -------
    wkt : str
        The LPS/LTM zone or geographic WKT.

    Raises
    ------
    TypeError
        If a required argument is missing: `south`, when `name` is not
        specified, or `zone`, when `proj` is `"LTM"`.
    ValueError
        If WKT cannot be interpreted, or if `proj` is `"LPS"`/`"LTM"`
        but `global_ltm`/`global_lps` is `True`.
    """
    params = _CrsParameters(name=name, **kwargs)
    wkt = params.make_wkt()
    return wkt


# endregion
###############################################################################
# region> GRIDDED REFERENCE SYSTEMS
###############################################################################
@_dataclasses.dataclass(frozen=True, kw_only=True)
class GRS:
    """
    Class for gridded reference systems, analogous to `pyproj.CRS`.

    Instances are not especially useful on their own. They are primarily
    intended as inputs to `LunarTransformer.from_srs()`.
    """

    form: _typing.Literal["ACC", "ACC_FULL", "LGRS"]
    digits: int | None = None
    multi_zone: bool = False
    domain: _typing.Literal["LPS", "LTM", "BOTH", "INFER"] = "INFER"
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
        digits : int, optional
            The number of digits in each northing and easting. If not
            specified, instance supports all possible digit counts.
                `digits`    precision
                --------    ---------
                0           25 km
                2           1 km
                3           100 m
                4           10 m
                5           1 m
        multi_zone : bool, default=False
            Whether to support multiple zones, where a zone is an LTM zone or
            an LPS-LGRS zone, which spans half of either pole. If `False`, on
            each call of `LunarTransformer.transform()`, the single zone used
            is determined by the first coordinate.
        domain : {"LPS", "LTM", "BOTH", "INFER"}, default="INFER"
            Whether the GRS supports the LPS or LTM domain, or both. If
            "INFER", `LunarTransformer.transform()` infers "LPS" or "LTM" on
            each call, from the first coordinate.
        extended_ltm : bool, default=False
            Whether to extend the LTM/LPS boundary to 82 degrees N and S.
        prefix : str, default=""
            Any number of characters that are guaranteed to start each
            coordinate. For example, for `form="LGRS"`, `prefix="S"` would
            constrain coordinates to the Southern Hemisphere. For `form="ACC"`,
            `prefix` is required and must identify the 25-km-grid area, which
            is the first 3-5 characters of an LGRS coordinate.

        Returns
        -------
        transformer : LunarTransformer
            A new transformer, with the useful `.transform()` method.
        """
        # TODO: Revisit and finalize these arguments. (The current
        #  arguments and docs above are initial ideas only. These will
        #  likely change and some may be moved to `LunarTransformer`.)
        # TODO: Decide whether all arguments should default to the most
        #  general, even when such generality is unlikely to be used and
        #  has performance cost. (For example, default `multi_zone` to
        #  `True` and `domain` to `"BOTH"`?)
        return cls(*args, **kwargs)


# endregion
