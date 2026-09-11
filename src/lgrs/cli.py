"""Support for the command-line interface."""

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
import inspect as _inspect
import pathlib as _pathlib
import pprint as _pprint
import re as _re
import types as _types
import typing as _typing

# External.
import typer as _typer
import typer.rich_utils as _rich_utils

# Internal.
import lgrs.coords as _coords
import lgrs.easy as _easy
import lgrs.util as _util

# endregion
###############################################################################
# region> INITIATE CLI SUPPORT
###############################################################################
_app = _typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=True,
)


# endregion
###############################################################################
# region> UTILITIES
###############################################################################
def _make_metadata(param: _inspect.Parameter, desc: str) -> _typing.Any:
    if param.default is param.empty:
        typer_typ = _typer.Argument
    else:
        typer_typ = _typer.Option
    normalized_desc = _re.sub(r"\s{2,}", "  ", desc)
    return typer_typ(help=normalized_desc)


def _parse_for_write_grid(string: str) -> _typing.Any:
    if string == "None":
        return None
    if not (string.startswith("(") and string.endswith(")")):
        return string
    parsed_list = []
    for raw_part in string[1:-1].split(",", maxsplit=4):
        part = raw_part.strip()
        if part == "None":
            parsed = None
        else:
            try:
                parsed = float(part)
            except ValueError:
                parsed = part
        parsed_list.append(parsed)
    return parsed_list


def _prep_for_cli(func: _types.FunctionType) -> _types.FunctionType:
    # Annotate parameters.
    # Note: Also remove "Parameters" section as redundant, with
    # potentially confusing type descriptions.
    numdoc = _util.NumpyDoc(func)
    numdoc.annotate_params(make_metadata=_make_metadata, delete_section=True)

    # Add new examples to docstring.
    examples = numdoc.section_name_to_content["Examples"]
    # Note: To make Examples a bit easier to write, replace any "{}"
    # with a literal "{}".
    indirect_escapes = ("{}",) * examples.count("{")
    populated_examples = examples.format(
        *indirect_escapes,
        cmd=(
            f"$ python {_pathlib.Path(__file__).name} "
            f"{func.__name__.replace('_', '-')}"
        ),
    )
    numdoc.replace_section("Examples", populated_examples)

    # Escape and colorize docstring, compatible with `rich` (used by
    # `typer`).
    docstring = func.__doc__
    docstring = docstring.replace("[", r"\[")
    docstring = _re.sub(
        "`{1,2}(.*?)`{1,2}",
        r"[cyan]`\1`[/cyan]",
        docstring,
    )
    func.__doc__ = docstring

    # Perform final preparation and return.
    out = _app.command(no_args_is_help=True)(func)
    return out


def _pretty_print(result: _typing.Any) -> None:
    match result:
        case _builtins.str():
            print(result)
        case _coords.BaseCoordinate():
            print(result)
        case _:
            # Note: Whereas `print()` prints `str()`, this prints
            # (formatted) `repr()`.
            _pprint.pp(result)


# endregion
###############################################################################
# region> COMMANDS
###############################################################################
# TODO: Add more examples.
@_prep_for_cli
@_util.partially_wraps(_easy.convert_coordinate)
def convert_coordinate(
    input_coordinate: str,
    *,
    precision: float,
    target: str = "json_full",
    **kwargs,
) -> None:
    """
    Convert an input coordinate to all relevant coordinates.

    Examples
    --------
    Convert the geographic (IAU_2015:30100) coordinate 80° N, 4° E to a JSON
    of all relevant coordinates, with 10-meter precision:

    {cmd} "80 N, 4 E" 10

    Equivalent calls include:

    {cmd} "80 4" 10
    {cmd} "80.0° N 4.0° E" 10
    {cmd} "4E 80N" 10

    Get just the condensed ACC for the LPS region:

    {cmd} "80 N, 4 E" 10 --target lps.acc.condensed
    """
    result = _easy.convert_coordinate(
        input_coordinate, precision=precision, target=target, **kwargs
    )
    _pretty_print(result)


@_prep_for_cli
@_util.partially_wraps(
    _easy.write_grid, extend=("bounds",), exclude=("Returns",)
)
def write_grid(
    bounds: str,
    precision: float,
    out_path: _pathlib.Path,
    **kwargs,
) -> None:
    """
    Write out an LGRS or ACC box grid to file(s).

    Parameters
    ----------
    bounds : a resolvable bounds hint
        [Note: The following description applies to the Python interface.
        Not all forms are supported at the command line. See Examples
        section.]

    Examples
    --------
    Target 3-5 degrees longitude, 4-6 degrees latitude in IAU_2015:30100.
    Geenerate an ACC grid with cell side length 1000 m. Output to auto-
    named layers (one per CRS) in `grid_1.gpkg`.

    {cmd} '(3, 4, 5, 6)' 1000 '~/grids/grid_1.gpkg|layer={}' --acc

    The commands below are also equivalent to this command:

    {cmd} '(3, 4, 5, 6, None)' 1_000 '~/grids/grid_1.gpkg|layer={}' --acc
    {cmd} '(3, 4, 5, 6, "IAU_2015:30100")' 1_000 '~/grids/grid_1.gpkg|layer={}' --acc

    The command below, by approximating the same `bounds`, also generates
    nearly the same result (differing only due to alignment/edge effects).
    Note that even though `bounds` is specified in LTM zone 23N coordinates,
    the results span 23N and 24N.

    {cmd} '(340512, 121534, 400702, 182964, "23N")' 1_000 '~/grids/grid_1.gpkg|layer={}' --acc

    For the entire LPS North region, generate an LGRS grid with cell side
    length 25,000 m. Incorporate an automatically generated name into the
    name of the output shapefile.

    {cmd} 'N' 25_000 'C:\\my_grids\\final_{}_Moon.shp'

    The above command is a special case in which the output is known
    beforehand to be confined to a single CRS. In such cases, the "{}"
    placeholder is optional:

    {cmd} 'N' 25_000 'C:\\my_grids\\final_LPS_N_Moon.shp'

    For the footprint of `craters.tif`, generate an ACC grid with cell side
    length 100 m. Split grid between multiple GeoPackages, one per CRS, each
    named automatically.

    {cmd} 'craters.tif' 100 '~/craters/{}.gpkg' --acc

    Generate an LGRS grid with cell side length 25 km. Split grid between
    GeoPackage layers, one per CRS, each named automatically.

    {cmd} 'None' 25_000 '~/grids/global.gpkg|layer={}'
    """  # noqa: E501
    coerced_bounds = _parse_for_write_grid(bounds)
    _easy.write_grid(coerced_bounds, precision, out_path, **kwargs)


# endregion
###############################################################################
# region> FINALIZE CLI SUPPORT
###############################################################################
if __name__ == "__main__":
    # Cautious monkey-patch so that negative values (e.g., latitudes) in
    # docstrings are not colored as though they represent CLI switches.
    # (Purely cosmetic.)
    _highlights = getattr(_rich_utils.OptionHighlighter, "highlights", None)
    if isinstance(_highlights, _collections.abc.Sequence):
        for i, elem in enumerate(_highlights):
            if not isinstance(elem, str):
                continue
            if elem == r"(^|\W)(?P<switch>\-\w+)(?![a-zA-Z0-9])":
                _highlights[i] = (
                    r"(^|\W)(?P<switch>\-[a-zA-Z]\w*)(?![a-zA-Z0-9])"
                )
                break

    # Enter CLI.
    _app()


# endregion
