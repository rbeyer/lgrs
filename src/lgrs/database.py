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
import collections as _collections
import functools as _functools
import itertools as _itertools
import numpy as _np
import re as _re
import pyproj as _pyproj
from pyproj import database as _pyproj_database
from pyproj import aoi as _pyproj_aoi
import typing as _typing

# Internal.
import lgrs.caching as _caching
import lgrs.srs.srs as _srs
import lgrs.srs.wkt as _wkt



# endregion
##############################################################################
# region> UTILITIES
##############################################################################
type _FloatIterable = _collections.abc.Iterable[float]

_lunar_crs_short_name_pattern = _re.compile(
    "^(?P<num>[0-9]{2})?(?P<hemi>[NS])(?P<suffix>[*]*)$"
)

class _ShortNameParsed(_typing.NamedTuple):
    zone_number: int | None
    hemisphere: str
    suffix: str

def _conform_latitudes(latitudes: _FloatIterable) -> list[float]:
    conformed = []
    for lat in latitudes:
        if abs(lat) > 90:
            raise TypeError("`latitude` must be in [-90, 90] interval")
        conformed.append(lat)
    return conformed

def _conform_longitudes(longitudes: _FloatIterable) -> list[float]:
    conformed = []
    for lon in longitudes:
        # TODO: Decide acceptable input range.
        if abs(lon) > 360:
            raise TypeError("`longitude` must be in [-360, 360] interval")
        # Note: Conformity to [-180, 180) interval required by Eq. 13 of
        # M2025 and by WKT.
        lon %= 360  # Conforms to [0, 360) interval.
        if lon >= 180:
            lon -= 360  # Conforms to [-180, 180) interval.
        conformed.append(lon)
    return conformed

def _ensure_float_iterable(
        obj: float | _FloatIterable, *, convert_np: bool = True
) -> tuple[bool, _FloatIterable]:
    if isinstance(obj, float | int):
        if convert_np and isinstance(obj, _np.number):
            converted = float(obj)
            return (True, (converted,))
        else:
            return (True, (obj,))
    else:
        if convert_np and isinstance(obj, _np.ndarray):
            converted = obj.tolist()  # *REASSIGNMENT*
            return (False, converted)
        else:
            return (False, obj)

@_functools.cache
def _get_all_lunar_crs_short_names(
        *, lps: bool = True, ltm: bool = True,
        extended_ltm: bool = False, polar_ltm: bool = False,
        prefer_ltm: bool = False, prefer_west_ltm: bool = False,
        south: bool | None = None
) -> tuple[str, ...]:
    # Note: `prefer_*` included for call signature compatibility with
    # `_get_lunar_crs_short_names()` but are intentionally unused.
    if polar_ltm:
        suffix = "**"
    elif extended_ltm:
        suffix = "*"
    else:
        suffix = ""
    if ltm and lps:
        lps_tuple = _get_all_lunar_crs_short_names(
            ltm=False, extended_ltm=extended_ltm, polar_ltm=polar_ltm,
            south=south
        )
        ltm_tuple = _get_all_lunar_crs_short_names(
            lps=False, extended_ltm=extended_ltm, polar_ltm=polar_ltm,
            south=south
        )
        complete = lps_tuple + ltm_tuple
        return complete
    elif lps:
        if polar_ltm:
            lps_tuple = ()
        else:
            lps_tuple = (f"N{suffix}", f"S{suffix}")
        return lps_tuple
    else:
        north_iter = (f"{i:02}N{suffix}" for i in range(1, 46))
        south_iter = (f"{i:02}S{suffix}" for i in range(1, 46))
        if south is None:
            final_iter = _itertools.chain(north_iter, south_iter)
        elif south:
            final_iter = south_iter
        else:
            final_iter = north_iter
        ltm_tuple = tuple(final_iter)
        return ltm_tuple

def _get_lunar_crs_short_names(
        *, conformed_latitudes: _FloatIterable,
        conformed_longitudes: _FloatIterable,
        extended_ltm: bool = False, polar_ltm: bool = False,
        prefer_ltm: bool = False, prefer_south_ltm: bool = False,
        prefer_west_ltm: bool = False
) -> list[str]:
    # Determine LTM vs. LPS condition.
    if polar_ltm:
        is_in_ltm = lambda test_lat: True
    else:
        if extended_ltm:
            ltm_max_abs_lat = _wkt.LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            ltm_max_abs_lat = _wkt.LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE
        if prefer_ltm:
            is_in_ltm = lambda test_lat: abs(test_lat) <= ltm_max_abs_lat
        else:
            is_in_ltm = lambda test_lat: abs(test_lat) < ltm_max_abs_lat

    # Evaluate each lat-lon pair.
    lunar_crs_short_names = []
    for lat, lon in zip(conformed_latitudes, conformed_longitudes):
        if prefer_south_ltm:
            hemi = ("N" if lat > 0 else "S")
        else:
            # Note: This inequality is from M2025 code.
            hemi = ("N" if lat >= 0 else "S")
        if is_in_ltm(lat):
            # Below: Eq. 13 of M2025. Zones are 1-indexed.
            zone_float = ((lon + 180) / (2 * _wkt.LTM_ZONE_HALF_WIDTH)) + 1
            zone_int = int(zone_float)
            if prefer_west_ltm and zone_float.is_integer():
                if zone_int == 1:
                    zone_int = 45  # *REASSIGNMENT*
                else:
                    zone_int -= 1  # *REASSIGNMENT*
            short_name = f"{zone_int:02}{hemi}"
        else:
            short_name = hemi
        if polar_ltm:
            short_name += "**"  # *REASSIGNMENT*
        elif extended_ltm:
            short_name += "*"  # *REASSIGNMENT*
        lunar_crs_short_names.append(short_name)
    return lunar_crs_short_names

def _grid_sample(
        *, latitudes: tuple[float, float], longitudes: tuple[float, float],
        lat_sample: int | float, lon_sample: int | float,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    # Support wraparound for longitude but not latitude.
    lat1, lat2 = latitudes
    if lat2 < lat1:
        # Note: Similarly, attempting to pass a
        # `pyproj.aoi.AreaOfInterest` with `south_lat_degree` >
        # `north_lat_degree` to `pyproj.database.query_utm_crs_info()`
        # fails.
        raise TypeError("`latitudes` must be specified in ascending order")
    lon1, lon2 = longitudes
    if lon2 < lon1:
        # Note: From inspection, passing a `pyproj.aoi.AreaOfInterest`
        # with `east_lon_degree` > `west_lon_degree` had variable
        # effect that depended, at least in part, on how the area of use
        # of each CRS is defined.
        lon2 += 360  # *REASSIGNMENT*
    if (lon2 - lon1) > 360:
        raise TypeError("`longitudes` cannot span > 360°")

    # Sample in each dimension.
    samp_coords = []
    for sample, max_bound, sample_hint in (
            (lat1, lat2, lat_sample), (lon1, lon2, lon_sample)
    ):
        samples = []
        if isinstance(sample_hint, float):
            incr = sample_hint
            while sample < max_bound:
                samples.append(sample)
                sample += incr
        else:
            count = sample_hint
            span = (max_bound - sample)
            incr = span / (count - 1)
            for _ in range(count - 1):
                samples.append(sample)
                sample += incr
        samples.append(max_bound)
        samp_coords.append(samples)

    # Construct and return iterable.
    result = tuple(zip(*_itertools.product(*samp_coords)))
    return result

def _parse_lunar_crs_short_name(short_name: str) -> _ShortNameParsed:
    match = _lunar_crs_short_name_pattern.search(short_name)
    if match is None:
        raise TypeError(
            f"`short_name` is not in supported format: {short_name!r}"
        )
    num_str = match.group("num")
    if num_str is None:
        zone_num = None
    else:
        zone_num = int(num_str)
    hemi = match.group("hemi")
    suffix = match.group("suffix")
    return _ShortNameParsed(zone_num, hemi, suffix)



# endregion
##############################################################################
# region> INFO CLASS
##############################################################################
class LunarCrsInfo(_pyproj_database.CRSInfo):
    """
    Subclass of `pyproj_database.CRSInfo`.

    Attributes
    ----------
    is_lps : bool
        Whether CRS is LPS.
    is_ltm : bool
        Whether CRS is LTM.
    hemisphere: str
        "N" or "S".
    ltm_zone : str | None
        The LTM zone (e.g., "23N"), or `None` if `.is_lps`.
    lps_hemisphere : str | None
        The LPS hemisphere ("N" or "S"), or `None` if `.is_ltm`.
    ltm_limit : float
        The magnitude of the LTM/LPS boundary: 80, 82, or 90 degrees.

    Methods
    -------
    get_crs()
        Get the corresponding `pyproj.CRS` instance.
    sorter()
        Convenient sorter for `LunarCrsInfo` instances.

    See Also
    --------
    pyproj_database.CRSInfo : Parent class, with additional documentation.
    """
    #* Basic behavior. ------------------------------------------------
    # Below: Assigned by `._from_short_name()`. All instances should be
    # created by that factory function.
    _short_name: str
    _short_name_parsed: _ShortNameParsed

    @_functools.cached_property
    def _sort_tuple(self) -> tuple[int, int, int | None, str]:
        # Note: Sort like N, N*, S, S*, 1N, 1N*, 1N**, 2N, ... 1S.
        tup = (
            0 if self.is_lps else 1,
            0 if self.hemisphere == "N" else 1,
            self.ltm_zone,
            self.ltm_limit
        )
        return tup

    #* Instantiation. -------------------------------------------------
    @classmethod
    @_caching._optionally_cache
    def _from_short_name(cls, short_name: str) -> _typing.Self:
        # Parse `short_name`.
        short_name_parsed = _parse_lunar_crs_short_name(short_name)
        zone_num, hemi, suffix = short_name_parsed

        # Precompute latitudinal bounds.
        if hemi == "N":
            sign = 1.
        else:
            sign = -1.
        match suffix:
            case "":
                trans_lat = sign * _wkt.LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE
            case "*":
                trans_lat = sign * _wkt.LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
            case "**":
                trans_lat = sign * 90
            case _:
                raise TypeError(f"`suffix` is not recognized: {suffix!r}")

        # Build `LunarCrsInfo` instsance.
        if zone_num is None:
            area_name = f"LPS {'South' if hemi == "S" else 'North'}"
            area_of_use = _pyproj_aoi.AreaOfUse(
                west=-180.,
                south=-90. if hemi == "S" else trans_lat,
                east=180.,
                north=90. if hemi == "N" else trans_lat,
                name=f"Moon - {area_name}"
            )
            # TODO: LPS has a suffix specifying the variant. Should we
            #  suffix with the central scale factor, as done?
            proj_method_name = (
                "Polar Stereographic (central scale factor "
                f"{_wkt.LTM_CENTRAL_SCALE_FACTOR})"
            )
        else:
            # TODO: Decide if names should encode same info as `suffix`.
            area_name = f"LTM zone {zone_num}{hemi}"
            west_lon = zone_num * (2 * _wkt.LTM_ZONE_HALF_WIDTH) - 188.
            area_of_use = _pyproj_aoi.AreaOfUse(
                west=west_lon,
                south=trans_lat if hemi == "S" else 0.,
                east=west_lon + (2 * _wkt.LTM_ZONE_HALF_WIDTH),
                north=trans_lat if hemi == "N" else 0.,
                name=f"Moon - {area_name}"
            )
            proj_method_name = "Transverse Mercator"
        auth_name = ""
        code = ""
        name = f"{_wkt.DATUM_NAME} / {area_name}"
        deprecated = False
        type_ = _pyproj_database.PJType.PROJECTED_CRS
        info = LunarCrsInfo(
            auth_name=auth_name, code=code, name=name, type=type_,
            deprecated=deprecated, area_of_use=area_of_use,
            projection_method_name=proj_method_name
        )

        # Attach useful attributes and return.
        info._short_name = short_name
        info._short_name_parsed = short_name_parsed
        return info

    #* Public data attributes. ----------------------------------------
    @_functools.cached_property
    def hemisphere(self) -> str:
        return self._short_name_parsed.hemisphere

    @_functools.cached_property
    def is_lps(self) -> bool:
        return (self._short_name_parsed.zone_number is None)

    @_functools.cached_property
    def is_ltm(self) -> bool:
        return (not self.is_lps)

    @_functools.cached_property
    def lps_hemisphere(self) -> str | None:
        if self.is_lps:
            return self.hemisphere
        else:
            return None

    @_functools.cached_property
    def ltm_limit(self) -> float:
        suffix = self._short_name_parsed.suffix
        match suffix:
            case "":
                limit = _wkt.LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE
            case "*":
                limit = _wkt.LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
            case "**":
                limit = 90.
            case _:
                raise TypeError(f"`suffix` is not recognized: {suffix!r}")
        return limit

    @_functools.cached_property
    def ltm_zone(self) -> str | None:
        return self._short_name_parsed.zone_number

    #* Public methods. ------------------------------------------------
    # Note: Added because instantiating a `pyproj.CRS` from a
    # `pyproj.CRSInfo` relies on `pyproj.CRS.from_authority()`, which we
    # cannot independently support.
    def get_crs(self) -> _pyproj.CRS:
        suffix = self._short_name_parsed.suffix
        name = self._short_name.removesuffix(suffix)
        kwargs = {}
        match suffix:
            case "":
                kwargs["extended_ltm"] = False
            case "*":
                kwargs["extended_ltm"] = True
            case "**":
                kwargs["polar_ltm"] = True
            case _:
                raise TypeError(f"`suffix` is not recognized: {suffix!r}")
        crs = _srs.make_lunar_crs(name, **kwargs)
        return crs

    @staticmethod
    def sorter(info: LunarCrsInfo) -> tuple:
        """
        Function suitable for use as the `key` argument to `sorted()`.

        Instances sort by:
            1) `.is_lps` before `.is_ltm`
            2) by `.hemisphere` ("N" before "S")
            3) by `.ltm_zone` (numerically)
            4) by `.ltm_limit`

        Parameters
        ----------
        info : LunarCrsInfo
            The instance to be sorted.

        Returns
        -------
        sort_tuple : tuple
            A `tuple` to support the described sort order.

        Examples
        --------
        >>> info_list = query_lunar_crs_info(extended_ltm=True, polar_ltm=True)
        >>> info_list.sort(key=LunarCrsInfo.sorter)
        But note that the above sort is already applied by
        `query_lunar_crs_info()`.
        >>> first_info = info_list[0]
        >>> all((first_info.lps_hemisphere == "N",
        ...      first_info.ltm_limit == 80.))
        True
        >>> last_info = info_list[-1]
        >>> all((last_info.ltm_zone == 45, last_info.hemisphere == "S",
        ...      last_info.ltm_limit == 90.))
        True
        """
        return info._sort_tuple

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
# Preferred option, which extends support to LPS and supports querying
# by point(s), which will be needed to support `GriddedTransform`
# (though `GriddedTransform` might use some intermediate `np.ndarray`
# form, for performance, rather than the final output of this function).
# Note: Might be preferable to instead return some subclass of `list`
# that has useful (but possibly empty) subsets accessible as `.lps`,
# `.ltm`, and `.ltm_extended`.
def query_lunar_crs_info(
        datum_name: str | None = _wkt.DATUM_NAME,
        area_of_interest: _pyproj_aoi.AreaOfInterest | None = None,
        contains: bool = False, *,
        primary_ltm: bool = True, extended_ltm: bool = False,
        polar_ltm: bool = False, inclusive_bounds: bool = False,
        latitude: float | _collections.abc.Iterable[float] | None = None,
        longitude: float | _collections.abc.Iterable[float] | None = None
) -> list[LunarCrsInfo]:
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
        If `True`, `infos` will only reference a CRS if its area of use
        entirely contains all spatial inputs, that is, `area_of_interest` or
        all `latitude` and `longitude`. If `False`, `infos` will reference a
        CRS if its area of use intersects any part of a spatial filter.
    primary_ltm : bool, default=True
        Whether to include the primary (unextended) LTM zones, which span
        from the equator to 80 degrees N and S.
    extended_ltm : bool, default=False
        Whether to include extended LTM zones, which span from the equator
        to 82 degrees N and S.
    polar_ltm : bool, default=False
        Whether to include polar LTM zones, which span from the equator to
        90 degrees N and S.
    inclusive_bounds : bool, default=False
        Whether to treat LPS and LTM boundaries as inclusive when applying
        spatial filters (`area_of_interest`, `latitude`, and `longitude`).
        If `False` and only one `*_ltm` argument is `True`, each coordinate
        is associated with exactly one `CRS`. `False` is generally more
        performant.
    latitude : float or iterable of floats, optional
        The latitude(s) to query.
    longitude : float or array, optional
        The longitudes(s) to query.

    Returns
    -------
    infos : list[LunarCrsInfo]
        List of LPS and/or LTM CRS information instances, sorted by
        `LunarCrsInfo.sorter`.

    Raises
    ------
    TypeError
        If the combination of `area_of_interest`, `latitude`, and `longitude`
        are under- or over-specified.

    Examples
    --------
    >>> query_lunar_crs_info(latitude=0., longitude=0.)
    """
    # Validate datum.
    if datum_name != _wkt.DATUM_NAME:
        raise TypeError(f"`datum_name` must be {_wkt.DATUM_NAME!r}")

    # Resolve (unconformed) latitudes and longitudes.
    has_spatial_filter = True  # Default.
    match (latitude, longitude).count(None):
        case 0:
            if area_of_interest:
                raise TypeError("Cannot specify both `area_of_interest` and "
                                "`latitude`, `longitude`.")
            _, raw_lats = _ensure_float_iterable(latitude)
            _, raw_lons = _ensure_float_iterable(longitude)
        case 1:
            raise TypeError(
                "Must specify both `latitude` and `longitude`, or "
                "neither."
            )
        case 2:
            if area_of_interest:
                raw_lats = (area_of_interest.south_lat_degree,
                            area_of_interest.north_lat_degree)
                raw_lons = (area_of_interest.west_lon_degree,
                            area_of_interest.east_lon_degree)
                if not contains:
                    # Note: This grid sampling is guaranteed to sample
                    # all relevant LPS and LTM zones for all inputs.
                    # *REASSIGNMENTs*
                    raw_lats, raw_lons = _grid_sample(
                        latitudes=raw_lats, longitudes=raw_lons,
                        lat_sample=4,
                        lon_sample=2.0 * _wkt.LTM_ZONE_HALF_WIDTH
                    )
            else:
                has_spatial_filter = False

    # Prepare for function calls.
    if has_spatial_filter:
        get_lunar_crs_short_names = _get_lunar_crs_short_names
        conformed_lats = _conform_latitudes(raw_lats)
        conformed_lons = _conform_longitudes(raw_lons)
        latlon_kwargs = {
            "conformed_latitudes": conformed_lats,
            "conformed_longitudes": conformed_lons
        }
    else:
        get_lunar_crs_short_names = _get_all_lunar_crs_short_names
        latlon_kwargs = {}
    ltm_kwargs_list = []
    if primary_ltm:
        ltm_kwargs_list.append({"extended_ltm": False, "polar_ltm": False})
    if extended_ltm:
        ltm_kwargs_list.append({"extended_ltm": True, "polar_ltm": False})
    if polar_ltm:
        ltm_kwargs_list.append({"extended_ltm": False, "polar_ltm": True})
    if inclusive_bounds:
        prefer_ltms = (False, True)
        prefer_south_ltms = (False, True)
        prefer_west_ltms = (False, True)
    else:
        prefer_ltms = (False,)
        prefer_south_ltms = (False,)
        prefer_west_ltms = (False,)

    # Determine CRS short names.
    cum_crs_short_names = []
    for ltm_kwargs in ltm_kwargs_list:
        inner_crs_short_names = []
        # Note: `prefer_ltm` and `prefer_south_ltm` can be iterated in
        # parallel, because they apply at disjoint latitudes: the LTM/
        # LPS boundary and the equator, respectively.
        for this_prefer_ltm, this_prefer_south_ltm in zip(prefer_ltms,
                                                          prefer_south_ltms):
            for this_prefer_west_ltm in prefer_west_ltms:
                crs_short_names = get_lunar_crs_short_names(
                    prefer_ltm=this_prefer_ltm,
                    prefer_south_ltm=this_prefer_south_ltm,
                    prefer_west_ltm=this_prefer_west_ltm,
                    **latlon_kwargs, **ltm_kwargs
                )
                inner_crs_short_names.append(crs_short_names)
        if contains:
            # Note: If and only if all sample points fall in the same
            # CRS should that CRS be included. However, inclusive
            # boundaries must be treated carefully.
            if inclusive_bounds:
                per_coord_crs_short_name_sets = [
                    set(crs_short_names)
                    for crs_short_names in zip(*inner_crs_short_names)
                ]
                common_crs_short_names = _functools.reduce(
                    set.intersection, per_coord_crs_short_name_sets
                )
                # *REASSIGNMENT*
                inner_crs_short_names = (common_crs_short_names,)
            else:
                assert len(inner_crs_short_names) == 1
                these_unique_crs_short_names = set(crs_short_names)
                try:
                    common_crs_short_name, = these_unique_crs_short_names
                except ValueError:
                    # *REASSIGNMENT*
                    inner_crs_short_names = ((),)
                else:
                    # *REASSIGNMENT*
                    inner_crs_short_names = ((common_crs_short_name,),)
        cum_crs_short_names.extend(
            _itertools.chain.from_iterable(inner_crs_short_names)
        )

    # Treat special case of all polar LTM zones meeting at the pole.
    if (inclusive_bounds
        and has_spatial_filter
        and polar_ltm):
        conformed_lat_set = set(conformed_lats)
        if contains:
            has_np = (conformed_lat_set == {90})
            has_sp = (conformed_lat_set == {-90})
        else:
            has_np = (90 in conformed_lat_set)
            has_sp = (-90 in conformed_lat_set)
        kwargs2 = {"polar_ltm": True}
        if has_np and has_sp:
            kwargs2["south"] = None
        elif has_sp:
            kwargs2["south"] = True
        elif has_np:
            kwargs2["south"] = False
        else:
            kwargs2 = None  # Special case does not apply.
        if kwargs2 is not None:
            addl_lunar_crs_short_names = _get_all_lunar_crs_short_names(
                **kwargs2
            )
            cum_crs_short_names.extend(addl_lunar_crs_short_names)

    # Gather unique `CRSInfo` instances and return.
    unique_crs_short_name_set = set(cum_crs_short_names)
    infos = list(map(LunarCrsInfo._from_short_name, unique_crs_short_name_set))
    infos.sort(key=LunarCrsInfo.sorter)
    return infos



# endregion