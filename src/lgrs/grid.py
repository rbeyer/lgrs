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
import dataclasses as _dataclasses
import math as _math
import pathlib as _pathlib
import typing as _typing

# External.
import geopandas as _geopandas
import numpy as _np
import pyproj as _pyproj
import rasterio as _rasterio
from pyproj import aoi as _pyproj_aoi

# Internal.
import lgrs.coords as _coords
import lgrs.database as _database
import lgrs.srs.srs as _srs
import lgrs.srs.wkt as _wkt
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
    bounds: GeographicBounds,
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
    min_lat = _clip(bounds.min_latitude - buff_lat, -90, +90)
    max_lat = _clip(bounds.max_latitude + buff_lat, -90, +90)
    lat_range = max_lat - min_lat

    # TODO: For large grid generation, most time is spent in converting
    #  each `LatLonPoint` to a box. This could be expedited by compiling
    #  lats and lons in arrays, bulk-transforming via `pyproj` (after
    #  carefully partitioning by CRS), and then directly instantiating
    #  LPS/LTM points with `validate=False`. Could use a public utility
    #  in a `util` module that is `pyproj.Transformer`-like, accepting
    #  either a float or array for each of a `lat` and `lon` argument,
    #  optimized for those values already being presorted, with an
    #  option like `latlon: bool | None = False` that determines whether
    #  `LatLonPoint`s are returned. For `True` and `False` (if caching),
    #  both `LatLonPoint` and `Lps/LtmPoint` would still be created and
    #  registered as a cousin to the returned instance. For `None` (and
    #  if not caching), would merely generate the returned instance.

    # Determine nominal latitude coordinates.
    # Note: Adopting this `delta` max spacing between grid points
    # ensures that the greatest distance between the nearest points in
    # adjacent rows is `precision`.
    delta = precision / _math.sqrt(2)
    grid_height = lat_range * _values.M_PER_DEGREE_LATITUDE
    row_count = _calculate_safe_count(grid_height, delta)
    lats = _np.linspace(min_lat, max_lat, row_count).tolist()
    crit_lats = bounds._get_critical_latitudes(constraints)

    # Determine critical latitude and longitude coordinates.
    if crit_lats is not None:
        lats.extend(crit_lats)
    crit_lons = bounds._get_critical_longitudes(constraints)

    # For each sampled latitude...
    points = []
    for lat in lats:

        # Find longitude range for (buffered) grid.
        m_per_deg_lon = _values.calculate_m_per_degree_longitude(lat)
        buff_lon = buff_length / m_per_deg_lon
        min_lon = bounds.min_longitude - buff_lon
        max_lon = bounds.max_longitude + buff_lon
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


def _make_crit_array(
    num_or_iter: float | _collections.abc.Iterable,
) -> _np.ndarray:
    if isinstance(num_or_iter, _collections.abc.Iterable):
        iterable = num_or_iter
    else:
        iterable = (-num_or_iter, num_or_iter)
    a = _np.fromiter(iterable, dtype=_np.float64)
    return a


def _resolve_file_path_and_layer_name_and_existence(
    path: _pathlib.Path | str, *, test_exists: bool = True
) -> tuple[_pathlib.Path, str | None, bool | None]:
    if not isinstance(path, _pathlib.Path):
        path = _pathlib.Path(path)  # *REASSIGNMENT*
    if path.parts[0] == "~":
        path = path.expanduser()  # *REASSIGNMENT*
    try:
        path_name, layer_name = path.name.split("|layername=")
    except ValueError:
        file_path = path
        layer_name = None
    else:
        file_path = path.with_name(path_name)
    if not test_exists:
        exists = None
    elif not file_path.exists():
        exists = False
    elif layer_name is None:
        exists = True
    else:
        exists = layer_name in _geopandas.list_layers(path)["name"].values
    return (file_path, layer_name, exists)


# endregion
###############################################################################
# region> SUPPORT CLASSES
###############################################################################
class GeoDataFrame(_geopandas.GeoDataFrame):
    """Subclass of `geopandas.GeoDataFrame`."""

    name_hint: str


@_dataclasses.dataclass(frozen=True)
class GeographicBounds:
    """
    Create an instance describing a geographic bounding box (envelope).

    Parameters
    ----------
    min_longitude : float
        The minimum longitude, in degrees.
    min_latitude : float
        The minimum latitude, in degrees.
    max_longitude : float
        The maximum longitude, in degrees.
    max_latitude : float
        That maximum latitude, in degrees.

    Raises
    ------
    TypeError
        If values are invalid. Namely, if the absolute value of any
        longitude exceeds 360, the absolute value of any latitude exceeds
        90, any maximum is not greater than its counterpart minimum, or
        the range implied by the minimum and maximum longitudes exceeds 360.

    Examples
    --------
    >>> bounds_1 = GeographicBounds(10, 10, 20, 20)

    Bounds can validly cross critical meridians but may not span from higher
    to lower values. Below, `bounds_2` and `bounds_3` are functionally
    equivalent, but `bounds_4` and `bounds_5` are invalid.


    >>> bounds_2 = GeographicBounds(-190, 10, -170, 20)
    >>> bounds_3 = GeographicBounds(170, 10, 190, 20)
    >>> bounds_4 = GeographicBounds(170, 10, -170, 20)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError:
      ...
    >>> bounds_5 = GeographicBounds(0, 89, 10, 87)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError:
      ...

    If the user intended to specify `bounds_5` as crossing the North Pole,
    they could achieve an area centered the pole thusly.

    >>> alt_bounds_5 = GeographicBounds(0, 87, 360, 90)

    Or, equivalently:

    >>> all_bounds_5b = GeographicBounds.from_north_pole_to(87)
    """  # noqa: E501

    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float

    # * INITIALIZATION AND INSTANTIATION. ─────────────────────────────
    def __post_init__(self):
        for field in _dataclasses.fields(self):
            val = getattr(self, field.name)
            match field.name:
                case "min_longitude" | "max_longitude":
                    max_abs = 360
                case "min_latitude" | "max_latitude":
                    max_abs = 90
                case _:
                    continue
            if abs(val) > max_abs:
                raise TypeError(
                    f"Absolute value of `{field.name}` must be <={max_abs}, "
                    f"not: {val!r}>"
                )
        if self.min_longitude >= self.max_longitude:
            raise TypeError(
                f"`max_longitude` ({self.max_longitude}) must be greater than "
                f"`min_longitude` ({self.min_longitude})."
            )
        if self.max_longitude - self.min_longitude > 360:
            raise TypeError(
                "The difference between `max_longitude` and `min_longitude` "
                "cannot exceed 360."
            )
        if self.min_latitude >= self.max_latitude:
            raise TypeError(
                f"`max_latitude` ({self.max_latitude}) must be greater than "
                f"`min_latitude` ({self.min_latitude})."
            )

    @classmethod
    def from_north_pole_to(cls, min_latitude: float) -> _typing.Self:
        """
        Create `GeographicBounds` from North Pole south to some latitude.

        Parameters
        ----------
        min_latitude : float
            The latitude to which the bounds should extend.

        Returns
        -------
        GeographicBounds
            The new instance.
        """
        return GeographicBounds(-180, min_latitude, 180, 90)

    @classmethod
    def from_other(
        cls,
        other: (
            _collections.abc.Iterable
            | _pyproj_aoi.AreaOfInterest
            | _pyproj_aoi.AreaOfUse
        ),
    ) -> _typing.Self:
        """
        Create `GeographicBounds` from iterable or `pyproj.aoi.AreaOfInterest`.

        Parameters
        ----------
        other : iterable or AreaOfInterest or AreaOfUse from pypoj
            An iterable of 4 numbers, in the same order as expected by
            `GeographicBounds()`, or a `pyproj.aoi.AreaOfInterest` or
            `pyproj.aoi.AreaOfUse`.

        Returns
        -------
        bounds : GeographicBounds
            The `GeographicBounds` instance. In the special case that `other`
            a `GeographicBounds` instance, `bounds` itself is returned.
        """
        match other:
            case GeographicBounds():
                return other
            case _pyproj_aoi.AreaOfUse():
                return cls(*tuple(other)[:4])
            case _collections.abc.Iterable():
                return cls(*other)
            case _pyproj_aoi.AreaOfInterest():
                return cls(
                    other.west_lon_degree,
                    other.south_lat_degree,
                    other.east_lon_degree,
                    other.north_lat_degree,
                )
            case _:
                raise TypeError(f"Unsupported type for `other`: {other!r}.")

    @classmethod
    def from_path(
        cls, path: _pathlib.Path | str, densify_pts: int = 21
    ) -> _typing.Self:
        """
        Create `GeographicBounds` based on a vector or raster file.

        Parameters
        ----------
        path :
            Path to a vector or raster file whose approximate geographic bounds
            will be used. You may specify a layer by the convention:
            ``"path/to/my.gpkg|layername=layer_name"``.
        densify_pts : int, default=21
            Number of points to add to each edge of the box. Having more
            vertices helps ensure that the transformation of the bounding box
            (from the CRS native to `path` to a geographic version) is
            more precise, but higher values will decrease performance.

        Returns
        -------
        bounds : GeographicBounds
            The `GeographicBounds` instance.
        """
        # Resolve CRS and bounds in that CRS.
        file_path, layer_name, exists = (
            _resolve_file_path_and_layer_name_and_existence(path)
        )
        if not exists:
            raise TypeError(f"Path could not be found: {path}")
        if layer_name is None:
            kwargs = {}
        else:
            kwargs = {"layer": layer_name}
        try:
            gdf = _geopandas.read_file(file_path, **kwargs)
        except Exception:
            try:
                with _rasterio.open(path) as src:
                    native_bounds = src.bounds
                    native_crs = src.crs
            except Exception:
                raise TypeError(
                    f"Path could not be read either as vector or raster data: "
                    f"{path}."
                )
        else:
            native_bounds = gdf.total_bounds
            native_crs = gdf.crs

        # Convert to geographic bounds.
        transformer = _pyproj.Transformer.from_crs(
            native_crs, _srs.make_lunar_crs(), always_xy=True
        )
        # TODO: Decide on best `densify_pts` option. Defaults to 21.
        geo_bounds = transformer.transform_bounds(
            *native_bounds, densify_pts=densify_pts
        )
        return GeographicBounds(*geo_bounds)

    @classmethod
    def from_south_pole_to(cls, max_latitude: float) -> _typing.Self:
        """
        Create `GeographicBounds` from South Pole north to some latitude.

        Parameters
        ----------
        max_latitude : float
            The latitude to which the bounds should extend.

        Returns
        -------
        GeographicBounds
            The new instance.
        """
        return GeographicBounds(-180, -90, 180, max_latitude)

    # * BASIC BEHAVIOR. ───────────────────────────────────────────────
    def __contains__(self, point: _coords.LatLonPoint) -> bool:
        if self.min_longitude <= point.longitude <= self.max_longitude:
            if self.min_latitude <= point.latitude <= self.max_latitude:
                return True
        return False

    def __iter__(self) -> _collections.abc.Iterator[float]:
        for field in _dataclasses.fields(self):
            yield getattr(self, field.name)

    # * CRITICAL LATITUDES AND LONGITUDES. ────────────────────────────
    # Note: The equator is not "critical" for these purposes, because
    # LTM boxes mate there precisely, without overlap.
    _crit_lats_extended_ltm_array = _make_crit_array(
        _wkt.LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
    )
    _crit_lats_unextended_ltm_array = _make_crit_array(
        _wkt.LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE
    )
    _crit_ltm_lons_array = _make_crit_array(range(-356, 361, 8))

    def _get_critical_latitudes(
        self, constraints: _coords.Constraints
    ) -> list[float] | None:
        if constraints.extended_ltm:
            crit_array = self._crit_lats_extended_ltm_array
        else:
            crit_array = self._crit_lats_unextended_ltm_array
        sliced_array = self._slice_array_by_interval_ends(
            crit_array, self.min_latitude, self.max_latitude
        )
        if sliced_array is None:
            return None
        final = sliced_array.tolist()
        sliced_array[sliced_array < 0] += _values.DEGREE_EPSILON
        sliced_array[sliced_array > 0] -= _values.DEGREE_EPSILON
        final.extend(sliced_array.tolist())
        final.sort()
        if final[0] < self.min_latitude:
            del final[0]
        if final[-1] > self.max_latitude:
            del final[-1]
        return final

    def _get_critical_longitudes(
        self, constraints: _coords.Constraints
    ) -> list[float] | None:
        # Note: If in exclusively LPS latitudes, there are no critical
        # longitudes.
        if self.min_latitude > constraints._max_abs_ltm_lat:
            return None
        elif self.max_longitude < -constraints._max_abs_ltm_lat:
            return None
        sliced_array = self._slice_array_by_interval_ends(
            self._crit_ltm_lons_array,
            self.min_longitude,
            self.max_longitude,
        )
        if sliced_array is None:
            return None
        final = sliced_array.tolist()
        sliced_array -= _values.DEGREE_EPSILON
        # Note: Reverse slice so that smallest value is at the end of
        # the list, for more performant removal, if necessary.
        final.extend(sliced_array[::-1].tolist())
        if final[-1] < self.min_longitude:
            del final[-1]
        return final

    @staticmethod
    def _slice_array_by_interval_ends(
        a: _np.ndarray,
        left: float,
        right: float,
    ) -> _np.ndarray | None:
        idx_0 = a.searchsorted(left, side="left")
        idx_n = a.searchsorted(right, side="right")
        if idx_0 == idx_n:
            return None
        sliced = a[idx_0:idx_n]
        return sliced


# endregion
###############################################################################
# region> GRID GENERATION
###############################################################################
def make_box_grid(
    bounds: (
        GeographicBounds
        | tuple[float, float, float, float]
        | str
        | _pyproj_aoi.AreaOfInterest
        | _pyproj_aoi.AreaOfUse
    ),
    precision: float,
    *,
    acc: bool = False,
    extended_ltm: bool = False,
    min_overlap: bool = True,
    min_zones: bool = False,
) -> list[_coords.BoxCoordinate]:
    """
    Generate a grid of LGRS or ACC boxes within geographic bounds.

    Parameters
    ----------
    bounds : GeographicBounds, iterable, string, or another hint
        The geogrpahic bounds, in degrees, for which to generate the grid. Any
        value compatible with ``GeographicBounds.from_other()`` is valid.
        Additionally, the name of a CRS (as supported by
        `lgrs.make_lunar_crs()`) may be used to generate all boxes for that
        CRS. Examples include "S" for the LPS south polar region and "23N"
        for LTM zone 23 in the Northern Hemisphere.
    precision : float
        The required precision of the grid. If not a supported precision,
        the actual precision is rounded down to a better precision. All
        boxes have the same precision.
    acc : bool, default=False
        Whether to use ACC. If `False`, LGRS is used.
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
        instead interpreted to relate to the overlap of that zone with its
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

    Returns
    -------
    boxes : list of lgrs.coords.BoxCoordinate instances
        A flat list of boxes. LPS and LTM boxes may be commingled.

    Warnings
    --------
    The `True` option for `min_zones` is not yet implemented.

    See Also
    --------
    GeographicBounds.from_path : Get geographic bounds from a file path

    Examples
    --------
    >>> aoi = GeographicBounds(
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

    # Determine geographic bounds, the minimum required buffer length,
    # and whether only default boxes should be used.
    # Note: `min_overlap` has two different meanings, depending on the
    # mode. (That mode in determined by how `bounds` is specified).
    # Initially, one meaning is assumed, but once mode resolution
    # confirms the intended meaning, `use_default_boxes_only` is set
    # accordingly.
    use_expanded_exclusive_crs = not min_overlap  # For clarity.
    if isinstance(bounds, str):
        exclusive_crs: _srs.CRS = _srs.make_lunar_crs(
            bounds, extended_ltm=extended_ltm
        )
        geo_bounds = GeographicBounds.from_other(exclusive_crs.area_of_use)
        if use_expanded_exclusive_crs:
            min_buffer = _values.calculate_diagonal_length(
                25_000, safe_up=True
            )
        else:
            min_buffer = 0
        use_default_boxes_only = True
    else:
        exclusive_crs = None
        geo_bounds = GeographicBounds.from_other(bounds)
        min_buffer = 0
        use_default_boxes_only = min_overlap
    del min_overlap  # Avoid accidental use.

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

    # Generate geographic sample point grid.
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

    # Filter any boxes that have no corner within bounds.
    if exclusive_crs is None:
        # TODO: Test whether this block generates gaps.
        box_list = []
        for box in box_set:
            for corner in box.corners_latlon:
                if corner in geo_bounds:
                    box_list.append(box)
                    break

    # Filter any boxes from outside the targeted CRS.
    else:
        box_list = [box for box in box_set if box.crs == exclusive_crs]

    # Sort and return.
    box_list.sort(key=lambda b: b.string)
    return box_list


def make_gdfs(
    boxes: _collections.abc.Sequence[_coords.BoxCoordinate],
) -> list[GeoDataFrame]:
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
    >>> aoi = GeographicBounds(
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
        gdf = GeoDataFrame(data, crs=crs_info.get_crs())
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
