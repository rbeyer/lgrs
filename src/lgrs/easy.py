"""High-level convenience functions for coordinate transformations."""

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

# Internal.
import lgrs.grid as _grid
import lgrs.srs.srs as _srs


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
    out_layer: str | None = None,
    *,
    acc: bool = False,
    extended_ltm: bool = False,
) -> None:
    """
    Write out an LGRS or ACC box grid to one or more files.

    Parameters
    ----------
    bounds : 4-float tuple, string, or path
        Sets the geographic bounds of the grid. May be specified in the
        following ways:
          (1) a 4-float tuple giving, as degrees,
              (min_lon, min_lat, max_lon, max_lat)
          (2) a string giving the short name for an LGRS CRS, such as "S"
              for the LPS south polar region and "23N" for LTM zone 23 in
              the Northern Hemisphere. This option generates all boxes
              within the specified region.
          (3) a path to a vector or raster file whose approximate
              geographic bounds will be used. You may treat a layer as
              a virtual path: `"path/to/my.gpkg/layer_name"`.
    precision : float
        The required precision of the grid. If not a supported precision,
        the actual precision is rounded down to a better precision. All
        boxes will have the same precision.
    out_path : string or pathlib.Path
        The output file path. May contain `"{}"` as a placeholder, which
        will be replaced with an automatically generated descriptive name
        that ensures uniqueness among the outputs of this call. If the
        parent directory of `out_path` does not exist, it will be created.
    out_layer : string or pathlib.Path, optional
        The output layer name, if any. May contain `"{}"` as a placeholder,
        which will be replaced with an automatically generated descriptive
        name that ensures uniqueness among the outputs of this call. If
        `out_path` is a GeoPackage, each output layer will be appended to
        it; the GeoPackage will also be created, if necessary.
    acc : bool, default=False
        Whether to use Artemis Condensed Coordinates (ACC) rather than the
        standard Lunar Grid Reference System (LGRS). The geometry of the
        boxes in each case are identical but the field data differ.
    extended_ltm : bool, default=False
        Whether to use the extended LTM region, which extends to 82° N/S
        instead of 80° N/S.

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If neither `out_path` nor `out_layer` contain the `"{}"`
        placeholder and `bounds` is not an LGRS CRS short name. In that
        case, a name collision is risked.
    """
    # Resolves bounds.
    if isinstance(bounds, str):
        try:
            _srs.make_lunar_crs(bounds)
        except TypeError:
            bounds = _pathlib.Path(bounds)
    match bounds:
        case _pathlib.Path():
            geo_bounds = _grid.GeographicBounds.from_path(bounds)
        case str():
            geo_bounds = bounds
        case _:
            geo_bounds = _grid.GeographicBounds.from_other(bounds)

    # Process `out_*` arguments.
    if isinstance(out_path, str):
        out_path = _pathlib.Path(out_path)  # *REASSIGNMENT*
    expect_exactly_one_crs = "{}" not in out_path.name and (
        out_layer is None or "{}" not in out_layer
    )
    # TODO: Could eventually support output to a single file generally
    #  by using a geographic CRS and densification.
    if expect_exactly_one_crs and not isinstance(geo_bounds, str):
        raise TypeError("`out_path.name` must contain '{}'")

    # Generate grid `GeoDataFrame`(s).
    boxes = _grid.make_box_grid(
        geo_bounds, precision=precision, acc=acc, extended_ltm=extended_ltm
    )
    gdfs = _grid.make_gdfs(boxes)

    # Output each `GeoDataFrame`.
    out_dir_path = out_path.parent
    out_name = out_path.name
    out_dir_path_exists = out_dir_path.exists()
    for gdf in gdfs:
        out_path = out_dir_path / out_name.format(gdf.name_hint)
        to_file_kwargs = {
            "filename": out_path,
            "index": True,
            "mode": "a" if out_path.exists() else "w",
        }
        if out_layer is not None:
            to_file_kwargs["layer"] = out_layer.format(gdf.name_hint)
        # Note: Wait to create out directory until necessary.
        if not out_dir_path_exists:
            out_dir_path.mkdir()
            out_dir_path_exists = True
        gdf.to_file(**to_file_kwargs)


# endregion


if __name__ == "__main__":
    shp_path = _pathlib.Path(
        "/home/eis/SETI Institute Dropbox/Ethan Schaefer/Lunar_Foundation_Model/ShadowCam/example_images/nac_dtm_byrd01_xml_ga.shp"
    )
    tif_path = _pathlib.Path(
        "/home/eis/SETI Institute Dropbox/Ethan Schaefer/Lunar_Foundation_Model/ShadowCam/example_images/NAC_DTM_BYRD01.tiff"
    )
    write_grid(
        shp_path,
        1_000,
        "/home/eis/PycharmProjects/lgrs/src/lgrs/out3/{}.gpkg",
        acc=False,
        extended_ltm=True,
    )
    # write_grid(
    #     tif_path,
    #     100,
    #     "/home/eis/PycharmProjects/lgrs/src/lgrs/out4/{}.gpkg",
    #     acc=True,
    #     extended_ltm=True,
    # )
    # write_grid(
    #     (1, 1, 2, 2),
    #     100,
    #     "/home/eis/PycharmProjects/lgrs/src/lgrs/out5/{}.gpkg",
    #     acc=False,
    #     extended_ltm=False,
    # )
    write_grid(
        (1, 1, 1.1, 1.1),
        10,
        "/home/eis/PycharmProjects/lgrs/src/lgrs/out6/{}.gpkg",
        acc=False,
        extended_ltm=False,
    )
    write_grid(
        (1, 1, 2, 2),
        1_000,
        "/home/eis/PycharmProjects/lgrs/src/lgrs/out7/{}.gpkg",
        acc=False,
        extended_ltm=False,
    )
    write_grid(
        (1, 1, 1.01, 1.01),
        1,
        "/home/eis/PycharmProjects/lgrs/src/lgrs/out8/{}.gpkg",
        acc=True,
        extended_ltm=True,
    )
    write_grid(
        (1, 1, 2, 2),
        25_000,
        "/home/eis/PycharmProjects/lgrs/src/lgrs/out9/{}.gpkg",
        acc=False,
        extended_ltm=True,
    )
    write_grid(
        (1, 1, 2, 2),
        1_000,
        "/home/eis/PycharmProjects/lgrs/src/lgrs/out10/{}.gpkg",
        acc=False,
        extended_ltm=True,
    )
