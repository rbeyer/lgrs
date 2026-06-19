"""High-level convenience functions."""

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
import enum as _enum
import pathlib as _pathlib
import typing as _typing

# Internal.
import lgrs.bounds as _bounds
import lgrs.grid as _grid


# endregion
###############################################################################
# region> ENUMERATIONS
###############################################################################
class Format(_enum.StrEnum):
    LAT_LON = _enum.auto()
    LON_LAT = _enum.auto()
    LPS_OR_LTM = _enum.auto()
    LGRS = _enum.auto()
    ACC = _enum.auto()
    ACC_FULL = _enum.auto()


class Region(_enum.StrEnum):
    POLAR = _enum.auto()
    NONPOLAR = _enum.auto()
    ANY = _enum.auto()


class Type(_enum.StrEnum):
    LABELED = _enum.auto()
    STRING = _enum.auto()
    PRETTY = _enum.auto()


# endregion
###############################################################################
# region> UTILITIES
###############################################################################
def _test_mode(path: _pathlib.Path, mode: str) -> str:
    match mode:
        case "x":
            if path.exists():
                raise TypeError(
                    f"Specified `mode='x'` but file path exists: {path}"
                )
            mode = "w"  # *REASSIGNMENT*
        case "a":
            if not path.exists():
                raise TypeError(
                    "Specified `mode='a'` but file path does not exist: "
                    f"{path}"
                )
        case "w":
            pass
        case _:
            raise TypeError(f"`mode` not supported: {mode!r}")
    return mode


# endregion
###############################################################################
# region> CONVENIENCE FUNCTIONS
###############################################################################
# def from_gridded(
#     string: str,
#     *,
#     fmt: Format = Format.LGRS,
#     typ: Type = Type.LABELED,
#     region: Region = Region.ANY,
#     extended_ltm: bool = False,
# ) -> tuple | str: ...
#
#
# def from_geographic(
#     latitude: float,
#     longitude: float,
#     *,
#     fmt: Format = Format.LGRS,
#     typ: Type = Type.LABELED,
#     region: Region = Region.ANY,
#     extended_ltm: bool = False,
# ) -> tuple | str: ...
#
#
# # TODO: Or could "cheat" and call this `from_projected()`, perhaps even
# #  replace-all "lps_or_ltm" ro "projected" across the package, with the
# #  understanding (as we'd state in the docs) that projected invariably
# #  means LPS or LTM in the package.
# def from_lps_or_ltm(
#     easting: float,
#     northing: float,
#     *,
#     fmt: Format = Format.LGRS,
#     typ: Type = Type.LABELED,
#     region: Region = Region.ANY,
#     extended_ltm: bool = False,
# ) -> tuple | str:
#     """
#     Convert from LPS or LTM coordinates.
#
#     Parameters
#     ----------
#     easting : float
#         Easting coordinate.
#     northing : float
#         Northing coordinate.
#     fmt : Format, default=Format.LGRS
#         The format of `converted`.
#     typ : Type, default=Type.LABELED
#         The type of `converted`.
#     region : Region, default=Region.ANY
#         Whether to enforce a polar or non-polar check.
#     extended_ltm : bool, default=False
#         Whether to use the extended LTM region (from 80 to 82 degrees).
#
#     Returns
#     -------
#     converted : tuple or str
#         A named tuple or string representing the converted coordinates.
#
#     Raises
#     ------
#     lgrs.exceptions.NonPolarError
#         If `region` requires the polar region but `converted` is not
#         poleward of 80 degrees (if `extended_ltm` is `False`) or 82 degrees
#         (if `extended_ltm` is `True`).
#     lgrs.exceptions.PolarError
#         If `region` requires the non-polar region but `converted` is
#         poleward of 80 degrees (if `extended_ltm` is `False`) or 82 degrees
#         (if `extended_ltm` is `True`).
#
#     """
#     # Examples
#     # --------
#     # >>> import lgrs.easy
#     # >>> lgrs.easy.from_lps_or_ltm(488590, 608480)
#     # (zone="A", area="ZS", easting=13590, northing=8480,
#     #  string="AZS1359008480")
#     # >>> lgrs.easy.from_lps_or_ltm(488590, 608480, typ=Type.STRING)
#     # "AZS1359008480"
#     # >>> lgrs.easy.from_lps_or_ltm(488590, 608480, typ=Type.PRETTY)
#     # "A ZS 13590 08480"
#
#     # """
#     # import sys
#     # _rich.print(
#     #   "[bold red]NonPolarError:[/bold red] Test.", file=sys.stderr,
#     #   flush=True
#     # )
#     ...


def write_grid(
    bounds: tuple[float, float, float, float] | str | _pathlib.Path,
    precision: float,
    out_path: _pathlib.Path | str,
    *,
    acc: bool = False,
    extended_ltm: bool = False,
    mode: _typing.Literal["x", "w", "a"] = "x",
    min_overlap: bool = True,
    min_zones: bool = False,
    fallback_to_geo: bool = False,
    densify_count: int = 21,
) -> None:
    """
    Write out an LGRS or ACC box grid to one or more files.

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
    out_path : string or pathlib.Path
        The output file path. You may specify a layer name by the
        convention: ``"path/to/my.gpkg|layer=layer_name"``. May contain `"{}"`
        as a placeholder (in file path and/or layer name portions), which will
        be replaced with an automatically generated descriptive name that
        ensures uniqueness among the outputs of this call. If the parent
        directory of `out_path` does not exist, it will be created. If
        `out_path` is a GeoPackage, each output layer will be appended to it;
        the GeoPackage will also be created, if necessary.
    acc : bool, default=False
        Whether to use Artemis Condensed Coordinates (ACC) rather than the
        standard Lunar Grid Reference System (LGRS). The geometry of the
        boxes in each case are identical but the field data differ.
    extended_ltm : bool, default=False
        Whether to use the extended LTM region, which extends to 82° N/S
        instead of 80° N/S.
    mode : "x", "w", or "a", default="x"
        The file write mode. ``"x"`` requires that the file to which
        `out_path` points (after resolution of any ``"{}"``) not preexist
        the call. ``"w"`` will create that file, overwriting if it preexists.
        ``"a"`` requires that the file preexist and appends to that file;
        if the layer also preexists, it is likewise appended to.
    min_overlap : bool, default=True
        Whether to reduce box overlap. If `True`, boxes only overlap near LPS
        and LTM zone boundaries, where overlap is necessary to ensure coverage.
        If `False`, all valid boxes in the targeted area are generated, which
        may include inter-zone overlaps of up to ~35.4 km, that is, the
        diagonal of a 25-km box. In the special case that `bounds` is specified
        by an LGRS CRS string, `min_overlap` is instead interpreted to relate
        to the overlap of that region with its neighbors. Then, `True`
        generates only boxes that are within the nominal bounds of the zone
        whereas `False` generates all valid boxes from the maximally expanded
        zone.
    min_zones : bool, default=False
        Whether to minimize the number of zones (and therefore, CRSs) that are
        used. If `True`, boxes from non-nominal (expanded) areas of zones may
        be generated if doing so enables fewer zones to be used overall. For
        example, when working near the nominal longitudinal boundary between
        two LTM zones, you may prefer all boxes to come from one zone, if
        possible, instead of nearly all boxes from that zone and a few from a
        neighboring zone.
    fallback_to_geo: bool, default=False
        Specifies the behavior when the CRS of a path-like `bounds` cannot
        be transformed to the geographic CRS IAU_2015:30100. If `True` and
        that CRS can be transformed to some geographic CRS, that geographic
        CRS is assumed equivalent to IAU_2015:30100. If `True` but no CRS
        can be identified for `path`, the coordinates are assumed to
        already be in IAU_2015:30100, with order (lat, lon). In all other
        cases, an exception is raised.
    densify_count : int, default=21
        Whenever a bounding box must be transformed between CRSs, this number
        of samples will be added to each edge prior to transformation. Having
        more samples helps ensure that the transformation of the bounding box
        is more precise, but higher values will decrease performance.

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If file state implied by `mode` is violated or the grandparent of
        `out_path` does not preexist. Also if `out_path` does not contain
        the ``"{}"`` placeholder and `bounds` is not an LGRS CRS short name.
        In that case, a name collision is risked if multiple CRSs generate
        multiple outputs.

    Warnings
    --------
    In the current implementation, the `True` option for `min_zones` has no
    effect unless `bounds` can be spanned by boxes from a single CRS.

    Examples
    --------
    >>> write_grid(  # doctest: +SKIP
    ...     (3, 3, 5, 5), 1_000, "~/grids/grid_1.gpkg|layer={}",  # doctest: +SKIP
    ...     acc=True  # doctest: +SKIP
    ... )  # doctest: +SKIP
    >>> write_grid("N", 25_000, r"C:\\my_grids\final_{}_Moon.shp")  # doctest: +SKIP
    >>> write_grid("path/to/craters.tif", 100, "~/grids/craters_{}.geojson")  # doctest: +SKIP
    """  # noqa: E501
    # Process `out_*` arguments.
    nom_out_path_template = _pathlib.Path(out_path)
    del out_path  # Avoid accidental use.
    out_file_path_template, open_kwargs = (
        _bounds._resolve_file_path_and_open_kwargs(nom_out_path_template)
    )
    if open_kwargs:
        ((layer_kw, layer_name),) = open_kwargs.items()
    else:
        layer_kw = None
    # Note: Satisfaction of `mode` expectations can only be evaluated
    # once the output file path is resolved.
    file_path_is_dynamic = "{}" in out_file_path_template.name
    if not file_path_is_dynamic:
        # *REASSIGNMENT*
        mode = _test_mode(out_file_path_template, mode)
    if not out_file_path_template.parent.parent.exists():
        raise TypeError(
            "The grandparent of `out_path` does not exist: "
            f"'{out_file_path_template.parent.parent}'"
        )

    # Verify required uniqueness.
    expect_exactly_one_crs = "{}" not in nom_out_path_template.name
    # TODO: Could eventually support output to a single file generally
    #  by using a geographic CRS and densification.
    if expect_exactly_one_crs:
        _, exclusive_crs = _grid._resolve_bounds(**locals())
        if exclusive_crs is None:
            raise TypeError("`out_path.name` must contain '{}'")

    # Generate grid `GeoDataFrame`(s).
    boxes = _grid.make_box_grid(
        bounds,
        precision=precision,
        acc=acc,
        extended_ltm=extended_ltm,
        min_overlap=min_overlap,
        min_zones=min_zones,
        fallback_to_geo=fallback_to_geo,
        densify_count=densify_count,
    )
    gdfs = _grid.make_gdfs(boxes)

    # Output each `GeoDataFrame`.
    out_dir_path = out_file_path_template.parent
    out_file_name_template = out_file_path_template.name
    out_dir_path_exists = out_dir_path.exists()
    for gdf in gdfs:
        gdf_out_path = out_dir_path / out_file_name_template.format(
            gdf.name_hint
        )
        if file_path_is_dynamic:
            mode = _test_mode(gdf_out_path, mode)  # *REASSIGNMENT*
        to_file_kwargs = {
            "filename": gdf_out_path,
            "index": True,
            "mode": mode,
        }
        if layer_kw is not None:
            to_file_kwargs[layer_kw] = layer_name.format(gdf.name_hint)
        # Note: Wait to create out directory until necessary.
        if not out_dir_path_exists:
            out_dir_path.mkdir()
            out_dir_path_exists = True
        gdf.to_file(**to_file_kwargs)


# endregion
