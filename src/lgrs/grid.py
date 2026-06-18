"""LGRS and ACC grid generation."""

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
from __future__ import annotations

import collections as _collections
import math as _math
import pathlib as _pathlib
import typing as _typing

# External.
import geopandas as _geopandas
import numpy as _np
import pyproj as _pyproj
from pyproj import aoi as _pyproj_aoi

# Internal.
import lgrs.bounds as _bounds
import lgrs.coords as _coords
import lgrs.database as _database
import lgrs.srs.srs as _srs
import lgrs.values as _values


# endregion
###############################################################################
# region> UTILITIES
###############################################################################
def _calculate_safe_count(span: float, delta: float) -> int:
    if span == 0:
        return 1
    # Note: "+ 2" accounts for first and last point.
    count = _math.floor(_values.SAFETY_FACTOR * (span / delta)) + 2
    return count


def _clip(value: float, minimum: float, maximum: float) -> float:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _construct_latlon_grid(
    bounds: _bounds.GeographicBounds,
    precision: int,
    constraints: _coords.Constraints,
    *,
    min_buffer: float = 0.0,
) -> list[_coords.LatLonPoint]:
    # Find latitude range for (buffered) grid.
    # Note: Must buffer around bounds to ensure that even a grid cell
    # for which a small corner extends into bounds is included.
    buff_length = max((_values.SAFETY_FACTOR * (0.5 * precision)), min_buffer)
    buff_lat = buff_length / _values.M_PER_DEGREE_LATITUDE
    min_lat = _clip(bounds.bottom - buff_lat, -90, +90)
    max_lat = _clip(bounds.top + buff_lat, -90, +90)
    lat_range = max_lat - min_lat

    # Determine nominal latitude coordinates.
    # Note: Adopting this `delta` max spacing between grid points
    # ensures that the greatest distance between the nearest points in
    # adjacent rows is `precision`.
    delta = precision / _math.sqrt(2)
    grid_height = lat_range * _values.M_PER_DEGREE_LATITUDE
    row_count = _calculate_safe_count(grid_height, delta)
    lats = _np.linspace(min_lat, max_lat, row_count).tolist()

    # Determine critical latitude and longitude coordinates.
    crit_lats = bounds._get_critical_latitudes(constraints)
    if crit_lats is not None:
        lats.extend(crit_lats)
    crit_lons = bounds._get_critical_longitudes(constraints)

    # For each sampled latitude...
    points = []
    for lat in lats:

        # Find longitude range for (buffered) grid.
        m_per_deg_lon = _values.calculate_m_per_degree_longitude(lat)
        buff_lon = buff_length / m_per_deg_lon
        min_lon = bounds.logical.left - buff_lon
        max_lon = bounds.logical.right + buff_lon
        lon_range = max_lon - min_lon
        if lon_range > 360:
            min_lon = -180  # *REASSIGNMENT*
            max_lon = 180  # *REASSIGNMENT*
            lon_range = 360  # *REASSIGNMENT*

        # Determine longitude coordinates.
        row_width = lon_range * m_per_deg_lon
        col_count = _calculate_safe_count(row_width, delta)
        lons = _np.linspace(min_lon, max_lon, col_count).tolist()
        if crit_lons is not None:
            lons.extend(crit_lons)

        # Create points.
        points.extend(_coords.LatLonPoint(lat, lon) for lon in lons)

    # Return points.
    return points


def _resolve_bounds(
    bounds: _typing.Any,
    *,
    extended_ltm: bool,
    fallback_to_geo: bool,
    **ignore,
) -> tuple[
    _bounds.GeographicBounds | _bounds.ProjectedBounds,
    _srs.CRS | None,
]:
    # Standardize `bounds`, so that each type as a single interpretation.
    geo_crs = _srs.make_lunar_crs()
    if isinstance(bounds, str):
        try:
            std_bounds = _srs.make_lunar_crs(bounds, extended_ltm=extended_ltm)
        except _pyproj.exceptions.CRSError:
            std_bounds = _pathlib.Path(bounds)
    elif isinstance(bounds, _collections.abc.Sequence):
        match len(bounds):
            case 4:
                std_bounds = (*bounds, geo_crs)
            case 5:
                crs = _bounds.resolve_crs(bounds[4])
                std_bounds = (*bounds[:4], crs)
            case _:
                raise TypeError(
                    "If `bounds` is a flat (1D) `sequence`, it must have "
                    f"length 4 or 5, not: {len(bounds)}"
                )
    elif bounds is None:
        std_bounds = _bounds.GeographicBounds(-180, -90, 180, 90)
    else:
        std_bounds = bounds

    # Resolve standardized `bounds` to a bounds instance.
    exclusive_crs = None  # Default.
    match std_bounds:
        case tuple():
            crs = std_bounds[-1]
            if crs == geo_crs:
                final_bounds = _bounds.GeographicBounds(*std_bounds[:-1])
            else:
                final_bounds = _bounds.ProjectedBounds(
                    *std_bounds[:-1], crs_hint=crs
                )
        case _pathlib.Path():
            final_bounds = _bounds._BaseBounds.from_path(
                std_bounds, fallback_to_geo=fallback_to_geo
            )
        case _srs.CRS():
            exclusive_crs = std_bounds
            final_bounds = _bounds.GeographicBounds.from_area(
                std_bounds.area_of_use
            )
        case _bounds.GeographicBounds() | _bounds.ProjectedBounds():
            final_bounds = std_bounds
        case _pyproj_aoi.AreaOfInterest() | _pyproj_aoi.AreaOfUse():
            final_bounds = _bounds.GeographicBounds.from_area(std_bounds)
        case _:
            raise TypeError(
                f"Type and/or form of `bounds` not supported: {bounds!r}"
            )

    # Return results.
    return (final_bounds, exclusive_crs)


# endregion
###############################################################################
# region> SUPPORT CLASSES
###############################################################################
class LunarGeoDataFrame(_geopandas.GeoDataFrame):
    """Subclass of `geopandas.GeoDataFrame`."""

    name_hint: str


# endregion
###############################################################################
# region> GRID GENERATION
###############################################################################
def make_box_grid(
    bounds: _typing.Any,
    precision: float,
    *,
    acc: bool = False,
    extended_ltm: bool = False,
    min_overlap: bool = True,
    min_zones: bool = False,
    fallback_to_geo: bool = False,
    densify_count: int = 21,
) -> list[_coords.BoxCoordinate]:
    """
    Generate a grid of LGRS or ACC boxes spanning specified bounds.

    Parameters
    ----------
    bounds : a resolvable bounds hint
        Resolved to define the footprint of the box grid. Supported inputs:
            (1) 4-sequence of `float`s
                Order of `float`s is (min_lon, min_lat, max_lon, max_lat).
                Values are in degrees in IAU_2015:30100.
            (2) 5-sequence of 4 `float`s followed by a CRS hint
                Order is (min_x, min_y, max_x, max_y, crs_hint). If the
                final element is not a `CRS`, it is coerced by
                `lgrs.bounds.resolve_crs()`. For example, "S" indicates the
                south LPS CRS, "23N" indicates the Northern Hemisphere LTM
                zone 23 CRS, and `None` indicates the underlying geographic
                CRS, IAU_2015:30100. Arguments compatible with
                `pyproj.CRS.from_user_input()` are also supported, such as
                "IAU_2015:30100" or "ESRI:104903".
            (3) path (`str` or `pathlib.Path`) to vector or raster data
                The target's bounds, in its CRS, are used. You may specify a
                layer or table by the convention:
                ``"path/to/my.gpkg|layer=my_layer_name"`` or
                ``"path/to/my.gpkg|table=my_table_name"``, as appropriate.
            (4) `str` short name for an LGRS CRS
                This option generates all boxes for the indicated CRS, which
                is resolved by `lgrs.bounds.resolve_crs()`.
            (5) `None`
                Interpreted as global bounds.
            (6) `bounds.GeographicBounds` or `bounds.ProjectedBounds`
                Used directly.
            (7) `pyproj.AreaOfInterest` or `pyproj.AreaOfUse`
                Converted by ``GeographicBounds.from_area(bounds)``.
    precision : float
        The required precision of the grid. If not a supported precision,
        the actual precision is rounded down to a better precision. All
        boxes have the same precision.
    acc : bool, default=False
        Whether to use Artemis Condensed Coordinates (ACC) rather than the
        standard Lunar Grid Reference System (LGRS). The geometry of the
        boxes in each case are identical but the field data differ.
    extended_ltm : bool, default=False
        Whether to use the extended LTM region, which extends to 82° N/S
        instead of 80° N/S.
    min_overlap : bool, default=True
        Whether to minimize the box overlap. If `True`, boxes only overlap
        near LPS and LTM zone boundaries, where overlap is necessary to
        ensure coverage. If `False`, all valid boxes in the targeted area
        are generated, which may include inter-zone overlaps of up to ~35.4
        km, that is, the diagonal of a 25-km box. In the special case that
        `bounds` is specified by an LGRS CRS string, `min_overlap` is
        instead interpreted to relate to the overlap of that region with its
        neighbors. Then, `True` generates only boxes that are within the
        nominal bounds of the zone whereas `False` generates all valid boxes
        from the maximally expanded zone.
    min_zones : bool, default=False
        Whether to minimize the number of zones (and therefore, CRSes) that
        are used. If `True`, boxes from non-nominal (expanded) areas of
        zones may be generated if doing so enables fewer zones to be used
        overall. For example, when working near the nominal longitudinal
        boundary between two LTM zones, you may prefer all boxes to come
        from one zone, if possible, instead of nearly all boxes from that
        zone and a few from a neighboring zone. If `False`, only boxes from
        the nominal area of each zone will be generated. If `bounds` is
        specified by an LGRS CRS string, this argument is ignored.
    fallback_to_geo: bool, default=False
        Specifies the behavior when the CRS of a path-like `bounds` cannot
        be transformed to the geographic CRS IAU_2015:30100. If `True` and
        that CRS can be transformed to some geographic CRS, that geographic
        CRS is assumed equivalent to IAU_2015:30100. If `True` but no CRS
        can be identified for `path`, the coordinates are assumed to
        already be in IAU_2015:30100, with order (lat, lon). In all other
        cases, an exception is raised.
    densify_count : int, default=21
        Whenever a bounding box must be transformed between CRSes, this number
        of samples will be added to each edge prior to transformation. Having
        more samples helps ensure that the transformation of the bounding box
        is more precise, but higher values will decrease performance.

    Returns
    -------
    boxes : list of lgrs.coords.BoxCoordinate instances
        A flat list of boxes. LPS and LTM boxes may be commingled.

    Warnings
    --------
    The `True` option for `min_zones` is not yet implemented.

    Examples
    --------
    >>> import lgrs.bounds
    >>> aoi = lgrs.bounds.GeographicBounds(
    ...     min_longitude=20, min_latitude=20,
    ...     max_longitude=40, max_latitude=40
    ... )
    >>> boxes = make_box_grid(aoi, precision=25_000, acc=True)
    >>> len(boxes)
    650
    >>> import lgrs.coords
    >>> isinstance(boxes[0], lgrs.coords.LtmAccBox)
    True
    """
    # Raise error if unsupported option is used.
    if min_zones:
        raise TypeError("`min_zones=True` not yet implemented.")

    # Resolve `bounds`.
    final_bounds, exclusive_crs = _resolve_bounds(**locals())

    # Determine geographic bounds for the sample-point grid, the minimum
    # required buffer length, and whether only default boxes should be
    # used.
    geo_bounds = final_bounds.in_crs(densify_count=densify_count)
    if exclusive_crs:
        if min_overlap:
            min_buffer = 0
        else:
            min_buffer = _values.calculate_diagonal_length(
                25_000, safe_up=True
            )
        use_default_boxes_only = True
    else:
        min_buffer = 0
        use_default_boxes_only = min_overlap

    # Determine the constraints to use.
    if exclusive_crs is None:
        constraints = _coords.Constraints(extended_ltm=extended_ltm)
    elif exclusive_crs.ltm_zone is None:
        constraints = _coords.Constraints(
            prefer_lps=True, extended_ltm=extended_ltm
        )
    else:
        ltm_zone_num = int(exclusive_crs.ltm_zone[:-1])
        constraints = _coords.Constraints(
            prefer_ltm=True,
            preferred_ltm_zone=ltm_zone_num,
            extended_ltm=extended_ltm,
        )

    # Generate geographic sample-point grid.
    # Note: Grid has sufficient density to ensure that all boxes at
    # desired precision are sampled, with careful sampling near region
    # (relevant zone) boundaries.
    # *REASSIGNMENT*
    precision = _coords.BaseCoordinate._resolve_precision_static(precision)
    latlon_sample_points = _construct_latlon_grid(
        geo_bounds, precision, constraints, min_buffer=min_buffer
    )

    # Create boxes.
    if use_default_boxes_only:
        if acc:
            get_box = _coords.LatLonPoint.to_acc
        else:
            get_box = _coords.LatLonPoint.to_lgrs
        box_set = {
            get_box(samp_pt, constraints=constraints, precision=precision)
            for samp_pt in latlon_sample_points
        }
    else:
        if acc:
            get_all_boxes = _coords.LatLonPoint.to_all_acc
        else:
            get_all_boxes = _coords.LatLonPoint.to_all_lgrs
        box_set = {
            box
            for samp_pt in latlon_sample_points
            for box in get_all_boxes(
                samp_pt, extended_ltm=extended_ltm, precision=precision
            )
        }

    # Filter any boxes from outside the targeted CRS.
    if exclusive_crs:
        box_list = [box for box in box_set if box.crs == exclusive_crs]

    # Filter boxes spatially, if necessary.
    elif geo_bounds.is_global:
        box_list = list(box_set)
    else:
        # On first pass, filter out any boxes that have no corner within
        # within the relevant bounds or, for cross-CRS tests, closer
        # than a (safe) box width.
        if final_bounds.crs.is_geographic:
            short_tolerance = precision / _values.M_PER_DEGREE_LATITUDE
        else:
            short_tolerance = precision
        default_tolerance = short_tolerance * _values.SAFETY_FACTOR
        box_list = []
        for box in box_set:
            if final_bounds.crs == box.crs_nominal:
                tolerance = 0
            else:
                tolerance = default_tolerance
            for corner in box._corners:
                if corner.is_within_bounds(final_bounds, tolerance=tolerance):
                    box_list.append(box)
                    break

        # If all boxes were filtered out in first pass, a single box
        # fully encloses the bounds (and therefore has no corners within
        # those bounds), so instead return that box.
        if not box_list:
            median_lon, median_lat = geo_bounds.median_xy
            median_latlon = _coords.LatLonPoint(median_lat, median_lon)
            # *REASSIGNMENT*
            box_list = [box for box in box_set if box.contains(median_latlon)]

    # Sort and return.
    box_list.sort(key=lambda b: b.string)
    return box_list


def make_gdfs(
    boxes: _collections.abc.Sequence[_coords.BoxCoordinate],
) -> list[LunarGeoDataFrame]:
    """
    Create one or more `GeoDataFrame` instances from a sequence of boxes.

    Each `GeoDaraFrame` will have a unique coordinate reference system
    (CRS).

    Parameters
    ----------
    boxes : sequence of lgrs.coords.BoxCoordinates instances
        The boxes to collect into `gdfs`. Their `.field_data` attributes
        are used to populate each `gdf`.

    Returns
    -------
    gdfs : list of GeoDataFrame instances
        The created `GeoDataFrame` instances. Note that each instance
        has the added attribute `.name_hint`, which is a string
        providing a suggested name suitable for use in layer and file
        names.

    Examples
    --------
    >>> import lgrs.bounds
    >>> aoi = lgrs.bounds.GeographicBounds(
    ...     min_longitude=20, min_latitude=20,
    ...     max_longitude=40, max_latitude=40
    ... )
    >>> boxes = make_box_grid(aoi, precision=25_000, acc=True)
    >>> gdfs = make_gdfs(boxes)
    >>> len(gdfs)
    4
    >>> [gdf.name_hint for gdf in gdfs]  # doctest: +NORMALIZE_WHITESPACE
    ['ACC_25km_LTM_25N_polygon_grid', 'ACC_25km_LTM_26N_polygon_grid',
     'ACC_25km_LTM_27N_polygon_grid', 'ACC_25km_LTM_28N_polygon_grid']
    >>> import geopandas
    >>> isinstance(gdfs[0], geopandas.GeoDataFrame)
    True
    """

    # Organize boxes by CRS.
    crs_info_to_boxes = _collections.defaultdict(list)
    make_info = _database.LunarCrsInfo.from_crs
    for box in boxes:
        crs_info_to_boxes[make_info(box.crs_nominal)].append(box)

    # Identify all field names.
    field_names_view_parent = {}
    field_names_view = field_names_view_parent.keys()
    for box in boxes:
        box_field_names_view = box.field_data.keys()
        if box_field_names_view <= field_names_view:
            continue
        if box_field_names_view > field_names_view:
            field_names_view_parent.clear()
        field_names_view_parent.update(box.field_data)

    # Create one GDF per CRS.
    gdfs = []
    sorted_crs_infos = sorted(
        crs_info_to_boxes, key=_database.LunarCrsInfo.sorter
    )
    for crs_info in sorted_crs_infos:
        boxes = crs_info_to_boxes[crs_info]
        data = {field_name: [] for field_name in field_names_view}
        for box in boxes:
            for field_name in field_names_view:
                data[field_name].append(box.field_data.get(field_name))
        data["geometry"] = [box.geometry for box in boxes]
        gdf = LunarGeoDataFrame(data, crs=crs_info.get_crs())
        gdfs.append(gdf)

        # Construct and attach name hint.
        name_hint_parts = []
        match box:
            case _coords.LpsLgrsBox() | _coords.LtmLgrsBox():
                name_hint_parts.append("LGRS")
            case _coords.LpsAccBox() | _coords.LtmAccBox():
                name_hint_parts.append("ACC")
            case _:
                # Note: This line should not be encountered.
                pass
        if box.precision < 1000:
            prec_str = f"{box.precision}m"
        else:
            prec_str = f"{box.precision // 1000}km"
        name_hint_parts.append(prec_str)
        if crs_info.is_lps:
            name_hint_parts.extend(("LPS", crs_info.lps_hemisphere))
        else:
            name_hint_parts.extend(("LTM", crs_info.ltm_zone))
        name_hint_parts.extend(("polygon", "grid"))
        name_hint = "_".join(name_hint_parts)
        gdf.name_hint = name_hint

    return gdfs
