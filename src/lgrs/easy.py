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
import collections as _collections
import enum as _enum
import functools as _functools
import inspect as _inspect
import json as _json
import pathlib as _pathlib
import re as _re
import types as _types
import typing as _typing

# Internal.
import lgrs.bounds as _bounds
import lgrs.database as _database
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
class _Adapter:
    def __init__(self, func: _types.FunctionType):
        self.func = func

    # * DATA ATTRIBUTES. ──────────────────────────────────────────────
    @_functools.cached_property
    def annotations(self) -> dict[str, _typing.Any]:
        return self.func.__annotations__.copy()

    @_functools.cached_property
    def docstring(self) -> str:
        self._set_clean_docstring(self.func.__doc__)
        return self.docstring

    # * UTILITIES. ────────────────────────────────────────────────────
    @staticmethod
    def _process_section_count(title: str, count: int) -> None:
        match count:
            case 1:
                return
            case 0:
                raise TypeError(f"Section not found for: {title!r}")
            case _:
                raise TypeError(f"Multiple sections found for: {title!r}")

    def _set_clean_docstring(self, raw_docstring: str) -> None:
        # Note: Collapse any sequences of 2+ empty/space-only lines to 1
        # empty line.
        clean_doc = _re.sub(r"(?m)(^ *\n){2,}", r"\n", raw_docstring).strip()
        self.docstring = clean_doc

    # * PUBLIC FUNCTIONS. ─────────────────────────────────────────────
    def add_to_notes(self, addition: str, *, prepend: bool = False) -> None:
        # Peel back each section that can follow Notes, in reverse
        # order.
        later_section_blocks = []
        for sec_title in ("Examples", "References"):
            sec_block_match = self.get_doc_section_match(
                sec_title, error=False
            )
            if sec_block_match is None:
                continue
            if sec_block_match.end() != len(self.docstring):
                raise TypeError(
                    "`.docstring` unexpectedly does not end with "
                    f"{sec_title!r} section."
                )
            sec_block = sec_block_match.group()
            later_section_blocks.append(sec_block)
            self.docstring = self.docstring[: sec_block_match.start()].rstrip()

        # Extract Notes section and body, or add stub, if necessary.
        notes_block_match = self.get_doc_section_match("Notes", error=False)
        if notes_block_match is None:
            self.docstring += "\n\nNotes\n-----\n..."
            old_notes_body = ""
        else:
            old_notes_body = notes_block_match.group("body").rstrip()

        # Replace Notes section with updated body.
        if prepend:
            new_notes_body = f"{addition}\n\n{old_notes_body}"
        else:
            new_notes_body = f"{old_notes_body}\n\n{addition}"
        self.replace_doc_section("Notes", new_notes_body)

        # Add back any terminal sections.
        if later_section_blocks:
            self._set_clean_docstring(
                r"\n\n".join((self.docstring, *later_section_blocks))
            )

    def get_doc_section_match(
        self, title: str, *, error: bool = True
    ) -> _re.Match | None:
        pattern = self.get_doc_section_pattern(title)
        matches = tuple(pattern.finditer(self.docstring))
        if not error and not matches:
            return None
        self._process_section_count(title, len(matches))
        (match,) = matches
        return match

    @staticmethod
    @_functools.cache
    def get_doc_section_pattern(title: str) -> _re.Pattern:
        pattern = _re.compile(
            rf"(?ms)^{title} *\n-+ *\n(?P<body>.*?(\Z|(^ *$)))"
        )
        pattern = _re.compile(rf"(?ms)^{title} *$.*?((^ *$)|\Z)")
        return pattern

    def make_new_func(self) -> _types.FunctionType:
        func = self.func
        new = _types.FunctionType(
            func.__code__,
            func.__globals__,
            func.__name__,
            func.__defaults__,
            func.__closure__,
        )
        _functools.update_wrapper(new, func)
        del new.__wrapped__
        new.__annotations__ = self.annotations
        new.__doc__ = self.docstring
        new.__kwdefaults__ = func.__kwdefaults__
        return new

    def replace_doc_section(self, title: str, new: str = "") -> None:
        pattern = self.get_doc_section_pattern(title)
        if new:
            full_new = "\n".join((title, "-" * len(title), new))
        else:
            full_new = ""
        raw_doc, sub_count = pattern.subn(full_new, self.docstring)
        self._process_section_count(title, sub_count)
        self._set_clean_docstring(raw_doc)


def _call_with_kwargs(
    func: _collections.abc.Callable,
    kwargs: dict[str, _typing.Any],
    *,
    defaults: dict[str, _typing.Any] | None = None,
    overrides: dict[str, _typing.Any] | None = None,
    used: set | None = None,
) -> _typing.Any:
    # Update set of used keys.
    if used is not None:
        used.update(kwargs)

    # Finalize `kwargs`.
    if defaults:
        new_kwargs = defaults.copy()
        new_kwargs.update(kwargs)
        kwargs = new_kwargs  # *REASSIGNMENT*
    if overrides:
        kwargs = kwargs.copy()  # *REASSIGNMENT*
        kwargs.update(overrides)
    sig = _inspect.signature(func)
    final_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

    # Call and return.
    return func(**final_kwargs)


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
    bounds: _typing.Any,
    precision: float,
    out_path: _pathlib.Path | str | None,
    *,
    acc: bool = False,
    extended_ltm: bool = False,
    mode: _typing.Literal["x", "w", "a"] = "x",
    min_overlap: bool = True,
    min_zones: bool = False,
    fallback_to_geo: bool = False,
    densify_count: int = 21,
    json_extras: bool = True,
    driver: str | None = None,
    **kwargs,
) -> dict[str, dict] | None:
    """
    Write out an LGRS or ACC box grid to file(s) or a GeoJSON-like `dict`.

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
            (4) short name (`str`) for an LGRS CRS
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
    out_path : string, pathlib.Path, or None
        The output file path, or `None` to return a GeoJSON-like `dict`. You
        may specify a layer name by the convention:
        ``"path/to/my.gpkg|layer=layer_name"``. May contain `"{}"` as a
        placeholder (in file path and/or layer name portions), which will be
        replaced with an automatically generated descriptive name that
        ensures uniqueness among the outputs of this call. If the parent
        directory of `out_path` does not exist, it will be created. If
        `out_path` is a GeoPackage, each output layer will be appended to
        it; the GeoPackage will also be created, if necessary.
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
        the call. ``"w"`` will create that file, overwriting if it
        preexists. ``"a"`` requires that the file preexist and appends to
        that file; if the layer also preexists, it is likewise appended to.
        Ignored if `out_path` is `None`.
    min_overlap : bool, default=True
        Whether to reduce box overlap. If `True`, boxes only overlap near
        LPS and LTM zone boundaries, where overlap is necessary to ensure
        coverage. If `False`, all valid boxes in the targeted area are
        generated, which may include inter-zone overlaps of up to ~35.4 km,
        that is, the diagonal of a 25-km box. In the special case that
        `bounds` is specified by an LGRS CRS string, `min_overlap` is
        instead interpreted to relate to the overlap of that region with its
        neighbors. Then, `True` generates only boxes that are within the
        nominal bounds of the zone whereas `False` generates all valid boxes
        from the maximally expanded zone.
    min_zones : bool, default=False
        Whether to minimize the number of zones (and therefore, CRSs) that
        are used. If `True`, boxes from non-nominal (expanded) areas of
        zones may be generated if doing so enables fewer zones to be used
        overall. For example, when working near the nominal longitudinal
        boundary between two LTM zones, you may prefer all boxes to come
        from one zone, if possible, instead of nearly all boxes from that
        zone and a few from a neighboring zone.
    fallback_to_geo: bool, default=False
        Specifies the behavior when the CRS of a path-like `bounds` cannot
        be transformed to the geographic CRS IAU_2015:30100. If `True` and
        that CRS can be transformed to some geographic CRS, that geographic
        CRS is assumed equivalent to IAU_2015:30100. If `True` but no CRS
        can be identified for `path`, the coordinates are assumed to
        already be in IAU_2015:30100, with order (lat, lon). In all other
        cases, an exception is raised.
    densify_count : int, default=21
        Whenever a bounding box must be transformed between CRSs, this
        number of samples will be added to each edge prior to
        transformation. Having more samples helps ensure that the
        transformation of the bounding box is more precise, but higher
        values will decrease performance.
    json_extras : bool, default=True
        Whether to add the following top-level foreign members to GeoJSON
        output:
            "name":
                An automatically generated descriptive name for the layer.
            "lgrs:crs_hint":
                A short `str` such as `"S"` for south LPS CRS or `"23N"` for
                the Northern Hemisphere LTM zone.
            "lgrs:crs_projjson":
                A `dict` generated by ``pyproj.CRS.to_json_dict()``.
            "lgrs:crs_wkt":
                A `str` generated by ``pyproj.CRS.to_wkt()``.
        This behavior is only available if (1) `out_path` is `None` or (2)
        `out_path` points to a GeoJSON file and no other argument implies
        driver-dependent behavior. (See Warnings section for more
        information.) In the latter case, ``json.dumps()`` is called for
        formatting.
    driver : string, optional
        Passed to ``geopandas.GeoDataFrame.to_file()``. Ignored if
        `out_path` is `None`.
    **kwargs
        Extra arguments are distributed among internally-called functions,
        including ``geopandas.GeoDataFrame.to_file()`` and others as
        documented herein.

    Returns
    -------
    hint_to_dict : a dict[str, dict] or None
        If `out_path` is `None`, a `dict` mapping CRS hint to GeoJSON-like
        `dict` is returned. Each CRS hint is a short string such as `"S"`
        for south LPS CRS or `"23N"` for the Northern Hemisphere LTM zone 23
        CRS. Each `dict` is generated by
        ``geopandas.GeoDataFrame.to_geo_dict()``.  Otherwise, `None` is
        returned.

    Raises
    ------
    TypeError
        If file state implied by `mode` is violated or the grandparent of
        `out_path` does not preexist. Also if `out_path` does not contain
        the ``"{}"`` placeholder and `bounds` is not an LGRS CRS short name.
        In that case, a name collision is risked if multiple CRSs generate
        multiple outputs. Finally, if arguments in `**kwargs` are unused.

    Warnings
    --------
    In the current implementation, the `True` option for `min_zones` has no
    effect unless `bounds` can be spanned by boxes from a single CRS.

    When writing out to a GeoJSON file or using the GeoJSON-like
    `hint_to_dict` values, bear in mind that the CRS foreign members added
    by `json_extras` will be the only CRS reference available, since the
    `"crs"` member does not support any LGRS CRS (at the time of writing).

    When writing out to a GeoJSON file, the default behavior is to bypass
    ``geopandas.GeoDataFrame.to_file()``. This bypassing makes `json_extras`
    behavior available at no cost to performance and is likely what you
    want. Conversely, to ensure that ``geopandas.GeoDataFrame.to_file()`` is
    called, specify ``driver="GeoJSON"`` (which will disable `json_extras`).
    Otherwise, heuristics will attempt to determine whether or not to bypass
    that call, which may cause unexpected behavior.

    Examples
    --------
    >>> write_grid(  # doctest: +SKIP
    ...     (3, 3, 5, 5), 1_000, "~/grids/grid_1.gpkg|layer={}",  # doctest: +SKIP
    ...     acc=True  # doctest: +SKIP
    ... )  # doctest: +SKIP
    >>> write_grid("N", 25_000, r"C:\\my_grids\final_{}_Moon.shp")  # doctest: +SKIP
    >>> json_dict = write_grid("path/to/craters.tif", 100, None)  # doctest: +SKIP
    """  # noqa: E501
    # Process `out_*` arguments.
    return_mapping = out_path is None
    if not return_mapping:
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
        # TODO: Could eventually support output to a single file
        #  generally by using a geographic CRS and densification.
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

    # Optionally generate a GeoJSON-like mapping.
    make_geo_dict = return_mapping or (
        driver is None
        and mode != "a"
        and layer_kw is None
        and out_file_path_template.suffix.lower() in (".json", ".geojson")
    )
    used_kwarg_set = set()
    if make_geo_dict:
        key_to_dict = {}
        for gdf in gdfs:
            crs_info: _database.LunarCrsInfo = _database.LunarCrsInfo.from_crs(
                gdf.crs
            )
            if return_mapping:
                key = crs_info.hint
            else:
                # Note: If not returning the mapping, use a more
                # accessible key.
                key = id(gdf)
            geo_dict = _call_with_kwargs(
                gdf.to_geo_dict,
                kwargs,
                used=used_kwarg_set,
            )
            key_to_dict[key] = geo_dict
            if json_extras:
                for key, val_or_func, defaults in (
                    ("name", gdf.name_hint, None),
                    ("lgrs:crs_hint", crs_info.hint, None),
                    ("lgrs:crs_projjson", gdf.crs.to_json_dict, None),
                    ("lgrs:crs_wkt", gdf.crs.to_wkt, {"pretty": True}),
                ):
                    if isinstance(val_or_func, _collections.abc.Callable):
                        func = val_or_func  # For clarity.
                        val = _call_with_kwargs(
                            func,
                            kwargs,
                            defaults=defaults,
                            used=used_kwarg_set,
                        )
                    else:
                        val = val_or_func
                    geo_dict[key] = val
        if return_mapping:
            return key_to_dict

    # If will call `geopandas.GeoDataFrame.to_file()`, subset `kwargs`.
    # Note: Since `geopandas.GeoDataFrame.to_file()` has open-ended
    # keyword arguments, must use process of elimination to determine
    # relevant arguments.
    else:
        # *REASSIGNMENT*
        kwargs = {k: v for k, v in kwargs.items() if k not in used_kwarg_set}
        if driver is not None:
            kwargs["driver"] = driver

    # Output each `GeoDataFrame` to a file or layer.
    out_dir_path = out_file_path_template.parent
    out_file_name_template = out_file_path_template.name
    out_dir_path_exists = out_dir_path.exists()
    for gdf in gdfs:
        gdf_out_path = out_dir_path / out_file_name_template.format(
            gdf.name_hint
        )
        if file_path_is_dynamic:
            mode = _test_mode(gdf_out_path, mode)  # *REASSIGNMENT*
        # Note: Wait to create out directory until necessary.
        if not out_dir_path_exists:
            out_dir_path.mkdir()
            out_dir_path_exists = True
        if make_geo_dict:
            geo_dict = key_to_dict[id(gdf)]
            geo_dict_str = _call_with_kwargs(
                _json.dumps,
                kwargs,
                defaults={"indent": 2},
                overrides={"obj": geo_dict},
            )
            with gdf_out_path.open(mode=mode) as f:
                f.write(geo_dict_str)
        else:
            if layer_kw is not None:
                kwargs[layer_kw] = layer_name.format(gdf.name_hint)
            gdf.to_file(gdf_out_path, index=True, mode=mode, **kwargs)


# endregion
