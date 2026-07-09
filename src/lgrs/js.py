"""Support for JavaScript interface."""

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
import builtins as _builtins
import collections as _collections
import functools as _functools
import pathlib as _pathlib
import shutil as _shutil

# Note: Although `sqlite3` is not explicitly used, importing it avoids a
# fatal error when grid generation is executed under Pyodide.
import sqlite3 as _sqlite3  # noqa: F401
import tempfile as _tempfile
import types as _types
import typing as _typing

# External.
try:
    import js as _js
    import pyodide as _pyodide
except ModuleNotFoundError:
    pass

# Internal.
import lgrs.coords as _coords
import lgrs.easy as _easy
import lgrs.grid as _grid
import lgrs.values as _values


# endregion
###############################################################################
# region> UTILITIES
###############################################################################
def _coerce_to_type[T](
    *, raw_val: str | _typing.Any, name: str, typ: type[T]
) -> T:
    try:
        return typ(raw_val)
    except Exception:
        raise TypeError(
            f"Could not coerce {name!r} to `{typ.__name__}`: {raw_val!r}"
        ) from None


def _prep_for_js(
    func: _types.FunctionType, notes: str, *, prepend: bool = False
) -> _types.FunctionType:
    adapter = _easy._Adapter(func)
    adapter.add_to_notes(notes, prepend=prepend)
    new = adapter.make_new_func()
    return new


# endregion
###############################################################################
# region> FUNCTIONS
###############################################################################
@_functools.cache
def _get_grid_type_hints(
    *, bounds_numerics_only: bool = False
) -> dict[str, _typing.Any]:
    if bounds_numerics_only:
        name_to_type = {
            name: float for name in ("left", "bottom", "right", "top")
        }
    else:
        name_to_type = _typing.get_type_hints(_easy.write_grid)
        del name_to_type["out_path"]
        name_to_type["out_name"] = str
        name_to_type.update(_get_grid_type_hints(bounds_numerics_only=True))
        name_to_type["crs"] = _typing.Any
    return name_to_type


def make_box_grid(
    bounds: _typing.Any, precision: float, **kwargs
) -> _pyodide.ffi.JsProxy:
    """
    Generate grid as an array of LGRS/ACC boxes spanning specified bounds.

    This function wraps, and is identical to, `lgrs.grid.make_box_grid()`
    except as noted below. See that function's documentation.

    Parameters
    ----------
    bounds : a resolvable bounds hint
        In addition to the forms accepted by the `bounds` argument of
        `lgrs.grid.make_box_grid()`, may be specified by a 4- or 5-element
        JavaScript array.
    **kwargs
        Remaining arguments are passed to `lgrs.grid.make_box_grid()`.

    Returns
    -------
    box_array : pyodide.ffi.JsProxy
        A JavaScript array of `pyodide.ffi.JsProxy` instances, each
        representing an `lgrs.coords.BoxCoordinate` instance.

    See Also
    --------
    package_grid : High-level grid packaging.
    package_grid_from_form :  Packages grid from an HTML form.

    Examples
    --------
    In JavaScript::

        // Create grid as array of boxes.
        const bounds = {1, 1, 2, 2, "IAU_2015:30100}";
        const boxes = make_box_grid(bounds, 25_000);

        // Print LGRS reference for first box.
        console.log(boxes[0].string);
    """
    if isinstance(bounds, _pyodide.ffi.JsProxy):
        bounds = bounds.to_py()  # *REASSIGNMENT*
    boxes = _grid.make_box_grid(bounds, precision, **kwargs)
    return _pyodide.ffi.to_js(boxes)


def make_gdfs(
    boxes: (
        _collections.abc.Sequence[_coords.BoxCoordinate] | _pyodide.ffi.JsProxy
    ),
) -> _pyodide.ffi.JsProxy:
    """
    Create one or more `GeoDataFrame` instances from a sequence of boxes.

    This function wraps, and is identical to, `lgrs.grid.make_gdfs()`
    except as noted below. See that function's documentation.

    Parameters
    ----------
    boxes : sequence of lgrs.coords.BoxCoordinates instances
        Sequence may be a JavaScript array.
    **kwargs
        Remaining arguments are passed to `lgrs.grid.make_gdfs()`.

    Returns
    -------
    gdfs : pyodide.ffi.JsProxy
        A JavaScript array of `pyodide.ffi.JsProxy` instances, each
        representing a `geopandas.GeoDataFrame` instance.

    Examples
    --------
    In JavaScript::

        // Create grid as an array of `geopandas.GeoDataFrame` instances.
        const bounds = {1, 1, 2, 2, "IAU_2015:30100}";
        const boxes = make_box_grid(bounds, 25_000);
        const gdfs = make_gdfs(boxes);

        // Print LGRS reference for first box of first gdf.
        const gdf = gdfs[0];
        console.log(gdf.iloc[0]["string"]);
    """
    if isinstance(boxes, _pyodide.ffi.JsProxy):
        boxes = boxes.to_py()  # *REASSIGNMENT*
    gdfs = _grid.make_gdfs(boxes)
    return _pyodide.ffi.to_js(gdfs)


def package_grid(
    bounds: _typing.Any = _values.DEFAULT,
    precision: int | str | None = None,
    out_name: str | None = None,
    **kwargs,
) -> _pyodide.ffi.JsProxy | None:
    """
    Package an LGRS grid to a standard format and optionally download it.

    This function wraps `lgrs.easy.write_grid()` and is intended to make
    grid packaging easier from a JavaScript environment. In addition to
    argument accommodations (described in the Parmaters section), the
    function optionally handles compression of all outputs to a single .zip
    file and triggers downloading of that file. All outputs, including the
    .zip file, are also cleared on exit.

    Parameters
    ----------
    bounds : a resolvable bounds hint
        In addition to the forms accepted by the `bounds` argument of
        `lgrs.easy.write_grid()`, the following are also supported:
            (1) a 4- or 5-element JavaScript array
                This is converted to a Python list of the same length, and
                the first four elements are coerced from strings
                to numbers, if necessary.
            (2) component keywords
                If `bounds` is not specified directly, it is populated by
                other expected keyword arguments thusly:
                    ``[left, botton, right, top, crs]``
    precision : float or string
        If specified as a sting, `precision` is coerced to a number.
    out_name : string or None, default=None
        The output name, equivalent to the final path component of
        `out_path` in `lgrs.easy.write_grid()`.
    left, bottom, right, top : float, optional
        Components of `bounds`. Should only be specified if `bounds` is not
        specified directly, but then required.
    crs : string, CRS, or None, optional
        Final component of `bounds`. Should only be specified if `bounds` is
        not specified directly, in which case it defaults to `None`.
    **kwargs
        Extra arguments are passed to `lgrs.easy.write_grid()`, but
        `out_path` is not supported. Arguments that should be numeric are
        coerced if necessary, for convenience.

    Returns
    -------
    multilayer_object : pyodide.ffi.JsProxy or None
        If `out_name` is `None`, a JavaScript ``Object`` created from
        the `hint_to_dict` mapping returned by `lgrs.easy.write_grid()`.
        (In that case, no download is triggered.) Otherwise, `None`.

    Raises
    ------
    TypeError
        If `precision` or `bounds` (even by components) is not specified.

    See Also
    --------
    package_grid_from_form :  Similar but accepts an HTML form name

    Examples
    --------
    In JavaScript::

        // Create multi-layer grid object.
        const bounds = {1, 1, 2, 2, "IAU_2015:30100}";
        const multiLyrObj = package_grid(bounds, "25000");

        // Print LGRS reference for first box of first layer.
        const lyrObj = Object.values(gridObj)[0];
        const feature = lyrObj.features[0];
        console.log(feature.properties.string);

        // Instead package grid to multi-layer GeoPackage and download.
        package_grid(bounds, 25_000, "out.gpkg|layer={}");
    """
    # Standardize argument values.
    if precision is None:
        raise TypeError("Must specify `precision`.")
    kwargs["precision"] = precision
    for arg_name, type_hint in _get_grid_type_hints().items():
        raw_val = kwargs.get(arg_name)
        if raw_val is None:
            continue
        match type_hint:
            case _builtins.int:
                typ = int
            case _builtins.float:
                typ = float
            case _:
                continue
        coerced_val = _coerce_to_type(raw_val=raw_val, name=arg_name, typ=typ)
        kwargs[arg_name] = coerced_val
    if isinstance(bounds, _pyodide.ffi.JsProxy):
        temp_bounds = bounds.to_py()
        # *REASSIGNMENT*
        bounds = [
            _coerce_to_type(
                raw_val=raw_val, name="<bounds component>", typ=float
            )
            for raw_val in temp_bounds[:4]
        ]
        if len(temp_bounds) == 5:
            bounds.append(temp_bounds[4])
    elif bounds is _values.DEFAULT:
        bounds = []  # *REASSIGNMENT*
        for arg_name in _get_grid_type_hints(bounds_numerics_only=True):
            val = kwargs.pop(arg_name, None)
            if val is None:
                raise TypeError(
                    f"Neither `bounds` nor `{arg_name}` are specified."
                )
            bounds.append(val)
        bounds.append(kwargs.pop("crs", None))

    # Return (proxied) JavaScript `Object`, if applicable.
    if out_name is None:
        name_to_json = _easy.write_grid(bounds, out_path=None, **kwargs)
        obj = _pyodide.ffi.to_js(name_to_json)
        return obj

    # Create temporary directory...
    with _tempfile.TemporaryDirectory(prefix="grid__") as temp_dir_name:

        # Generate grid outputs within temporary directory.
        temp_dir_path = _pathlib.Path(temp_dir_name)
        grid_files_out_dir_path = temp_dir_path / "output_files"
        grid_nom_out_path = grid_files_out_dir_path / out_name
        _easy.write_grid(bounds, out_path=grid_nom_out_path, **kwargs)

        # Zip grid outputs.
        out_zip_path = temp_dir_path / "grid.zip"
        _shutil.make_archive(
            out_zip_path.with_suffix(""), "zip", grid_files_out_dir_path
        )

        # Trigger download.
        data = _pyodide.ffi.to_js(out_zip_path.read_bytes())
        blob = _js.Blob.new([data], {"type": "application/zip"})
        url = _js.URL.createObjectURL(blob)
        a = _js.document.createElement("a")
        a.href = url
        a.download = out_zip_path.name
        a.click()
        _js.URL.revokeObjectURL(url)


def package_grid_from_form(
    form_id: str, **kwargs
) -> _pyodide.ffi.JsProxy | None:
    """
    Generate and download an LGRS grid that is specified by an HTML form.

    Note:
        (1) Any element with the same name as an argument supported by
            `package_grid()` will have its value used for that argument. For
            example, ``<input name="precision">``.
        (2) Checkboxes are processed as booleans: `True` if checked and
            `False` if unchecked.
        (3) For radio buttons with the same name, the value of the
            checked button (if any) is used.
        (4) Any element whose name is not that of an argument supported by
            `package_grid()` is silently ignored.
        (5) `package_grid()` coerces strings to numeric values, where
            appropriate.

    Parameters
    ----------
    form_id : string
        The ID of the form, that is, ``<form id=form_id>``. The elements of
        the form are extracted and their values (as described above) are
        passed to `package_grid()`.
    **kwargs
        Extra arguments are passed `package_grid()`. In the event of
        collision, these arguments override those set by the form.

    Returns
    -------
    geojson_object : pyodide.ffi.JsProxy or None
        See `package_grid()`.
    """
    # Read form.
    form = _js.document.getElementById(form_id)
    ok_arg_names = _get_grid_type_hints()
    form_kwargs = {}
    for elem in form:
        if elem.name not in ok_arg_names:
            continue
        match elem.type:
            case "checkbox":
                value = elem.checked
            case "radio":
                if not elem.checked:
                    continue
                value = elem.value
            case _:
                value = elem.value
        form_kwargs[elem.name] = value

    # Pass to `grid_generation()`.
    form_kwargs.update(kwargs)
    return package_grid(**form_kwargs)


# endregion
