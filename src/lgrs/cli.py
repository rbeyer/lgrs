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
import inspect as _inspect
import pathlib as _pathlib
import re as _re
import textwrap as _textwrap
import types as _types
import typing as _typing

# External.
import typer as _typer

# Internal.
import lgrs.easy as _easy

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
def _prep_for_cli(
    func: _types.FunctionType, examples: str
) -> _types.FunctionType:
    # Parse parameter names and descriptions from numpy-styled
    # docstring.
    # Note: Avoid adding `numpydoc` as a dependency.
    adapter = _easy._Adapter(func)
    params_block_match = adapter.get_doc_section_match("Parameters")
    param_name_to_desc = {}
    for match in _re.finditer(
        r"(?m)^(?P<pname>[a-z_]+) : .*\n(?P<pdesc>(    .*\n)+)",
        params_block_match.group(),
    ):
        # Note: The parameter type description is intentionally not
        # retained, as the stricter type hint is more precise.
        param_name = match.group("pname")
        raw_desc = match.group("pdesc")
        param_desc = _textwrap.dedent(raw_desc).strip().replace("\n", " ")
        param_name_to_desc[param_name] = param_desc

    # Annotate each parameter.
    sig = _inspect.signature(func)
    for pname, pdesc in param_name_to_desc.items():
        old_ptype = adapter.annotations[pname]
        if sig.parameters[pname].default is sig.empty:
            typer_typ = _typer.Argument
        else:
            typer_typ = _typer.Option
        new_ptype = _typing.Annotated[old_ptype, typer_typ(help=pdesc)]
        adapter.annotations[pname] = new_ptype

    # Remove "Parameters" section as redundant, with potentially
    # confusing type descriptions.
    adapter.replace_doc_section("Parameters")

    # Add new examples to docstring.
    populated_examples = examples.format(
        cmd=(
            f"$ python {_pathlib.Path(__file__).name} "
            f"{func.__name__.replace('_', '-')}"
        )
    )
    clean_examples = _textwrap.dedent(populated_examples).strip()
    adapter.replace_doc_section("Examples", clean_examples)

    # Create a (near) copy of `func`.
    new = adapter.make_new_func()

    # Perform final preparation and return.
    out = _app.command(no_args_is_help=True)(new)
    return out


# endregion
###############################################################################
# region> COMMANDS
###############################################################################
# from_lps_or_ltm = _prep_for_cli(
#     _easy.from_lps_or_ltm,
#     """
#     {cmd} 488590 608480
#     (zone="A", area="ZS", easting=13590, northing=8480,
#      string="AZS1359008480")
#     """,
# )


# endregion
###############################################################################
# region> FINALIZE CLI SUPPORT
###############################################################################
if __name__ == "__main__":
    _app()


# endregion
