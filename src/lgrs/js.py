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
import collections as _collections
import json as _json
import pathlib as _pathlib
import shutil as _shutil

# Note: Although `sqlite3` is not explicitly used, importing it avoids a
# fatal error when grid generation is executed under Pyodide.
import sqlite3 as _sqlite3  # noqa: F401
import tempfile as _tempfile
import typing as _typing

# External.
try:
    import js as _js
    import pyodide as _pyodide
except ModuleNotFoundError:
    # Note: Allows corresponding type hints to be resolved.
    _JsProxyHint = _typing.Any
else:
    from pyodide.ffi import JsProxy as _JsProxyHint

# Internal.
import lgrs.coords as _coords
import lgrs.easy as _easy
import lgrs.grid as _grid
import lgrs.values as _values

# endregion
###############################################################################
# region> UTILITIES
###############################################################################
_bounds_numeric_name_to_type = {
    name: float for name in ("left", "bottom", "right", "top")
}


def _coerce_kwargs(
    kwargs: dict[str, _typing.Any],
    /,
    *funcs: _collections.abc.Callable,
    seed: dict | None = None,
    call: bool = False,
) -> _typing.Any:
    # Get name-to-type mapping.
    name_to_type = _get_type_hints(*funcs, seed=seed)

    # Flatten `kwargs`, if necessary.
    nested_kwargs = kwargs.pop("kwargs", None)
    if nested_kwargs is not None:
        nested_kwargs.update(kwargs)
        kwargs = nested_kwargs  # *REASSIGNMENT*

    # Update `kwargs` with coerced values.
    new_kwargs = {}
    for name, val in tuple(kwargs.items()):
        targ_type = name_to_type.get(name, None)
        if isinstance(val, _pyodide.ffi.JsProxy):
            coerced_val = val.to_py()
        elif isinstance(val, str) and val == "":
            coerced_val = None
        else:
            if targ_type not in (int, float):
                continue
            coerced_val = _coerce_to_type(
                raw_val=val, name=name, typ=targ_type
            )
        if not isinstance(coerced_val, targ_type):
            raise TypeError(f"`{name}` does not support: {coerced_val!r}")
        new_kwargs[name] = coerced_val
    kwargs.update(new_kwargs)

    # Optionally call.
    if call:
        result = funcs[0](**kwargs)
        return _pyodide.ffi.to_js(result)
    else:
        return kwargs


def _coerce_to_type[T](
    *, raw_val: str | _typing.Any, name: str, typ: type[T]
) -> T:
    try:
        return typ(raw_val)
    except Exception:
        raise TypeError(
            f"Could not coerce {name!r} to `{typ.__name__}`: {raw_val!r}"
        ) from None


def _get_type_hints(
    *funcs: _collections.abc.Callable, seed: dict | None = None
) -> dict[str, _typing.Any]:
    if seed is None:
        cum_name_to_type = {}
    else:
        cum_name_to_type = seed.copy()
    for func in funcs:
        name_to_type = _typing.get_type_hints(func)
        for name, typ in name_to_type.items():
            if name in cum_name_to_type:
                continue
            cum_name_to_type[name] = typ
    return cum_name_to_type


def _read_form_to_kwargs(
    form_id: str, *, ok_arg_names: _collections.abc.Collection[str]
) -> dict[str, _typing.Any]:
    form = _js.document.getElementById(form_id)
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
    return form_kwargs


# endregion
###############################################################################
# region> FUNCTIONS
###############################################################################
def convert_coordinate(
    input_coordinate: _coords.BaseCoordinate | str,
    *,
    deserialize: bool = False,
    **kwargs: _typing.Any,
) -> _typing.Any:
    """
    Convert an input coordinate to all relevant coordinates.

    This function wraps, and is identical to,
    `lgrs.easy.convert_coordinate()` except as noted herein. See that
    function's documentation for more details.

    Arguments representing a single numeric value may be passed as strings
    (such as `"0.0"`) and will be coerced. Empty strings are replaced with
    `None`.

    Parameters
    ----------
    input_coordinate : a point or box coordinate, or equivalent string
        The input coordinate to convert.
    deserialize : bool, default=False
        When `target` is ``"json"`` or ``"json_full"``, specifies whether
        the generated string should be deserialized so that a JavaScript
        ``Object`` is instead returned. For any other `target` value, this
        argument is ignored.
    **kwargs
        Remaining arguments are passed to `lgrs.easy.convert_coordinate()`.

    Returns
    -------
    relatives_or_value : pyodide.ffi.JsProxy or typing.Any
        A JavaScript proxy of the `GeoRelatives` instance (if `target` is not
        specified) or whatever object is targeted by `target`. In the latter
        case, a JavaScript-native counterpart, rather than a proxy, is returned
        if possible.

    See Also
    --------
    convert_coordinate_from_form :  Similar but accepts an HTML form name

    Warnings
    --------
    Wherever possible, `target` should be specified to avoid the generation
    of JavaScript proxies and the resulting memory leak, as such proxies are
    never garbage collected. For broad use, consider specifying `target` as
    `"json"` or `"json_full"` (rather than `"json_dict"`), in which case the
    `deserialize` option may be helpful.
    """
    full_kwargs = _coerce_kwargs(locals(), _easy.convert_coordinate)
    del full_kwargs["deserialize"]
    result = _easy.convert_coordinate(**full_kwargs)
    if deserialize and full_kwargs["target"] in ("json", "json_full"):
        result = _json.loads(result)  # *REASSIGNMENT*
    return _pyodide.ffi.to_js(result)


def convert_coordinate_from_form(
    form_id: str, **kwargs: _typing.Any
) -> _typing.Any:
    """
    Convert an input coordinate, as specified by an HTML form.

    Note:
        (1) Any element with the same name as an argument supported by
            `convert_coordinate()` will have its value used for that
            argument. For example, ``<input name="precision">``.
        (2) Checkboxes are processed as booleans: `True` if checked and
            `False` if unchecked.
        (3) For radio buttons with the same name, the value of the
            checked button (if any) is used.
        (4) Any element whose name is not that of an argument supported by
            `convert_coordinate()` is silently ignored.
        (5) `convert_coordinate()` also performs some coercion to numeric
            values and `None`, as described in its documentation.

    Parameters
    ----------
    form_id : string
        The ID of the form, that is, ``<form id=form_id>``. The elements of
        the form are extracted and their values (as described above) are
        passed to `convert_coordinate()`.
    **kwargs
        Extra arguments are passed `convert_coordinate()`. In the event of
        collision, these arguments override those set by the form.

    Returns
    -------
    relatives_or_value : pyodide.ffi.JsProxy or typing.Any
        See `convert_coordinate()`.

    See Also
    --------
    convert_coordinate :  Similar but accepts direct arguments.
    """
    # Compile list of supported argument names.
    ok_arg_names = set(
        _get_type_hints(convert_coordinate, _easy.convert_coordinate)
    )

    # Read form.
    form_kwargs = _read_form_to_kwargs(form_id, ok_arg_names=ok_arg_names)

    # Pass to `convert_coordinate()`.
    form_kwargs.update(kwargs)
    return convert_coordinate(**form_kwargs)


def make_box_grid(
    bounds: _typing.Any, precision: float, **kwargs: _typing.Any
) -> _JsProxyHint:
    """
    Generate grid as an array of LGRS/ACC boxes spanning specified bounds.

    This function wraps, and is identical to, `lgrs.grid.make_box_grid()`
    except as noted herein. See that function's documentation for more details.

    Arguments representing a single numeric value may be passed as strings
    (such as `"0.0"`) and will be coerced. Empty strings are replaced with
    `None`.

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
    boxes = _coerce_kwargs(locals(), _grid.make_box_grid, call=True)
    return boxes


def make_gdfs(
    boxes: _collections.abc.Sequence[_coords.BoxCoordinate] | _JsProxyHint,
    **kwargs: _typing.Any,
) -> _JsProxyHint:
    """
    Create one or more `GeoDataFrame` instances from a sequence of boxes.

    This function wraps, and is identical to, `lgrs.grid.make_gdfs()` except
    as noted herein. See that function's documentation for more details.

    Arguments representing a single numeric value may be passed as strings
    (such as `"0.0"`) and will be coerced. Empty strings are replaced with
    `None`.

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

    See Also
    --------
    package_grid : High-level grid packaging.

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
    gdfs = _coerce_kwargs(locals(), _grid.make_gdfs, call=True)
    return gdfs


def package_grid(
    bounds: _typing.Any = _values.DEFAULT,
    precision: int | str | None = None,
    out_name: str | None = None,
    **kwargs: _typing.Any,
) -> _JsProxyHint | None:
    """
    Package an LGRS grid to a standard format and optionally download it.

    This function wraps `lgrs.easy.write_grid()` and is intended to make
    grid packaging easier from a JavaScript environment. The function
    optionally handles compression of all outputs to a single .zip file and
    triggers downloading of that file. All outputs, including the .zip file,
    are also cleared on exit.

    Arguments representing a single numeric value may be passed as strings
    (such as `"0.0"`) and will be coerced. Empty strings are replaced with
    `None`. Additional argument accommodations are described in the Parameters
    section.

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
    left, bottom, right, top : float or string, optional
        Components of `bounds`. Should only be specified if `bounds` is not
        specified directly, but then required.
    crs : string, CRS, or None, default=None
        Final component of `bounds`. Should only be specified if `bounds` is
        not specified directly, in which case it defaults to `None`.
    **kwargs
        Extra arguments are passed to `lgrs.easy.write_grid()`, but
        `out_path` is not supported.

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
    package_grid_from_form :  Similar but accepts an HTML form name.

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
    full_kwargs = _coerce_kwargs(
        locals(), _easy.write_grid, seed=_bounds_numeric_name_to_type
    )
    bounds = full_kwargs.pop("bounds")  # *REASSIGNMENT*
    if isinstance(bounds, _pyodide.ffi.JsProxy):
        temp_bounds = bounds
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
        for arg_name in _bounds_numeric_name_to_type:
            val = kwargs.pop(arg_name, None)
            if val is None:
                raise TypeError(
                    f"Neither `bounds` nor `{arg_name}` are specified."
                )
            bounds.append(val)
        bounds.append(full_kwargs.pop("crs", None))

    # Return (proxied) JavaScript `Object`, if applicable.
    out_name = full_kwargs.pop("out_name")  # *REASSIGNMENT*
    if out_name is None:
        name_to_json = _easy.write_grid(bounds, out_path=None, **full_kwargs)
        obj = _pyodide.ffi.to_js(name_to_json)
        return obj

    # Create temporary directory...
    with _tempfile.TemporaryDirectory(prefix="grid__") as temp_dir_name:

        # Generate grid outputs within temporary directory.
        temp_dir_path = _pathlib.Path(temp_dir_name)
        grid_files_out_dir_path = temp_dir_path / "output_files"
        grid_nom_out_path = grid_files_out_dir_path / out_name
        _easy.write_grid(bounds, out_path=grid_nom_out_path, **full_kwargs)

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
    form_id: str, **kwargs: _typing.Any
) -> _JsProxyHint | None:
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
        (5) `package_grid()` also performs some coercion to numeric values
            and `None`, as described in its documentation.

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

    See Also
    --------
    package_grid :  Similar but accepts direct arguments.
    """
    # Compile list of supported argument names.
    ok_arg_names = set(
        _get_type_hints(
            _easy.write_grid,
            package_grid,
            seed=_bounds_numeric_name_to_type,
        )
    )
    ok_arg_names.remove("out_path")  # Replaced by `out_name`.
    ok_arg_names.add("crs")

    # Read form.
    form_kwargs = _read_form_to_kwargs(form_id, ok_arg_names=ok_arg_names)

    # Pass to `package_grid()`.
    form_kwargs.update(kwargs)
    return package_grid(**form_kwargs)


# endregion
