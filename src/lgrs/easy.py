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
# Special.
from __future__ import annotations

# Standard.
import collections as _collections
import dataclasses as _dataclasses
import functools as _functools
import inspect as _inspect
import itertools as _itertools
import json as _json
import pathlib as _pathlib
import re as _re
import types as _types
import typing as _typing

# Internal.
import lgrs.bounds as _bounds
import lgrs.coords as _coords
import lgrs.database as _database
import lgrs.grid as _grid


# endregion
###############################################################################
# region> FAMILIES
###############################################################################
@_dataclasses.dataclass(frozen=True, kw_only=True)
class _BaseFamily:
    """A group of coordinates derived from `latlon`."""


class _BaseFullFamily:
    """
    A family of related coordinates derived from `latlon`.

    Attributes
    ----------
    point: lgrs.coords.LpsPoint | lgrs.coords.LtmPoint
        A point at the same location as `latlon`.
    lgrs: lgrs.coords.LpsLgrsBox | lgrs.coords.LtmLgrsBox
        An LGRS box that contains `latlon`.
    acc: lgrs.coords.LpsAccBox | lgrs.coords.LtmAccBox
        An ACC box that contains `latlon`.
    corner: lgrs.coords.LpsPoint | lgrs.coords.LtmPoint
        The reference (lower-left) corner of `lgrs` and `acc`.
    center: lgrs.coords.LpsPoint | lgrs.coords.LtmPoint
        The center point of `lgrs` and `acc`.
    """


@_dataclasses.dataclass(frozen=True, kw_only=True)
class _FamilyTemplate:
    input_latlon: _coords.LatLonPoint
    input_lgrs: _coords.LpsLgrsBox | _coords.LtmLgrsBox | None = None
    precision: float = 1  # Aligned with `input_lgrs`.
    extended_ltm: bool = False  # Aligned with `input_lgrs`.

    def __post_init__(self):
        if self.input_lgrs is not None:
            object.__setattr__(self, "precision", self.input_lgrs.precision)
            object.__setattr__(
                self, "extended_ltm", self.input_lgrs.constraints.extended_ltm
            )

    # * DATA ATTRIBUTES. ──────────────────────────────────────────────
    @_functools.cached_property
    def acc(self) -> _coords.LpsAccBox | _coords.LtmAccBox:
        return self.lgrs.to_acc()

    @_functools.cached_property
    def center(self) -> _coords.LpsPoint | _coords.LtmPoint:
        return self.lgrs.center_latlon.to_lps_or_ltm(
            constraints=self.constraints
        )

    @_functools.cached_property
    def constraints(self) -> _coords.Constraints:
        if self.input_lgrs is None:
            constraints = _coords.Constraints(extended_ltm=self.extended_ltm)
        else:
            constraints = _coords.Constraints(global_crs=self.input_lgrs.crs)
        return constraints

    @_functools.cached_property
    def corner(self) -> _coords.LpsPoint | _coords.LtmPoint:
        return self.lgrs.to_lps_or_ltm(constraints=self.constraints)

    @_functools.cached_property
    def lgrs(self) -> _coords.LpsLgrsBox | _coords.LtmLgrsBox:
        if self.input_lgrs is None:
            return self.input_latlon.to_lgrs(
                precision=self.precision, constraints=self.constraints
            )
        else:
            return self.input_lgrs

    @_functools.cached_property
    def point(self) -> _coords.LpsPoint | _coords.LtmPoint:
        return self.input_latlon.to_lps_or_ltm(constraints=self.constraints)

    # * METHODS. ──────────────────────────────────────────────────────
    def make_family(self) -> LpsFamily | LtmFamily:
        if self.input_lgrs is None:
            fam_typ = NominalFamily
        else:
            match self.lgrs:
                case _coords.LpsLgrsBox():
                    fam_typ = LpsFamily
                case _coords.LtmLgrsBox():
                    fam_typ = LtmFamily
                case _:
                    raise TypeError(
                        "`.lgrs` does not have an expected type: "
                        f"{self.lgrs!r}"
                    )
        fam = fam_typ(
            point=self.point,
            lgrs=self.lgrs,
            acc=self.acc,
            corner=self.corner,
            center=self.center,
        )
        return fam


@_dataclasses.dataclass(frozen=True, kw_only=True)
class ForcedFamily(_BaseFamily):
    lps: _coords.LpsPoint
    ltm: _coords.LtmPoint


@_dataclasses.dataclass(frozen=True, kw_only=True)
class LpsFamily(_BaseFamily):
    point: _coords.LpsPoint
    lgrs: _coords.LpsLgrsBox
    acc: _coords.LpsAccBox
    corner: _coords.LpsPoint
    center: _coords.LpsPoint


@_dataclasses.dataclass(frozen=True, kw_only=True)
class LtmFamily(_BaseFamily):
    point: _coords.LtmPoint
    lgrs: _coords.LtmLgrsBox
    acc: _coords.LtmAccBox
    corner: _coords.LtmPoint
    center: _coords.LtmPoint


@_dataclasses.dataclass(frozen=True, kw_only=True)
class NominalFamily(_BaseFamily):
    point: _coords.LpsPoint | _coords.LtmPoint
    lgrs: _coords.LpsLgrsBox | _coords.LtmLgrsBox
    acc: _coords.LpsAccBox | _coords.LtmAccBox
    corner: _coords.LpsPoint | _coords.LtmPoint
    center: _coords.LpsPoint | _coords.LtmPoint


# endregion
###############################################################################
# region> RELATIVES
###############################################################################
@_dataclasses.dataclass(frozen=True)
class GeoRelatives:
    """
    Create an organized structure of related coordinates.

    Given an `input_coordinate` (point or box), extracts a geographic point
    coordinate (`.latlon`) and from that point coordinate derives many
    related coordinates. Derived coordinates are logically grouped into
    "families", but not all families may be relevant for a given
    `input_coordinate`. Each coordinate within a family is called a
    "member".

    Parameters
    ----------
    input_coordinate : lgrs.coords.BaseCoordinate
        The coordinate from which `latlon` is derived.
    precision : float
        The maximum allowed nominal side length of each box member. If not a
        supported precision, the actual precision is rounded down to a
        better precision.
    extended_ltm : bool, default=False
        Whether to use the extended LTM region, which extends to 82° N/S
        instead of 80° N/S.
    use_center : bool, default=False
        When `input_coordinate` is a `BoxCoordinate`, specifies whether to
        use its center instead of its reference (lower-left) corner to
        derive `latlon` and hence all members. If `input_coordinate` is
        instead a `PointCoordinate`, this argument is ignored.
    sort_by_center : bool, default=True
        If `.ltm_2` is populated, it will represent the box whose center
        (if `True`) or reference (lower-left) corner (if `False`) is closest
        to `latlon`.
    note : string, optional
        A custom note.

    Attributes
    ----------
    latlon : lgrs.coords.LatLonPoint
        `input_coordinate` as a geographic point coordinate. Honors
        `use_center`, if applicable.
    nominal : NominalFamily
        The family of nominal coordinates. Each member is derived from
        `latlon` using default constraints only, except that `extended_ltm`
        is honored.
    lps : LpsFamily | None
        The family of LPS-based coordinates, which all share the same CRS.
        `None` if no LPS-based box is compatible with `latlon`.
    ltm_1 : LtmFamily | None
        A family of LTM-based coordinates, which all share the same CRS.
        `None` if no LTM-based box is compatible with `latlon`.
    ltm_2 : LpsFamily | None
        A second family of LTM-based coordinates, which all share the same
        CRS. Only populated when `latlon` is near the boundary between two
        LTM zones, so that a valid box in each zone contains `latlon`. Then,
        the CRS of `ltm_2` differs from that of `ltm_1`. See
        `center_proximity`.
    forced : ForcedFamily
        A pair of LPS and LTM coordinates representing the same location as
        `latlon`. Each of these is populated regardless of the location of
        `latlon` (hence "forced").
    json_dict : dict
        A mapping representation that includes `GeoRelatives` initialization
        parameters and all `GeoRelatives` attributes except for `json` and
        `json_dict`, as well as initialization parameters and some salient
        attributes (such as `.string`) for coordinate members.
    json : string
        A JSON-compatible pretty string representation of `json_dict` whose
        values are all JSON objects, strings, numbers (int or real),
        booleans, or null. Created by calling `.to_json()`.

    Notes
    -----
    When all families are relevant, the overall structure is as shown below.
    For easy reference, each attribute name representing a family is shown
    in square brackets (for example, ``[nominal]``, even though the
    attribute name is ``nominal``) and comments are shown in angle
    brackets::

        GeoRelatives
        ├── input_coordinate
        ├── precision
        ├── extended_ltm
        ├── center_proximity
        ├── latlon
        ├── note
        ├── [nominal]
        │   ├── point: LpsPoint | LtmPoint <same location as `latlon`>
        │   ├── lgrs: LpsLgrsBox | LtmLgrsBox <contains `latlon`>
        │   ├── acc: LpsAccBox | LtmAccBox <contains `latlon`>
        │   ├── corner: LpsPoint | LtmPoint <`lgrs`/`acc` lower-left corner>
        │   └── center: LpsPoint | LtmPoint <`lgrs`/`acc` center>
        ├── [lps]
        │   ├── point: LpsPoint <same location as `latlon`>
        │   ├── lgrs: LpsLgrsBox <contains `latlon`>
        │   ├── acc: LpsAccBox <contains `latlon`>
        │   ├── corner: LpsPoint <`lgrs`/`acc` lower-left corner>
        │   └── center: LpsPoint <`lgrs`/`acc` center>
        ├── [ltm_1]
        │   ├── point: LtmPoint <same location as `latlon`>
        │   ├── lgrs: LtmLgrsBox <contains `latlon`>
        │   ├── acc: LtmAccBox <contains `latlon`>
        │   ├── corner: LtmPoint <`lgrs`/`acc` lower-left corner>
        │   └── center: LtmPoint <`lgrs`/`acc` center>
        ├── [ltm_2]
        │   ├── point: LtmPoint <same location as `latlon`>
        │   ├── lgrs: LtmLgrsBox <contains `latlon`>
        │   ├── acc: LtmAccBox <contains `latlon`>
        │   ├── corner: LtmPoint <`lgrs`/`acc` lower-left corner>
        │   └── center: LtmPoint <`lgrs`/`acc` center>
        ├── [forced]
        │   ├── lps: LpsPoint <same location as `latlon`>
        │   └── ltm: LtmPoint <same location as `latlon`>
        ├── json_dict
        └── json

    It is guaranteed that `nominal.point`, `nominal.lgrs`, and `nominal.acc`
    have identical coordinate values (but not necessarily constraints) to
    their counterparts in exactly one of `lps`, `ltm_1`, or `ltm_2`.
    Typically, all members of `nominal` are (non-constraint) identical to
    their counterparts in one of those other families, but this is not
    guaranteed generally due to complications near zone boundaries.

    All `lgrs` members come from ``latlon.to_all_lgrs(...)``. Better
    performance and more precise control can be achieved using coordinate
    instances and their methods directly. In that case, use
    `lgrs.coords.Constraints()` to target non-nominal coordinates.
    """

    input_coordinate: _coords.PointCoordinate
    _: _dataclasses.KW_ONLY
    precision: float
    extended_ltm: bool = False
    use_center: bool = False
    sort_by_center: bool = True
    note: str | None = None

    # * UTILITIES. ────────────────────────────────────────────────────
    def _assign_nonnominal(self) -> None:
        # Organize LGRS boxes by region.
        region_to_boxes = _collections.defaultdict(list)
        for box in self.latlon.to_all_lgrs(
            precision=self.precision, extended_ltm=self.extended_ltm
        ):
            match box:
                case _coords.LpsLgrsBox():
                    region = "LPS"
                case _coords.LtmLgrsBox():
                    region = "LTM"
                case _:
                    raise TypeError(
                        f"`box` does not have an expected type: {box!r}"
                    )
            region_to_boxes[region].append(box)

        # Sort LTM boxes, if necessary.
        ltm_boxes = region_to_boxes["LTM"]
        if len(ltm_boxes) > 1:
            if self.sort_by_center:
                sorter = self._sort_by_center
            else:
                sorter = self._sort_by_corner
            ltm_boxes.sort(key=sorter)

        # Assign attributes.
        lps_boxes = region_to_boxes["LPS"]
        for boxes, attr_names in (
            (lps_boxes, ("lps",)),
            (ltm_boxes, ("ltm_1", "ltm_2")),
        ):
            for box, attr_name in _itertools.zip_longest(boxes, attr_names):
                if box is None:
                    fam = None
                elif attr_name is None:
                    region = attr_name.split("_")[0].upper()
                    max_count = len(attr_names)
                    box_count = len(boxes)
                    raise TypeError(
                        f"{region} region expected to have {max_count} "
                        f"boxes at most, but has: {box_count}"
                    )
                else:
                    fam = _FamilyTemplate(
                        input_latlon=self.latlon, input_lgrs=box
                    ).make_family()
                object.__setattr__(self, attr_name, fam)

    def _sort_by_center(self, box: _coords.LtmLgrsBox) -> float:
        return box.center_latlon.distance_to(self.latlon)

    def _sort_by_corner(self, box: _coords.LtmLgrsBox) -> float:
        return box.to_latlon().distance_to(self.latlon)

    # * BASIC DATA ATTRIBUTES. ────────────────────────────────────────
    @_functools.cached_property
    def forced(self) -> ForcedFamily:
        return ForcedFamily(
            lps=self.latlon.to_lps(search=True),
            ltm=self.latlon.to_ltm(search=True),
        )

    @_functools.cached_property
    def latlon(self) -> _coords.LatLonPoint:
        if (
            isinstance(self.input_coordinate, _coords.BoxCoordinate)
            and self.use_center
        ):
            latlon = self.input_coordinate.center_latlon
        else:
            latlon = self.input_coordinate.to_latlon()
        return latlon

    @_functools.cached_property
    def lps(self) -> LpsFamily | None:
        self._assign_nonnominal()
        return self.lps

    @_functools.cached_property
    def ltm_1(self) -> LtmFamily | None:
        self._assign_nonnominal()
        return self.ltm_1

    @_functools.cached_property
    def ltm_2(self) -> LtmFamily | None:
        self._assign_nonnominal()
        return self.ltm_2

    @_functools.cached_property
    def nominal(self) -> LpsFamily | LtmFamily:
        return _FamilyTemplate(
            input_latlon=self.latlon, precision=self.precision
        ).make_family()

    # * DERIVED ATTRIBUTES. ───────────────────────────────────────────
    @_functools.cached_property
    def json(self) -> str:
        return self.to_json()

    @_functools.cached_property
    def json_dict(self) -> dict:
        json_dict = {}
        for top_key in (
            *(field.name for field in _dataclasses.fields(self)),
            "latlon",
            "nominal",
            "lps",
            "ltm_1",
            "ltm_2",
            "forced",
        ):
            val = getattr(self, top_key)
            if isinstance(val, _BaseFamily):
                # *REASSIGNMENT*
                val = {
                    field.name: getattr(val, field.name)
                    for field in _dataclasses.fields(val)
                }
            json_dict[top_key] = val
        return json_dict

    # * METHODS. ──────────────────────────────────────────────────────
    def get(self, address: str) -> _typing.Any:
        """
        Safely get any attribute chain from `self`.

        When an attribute chain first encounters `None`, the remaining
        chained attributes are ignored and `None` is returned. This makes
        it a little easier to work with attribute chains in which the final
        attribute, or one of its ancestors, does not exist. See Examples.

        Parameters
        ----------
        address : string
            The dot-delimited attribute name to get, such as
            `"ltm_2.point"`.

        Returns
        -------
        value : typing.Any
            The value at `address` or `None`, if `None` was encountered.

        Examples
        --------
        Consider an instance for which `.ltm_1` is populated but neither
        `.ltm_2` nor `.lps`.

        >>> from lgrs.coords import LatLonPoint
        >>> geo_point = LatLonPoint(0, 0)
        >>> relatives = GeoRelatives(geo_point, precision=1)
        >>> relatives.ltm_1 is not None
        True
        >>> relatives.ltm_2 is not None
        False
        >>> relatives.lps is not None
        False

        Now imagine that you wanted to compile the `CRS` of all LGRS members
        without knowing which families were populated. With the current
        method, this is much less cumbersome.

        >>> crs_list = [
        ...     crs for address in
        ...     ("ltm_1.lgrs.crs", "ltm_2.lgrs.crs", "lps.lgrs.crs")
        ...     if (crs := relatives.get(address)) is not None
        ... ]
        >>> len(crs_list)
        1
        """
        result = self  # Initialize.
        for attr_name in address.split("."):
            result = getattr(result, attr_name)
            if result is None:
                return None
        return result

    def to_json(
        self,
        *,
        use_objects: bool = False,
        ensure_ascii: bool = False,
        indent: int | str | None = 4,
        **kwargs,
    ) -> str:
        """
        Make JSON string representation of `.json_dict`.

        Parameters
        ----------
        use_objects : bool, default=False
            Whether to represent coordinates as JSON objects rather than
            strings. Internally, sets ``default`` to `str` if `False` or
            `lgrs.coords.BaseCoordinate.to_json` if `True`. If ``default``
            is specified explicitly, that argument overrides `use_objects`.
        ensure_ascii : bool, default=False
            Passed to ``json.dumps()``. Note default.
        indent : int or str or None, default=4
            Passed to ``json.dumps()``. Note default.
        **kwargs
            Additional keyword arguments, including ``default``, are passed
            to ``json.dumps()``.

        Returns
        -------
        string : str
            The JSON representation.
        """
        # Collect `json.dumps()` kwargs.
        dumps_kwargs = locals().copy()
        del dumps_kwargs["self"]
        del dumps_kwargs["use_objects"]
        dumps_kwargs.update(dumps_kwargs.pop("kwargs"))

        # Set `default`, if applicable.
        if "default" not in dumps_kwargs:
            if use_objects:
                default = _coords.BaseCoordinate.to_json_dict
            else:
                default = str
            dumps_kwargs["default"] = default

        # Dump to string and return.
        return _json.dumps(self.json_dict, **dumps_kwargs)


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
# TODO: Decide what `maxsize` should be.
@_functools.lru_cache(maxsize=1000)
def _make_georelatives_instance(*args, **kwargs):
    return GeoRelatives(*args, **kwargs)


def convert_coordinate(
    input_coordinate: _coords.BaseCoordinate | str,
    *,
    precision: float,
    extended_ltm: bool = False,
    use_center: bool = False,
    sort_by_center: bool = True,
    note: str | None = None,
    target: str | None = None,
) -> GeoRelatives | _typing.Any:
    """
    Convert an input coordinate to all relevant coordinates.

    Internally, a `GeoRelatives` instance is generated. Recent
    `GeoRelatives` instances are cached when created by the present
    function, so there is trivial cost to making subsequent calls with a
    different `target` each time (but all other arguments the same). See the
    `GeoRelatives` documentation for other relevant information.

    Parameters
    ----------
    input_coordinate : a point or box coordinate, or equivalent string
        The input coordinate to convert. If a string, it is converted to a
        coordinate instance (by `lgrs.coords.BaseCoordinate.from_string()`)
        before being passed to `GeoRelatives()`.
    precision : float
        See `GeoRelatives` documentation.
    extended_ltm : bool, default=False
        See `GeoRelatives` documentation.
    use_center : bool, default=False
        See `GeoRelatives` documentation.
    sort_by_center : bool, default=True
        See `GeoRelatives` documentation.
    note : string, optional
        See `GeoRelatives` documentation.
    target : string, optional
        Specifies the address (attribute reference, possibly chained) on the
        `GeoRelatives` instance whose value should be returned, such as
        `"json"`, `"nominal.lgrs"`, or `"forced.lps.northing"`. Internally,
        uses ``GeoRelatives.get(target)``, so that chains that may be
        interrupted by `None` can be safely used. See Examples.

    Returns
    -------
    relatives_or_value : GeoRelatives or typing.Any
        The `GeoRelatives` instance (if `target` is not specified) or
        whatever object is targeted by `target`.

    Examples
    --------
    Consider an example point.

    >>> example = "80 N, 0 E"

    First, let's confirm that parsing works.

    >>> convert_coordinate(example, precision=1, target="latlon")
    LatLonPoint(latitude=80, longitude=0, constraints=Constraints())

    To get the 1-m LGRS box as a coordinate:

    >>> convert_coordinate(example, precision=1, target="nominal.lgrs") # doctest: +NORMALIZE_WHITESPACE
    LpsLgrsBox(longitudinal_band='Z', easting_area='A', northing_area='-',
    easting='00000', northing='22818', constraints=Constraints())

    To get that same box as a string reference:

    >>> convert_coordinate(
    ...     example, precision=1, target="nominal.lgrs.string"
    ... )
    'ZA-0000022818'

    To get the (pretty-formatted) geographic coordinate at the center of
    that box:

    >>> convert_coordinate(
    ...     example, precision=1, target="nominal.lgrs.center_latlon.string"
    ... )
    '80.00000244867157° N, 9.480358578044988e-05° E'

    To determine whether the example point lies in both valid LPS and LTM
    ACC boxes:

    >>> in_lps = convert_coordinate(
    ...     example, precision=1, target="lps.acc"
    ... ) is not None
    >>> in_ltm = convert_coordinate(
    ...     example, precision=1, target="ltm_1.acc"
    ... ) is not None
    >>> in_lps and in_ltm
    True

    To make it easier to work with deep targets, any target that is
    interrupted by `None` simply returns `None` (rather than, say, raising
    an `AttributeError`).

    >>> lps_2 = convert_coordinate(example, precision=1, target="lps_2")
    >>> lps_2 is None
    True
    >>> convert_coordinate(example, precision=1, target="lps_2.lgrs.string")
    None
    """  # noqa: E501
    # Create `GeoRelatives` instance.
    if isinstance(input_coordinate, str):
        # *REASSIGNMENT*
        input_coordinate = _coords.BaseCoordinate.from_string(input_coordinate)
    georel_kwargs = locals().copy()
    del georel_kwargs["target"]
    georel = _make_georelatives_instance(**georel_kwargs)

    # Extract and return targeted value.
    if target is None:
        return georel
    else:
        return georel.get(target)


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
        The maximum allowed precision, which is the nominal side length of
        each grid box. If not a supported precision, the actual precision is
        rounded down to a better precision. All boxes have the same precision.
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
