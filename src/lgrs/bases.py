##############################################################################
# region> IMPORT
##############################################################################
# External.
from __future__ import annotations
import abc as _abc
import re as _re
import types as _types
import typing as _typing

# Internal.
import lgrs.util as _util

# endregion


##############################################################################
# region> AREAL
##############################################################################
class AbstractBaseAreal(_abc.ABC):
    name: str = _util.make_abstract_property()

    def is_compatible_with(self, other: AbstractBaseAreal) -> bool:
        if isinstance(other, type(self)):
            # Note: Extent is intentionally ignored.
            return (self.name == other.name)
        return False

class AbstractBaseZone(AbstractBaseAreal):
    extended_ltm: bool = _util.ExpectedAttribute()
    hemisphere: str = _util.ExpectedAttribute()
    is_global: bool = _util.ExpectedAttribute()
    number: int = _util.ExpectedAttribute()

# endregion



##############################################################################
# region> COORDINATES
##############################################################################
# Credit: https://stackoverflow.com/a/12643073/2503724
_simple_number_pattern = _re.compile(
    r"^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)$"
)

class AbstractBaseCoordinates(_abc.ABC):
    latitude: float = _util.make_abstract_property()
    longitude: float = _util.make_abstract_property()

    @staticmethod
    def _parse_string(
            string: str, *,
            form: tuple[type | _types.UnionType, ...] | None = None
    ) -> tuple[int | float | str]:
        """
        Parse space-delimited string to a tuple of numbers and strings.

        Type coercion preference is: ``int``, ``float``, ``str``. Parsing
        should be safe: an overly long `string` will raise an error, and
        coercion is only attempted if `string` part is a simple number
        (that is, consists only of 0-9 and a decimal point, possibly
        with a leading sign).

        Parameters
        ----------
        string : str
            String to be parsed.
        form : tuple[type | types.UnionType, ...], optional
            Specifies the expected form of `parsed`. For example,
            ``(int | float, str, float, float)``.

        Raises
        ------
        TypeError
            If `string` is too long or `parsed` does not match `form`.

        Returns
        -------
        parsed : tuple[int | float | str]
            `string` parsed to a tuple.
        """
        # Validate input length.
        if len(string) > 50:
            raise TypeError(f"`string` is too long: {string!r}")

        # Parse.
        string_parts = string.split(" ")
        final_parts = []
        for part in string_parts:
            final_part = part  # Default.
            if _simple_number_pattern.search(part):
                for typ_ in (int, float):
                    try:
                        final_part = typ_(part)
                    except ValueError:
                        continue
                    else:
                        break
            final_parts.append(final_part)

        # Optionally compare to `form`.
        final_parts_tup = tuple(final_parts)
        if form is not None:
            expected_len = len(form)
            parsed_len = len(final_parts_tup)
            if expected_len != parsed_len:
                raise TypeError(f"Expected a parsed length of {expected_len}, "
                                f"but got {parsed_len}: {final_parts_tup!r}")
            for typ_, val in zip(form, final_parts_tup):
                if not isinstance(val, typ_):
                    raise TypeError(f"Expected `form={form}` for `parsed`, "
                                    f"but got: {final_parts_tup!r}")

        # Return.
        return final_parts_tup

    # TODO: Remove this commented code when implemented elsewhere.
    # @classmethod
    # def from_string(cls, string: str) -> _typing.Self:
    #     # Parse `string`.
    #     if " " in string:
    #         parts = string.split(" ")
    #         if len(parts) != 4:
    #             raise TypeError("If non-condensed, `string` must have four "
    #                             "parts delimited by spaces: <zone_number> "
    #                             "<hemisphere> <easting> <northing>")
    #         zone_num_str, hemi, easting_str, northing_str = parts
    #     elif "." in string:
    #         raise TypeError("The decimal point is only supported in the non-"
    #                         "condensed format.")
    #     else:
    #         # TODO: Implement condensed format.
    #         raise NotImplementedError("Support for condensed format.")
    #
    #     # Return new coordinates instance.
    #     import areal  # Lazy import, to avoid circular import.
    #     zone = areal.LtmZone(number=int(zone_num_str), hemisphere=hemi)
    #     new = cls(easting=float(easting_str), northing=float(northing_str),
    #               zone=zone)
    #     return new

class AbstractGeographicCoordinates(AbstractBaseCoordinates):
    latitude: float = _util.ExpectedAttribute()
    longitude: float = _util.ExpectedAttribute()

class AbstractGridCoordinates(AbstractBaseCoordinates):
    northing: float = _util.ExpectedAttribute()
    easting: float = _util.ExpectedAttribute()
    zone: AbstractBaseZone = _util.ExpectedAttribute()

# endregion