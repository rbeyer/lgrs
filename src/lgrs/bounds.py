"""Simple spatial bounding boxes."""

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
import functools as _functools
import pathlib as _pathlib
import re as _re
import typing as _typing

# External.
import geopandas as _geopandas
import numpy as _np
import pyproj as _pyproj
import pyproj.aoi as _pyproj_aoi
import rasterio as _rasterio
import shapely as _shapely

# Internal.
import lgrs.caching as _caching
import lgrs.database as _database
import lgrs.srs.srs as _srs
import lgrs.srs.wkt as _wkt
import lgrs.values as _values

# endregion
###############################################################################
# region> TYPE ALIASES
###############################################################################
type CrsHint = _pyproj.CRS | str | None


# endregion
###############################################################################
# region> UTILITIES
###############################################################################
def _make_crit_array(
    num_or_iter: float | _collections.abc.Iterable,
) -> _np.ndarray:
    if isinstance(num_or_iter, _collections.abc.Iterable):
        iterable = num_or_iter
    else:
        iterable = (-num_or_iter, num_or_iter)
    a = _np.fromiter(iterable, dtype=_np.float64)
    return a


def _resolve_file_path_and_open_kwargs(
    path: _pathlib.Path | str,
) -> tuple[_pathlib.Path, dict[str, str]]:
    if not isinstance(path, _pathlib.Path):
        path = _pathlib.Path(path)  # *REASSIGNMENT*
    if path.parts[0] == "~":
        path = path.expanduser()  # *REASSIGNMENT*
    match = _re.search(
        r"(?P<path>.+)\|(?P<kw>[a-z]+)=(?P<kwarg>.+)", path.name
    )
    kwargs = {}
    if match is None:
        file_path = path
    else:
        file_path = path.with_name(match.group("path"))
        kwargs[match.group("kw")] = match.group("kwarg")
    return (file_path, kwargs)


def resolve_crs(crs_hint: CrsHint) -> _pyproj.CRS:
    """
    Resolve a `pyproj.CRS` instance from a hint.

    Parameters
    ----------
    crs_hint : pyproj.CRS, string, or None
        A hint for the desired CRS. This may be a `CRS` instance, a string
        suitable for `lgrs.make_lunar_crs()` or
        `pyproj.CRS.from_user_input()`, or `None`, in which case
        IAU_2015:30100 is assumed.

    Returns
    -------
    crs : pyproj.CRS
        The resolved CRS.

    Raises
    ------
    pyproj.exceptions.CRSError
        If `crs_hint` cannot be resolved.
    """
    if isinstance(crs_hint, _pyproj.CRS):
        crs = crs_hint
    else:
        try:
            crs = _srs.make_lunar_crs(crs_hint)
        except TypeError:
            crs = _pyproj.CRS(crs_hint)
    return crs


# endregion
###############################################################################
# region> NAMED TUPLE
###############################################################################
class BoundsTuple(_typing.NamedTuple):
    left: float
    bottom: float
    right: float
    top: float


# endregion
###############################################################################
# region> BASE CLASS
###############################################################################
@_dataclasses.dataclass(frozen=True)
class _Base:
    def _iter_first_four_field_values(self) -> _typing.Iterator:
        for i, field in enumerate(self._get_fields()):
            if i == 4:
                break
            yield getattr(self, field.name)

    @_functools.cached_property
    def _field_dict(self) -> dict[str, _typing.Any]:
        return {
            field.name: getattr(self, field.name)
            for field in self._get_fields()
        }

    @classmethod
    @_functools.cache
    def _get_fields(cls) -> tuple[_dataclasses.Field, ...]:
        return tuple(_dataclasses.fields(cls))


# endregion
###############################################################################
# region> BOUNDS CLASSES
###############################################################################
class _BaseBounds(_Base):
    crs: _srs.CRS | _pyproj.CRS

    # * INITIALIZATION & INSTANTIATION. ───────────────────────────────
    def __post_init__(self):
        self._validate()

    def _validate(self) -> None:
        (
            (min_x_name, min_x),
            (min_y_name, min_y),
            (max_x_name, max_x),
            (max_y_name, max_y),
            *_,
        ) = self._field_dict.items()
        logical_min_x, logical_min_y, logical_max_x, logical_max_y = (
            self.logical
        )
        for (
            min_name,
            min_val,
            logical_min_val,
            max_name,
            max_val,
            logical_max_val,
        ) in (
            (
                min_x_name,
                min_x,
                logical_min_x,
                max_x_name,
                max_x,
                logical_max_x,
            ),
            (
                min_y_name,
                min_y,
                logical_min_y,
                max_y_name,
                max_y,
                logical_max_y,
            ),
        ):
            if logical_min_val >= logical_max_val:
                if logical_max_val == max_val:
                    max_val_desc = logical_max_val
                else:
                    max_val_desc = f"{logical_max_val}, from {max_val}"
                if logical_min_val == min_val:
                    min_val_desc = logical_min_val
                else:
                    min_val_desc = f"{logical_min_val}, from {min_val}"
                raise TypeError(
                    f"`{max_name}` ({max_val_desc}) must be greater than "
                    f"`{min_name}` ({min_val_desc})."
                )

    @classmethod
    def from_path(
        cls,
        path: _pathlib.Path | str,
        *,
        fallback_to_geo: bool = False,
    ) -> GeographicBounds | ProjectedBounds:
        """
        Create a bounds instance from the footprint of a vector or raster file.

        Parameters
        ----------
        path :
            Path to a vector or raster file whose approximate bounds will be
            used. You may specify a layer or table by the convention:
            ``"path/to/my.gpkg|layer=layer_name"`` or
            ``"path/to/my.gpkg|table=table_name"``.
        fallback_to_geo: bool, default=False
            Specifies the behavior when the CRS of `path` cannot be transformed
            to the geographic CRS IAU_2015:30100. If `True` and that CRS can be
            transformed to some geographic CRS, that geographic CRS is assumed
            equivalent to IAU_2015:30100. If `True` but no CRS can be
            identified for `path`, the coordinates are assumed to already be in
            IAU_2015:30100, with order (lat, lon). In all other cases, an
            exception is raised.

        Returns
        -------
        bounds : GeographicBounds or ProjectedBounds
            The bounds instance.

        Raises
        ------
        TypeError
            If `path` cannot be found or cannot be read.
        pyproj.ProjError
            If CRS cannot be transformed to IAU_2015:30100, even after applying
            `fallback_to_geo` behavior, if enabled.
        """
        # Determine CRS and bounds in that CRS.
        file_path, open_kwargs = _resolve_file_path_and_open_kwargs(path)
        if not file_path.exists():
            raise TypeError(f"Path could not be found: {file_path}")
        try:
            gdf = _geopandas.read_file(file_path, **open_kwargs)
        except Exception:
            try:
                with _rasterio.open(path, **open_kwargs) as src:
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

        # Ensure that CRS if compatible, if possible.
        if native_crs is None:
            if fallback_to_geo:
                native_crs = _srs.make_lunar_crs()  # *REASSIGNMENT*
            else:
                raise _pyproj.ProjError(
                    f"CRS for `path` could not be determined: {path}"
                )
        else:
            try:
                _srs.get_transformer(
                    native_crs, _srs.make_lunar_crs(), always_xy=True
                )
            except _pyproj.ProjError as e:
                if not fallback_to_geo:
                    raise e
                src_geo_crs = native_crs.geodetic_crs
                if src_geo_crs is None:
                    raise e
                transformer: _pyproj.Transformer = _srs.get_transformer(
                    native_crs, src_geo_crs, always_xy=True
                )
                # *REASSIGNMENT*
                native_bounds = transformer.transform_bounds(*native_bounds)
                native_crs = _srs.make_lunar_crs()  # *REASSIGNMENT*

        # Instantiate and return.
        if native_crs == _srs.make_lunar_crs():
            bounds = GeographicBounds(*native_bounds)
        else:
            bounds = ProjectedBounds(*native_bounds, crs_hint=native_crs)
        return bounds

    # * BASIC BEHAVIOR. ───────────────────────────────────────────────
    def __iter__(self) -> _typing.Iterator[float]:
        for v in self._iter_first_four_field_values():
            yield v

    # * PUBLIC DATA & METHODS. ────────────────────────────────────────
    @_caching._optionally_cache
    def in_crs(
        self,
        crs_hint: CrsHint = None,
        *,
        densify_count: int = 21,
    ) -> GeographicBounds | ProjectedBounds:
        """
        Get `*Bounds` instance in specified CRS.

        Parameters
        ----------
        crs_hint : pyproj.CRS, string, or None, default=None
            A hint for the CRS of `out_bounds`. This may be a `CRS` instance, a
            string suitable for `lgrs.make_lunar_crs()` or
            `pyproj.CRS.from_user_input()`, or `None`, in which case
            IAU_2015:30100 is assumed.
        densify_count : int, default=21
            The number of samples that are added to each edge prior to
            transformation. Having more samples helps ensure that the
            transformation of the bounding box is more precise, but higher
            values will decrease performance.

        Returns
        -------
        out_bounds : GeographicBounds or ProjectedBounds
            The output bounds. If ``self.crs == crs``, `self` is returned.
        """
        crs = resolve_crs(crs_hint)
        if crs == self.crs:
            return self
        transformer: _pyproj.Transformer = _srs.get_transformer(
            self.crs, crs, always_xy=True
        )
        bounds_tup = transformer.transform_bounds(
            *self, densify_pts=densify_count
        )
        if crs == _srs.make_lunar_crs():
            bounds = GeographicBounds(*bounds_tup)
        else:
            bounds = ProjectedBounds(*bounds_tup, crs_hint=crs)
        return bounds

    @_functools.cached_property
    def geometry(self) -> _shapely.Polygon:
        return _shapely.box(*self)

    @_functools.cached_property
    def logical(self) -> BoundsTuple:
        return BoundsTuple(*self)

    @_functools.cached_property
    def median_xy(self) -> tuple[float, float]:
        left, bottom, right, top = self.logical
        mid_x = (left + right) / 2
        mid_y = (top + bottom) / 2
        return (mid_x, mid_y)

    @_functools.cached_property
    def parts(
        self,
    ) -> tuple[BoundsTuple]:
        return (BoundsTuple(*self),)


@_dataclasses.dataclass(frozen=True)
class GeographicBounds(_BaseBounds):
    """
    Create an instance describing a geographic bounding box (envelope).

    Parameters
    ----------
    left : float
        The left longitude, in degrees.
    bottom : float
        The bottom latitude, in degrees.
    right : float
        The right longitude, in degrees.
    top : float
        That top latitude, in degrees.

    Attributes
    ----------
    area_of_interest : pyproj.aoi.AreaOfInterest
        `.conformed` as an area of interest.
    crs : pyproj.CRS
        The IAU_2015:30100 CRS.
    brackets_antimeridian : bool
        Whether bounds bracket the antimeridian (±180°). Note that bounds
        that wrap to span all longitudes are not considered to bracket the
         antimeridian.
    conformed : 4-float BoundsTuple
        Similar to ``tuple(self)`` but a `BoundsTuple` (named tuple) whose
        longitudes are conformed to the interval [-180, +180).
    geometry : shapely.Polygon
        The shapely polygon form of the bounds.
    logical : 4-float BoundsTuple
        For bounds bracketing the antimeridian, `logical.left` and
        `logical.right` are conformed to the interval [-360, +360] so that
         `logical.right > logical.left`. Otherwise, equivalent to
         `.conformed`.
    median_xy : tuple[float, float]
        The median longitude and latitude, respectively, calculated from
        `.logical`. The longitude is then conformed to the interval [-180,
        +180).
    parts : tuple of one or two 4-float BoundsTuples
        For bounds bracketing the antimeridian, each 4-float `tuple`
        represents the box on either side of the antimeridian. Otherwise,
        there is a single 4-float `tuple` equivalent to `.conformed`.

    Raises
    ------
    TypeError
        If values are invalid. Namely, if the absolute value of any
        longitude exceeds 360, the absolute value of any latitude exceeds
        90, or the range implied by the minimum and maximum longitudes
        exceeds 360.

    Examples
    --------
    >>> bounds_1 = GeographicBounds(10, 10, 20, 20)

    To specify bounds that cross the antimeridian, either use longitudes
    outside the standard interval [-180, 180] (but within [-360, 360]) or
    specify `left` greater than `right`.

    >>> bounds_2 = GeographicBounds(-190, 10, -170, 20)
    >>> bounds_3 = GeographicBounds(170, 10, 190, 20)
    >>> bounds_4 = GeographicBounds(170, 10, -170, 20)
    >>> bounds_2.logical == bounds_3.logical
    True
    >>> bounds_3.logical == bounds_4.logical
    True

    If either pole lies within the bounds, the bounds must be specified
    equatorward from that pole. Hence:

    >>> bounds_5 = GeographicBounds(-180, 87, 180, 90)

    Or, equivalently:

    >>> all_bounds_5 = GeographicBounds.from_north_pole_to(87)
    """

    left: float
    bottom: float
    right: float
    top: float
    crs: _typing.ClassVar[_srs.CRS] = _srs.make_lunar_crs()

    # * INITIALIZATION & INSTANTIATION. ───────────────────────────────
    def _validate(self):
        super()._validate()
        for field_name, field_val in self._field_dict.items():
            match field_name:
                case "left" | "right":
                    max_abs = 360
                case "bottom" | "top":
                    max_abs = 90
                case _:
                    continue
            if abs(field_val) > max_abs:
                raise TypeError(
                    f"Absolute value of `{field_name}` must be <={max_abs}, "
                    f"not: {field_val!r}>"
                )
        if self.right - self.left > 360:
            raise TypeError(
                "The difference between `right` and `left` cannot exceed 360."
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
    def from_area(
        cls,
        area: _pyproj_aoi.AreaOfInterest | _pyproj_aoi.AreaOfUse,
    ) -> _typing.Self:
        """
        Create `GeographicBounds` from `pyproj` area of interest or use.

        Parameters
        ----------
        area : AreaOfInterest or AreaOfUse
            A `pyproj.aoi.AreaOfInterest` or `pyproj.aoi.AreaOfUse`.

        Returns
        -------
        bounds : GeographicBounds
            The `GeographicBounds` instance.
        """
        match area:
            case _pyproj_aoi.AreaOfUse():
                return cls(*tuple(area)[:4])
            case _pyproj_aoi.AreaOfInterest():
                return cls(
                    area.west_lon_degree,
                    area.south_lat_degree,
                    area.east_lon_degree,
                    area.north_lat_degree,
                )
            case _:
                raise TypeError(f"Unsupported type for `area`: {area!r}.")

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

    # * CRITICAL LATITUDES & LONGITUDES. ──────────────────────────────
    # Note: The equator is not "critical" for these purposes, because
    # LTM boxes mate there precisely, without overlap.
    _crit_lats_extended_ltm_array = _make_crit_array(
        _wkt.LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
    )
    _crit_lats_unextended_ltm_array = _make_crit_array(
        _wkt.LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE
    )
    _crit_ltm_lons_array = _make_crit_array(range(-356, 361, 8))

    # Note: Type-hinting `coords.Constraints` would cause circular
    # import in Python <= 3.13.
    def _get_critical_latitudes(
        self,
        constraints: _typing.Any,
    ) -> list[float] | None:
        if constraints.extended_ltm:
            crit_array = self._crit_lats_extended_ltm_array
        else:
            crit_array = self._crit_lats_unextended_ltm_array
        sliced_array = self._slice_array_by_interval_ends(
            crit_array,
            self.logical.bottom,
            self.logical.top,
        )
        if sliced_array is None:
            return None
        final = sliced_array.tolist()
        sliced_array[sliced_array < 0] += _values.DEGREE_EPSILON
        sliced_array[sliced_array > 0] -= _values.DEGREE_EPSILON
        final.extend(sliced_array.tolist())
        final.sort()
        if final[0] < self.logical.bottom:
            del final[0]
        if final[-1] > self.logical.top:
            del final[-1]
        return final

    # Note: Type-hinting `coords.Constraints` would cause circular
    # import in Python <= 3.13.
    def _get_critical_longitudes(
        self,
        constraints: _typing.Any,
    ) -> list[float] | None:
        # Note: If in exclusively LPS latitudes, there are no critical
        # longitudes.
        if self.logical.bottom > constraints._max_abs_ltm_lat:
            return None
        elif self.logical.top < -constraints._max_abs_ltm_lat:
            return None
        sliced_array = self._slice_array_by_interval_ends(
            self._crit_ltm_lons_array,
            self.logical.left,
            self.logical.right,
        )
        if sliced_array is None:
            return None
        final = sliced_array.tolist()
        sliced_array -= _values.DEGREE_EPSILON
        # Note: Reverse slice so that smallest value is at the end of
        # the list, for more performant removal, if necessary.
        final.extend(sliced_array[::-1].tolist())
        if final[-1] < self.logical.left:
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

    # * PUBLIC DATA. ──────────────────────────────────────────────────
    @_functools.cached_property
    def area_of_interest(self) -> _pyproj_aoi.AreaOfInterest:
        return _pyproj_aoi.AreaOfInterest(*self.conformed)

    @_functools.cached_property
    def brackets_antimeridian(self) -> bool:
        return self.conformed.right < self.conformed.left

    @_functools.cached_property
    def conformed(self) -> BoundsTuple:
        left, bottom, right, top = self
        c_left = _database._conform_longitude(left)
        c_right = _database._conform_longitude(right)
        if c_left == c_right:
            c_left = -180  # *REASSIGNMENT*
            c_right = +180  # *REASSIGNMENT*
        return BoundsTuple(c_left, bottom, c_right, top)

    @_functools.cached_property
    def is_global(self) -> bool:
        return all(
            (
                self.conformed.right - self.conformed.left == 360,
                self.conformed.top - self.conformed.bottom == 180,
            )
        )

    @_functools.cached_property
    def logical(self) -> BoundsTuple:
        if self.brackets_antimeridian:
            c_left, c_bottom, c_right, c_top = self.conformed
            lon_delta = (c_right - c_left) + 360
            cand_log_right = c_left + lon_delta
            if cand_log_right > 360:
                log_left = c_right - lon_delta
                log_right = c_right
            else:
                log_left = c_left
                log_right = cand_log_right
            return BoundsTuple(log_left, c_bottom, log_right, c_top)
        else:
            return self.conformed

    @_functools.cached_property
    def median_xy(self) -> tuple[float, float]:
        ctr_x, ctr_y = super().median_xy
        c_ctr_x = _database._conform_longitude(ctr_x)
        return (c_ctr_x, ctr_y)

    @_functools.cached_property
    def parts(
        self,
    ) -> tuple[BoundsTuple, ...]:
        if self.brackets_antimeridian:
            c_left, c_bottom, c_top, c_right = self.conformed
            return (
                BoundsTuple(c_left, c_bottom, +180, c_top),
                BoundsTuple(-180, c_bottom, c_right, c_top),
            )
        else:
            return (self.conformed,)


@_dataclasses.dataclass(frozen=True)
class ProjectedBounds(_BaseBounds):
    """
    Create an instance describing a projected bounding box (envelope).

    Parameters
    ----------
    min_easting : float
        The minimum easting.
    min_northing : float
        The minimum northing.
    max_easting : float
        The maximum easting.
    max_northing : float
        The maximum northing.
    crs_hint : pyproj.CRS, string, or None
        A hint for the desired CRS. This may be a `CRS` instance, a string
        suitable for `lgrs.make_lunar_crs()` or
        `pyproj.CRS.from_user_input()`, or `None`, in which case
        IAU_2015:30100 is assumed.

    Attributes
    ----------
    crs : pyproj.CRS
        The CRS resolved from `crs_hint`.
    logical : 4-float BoundsTuple
        Equivalent to ``BoundsTuple(*self)``. Included for compatibility
        with `GeographicBounds`.
    median_xy : tuple[float, float]
        The median easting and northing, respectively.
    parts : tuple containing a 4-float BoundsTuple
        Equivalent to ``(self.logical,)``. Included for compatibility
        with `GeographicBounds`.

    Raises
    ------
    TypeError
        If values are invalid. Namely, if any maximum is not greater than
        its counterpart minimum.
    """

    min_easting: float
    min_northing: float
    max_easting: float
    max_northing: float
    _: _dataclasses.KW_ONLY
    crs_hint: CrsHint

    @_functools.cached_property
    def crs(self) -> _srs.CRS | _pyproj.CRS:
        return resolve_crs(self.crs_hint)
