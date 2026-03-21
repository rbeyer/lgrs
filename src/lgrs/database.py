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
        extend_ltm: bool = False, force_ltm: bool = False,
        prefer_ltm: bool = False, prefer_west_ltm: bool = False,
        south: bool | None = None
) -> tuple[str, ...]:
    # Note: `prefer_*` included for call signature compatibility with
    # `_get_lunar_crs_short_names()` but are intentionally unused.
    if force_ltm:
        suffix = "**"
    elif extend_ltm:
        suffix = "*"
    else:
        suffix = ""
    if ltm and lps:
        lps_tuple = _get_all_lunar_crs_short_names(
            ltm=False, extend_ltm=extend_ltm, force_ltm=force_ltm, south=south
        )
        ltm_tuple = _get_all_lunar_crs_short_names(
            lps=False, extend_ltm=extend_ltm, force_ltm=force_ltm, south=south
        )
        complete = lps_tuple + ltm_tuple
        return complete
    elif lps:
        if force_ltm:
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

@_caching._optionally_cache
def _get_lunar_crs_info(short_name: str) -> LunarCrsInfo:
    # Parse `short_name`.
    zone_num, hemi, suffix = _parse_lunar_crs_short_name(short_name)

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

    # Build `pyproj_database.CRSInfo`.
    if zone_num is None:
        area_name = f"LPS {'South' if hemi == "S" else 'North'}"
        area_of_use = _pyproj_aoi.AreaOfUse(
            west = -180.,
            south = -90. if hemi == "S" else trans_lat,
            east = 180.,
            north = 90. if hemi == "N" else trans_lat,
            name = f"Moon - {area_name}"
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
            west = west_lon,
            south = trans_lat if hemi == "S" else 0.,
            east = west_lon + (2 * _wkt.LTM_ZONE_HALF_WIDTH),
            north = trans_lat if hemi == "N" else 0.,
            name = f"Moon - {area_name}"
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
    info._short_name = short_name
    return info

def _get_lunar_crs_short_names(
        *, conformed_latitudes: _FloatIterable, conformed_longitudes: _FloatIterable,
        extend_ltm: bool = False, force_ltm: bool = False,
        prefer_ltm: bool = False, prefer_west_ltm: bool = False
) -> list[str]:
    # Determine LTM vs. LPS condition.
    if force_ltm:
        is_in_ltm = lambda test_lat: True
    else:
        if extend_ltm:
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
        # Note: This inequality is from M2025 code.
        hemi = ("N" if lat >= 0 else "S")
        if is_in_ltm(lat):
            # Below: Eq. 13 of M2025. Zones are 1-indexed.
            zone_float = (lon + 180) / (2 * _wkt.LTM_ZONE_HALF_WIDTH)
            zone_int = int(zone_float)
            if not prefer_west_ltm or not zone_float.is_integer():
                zone_int += 1  # *REASSIGNMENT*
            short_name = f"{zone_int:02}{hemi}"
        else:
            short_name = hemi
        if force_ltm:
            short_name += "**"  # *REASSIGNMENT*
        elif extend_ltm:
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
@_functools.total_ordering
class LunarCrsInfo(_pyproj_database.CRSInfo):
    """
    Subclass of `pyproj_database.CRSInfo`.

    Methods
    -------
    get_crs()
        Get the corresponding `pyproj.CRS` instance.

    See Also
    --------
    pyproj_database.CRSInfo : Parent class, with additional documentation.
    """
    def __eq__(self, other):
        return  self._sort_tuple == other._sort_tuple

    def __lt__(self, other):
        return  self._sort_tuple > other._sort_tuple

    @_functools.cached_property
    def _short_name_parsed(self) -> _ShortNameParsed:
        parsed = _parse_lunar_crs_short_name(self._short_name)
        return parsed

    @_functools.cached_property
    def _sort_tuple(self) -> tuple[int, int, int | None, str]:
        # Note: Sort like N, N*, S, S*, 1N, 1N*, 1N**, 2N, ... 1S.
        tup = (
            0 if self._short_name_parsed.zone_number is None else 1,
            0 if self._short_name_parsed.hemisphere == "N" else 1,
            self._short_name_parsed.zone_number,
            self._short_name_parsed.suffix
        )
        return tup

    # Note: Added because instantiating a `pyproj.CRS` from a
    # `pyproj.CRSInfo` relies `pyproj.CRS.from_authority()`, which we
    # cannot independently support.
    def get_crs(self) -> _pyproj.CRS:
        zone_num, hemi, suffix = self._short_name_parsed
        kwargs = {}
        match suffix:
            case "":
                kwargs["extend_ltm"] = False
            case "*":
                kwargs["extend_ltm"] = True
            case "**":
                kwargs["force_ltm"] = True
            case _:
                raise TypeError(f"`suffix` is not recognized: {suffix!r}")
        crs = _srs.make_lunar_crs(f"{zone_num}{hemi}", **kwargs)
        return crs


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
        extend_ltm: bool | None = None, force_ltm: bool | None = None,
        inclusive_bounds: bool = False,
        latitude: float | _collections.abc.Iterable[float] | None = None,
        longitude: float | _collections.abc.Iterable[float] | None = None
) -> list[_pyproj_database.CRSInfo]:
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
    extend_ltm : bool or None, default=None
        Whether to use extended LTM zones, which span from 80 to 82 degrees N
        and S. If `None`, both extended and non-extended zones are used.
    force_ltm : bool or None, default=None
        Whether to use LTM zones that extend from the equator to one pole.
        If `None`, both pole-extended and non-pole-extended zones are used.
    inclusive_bounds : bool, default=False
        Whether to treat LPS and LTM boundaries as inclusive when applying
        spatial filters (`area_of_interest`, `latitude`, and `longitude`).
        If `False`, the behavior is undefined but typically faster than
        `True`.
    latitude : float or iterable of floats, optional
        The latitude(s) to query.
    longitude : float or array, optional
        The longitudes(s) to query.

    Returns
    -------
    infos : list[LunarCrsInfo]
        List of LPS and/or LTM CRS information instances.

    Raises
    ------
    TypeError
        If the combination of `area_of_interest`, `latitude`, and `longitude`
        are under- or over-specified.

    Examples
    --------
    >>> query_lunar_crs_info(latitude=0., longitude=0.)
    """
    # TODO: Consider whether `extend_ltm` and `force_ltm` should be
    #  combined into a single enum, both to reduce the argument count
    #  and to be more explicit that non-extended LTM zones are included
    #  unless both `extend_ltm` and `force_ltm` are not `None`.
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
                raw_lats = (area_of_interest.north_lat_degree,
                            area_of_interest.south_lat_degree)
                raw_lons = (area_of_interest.east_lon_degree,
                            area_of_interest.west_lon_degree)
                if not contains:
                    # Note: This grid sampling is guaranteed to sample
                    # all relevant LPS and LTM zones for all inputs.
                    # *REASSIGNMENTs*
                    raw_lats, raw_lons = _grid_sample(
                        latitudes=raw_lats, longitudes=raw_lons,
                        lat_sample=4,
                        lon_sample=2.0*_wkt.LTM_ZONE_HALF_WIDTH
                    )
            else:
                has_spatial_filter = False

    # Prepare for function calls.
    if has_spatial_filter:
        get_lunar_crs_short_names = _get_lunar_crs_short_names
        conformed_lats = _conform_latitudes(raw_lats)
        conformed_lons = _conform_longitudes(raw_lons)
        kwargs = {
            "conformed_latitudes": conformed_lats,
            "conformed_longitudes": conformed_lons
        }
    else:
        get_lunar_crs_short_names = _get_all_lunar_crs_short_names
        kwargs = {}
    if extend_ltm is None:
        extend_ltms = (False, True)
    else:
        extend_ltms = (extend_ltm,)
    if force_ltm is None:
        force_ltms = (False, True)
    else:
        force_ltms = (force_ltm,)
    if inclusive_bounds:
        prefer_ltms = (False, True)
        prefer_west_ltms = (False, True)
    else:
        prefer_ltms = (False,)
        prefer_west_ltms = (False,)

    # Determine CRS short names.
    cum_crs_short_names = []
    for this_extend_ltm in extend_ltms:
        for this_force_ltm in force_ltms:
            inner_crs_short_names = []
            for this_prefer_ltm in prefer_ltms:
                for this_prefer_west_ltm in prefer_west_ltms:
                    crs_short_names = get_lunar_crs_short_names(
                        extend_ltm=this_extend_ltm, force_ltm=this_force_ltm,
                        prefer_ltm=this_prefer_ltm,
                        prefer_west_ltm=this_prefer_west_ltm,
                        **kwargs
                    )
                    inner_crs_short_names.append(crs_short_names)
            if contains:
                # Note: If and only if all sample points fall in the
                # same CRS should that CRS be included. However,
                # inclusive boundaries must be treated carefully.
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

    # Treat special case of all `force_ltm` zones meeting at the pole.
    if (inclusive_bounds
        and has_spatial_filter
        and force_ltm in (None, True)):
        conformed_lat_set = set(conformed_lats)
        if contains:
            has_np = (conformed_lat_set == {90})
            has_sp = (conformed_lat_set == {-90})
        else:
            has_np = (90 in conformed_lat_set)
            has_sp = (-90 in conformed_lat_set)
        kwargs2 = {"force_ltm": True}
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
    infos = list(map(_get_lunar_crs_info, unique_crs_short_name_set))
    infos.sort()
    return infos



# endregion