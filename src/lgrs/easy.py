# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

##############################################################################
# region> IMPORT
##############################################################################
# External.
import enum as _enum

# Internal.
import lgrs.exceptions as _exceptions



# endregion
##############################################################################
# region> ENUMERATIONS
##############################################################################
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
##############################################################################
# region> CONVENIENCE FUNCTIONS
##############################################################################
def from_gridded(string: str, *,
                 fmt: Format = Format.LGRS,
                 typ: Type = Type.LABELED,
                 region: Region = Region.ANY,
                 extended_ltm: bool = False) -> tuple | str:
    ...

def from_geographic(latitude: float, longitude: float, *,
                    fmt: Format = Format.LGRS,
                    typ: Type = Type.LABELED,
                    region: Region = Region.ANY,
                    extended_ltm: bool = False) -> tuple | str:
    ...

# Note: Or could "cheat" and call this `from_projected()`.
def from_lps_or_ltm(easting: float, northing: float, *,
                    fmt: Format = Format.LGRS,
                    typ: Type = Type.LABELED,
                    region: Region = Region.ANY,
                    extended_ltm: bool = False) -> tuple | str:
    """
    Convert from LPS or LTM coordinates.

    Parameters
    ----------
    easting : float
        Easting coordinate.
    northing : float
        Northing coordinate.
    fmt : Format, default=Format.LGRS
        The format of `converted`.
    typ : Type, default=Type.LABELED
        The type of `converted`.
    region : Region, default=Region.ANY
        Whether to enforce a polar or non-polar check.
    extended_ltm : bool, default=False
        Whether to use the extended LTM region (from 80 to 82 degrees).

    Returns
    -------
    converted : tuple or str
        A named tuple or string representing the converted coordinates.

    Raises
    ------
    lgrs.exceptions.NonPolarError
        If `region` requires the polar region but `converted` is not
        poleward of 80 degrees (if `extended_ltm` is `False`) or 82 degrees
        (if `extended_ltm` is `True`).
    lgrs.exceptions.PolarError
        If `region` requires the non-polar region but `converted` is
        poleward of 80 degrees (if `extended_ltm` is `False`) or 82 degrees
        (if `extended_ltm` is `True`).

    Examples
    --------
    >>> import lgrs.cli
    >>> lgrs.cli.from_lps_or_ltm(488590, 608480)
    (zone="A", area="ZS", easting=13590, northing=8480,
     string="AZS1359008480")
    >>> lgrs.cli.from_lps_or_ltm(488590, 608480, typ=Type.STRING)
    "AZS1359008480"
    >>> lgrs.cli.from_lps_or_ltm(488590, 608480, typ=Type.STRING)
    "A ZS 13590 08480"

    """
    # import sys
    # _rich.print("[bold red]NonPolarError:[/bold red] Test.", file=sys.stderr, flush=True)
    ...



# endregion