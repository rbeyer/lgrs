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
import inspect as _inspect
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
import lgrs.easy as _easy


# endregion
###############################################################################
# region> UTILITIES
###############################################################################
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
def generate_grid(
    bounds: _typing.Any = None,
    precision: int | str = None,
    out_name: str = "out.gpkg|layer={}",
    **kwargs,
) -> None:
    """
    Generate and download an LGRS grid.

    This function wraps `easy.write_grid()` and is intended to make grid
    generation easier from a JavaScript environment. In addition to argument
    accommodations (described in the Parmaters section), the function
    handles compression of all outputs to a single .zip file and triggers
    downloading of that file. All outputs, including the .zip file, are also
    cleared on exit.

    Parameters
    ----------
    bounds : a resolvable bounds hint
        In addition to the forms accepted by the `bounds` argument of
        `easy.write_grid()`, the following are also supported:
            (1) a 4- or 5-element JavaScript array
                This is converted to a Python list of the same length, and
                the first four elements are coerced from strings
                to numbers, if necessary.
            (2) component keywords, if `bounds` is `None`
                If `bounds` is `None`, it is populated by other expected
                keyword arguments thusly:
                    ``[left, botton, right, top, crs]``
                The first four keywords must be present. `crs` defaults to
                `None`.
    precision : integer or string
        If specified as a sting, `precision` is coerced to an integer.
    out_name : string, default="out.gpkg|layer={}
        Specify the output name, equivalent to the final path component of
        `out_path` in `easy.write_grid()`.
    **kwargs
        Extra arguments (except those used to populate `bounds`) are passed
        to `easy.write_grid()`, but `out_path` is not supported. Arguments
        that should be numeric but are passed as strings will be coerced,
        for convenience.

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If `precision` or `bounds` (even by components) is not specified.

    See Also
    --------
    generate_grid_from_form :  Similar but accepts an HTML form name

    Examples
    --------
    In JavaScript::

    lgrs.js.generate_grid({"1", "1", "2", "2", "IAU_2015:30100}", "25000");

    """
    # Standardize argument values.
    if precision is None:
        raise TypeError("Must specify `precision`.")
    if isinstance(bounds, _pyodide.ffi.JsProxy):
        temp_bounds = bounds.to_py()
        bounds = list(map(float, temp_bounds[:4]))  # *REASSIGNMENT*
        if len(temp_bounds) == 5:
            bounds.append(temp_bounds[4])
    elif bounds is None:
        bounds = []  # *REASSIGNMENT*
        for arg_name in ("left", "bottom", "right", "top"):
            raw_val = kwargs.pop(arg_name, None)
            if raw_val is None:
                raise TypeError(
                    "Neither `bounds` nor its components are specified."
                )
            bounds.append(float(raw_val))
        bounds.append(kwargs.pop("crs", None))
    kwargs["precision"] = precision
    for arg_name, type_hint in _typing.get_type_hints(
        _easy.write_grid
    ).items():
        raw_val = kwargs.get(arg_name)
        if raw_val is None:
            continue
        match type_hint:
            case _builtins.int:
                new_val = int(raw_val)
            case _builtins.float:
                new_val = float(raw_val)
            case _:
                continue
        kwargs[arg_name] = new_val

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


def generate_grid_from_form(form_id: str, **kwargs) -> None:
    """
    Generate and download an LGRS grid that is specified by an HTML form.

    This can be the easiest way to generate an LGRS grid from JavaScript,
    but note:
        (1) Any element with the same name as an argument supported by
            `generate_grid()` will have its value used for that argument.
            For example, ``<input name="precision">``.
        (2) Checkboxes are processed as booleans: `True` if checked and
            `False` if unchecked.
        (3) For radio buttons with the same name, the value of the
            checked button (if any) is used.
        (4) Any element whose name is not that of an argument supported by
            `generate_grid()` is silently ignored.
        (5) `generate_grid()` coerces strings to numeric values, where
            appropriate.

    Parameters
    ----------
    form_id : string
        The ID of the form, that is, ``<form id=form_id>``. The elements of
        the form are extracted and their values (as described above) are
        passed to `generate_grid()`.
    **kwargs
        Extra arguments are passed `generate_grid()`. In the event of
        collision, these arguments override those set by the form.

    Returns
    -------
    None
    """
    # Collect set of valid argument names.
    ok_arg_name_set = set(_inspect.signature(_easy.write_grid).parameters)
    ok_arg_name_set.remove("out_path")
    ok_arg_name_set.update(_inspect.signature(generate_grid).parameters)
    ok_arg_name_set.update(("left", "bottom", "right", "top", "crs"))

    # Read form.
    form = _js.document.getElementById(form_id)
    form_kwargs = {}
    for elem in form:
        if elem.name not in ok_arg_name_set:
            continue
        match form.type:
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
    return generate_grid(**form_kwargs)
