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
import collections as _collections
import math as _math
import typing as _typing

# External.
import geopandas as _geopandas
import numpy as _np

# Internal.
import lgrs.coords as _coords
import lgrs.values as _values

# endregion
###############################################################################
# region> GRID GENERATION
###############################################################################
_precision_array = _np.array((1, 10, 100, 1_000, 25_000))


class GeographicBounds(_typing.NamedTuple):
    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float

    def __contains__(self, point: _coords.LatLonPoint) -> bool:
        if self.min_longitude <= point.longitude <= self.max_longitude:
            if self.min_latitude <= point.latitude <= self.max_latitude:
                return True
        return False


def _calculate_safe_count(span: float, delta: float) -> int:
    if span == 0:
        return 1
    if span < 0:  # TODO: Remove after testing.
        pass  # TODO: Remove after testing.
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
    bounds: GeographicBounds, precision: int
) -> list[_coords.LatLonPoint]:
    # Find latitude range for (buffered) grid.
    # Note: Must buffer around bounds to ensure that even a grid cell
    # for which a small corner extends into bounds is included.
    buff_length = _values.SAFETY_FACTOR * (0.5 * precision)
    buff_lat = buff_length / _values.M_PER_DEGREE_LATITUDE
    min_lat = _clip(bounds.min_latitude - buff_lat, -90, +90)
    max_lat = _clip(bounds.max_latitude + buff_lat, -90, +90)
    lat_range = max_lat - min_lat

    # Determine latitude coordinates.
    # Note: Adopting this `delta` max spacing between grid points
    # ensures that the greatest distance between the nearest points in
    # adjacent rows is `precision`.
    delta = precision / _math.sqrt(2)
    grid_height = lat_range * _values.M_PER_DEGREE_LATITUDE
    row_count = _calculate_safe_count(grid_height, delta)
    lats = _np.linspace(min_lat, max_lat, row_count).tolist()

    # For each sampled latitude...
    points = []
    for lat in lats:

        # Find longitude range for (buffered) grid.
        m_per_deg_lon = _values.calculate_m_per_degree_longitude(lat)
        buff_lon = buff_length / m_per_deg_lon
        min_lon = _clip(bounds.min_longitude - buff_lon, -180, +180)
        max_lon = _clip(bounds.max_longitude + buff_lon, -180, +180)
        lon_range = max_lon - min_lon

        # Determine longitude coordinates.
        row_width = lon_range * m_per_deg_lon
        col_count = _calculate_safe_count(row_width, delta)
        lons = _np.linspace(min_lon, max_lon, col_count).tolist()
        points.extend(_coords.LatLonPoint(lat, lon) for lon in lons)

    # Return points.
    return points


def make_box_grid(
    bounds: tuple[float, float, float, float],
    min_precision: float,
    acc: bool = False,
) -> list[_coords.BoxCoordinate]:
    """
    Generate a grid of LGRS or ACC boxes within geographic bounds.

    Parameters
    ----------
    bounds : GeographicBounds or other 4-float tuple
        The bounds for which to generate the grid.

    min_precision : float
        The minimum precision that the grid should have. If not a
    supported precision, the actual precision is rounded down. All
    boxes have the same precision.

    acc : bool, default=False
        Whether to use ACC. If `False`, LGRS is used.

    Returns
    -------
    boxes : list of lgrs.coords.BoxCoordinate instances
        A flat list of boxes. LPS and LTM boxes may be commingled.

    Examples
    --------
    >>> aoi = GeographicBounds(
    ...     min_longitude=20, min_latitude=20,
    ...     max_longitude=40, max_latitude=40
    ... )
    >>> boxes = make_box_grid(aoi, min_precision=25_000, acc=True)
    >>> len(boxes)
    602
    >>> import lgrs.coords
    >>> isinstance(boxes[0], lgrs.coords.LtmAccBox)
    """
    # Determine target precision.
    idx_plus_1 = int(_precision_array.searchsorted(min_precision, "right"))
    if idx_plus_1 == 0:
        raise TypeError(
            f"`min_precision` must be >= 1, not: {min_precision!r}"
        )
    precision = int(_precision_array[idx_plus_1 - 1])

    # Generate geographic sample point grid.
    # Note: Grid has sufficient density to ensure that all boxes at
    # desired precision are sampled.
    geo_bounds = GeographicBounds(*bounds)
    latlon_sample_points = _construct_latlon_grid(geo_bounds, precision)

    # Create boxes.
    if acc:
        func = _coords.LatLonPoint.to_acc
    else:
        func = _coords.LatLonPoint.to_lgrs
    box_set: set[_coords.BoxCoordinate] = {
        func(samp_pt).truncate(precision) for samp_pt in latlon_sample_points
    }

    # Filter any boxes that have no corner within bounds.
    box_list = []
    for box in box_set:
        for corner in box.corners_latlon:
            if corner in geo_bounds:
                box_list.append(box)
                break
    box_list.sort(key=lambda b: b.string)
    return box_list


# TODO: Implement `LgrsGeoDataFrame` to better document `.name_hint`.
def make_gdfs(
    boxes: _collections.abc.Sequence[_coords.BoxCoordinate],
) -> dict[str, _geopandas.GeoDataFrame]:
    """
    Create one or more `GeoDataFrame` instances from a sequence of boxes.

    Each `GeoDaraFrame` will have a unique coordinate reference system
    (CRS).

    Parameters
    ----------
    boxes : sequence of lgrs.coords.BoxCoordinates instances
        The boxes to collect into `gdfs`.

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
    >>> boxes = make_box_grid(aoi, min_precision=25_000, acc=True)
    >>> gdfs = make_gdfs(boxes)
    >>> len(gdfs)
    4
    >>> [gdf.crs_name for gdf in gdfs]  # doctest: +NORMALIZE_WHITESPACE
    ['LTM_25N_polygon_grid', 'LTM_26N_polygon_grid',
     'LTM_27N_polygon_grid', 'LTM_28N_polygon_grid']
    >>> import geopandas
    >>> isinstance(gdfs[0], geopandas.GeoDataFrame)
    True
    """
    # Organize boxes by CRS.
    crs_to_boxes = _collections.defaultdict(list)
    for box in boxes:
        crs_to_boxes[box.crs_nominal].append(box)

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
    for crs, boxes in crs_to_boxes.items():
        data = {field_name: [] for field_name in field_names_view}
        for box in boxes:
            for field_name in field_names_view:
                data[field_name].append(box.field_data.get(field_name))
        data["geometry"] = [box.geometry for box in boxes]
        gdf = _geopandas.GeoDataFrame(data, crs=crs)
        if crs.lps_hemisphere is not None:
            name_hint = f"LPS_{crs.lps_hemisphere}_polygon_grid"
        else:
            name_hint = f"LTM_{crs.ltm_zone}_polygon_grid"
        gdf.name_hint = name_hint
        gdfs.append(gdf)
    return gdfs


# TODO: Remove after proper tests are implemented.
if __name__ == "__main__":
    # Note: Three demos given below, in order of increasing output size.
    # You must delete the "out" directory between demo executions.
    bounds = GeographicBounds(
        min_longitude=12, min_latitude=79, max_longitude=20, max_latitude=81
    )
    bounds = GeographicBounds(
        min_longitude=0, min_latitude=-88, max_longitude=170, max_latitude=88
    )
    bounds = GeographicBounds(
        min_longitude=-175,
        min_latitude=-89,
        max_longitude=+175,
        max_latitude=+89,
    )
    boxes = make_box_grid(bounds, min_precision=25_000, acc=True)
    gdfs = make_gdfs(boxes)
    import pathlib

    out_dir_path = pathlib.Path("out")
    out_dir_path.mkdir(parents=True, exist_ok=False)
    for gdf in gdfs:
        out_path = out_dir_path / f"{gdf.name_hint}.gpkg"
        gdf.to_file(out_path, index=True)
