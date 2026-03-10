# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

##############################################################################
# region> IMPORT
##############################################################################
# External.
import functools as _functools
import inspect as _inspect
import pathlib as _pathlib
import re as _re
import rich as _rich
import textwrap as _textwrap
import typer as _typer
import types as _types
import typing as _typing

# Internal.
import easy as _easy
import database as _database



# endregion
##############################################################################
# region> INITIATE CLI SUPPORT
##############################################################################
_app = _typer.Typer(add_completion=False, no_args_is_help=True,
                    pretty_exceptions_show_locals=True)



# endregion
##############################################################################
# region> UTILITIES
##############################################################################
def _prep_for_cli(
        func: _types.FunctionType, examples: str
) -> _types.FunctionType:
    # Extract parameter info from numpy-styled docstring.
    # Note: Avoid using `numpydoc` module, due to dependencies.
    params_pattern = _re.compile("(?ms)^Parameters *$.*?^ *$")
    params_block_match = params_pattern.search(func.__doc__)
    param_name_to_desc = {}
    for match in _re.finditer(
            r"(?m)^(?P<pname>[a-z_]+) : .*\n(?P<pdesc>(    .*\n)+)",
            params_block_match.group()
    ):
        param_name = match.group("pname")
        raw_desc = match.group("pdesc")
        param_desc = _textwrap.dedent(raw_desc).strip().replace("\n", " ")
        param_name_to_desc[param_name] = param_desc

    # Annotate each parameter.
    sig = _inspect.signature(func)
    new_annotations = func.__annotations__.copy()
    for pname, pdesc in param_name_to_desc.items():
        old_ptype = new_annotations[pname]
        if sig.parameters[pname].default is sig.empty:
            typer_typ = _typer.Argument
        else:
            typer_typ = _typer.Option
        new_ptype = _typing.Annotated[old_ptype, typer_typ(help=pdesc)]
        new_annotations[pname] = new_ptype

    # Remove "Parameters" and "Examples" section from docstring.
    # Note: "Parameters" is now redundant (with potentially confusing
    # types) and "Examples" may be confusing due to call signature
    # differences.
    old_doc = func.__doc__
    no_params_doc = _re.sub(params_pattern, "", old_doc, count=1)
    examples_pattern = _re.compile(r"(?ms)^Examples *$.*?((^ *$)|\Z)")
    excerpted_doc = _re.sub(examples_pattern, "", no_params_doc, count=1)
    clean_doc = _re.sub(
        r"(?m)(^ *\n){2,}", r"\n", excerpted_doc
    ).strip()

    # Add new examples to docstring.
    populated_examples = examples.format(
        cmd=f"$ python {_pathlib.Path(__file__).name} {func.__name__.replace('_', '-')}"
    )
    clean_examples = _textwrap.dedent(populated_examples).strip()
    new_doc = clean_doc.strip() + "\n\n" + clean_examples

    # Create a (near) copy of `func`.
    new = _types.FunctionType(
        func.__code__, func.__globals__, func.__name__,
        func.__defaults__, func.__closure__
    )
    _functools.update_wrapper(new, func)
    del new.__wrapped__
    new.__annotations__ = new_annotations
    new.__doc__ = new_doc
    new.__kwdefaults__ = func.__kwdefaults__

    # Perform final preparation and return.
    out = _app.command(no_args_is_help=True)(new)
    return out



# endregion
##############################################################################
# region> COMMANDS
##############################################################################
from_lps_or_ltm = _prep_for_cli(
    _easy.from_lps_or_ltm,
    """
    Examples
    --------
    {cmd} 488590 608480
    (zone="A", area="ZS", easting=13590, northing=8480,
     string="AZS1359008480")
    """
)



# endregion
##############################################################################
# region> FINALIZE CLI SUPPORT
##############################################################################
if __name__ == "__main__":
    _app()



# endregion