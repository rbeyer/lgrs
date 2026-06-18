"""
Coordinate types: geographic and projected, point and box.

This module also supports coordinate transformations.

Examples

>>> lps_lgrs_box = LpsLgrsBox(
...     longitudinal_band="A", easting_area="Z", northing_area="S",
...     easting="13590", northing="08480"
... )
>>> alt_lps_lgrs_box = LpsLgrsBox.from_string("AZS1359008480")
>>> alt_lps_lgrs_box.is_equal_to(lps_lgrs_box, error=True)
True
"""

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
import abc as _abc
import collections as _collections
import dataclasses as _dataclasses
import functools as _functools
import itertools as _itertools
import types as _types
import typing as _typing
import weakref as _weakref
from math import floor as _floor

# External.
import pyproj as _pyproj
import regex as _regex
import shapely as _shapely
from beartype._check.forward.reference.fwdrefmeta import (
    BeartypeForwardRefMeta as _BeartypeForwardRefMeta,
)

# Internal.
import lgrs.bounds as _bounds
import lgrs.caching as _caching
import lgrs.database as _database
import lgrs.exceptions as _exceptions
import lgrs.srs.srs as _srs
import lgrs.srs.wkt as _wkt
import lgrs.values as _values

# endregion
###############################################################################
# region> TYPE ALIASES
###############################################################################
type _ToMethod = _collections.abc.Callable[..., BaseCoordinate]
type FieldData = _collections.abc.Mapping[str, _typing.Any]


# endregion
###############################################################################
# region> CORNERS
###############################################################################
@_dataclasses.dataclass(frozen=True)
class GeographicCorners(_bounds._Base):
    lower_left: LatLonPoint
    lower_right: LatLonPoint
    upper_right: LatLonPoint
    upper_left: LatLonPoint

    def __iter__(self) -> _typing.Iterator[LatLonPoint]:
        for v in self._iter_first_four_field_values():
            yield v


@_dataclasses.dataclass(frozen=True)
class ProjectedCorners(_bounds._Base):
    lower_left: LpsPoint | LtmPoint
    lower_right: LpsPoint | LtmPoint
    upper_right: LpsPoint | LtmPoint
    upper_left: LpsPoint | LtmPoint

    def __iter__(self) -> _typing.Iterator[LpsPoint | LtmPoint]:
        for v in self._iter_first_four_field_values():
            yield v


# endregion
###############################################################################
# region> UTILITIES: CACHING
###############################################################################
def _cache_new_cousin(func: _ToMethod) -> _ToMethod:
    """
    Cache the new `BaseCoordinate` returned whenever `func()` is called.`.

    See `BaseCoordinate._get_cached_or_create()` for a description of what a
    "cousin" is.

    Parameters
    ----------
    func : callable
        The hidden `._to_*()` method to be decorated.

    Returns
    -------
    wrapped : callable
        The wrapped `func`.
    """

    # Wrap function.
    @_functools.wraps(func)
    def wrapped(self: BaseCoordinate, **kwargs) -> BaseCoordinate:
        new = func(self, **kwargs)
        self._register_cousin(new)
        return new

    # Return wrapped function.
    return wrapped


def _resolve_beartype_fwd_refs(refs: _typing.Any) -> _typing.Any:
    # Somewhat ugly patch to undo some `beartype` magic.
    was_tup = isinstance(refs, tuple)
    if not was_tup:
        if isinstance(refs, _BeartypeForwardRefMeta):
            refs = (refs,)
        else:
            return refs
    resolved = (
        (
            globals()[ref.__name__]
            if isinstance(ref, _BeartypeForwardRefMeta)
            else ref
        )
        for ref in refs
    )
    if was_tup:
        return tuple(resolved)
    else:
        (single_resolved,) = resolved
        return single_resolved


@_functools.cache
def _resolve_out_types(func: _collections.abc.Callable) -> tuple[type, ...]:
    out_hint = _resolve_beartype_fwd_refs(
        _typing.get_type_hints(func)["return"]
    )
    if isinstance(out_hint, _BeartypeForwardRefMeta):
        out_hint = globals()[out_hint.__name__]
    if isinstance(out_hint, _types.UnionType):
        out_types = _resolve_beartype_fwd_refs(_typing.get_args(out_hint))
    else:
        out_types = (out_hint,)
    return out_types


def _return_none(self: BaseCoordinate) -> None:
    return None


# endregion
###############################################################################
# region> UTILITIES: REGEX
###############################################################################
def _calc_na_letterset(zone_number: int) -> int:
    # TODO: Determine if the "- 1" (which appears in the reference
    #  code but not in Eq. 83) is correct.
    na_letterset = (zone_number - 1) % 3  # Eq. 83
    return na_letterset


def _compile_regex_without_i_and_o(pattern: str) -> _regex.Pattern:
    clean_pattern = _regex.sub("[A-Z]-[A-Z]", _remove_i_and_o, pattern)
    annotated_clean_pattern = f"{clean_pattern}(?# {_regex.escape(pattern)})"
    return _regex.compile(annotated_clean_pattern)


def _expand_char_range(char_range: str) -> list[str]:
    start_char, end_char = char_range.split("-")
    chars = [chr(i) for i in range(ord(start_char), ord(end_char) + 1)]
    return chars


def _extract_chars_from_pattern(
    pattern: _regex.Pattern | None = None,
    name: str | None = None,
    *,
    pre: str = "",
    post: str = "",
) -> str:
    # Note: M2025 assigns a value to each character in each table.
    # However, in all M2025 equations, characters are treated as 0-
    # indexed. Therefore, a string (rather than mapping) is sufficient.
    # Note: Extraction is not general (e.g., does not accommodate
    # escaped ")").
    chars = _regex.search(
        rf"\(\?P<{name}>\[(?P<gpattern>.*?)]\)", pattern.pattern
    ).group("gpattern")
    final = pre + chars + post
    return final


def _format_as_five_digit_int(n: float) -> str:
    return f"{_smart_truncate(n):05}"


def _make_en_pattern(*digit_count: int) -> str:
    pattern = "|".join(
        f"((?P<easting>[0-9]{{{i}}})(?P<northing>[0-9]{{{i}}}))"
        for i in sorted(digit_count, reverse=True)
    )
    return pattern


def _remove_i_and_o(match: _regex.Match) -> str:
    expanded = _expand_char_range(match.group())
    for char in ("I", "O"):
        try:
            expanded.remove(char)
        except ValueError:
            continue
    return "".join(expanded)


# endregion
###############################################################################
# region> UTILITIES: OTHER
###############################################################################
def _as_str(str_or_none: str | None) -> str:
    if str_or_none is None:
        return ""
    else:
        return str_or_none


@_functools.cache
def _get_geod() -> _pyproj.Geod:
    return _pyproj.Geod(sphere=True, a=_wkt.LUNAR_RADIUS)


def _smart_truncate(f: float, *, tolerance: float = 0.001) -> int:
    # TODO: Code originally rounded to nearest int when that int was
    #  within `tolerance`, mimicking `check_decimal_round()` of
    #  reference code and presumably designed to mitigates undesirable
    #  results that arise due to floating-point precision. However, in
    #  testing, rounding thusly could push a point barely on one side
    #  of a zone to another zone, resulting in an invalid coordinate.
    #  Currently testing whether this rounding can be dropped.
    return _floor(f)
    # Original code:
    # nearest_int = round(f)
    # if abs(nearest_int - f) < tolerance:
    #     return nearest_int
    # else:
    #     return _floor(f)


# endregion
###############################################################################
# region> CONSTRAINTS
###############################################################################
@_dataclasses.dataclass(frozen=True, kw_only=True)
class Constraints(metaclass=_caching._MetaMultiton):
    """
    Create a set of constraints for coordinates and their transforms.

    By default, the lunar surface is partitioned into three discrete regions,
    each with its own latitudinal range. The two polar regions (north and
    south) are at high latitudes and use the Lunar Polar Stereographic (LPS)
    system; the non-polar region includes middle and low latitudes and uses
    the Lunar Transverse Mercator (LTM) system. Together, a set of
    constraints determines the details of this partitioning.

    Namely, `extended_ltm`, `global_ltm`, and `global_lps` determine the
    respective latitudinal ranges of the LPS and LTM regions. (At most, only
    one of those constraints may be enabled.) If none of these three
    constraints are enabled, the preferred LPS/LTM boundary at 80° N/S is
    used. The remaining constraints determine the precise shape of
    boundaries. Specifically, `prefer_lps` and `prefer_ltm` (which are
    mutually incompatible) control the shape of the nominally latitudinal
    LPS/LTM boundary whereas `preferred_ltm_zone` controls the shape of
    nominally longitudinal boundary between adjacent LTM zones. If these
    constraints are disabled, boundaries follow lines of latitude and
    longitude exactly, which cut LGRS boxes along curved traces (as viewed
    in LPS and LTM space) on either side of each boundary. Finally, note
    that any `global_*` constraint should not be combined with any `prefer*`
    constraint.

    Parameters
    ----------
    prefer_lps : bool, default=False
        Whether to prefer the LPS system in nominally LTM areas that are
        just slightly equatorward of the nominal LPS/LTM boundary. Enabling
        this constraint causes the effective LPS/LTM boundary to follow the
        edges of LPS-LGRS 25-km boxes and cut through LTM-LGRS 25-km boxes.
    prefer_ltm : bool, default=False
        Whether to prefer the LTM system in nominally LPS areas that are
        just slightly poleward of the nominal LPS/LTM boundary. Enabling
        this constraint causes the effective LPS/LTM boundary to follow the
        edges of LTM-LGRS 25-km boxes and cut through LPS-LGRS 25-km boxes.
    preferred_ltm_zone : int, optional
        An LTM zone to prefer over the LTM zones on either side (to the
        west and east). Enabling this constraint causes the effective
        inter-zone boundary to follow the edges of 25-km boxes from the
        preferred zone.
    extended_ltm : bool, default=False
        Whether to use the extended LTM region. If `True`, the nominal
        poleward extent of the LTM region is 82° N/S instead of 80° N/S.
    global_lps : bool, default=False
        Whether to extend the LPS region globally. If `True`, there is no
        LTM region. This constraint is incompatible with all box
        coordinates.
    global_ltm : bool, default=False
        Whether to extend the LTM region globally. If `True`, there is no
        LPS region. This constraint is incompatible with all box
        coordinates.
    global_crs : lgrs.srs.srs.CRS, optional
        Used to force a specific CRS. Mostly intended for internal use. Not
        compatible with box coordinates nor with any other constraint.

    Raises
    ------
    TypeError
        If mutually incompatible constraints are used.
    """

    prefer_lps: bool = False
    prefer_ltm: bool = False
    preferred_ltm_zone: int | None = None
    extended_ltm: bool = False
    global_lps: bool = False
    global_ltm: bool = False
    global_crs: _srs.CRS | None = None

    def __post_init__(self) -> None:
        enabled_count = _wkt._validate_constraints(**self.__dict__)
        if self.global_crs and enabled_count > 1:
            raise TypeError(
                "If `global_crs` is specified, no other constraint can be set."
            )

    def __repr__(self) -> str:
        enabled_arg_strs = []
        for field in _dataclasses.fields(self):
            val = getattr(self, field.name)
            if val in (False, None):
                continue
            enabled_arg_strs.append(f"{field.name}={val!r}")
        return f"{self.__class__.__name__}({', '.join(enabled_arg_strs)})"

    _max_geod_length_of_25km_box_diag = _values.calculate_diagonal_length(
        25_000, safe_up=True
    )

    _max_geod_length_of_25km_box_diag_in_deg_lat = (
        _max_geod_length_of_25km_box_diag / _values.M_PER_DEGREE_LATITUDE
    )

    @_functools.cached_property
    def _crs_kwargs(self) -> dict[str, bool]:
        return {
            "extended_ltm": self.extended_ltm,
            "global_lps": self.global_lps,
            "global_ltm": self.global_ltm,
        }

    def _get_proj_crs_and_new_cousins(
        self, point: LatLonPoint
    ) -> tuple[_srs.CRS, _collections.abc.Sequence[BaseCoordinate]]:
        # Treat special forced CRS case.
        if self.global_crs is not None:
            return (self.global_crs, ())

        # Get nominal CRS.
        # Note: These lines are equivalent to, but faster than, calling
        # `lgrs.query_lunar_crs_info(...)`.
        (internal_name,) = _database._get_lunar_crs_internal_names(
            conformed_latitudes=(point.latitude,),
            conformed_longitudes=(point.longitude,),
            **self._crs_kwargs,
        )
        default_crs_info: _database.LunarCrsInfo = (
            _database.LunarCrsInfo._from_internal_name(internal_name)
        )
        default_crs = default_crs_info.get_crs()
        default_result = (default_crs, ())

        # If constrained to global LPS or LTM, nominal CRS is only
        # possible CRS.
        if self.global_lps or self.global_ltm:
            return default_result

        # If preference is for the other system...
        other_sys_is_preferred = any(
            (
                self.prefer_lps and default_crs_info.is_ltm,
                self.prefer_ltm and default_crs_info.is_lps,
            )
        )
        if other_sys_is_preferred:
            is_close_to_lps_ltm_boundary = (
                abs(self._min_abs_lps_lat - abs(point.latitude))
            ) < self._max_geod_length_of_25km_box_diag_in_deg_lat
            if is_close_to_lps_ltm_boundary:
                crs, new_cousins = self._test_forced_lgrs_box(
                    point, target_lps=self.prefer_lps
                )
                if crs is not None:
                    del default_crs_info  # Avoid accidental reuse.
                    default_crs = crs  # *REASSIGNMENT*
                    default_result = (crs, new_cousins)  # *REASSIGNMENT*

        # If `point` is (1) in an LPS region or (2) there is no LTM zone
        # preference, (2) that preference is already satisfied, or (3)
        # preferred LTM zone is too far away, return (current) default.
        if default_crs.ltm_zone is None or self.preferred_ltm_zone is None:
            return default_result
        ltm_zone_number = int(default_crs.ltm_zone[:-1])
        if (
            ltm_zone_number == self.preferred_ltm_zone
            or self.preferred_ltm_zone not in point._potential_ltm_zone_nums
        ):
            return default_result

        # Finally, check whether preferred LTM zone can accommodate
        # `point`.
        ltm_crs, new_cousins = self._test_forced_lgrs_box(
            point, ltm_zone_number=self.preferred_ltm_zone
        )
        if ltm_crs is not None:
            return (ltm_crs, new_cousins)
        return default_result

    @_functools.cached_property
    def _known_invalid_boxes(self) -> _weakref.WeakSet[BoxCoordinate]:
        return _weakref.WeakSet()

    @_functools.cached_property
    def _known_valid_boxes(self) -> _weakref.WeakSet[BoxCoordinate]:
        return _weakref.WeakSet()

    @_functools.cached_property
    def _max_abs_ltm_lat(self) -> float:
        if self.extended_ltm:
            return _wkt.LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        elif self.global_ltm:
            return 90.0
        elif self.global_lps:
            return -float("inf")
        else:
            return _wkt.LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE

    @_functools.cached_property
    def _max_abs_ltm_lat_with_preference(self) -> float:
        if not self.prefer_ltm:
            return self._max_abs_ltm_lat
        extreme_max = (
            self._max_abs_ltm_lat
            + self._max_geod_length_of_25km_box_diag_in_deg_lat
        )
        return extreme_max

    @_functools.cached_property
    def _min_abs_lps_lat(self) -> float:
        if self.extended_ltm:
            return _wkt.LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        elif self.global_ltm:
            return float("inf")
        elif self.global_lps:
            return 0.0
        else:
            return _wkt.LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE

    @_functools.cached_property
    def _min_abs_lps_lat_with_preference(self) -> float:
        if not self.prefer_lps:
            return self._min_abs_lps_lat
        extreme_min = (
            self._min_abs_lps_lat
            - self._max_geod_length_of_25km_box_diag_in_deg_lat
        )
        return extreme_min

    def _test_forced_lgrs_box(
        self,
        point: LatLonPoint,
        *,
        target_lps: bool = False,
        ltm_zone_number: int | None = None,
    ) -> tuple[_srs.CRS | None, _collections.abc.Sequence[BaseCoordinate]]:
        # Validate arguments.
        if target_lps and ltm_zone_number is not None:
            raise TypeError(
                "If `target_lps` is `True`, cannot specify `ltm_zone_number`"
            )

        # Get targeted CRS.
        if point.latitude >= 0:
            n_or_s = "N"
        else:
            n_or_s = "S"
        if target_lps:
            proj_crs: _srs.CRS = _srs.make_lunar_crs(
                n_or_s, extended_ltm=self.extended_ltm
            )
        else:
            if ltm_zone_number is None:
                # *REASSIGNMENT*
                _, ltm_zone_number = _database._calculate_ltm_zone_number(
                    point.longitude
                )
            proj_crs = _srs.make_lunar_crs(
                f"{ltm_zone_number}{n_or_s}", extended_ltm=self.extended_ltm
            )

        # Insofar as possible, force creation of a reference 25-km box.
        # Note: Make copy, so that potentially invalid products are kept
        # out of the cache of `point`.
        point_copy: LatLonPoint = point.copy()
        result_on_failure = (None, ())
        try:
            proj_point = point_copy._to_lps_or_ltm(
                proj_crs=proj_crs, validate=False
            )
            box: BoxCoordinate = proj_point.to_lgrs(validate=False)
            # Note: Transform may yield most extreme supported box
            # rather than a box containing `point`.
            if not box.contains(point, same_crs_only=False):
                return result_on_failure
            test_box: BoxCoordinate = box.with_precision(25_000)
        except Exception:
            # Note: Assume any exceptions (such as an IndexError)
            # indicates failure.
            return result_on_failure

        # Test whether any sample along edges of the reference box meets
        # constraint criteria (i.e., whether the box is valid).
        # Note: Code elsewhere expects exactly this list order.
        result_on_success = (proj_crs, [box, test_box, proj_point])
        # Note: When building a grid, for example, an equivalent
        # `test_box` may be generated many times by different box
        # instances. To improve performance, cache the result of this
        # block futher below, and immediately below, check that cache.
        if test_box in self._known_valid_boxes:
            return result_on_success
        elif test_box in self._known_invalid_boxes:
            return result_on_failure
        if target_lps:
            # TODO: Determine how many samples are required per edge.
            count_per_side = 1
        else:
            # TODO: Determine how many samples are required per edge.
            count_per_side = 1
        for lat, lon in test_box._sample_boundary(
            count_per_side, as_latlon=True
        ):
            if target_lps:
                if abs(lat) >= self._min_abs_lps_lat:
                    break
            elif all(
                (
                    proj_crs.area_of_use.south
                    <= lat
                    <= proj_crs.area_of_use.north,
                    proj_crs.area_of_use.west
                    <= lon
                    <= proj_crs.area_of_use.east,
                )
            ):
                break
        else:
            self._known_invalid_boxes.add(test_box)
            return result_on_failure
        self._known_valid_boxes.add(test_box)
        return result_on_success


_default_constraints = Constraints()


# endregion
###############################################################################
# region> COORDINATE BASE TYPES
###############################################################################
class _AbstractBaseCoordinate(_abc.ABC):
    pass


# Note: `_BaseCoordinate` is useful for defining behavior that depends
# on the class being a dataclass. Conversely, `BaseCoordinate` and its
# hidden subclasses are useful for defining all other behavior (without
# accidentally implying dataclass fields).
@_dataclasses.dataclass(frozen=True, kw_only=True)
class _BaseCoordinate(_AbstractBaseCoordinate):
    _fields_cached: _typing.ClassVar[tuple[_dataclasses.Field, ...]]

    # * FIELDS AND VALIDATION. ────────────────────────────────────────
    constraints: Constraints = _dataclasses.field(
        default=_default_constraints,
        compare=False,
    )
    validate: _dataclasses.InitVar[bool] = True

    def _raise_fallback_exception(self) -> _typing.NoReturn:
        raise _exceptions.MalformedCoordinate(
            f"Coordinate is not valid: {self!r}"
        )

    def _register_validation(self) -> None:
        object.__setattr__(self, "_was_validated", True)

    def _validate(self, *, raise_fallback: bool = True) -> bool:
        # First, attempt validation by reconstruction.
        # Note: This also tests that constraints are consistent with
        # `self`.
        try:
            self._validate_by_reconstruction()
        except _exceptions.MalformedCoordinate:
            raise
        except Exception:
            pass
        else:
            self._register_validation()
            return True

        # Reconstruction failed, so instance is invalid, but try to
        # diagnose cause for user.
        try:
            self._validate_each_field()
        except _exceptions.MalformedCoordinate:
            raise
        except Exception:
            pass
        if raise_fallback:
            self._raise_fallback_exception()
        return False

    @_abc.abstractmethod
    def _validate_by_reconstruction(self) -> None: ...

    def _validate_each_field(self) -> None:
        first_other_error = None  # Initialize.
        for field in self._get_fields():
            func = getattr(self, f"_validate_{field.name}", None)
            if func is not None:
                try:
                    func()
                except _exceptions.MalformedCoordinate:
                    raise
                except Exception as e:
                    if first_other_error is None:
                        first_other_error = e
        if first_other_error:
            raise first_other_error from None

    # * INITIALIZATION. ───────────────────────────────────────────────
    def __post_init__(self, validate: bool) -> None:
        if validate:
            self._validate()

    @_functools.cached_property
    def _init_kwargs(self) -> dict[str, _typing.Any]:
        return {
            field.name: getattr(self, field.name)
            for field in self._get_fields()
        }

    # * FIELD SUPPORT. ────────────────────────────────────────────────
    def __iter__(self) -> _collections.abc.Iterator[_typing.Any]:
        for key, value in self._init_kwargs.items():
            if key == "constraints":
                continue
            yield value

    @classmethod
    @_functools.cache
    def _get_fields(cls) -> tuple[_dataclasses.Field, ...]:
        name_to_field = {
            field.name: field for field in _dataclasses.fields(cls)
        }
        name_to_field["constraints"] = name_to_field.pop("constraints")
        return tuple(name_to_field.values())

    @classmethod
    @_functools.cache
    def _get_field_name_to_type(cls) -> dict[str, type]:
        field_name_to_type = {}
        all_name_to_type = _typing.get_type_hints(cls)
        for field in cls._get_fields():
            typ = all_name_to_type[field.name]
            if isinstance(typ, _types.UnionType):
                types = list(_typing.get_args(typ))
                types.remove(type(None))
                (typ,) = types  # *REASSIGNMENT*
            field_name_to_type[field.name] = typ
        return field_name_to_type


class BaseCoordinate(_BaseCoordinate):
    """The base class for all coordinates, both points and grid boxes."""

    _template: _collections.abc.Callable | str | None = None
    _was_validated: bool = False
    # Note: Hints below are "promises" that are realized when an
    # instantiable class inherits from both `BaseCoordinate` and
    # `_BaseCoordinate`. This inheritance is postponed so that the
    # `constraints` and `validate` fields appear at the end of the
    # auto-generated initialization function.
    constraints: Constraints
    validate: bool

    # * BASIC BEHAVIOR. ───────────────────────────────────────────────
    def __copy__(self) -> _typing.Self:
        return self.copy()

    def __repr__(self) -> str:
        arg_strs = []
        for name, val in self._init_kwargs.items():
            if isinstance(val, (int, float)):
                val_str = f"{val:_}"
            else:
                val_str = repr(val)
            arg_strs.append(f"{name}={val_str}")
        return f"{self.__class__.__name__}({', '.join(arg_strs)})"

    def __str__(self) -> str:
        return self.string

    # * INSTANTIATION. ────────────────────────────────────────────────
    @classmethod
    def _from_ref_string(cls, string: str) -> _typing.Self:
        # Note: Unlike `BoxCoordinate.from_string()`, this method exists
        # solely to support parsing values from
        # `LGRS_Coordinate_Conversion`.
        parts = tuple(string.split(" "))
        if len(parts) == 1:
            raise _exceptions.MalformedCoordinate(
                "`string` must be space-delimited"
            )
        field_name_to_type = cls._get_field_name_to_type()
        if len(parts) > len(field_name_to_type):
            raise _exceptions.MalformedCoordinate(
                "`string` contains too many space-delimited "
                f"components: {string!r}"
            )
        init_kwargs = {
            name: typ(part)
            for part, (name, typ) in zip(parts, field_name_to_type.items())
        }
        return cls(**init_kwargs)

    # * TRANSFORMATION CACHING. ───────────────────────────────────────
    _precision: int
    # Note: `_precision_origin` records the the underlying precision,
    # which is the greater of the actual precision and coarsest
    # precision encountered during derivation. For example, a directly
    # instantiated point has (for our purposes) infinitesimal
    # underlying precision and therefor a precision origin of 0
    # whereas point derived from the reference corner of a box has the
    # precision origin of that box.
    _precision_origin: int

    @_functools.cached_property
    def _cache_key(self) -> _collections.abc.Hashable:
        return self._make_cache_key(
            constraints=self.constraints, intended_precision=self._precision
        )

    # Note: See `._get_cached_or_create()` for a description of what a
    # "cousin" is.
    @_functools.cached_property
    def _cache_key_to_cousins(
        self,
    ) -> _collections.abc.Mapping[
        _collections.abc.Hashable, _collections.deque[BaseCoordinate]
    ]:
        cache_key_to_cousins = _collections.defaultdict(_collections.deque)
        cache_key_to_cousins[self._cache_key].appendleft(self)
        return cache_key_to_cousins

    def _get_cached_cousin(
        self,
        *targ_types: type,
        constraints: Constraints,
        precision: int,
        truncation_ok: bool = True,
    ) -> BaseCoordinate | None:
        # Ensure that `self` is invariably returned, if suitable.
        # Note: If caching is disabled or cache was cleared, `self` may
        # not be otherwise available.
        targ_cache_key = self._make_cache_key(
            constraints=constraints, intended_precision=precision
        )
        if self._cache_key == targ_cache_key:
            cousins = [self]
        else:
            cousins = []
        if _caching._CACHING_IS_ENABLED:
            cousins.extend(self._cache_key_to_cousins[targ_cache_key])

        # Return suitable cached cousin, if any.
        fallback = None
        for cousin in cousins:
            if not isinstance(cousin, targ_types):
                continue
            elif cousin._precision == precision:
                return cousin
            elif cousin._precision < precision:
                fallback = cousin
        if fallback is None or not truncation_ok:
            return None
        return fallback.with_precision(precision)

    def _make_cache_key(
        self,
        *,
        constraints: Constraints,
        intended_precision: int,
    ) -> _collections.abc.Hashable:
        return (constraints, max(self._precision_origin, intended_precision))

    def _register_cousin(self, cousin: BaseCoordinate) -> None:
        # Record cousin's precision origin.
        object.__setattr__(
            cousin,
            "_precision_origin",
            max(cousin._precision, self._precision_origin),
        )

        # Invariably register for possible later clearing of the cache.
        _caching._coord_weak_set.add(cousin)

        # If caching is disabled, do nothing more.
        if not _caching._CACHING_IS_ENABLED:
            return

        # Attach cousins record and update it.
        # Note: Effectively, the references to a given instance of
        # `._cache_key_to_cousins` keeps all cousins in the group alive
        # until all direct references to cousins in the group are dead.
        # Then, all cousins are garbage collected.
        object.__setattr__(
            cousin,
            "_cache_key_to_cousins",
            self._cache_key_to_cousins,
        )
        self._cache_key_to_cousins[cousin._cache_key].appendleft(cousin)

    def _unregister_cousins(self, *cousins: BaseCoordinate) -> None:
        if not _caching._CACHING_IS_ENABLED:
            return
        for cousin in cousins:
            try:
                self._cache_key_to_cousins[cousin._cache_key].remove(cousin)
            except ValueError:
                pass

    # * VALIDATION. ───────────────────────────────────────────────────
    def _raise_malformed_coordinate(
        self,
        middle: str,
        *,
        attr_name: str,
        if_attr_name: str | None = None,
    ) -> _typing.NoReturn:
        if if_attr_name is None:
            prefix = ""
        else:
            prefix = f"For `{if_attr_name}={getattr(self, if_attr_name)!r}`, "
        raise _exceptions.MalformedCoordinate(
            f"{prefix}"
            f"`{attr_name}` must be "
            f"{middle}"
            f", not: {getattr(self, attr_name)!r}"
        )

    @staticmethod
    def _raise_unexpected(
        func: _collections.abc.Callable | None = None,
    ) -> _typing.NoReturn:
        if func is not None:
            func()
        raise TypeError("An unexpected error occurred.")

    def _validate_against_closed_interval(
        self,
        *,
        attr_name: str,
        minimum: _typing.Any,
        maximum: _typing.Any,
        if_attr_name: str | None = None,
        coerce_str: bool = False,
    ) -> None:
        val = getattr(self, attr_name)
        if coerce_str:
            val = float(val)  # *REASSIGNMENT*
        if not (minimum <= val <= maximum):
            self._raise_malformed_coordinate(
                f"between {minimum} and {maximum}, inclusive",
                attr_name=attr_name,
                if_attr_name=if_attr_name,
            )

    def _validate_against_sequence(
        self,
        *,
        attr_name: str,
        sequence: _collections.abc.Sequence,
        if_attr_name: str | None = None,
    ) -> None:
        val = getattr(self, attr_name)
        if val not in sequence:
            if len(sequence) == 2:
                item_1, item_2 = sequence
                middle = f"{item_1!r} or {item_2!r}"
            else:
                middle = (
                    f"one of {', '.join(map(repr, sequence[:-1]))}, "
                    f"or {sequence[-1]!r}"
                )
            self._raise_malformed_coordinate(
                middle=middle, attr_name=attr_name, if_attr_name=if_attr_name
            )

    def _validate_by_reconstruction(self) -> None:
        # Create forward-converted equivalent and compare.
        (latlon_point,) = self._conform_to_latlon_points(self, center=True)
        # Note: Validate geographic point because that validation is
        # cheap and tests fundamental assumptions.
        latlon_point.validate()
        twin = latlon_point.copy().to(type(self), any_system=True)
        if isinstance(twin, BoxCoordinate):
            twin = twin.with_precision(self.precision)  # *REASSIGNMENT*
        if self.is_lps_based() != twin.is_lps_based():
            raise _exceptions.MalformedCoordinate(
                f"For the given constraints, {self.constraints!r}, location "
                f"should be in {'LPS' if twin.is_lps_based() else 'LTM'} "
                f"region, not: {self!r}"
            )
        if self._init_kwargs == twin._init_kwargs:
            return
        # Note: This test is included for completeness but should never
        # fail.
        if self._init_kwargs.keys() != twin._init_kwargs.keys():
            raise _exceptions.MalformedCoordinate(
                f"Cannot compare `self` to `twin`: {self!r}"
            )
        for field_name in self._init_kwargs:
            self_val = getattr(self, field_name)
            twin_val = getattr(twin, field_name)
            if self_val == twin_val:
                continue
            # Note: Easting and northing may have small precision
            # discrepancies. Since all transformations are via `pyproj`,
            # do not examine further.
            if field_name in ("easting", "northing") and isinstance(
                self, PointCoordinate
            ):
                continue
            break
        else:
            return
        raise _exceptions.MalformedCoordinate(
            f"For the given constraints, {self.constraints!r}, location "
            f"should have the form\n"
            f"    {twin!r}\n"
            "not\n"
            f"    {self!r}"
        )

    def _validate_hemisphere(self) -> None:
        self._validate_against_sequence(
            attr_name="hemisphere", sequence=("N", "S")
        )

    def validate(self, *, revalidate: bool = False) -> None:
        """
        Validate this coordinate.

        Use this method to validate the instance or confirm that it has already
        been validated. Note that validating at initialization instead is
        generally recommended.

        Parameters
        ----------
        revalidate : bool, default=False
            Whether to re-validate the instance if it has already been
            validated. This option is likely only useful in special cases.

        Returns
        -------
        None

        Raises
        ------
        lgrs.Exceptions.MalformedCoordinate
            If the instance is invalid. Unlike at-initialization validation,
            an instance is considered invalid even if its values are merely
            not conformed. See Examples.

        Examples
        --------
        >>> latlon_1 = LatLonPoint(45, 182)
        >>> latlon_1.longitude == -178  # Conformed.
        True
        >>> latlon_2 = LatLonPoint(45, 182, validate=False)
        >>> latlon_2.longitude == -178   # Not conformed.
        False
        >>> latlon_2.validate()  # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
          ...
        lgrs.exceptions.MalformedCoordinate:
          Validation conformed the following value(s):
            longitude: 182 --> -178

        """
        if not revalidate and self._was_validated:
            return
        copy = self.copy(validate=False)
        copy._validate()
        if copy._init_kwargs == self._init_kwargs:
            self._register_validation()
            return
        change_lines = []
        for k, new_v in copy._init_kwargs.items():
            old_v = self._init_kwargs[k]
            if new_v != old_v:
                change_lines.append(f"    {k}: {old_v!r} --> {new_v!r}")
        raise _exceptions.MalformedCoordinate(
            "\n"
            "  Validation conformed the following value(s):\n"
            f"{'\n'.join(change_lines)}"
        )

    # * COORDINATE TRANSFORMATION. ────────────────────────────────────
    @_abc.abstractmethod
    def _get_crs_name(self) -> str | None: ...

    def _get_crs(self, *, set_area_of_use: bool):
        crs_name = self._get_crs_name()
        if crs_name is None:
            return _srs.make_lunar_crs()
        if self.constraints.global_crs is not None:
            return self.constraints.global_crs
        if set_area_of_use:
            crs_kwargs = self.constraints._crs_kwargs
        else:
            crs_kwargs = {}
        return _srs.make_lunar_crs(crs_name, **crs_kwargs)

    @_functools.cached_property
    def crs(self) -> _srs.CRS:
        """
        The coordinate reference system used by this coordinate.

        `self.crs.area_of_use` represents the latitudinal and longitudinal
        bounds indicated by constraints, that is, it factors in the
        constraints `extended_ltm`, `global_lps`, and `global_ltm`.
        However, the area of use is not affected by `prefer_lps` and
        `prefer_ltm` constraints.

        See Also
        --------
        crs_nominal : Ignores constraint effects on area of use.

        """
        return self._get_crs(set_area_of_use=True)

    @_functools.cached_property
    def crs_nominal(self) -> _srs.CRS:
        """
        The nominal coordinate reference system used by this coordinate.

        `self.crs_nominal.area_of_use` always represents the nominal
        latitudinal and longitudinal bounds, that is, it is unaffected by
        constraints (except when `global_crs` is used by a projected
        coordinate). Therefore, if two coordinate instances have equal
        `.crs_nominal` attributes, their coordinate values lie on the same
        plane and are indexed identically, that is, are directly comparable.

        See Also
        --------
        crs : Includes constraint effects on area of use.

        """
        return self._get_crs(set_area_of_use=False)

    # * PUBLIC DATA. ──────────────────────────────────────────────────
    @_functools.cached_property
    def string(self) -> str:
        """
        The string representation of the coordinate.

        Equivalent to `str(self)`. Cached after first use.
        """
        match self._template:
            case None:
                string = "".join(self._iter_value_strings())
            case str():
                string = self._template.format(**self._init_kwargs)
            case _:
                string = self._template()
        return string

    # * GENERAL PUBLIC METHODS. ───────────────────────────────────────
    @staticmethod
    def _conform_to_latlon_points(
        *coords: BaseCoordinate, center: bool
    ) -> _collections.abc.Iterator[LatLonPoint]:
        for coord in coords:
            if center and isinstance(coord, BoxCoordinate):
                yield coord.center_latlon
            else:
                yield coord.to_latlon()

    @classmethod
    def _is_x_based(cls, prefix: str) -> bool:
        if issubclass(cls, LatLonPoint):
            raise TypeError("`LatLonPoint` is neither LPS- nor LTM-based")
        return cls.__name__.startswith(prefix)

    # TODO: Un-skip doctest once complete validation is implemented.
    def copy(self, *, validate: bool = False) -> _typing.Self:
        """
        Create independent copy of this coordinate.

        Although `copy` is a different instance from `self`, its cache is not
        guaranteed independnet. See Examples.

        Parameters
        ----------
        validate : bool, default=False
            Whether to validate the copy. The default is `False` because it's
            assumed that either `self` was validated or intentionally not
            validated, because its values are known to be valid.

        Returns
        -------
        copy : typing.Self
            A copy of this coordinate.

        Examples
        --------
        >>> import lgrs.caching
        >>> lgrs.caching.enable_caching()
        >>> example_latlon = LatLonPoint(0, 0)
        >>> example_lgrs = example_latlon.to_lgrs()
        >>> alt_latlon = example_latlon.copy()
        >>> example_latlon is alt_latlon
        False
        >>> example_latlon.to_lgrs() is example_latlon.to_lgrs()
        True
        >>> example_latlon.to_lgrs() is alt_latlon.to_lgrs()  # doctest: +SKIP

        Whether this final statement evaluates as `True` or `False` is not
        guaranteed. To guarantee independence, caching should be disabled
        globally by `lgrs.caching.enable_caching(False)`.
        """
        # Note: `self` can only exist if validated or explicitly not
        # validated. Either way, defaulting `validate` to `False` is
        # appropriate.
        new = type(self)(
            **self._init_kwargs,
            validate=(validate and not self._was_validated),
        )
        return new

    def distance_to(
        self, other: BaseCoordinate, *, center: bool = False
    ) -> float:
        """
        Calculate the geodesic distance between two coordinates, in meters.

        For any box coordinate (`self` and/or `other`), distance is measured
        to a representative point, as determined by `center`.

        Parameters
        ----------
        other : BaseCoordinate
            The other coordinate.
        center : bool, default=False
            Whether to use the center of any box coordinate instead of the
            lower-left (grid-southwest) corner.

        Returns
        -------
        distance : float
            The geodesic distance between `self` and `other`, in meters.

        See Also
        --------
        contains : Whether a box coordinate contains another coordinate.
        grid_distance_to : Point-to-point grid distance.

        Examples
        --------
        >>> latlon_point = LatLonPoint(0, 0)
        >>> acc_box = LtmAccBox.from_string("23NFF-001-001")
        >>> latlon_point.distance_to(acc_box)
        1.415638994018731
        >>> latlon_point.distance_to(acc_box, center=True)
        2.1234979460292074
        """
        self_latlon_point, other_latlon_point = self._conform_to_latlon_points(
            self, other, center=center
        )
        _, _, dist = _get_geod().inv(
            self_latlon_point.longitude,
            self_latlon_point.latitude,
            other_latlon_point.longitude,
            other_latlon_point.latitude,
        )
        return dist

    # TODO: Decide whether to support mixed types.
    def is_equal_to(
        self,
        other: _typing.Self,
        *,
        error: bool = False,
        constraints: bool = False,
    ) -> bool:
        """
        Test whether two coordinates are equal, optionally including
        constraints.

        Note that::

            coord_1 == coord_2

        is equivalent to::

            coord_1.is_equal_to(coord_2, constraints=False)

        except that the latter does not support mixed types.

        Parameters
        ----------
        other : BaseCoordinate
            The other coordinate to compare to.
        error : bool, default=False
            Whether to raise a descriptive error rather than return `False`.
        constraints : bool, default=False
            Whether to include constraints when evaluating equality. If
            `False`, only coordinate values are compared. If `True`,
            `.constraints` is also compared.

        Returns
        -------
        is_equal : bool
            Whether `self` and `other` are equal.

        Raises
        ------
        TypeError
            If `self` and `other` are of different types.

        Examples
        --------
        >>> latlon_point_1 = LatLonPoint(0, 0)
        >>> latlon_point_2 = LatLonPoint(
        ...     0, 0, constraints=Constraints(extended_ltm=True)
        ... )
        >>> latlon_point_1.is_equal_to(latlon_point_2)
        True
        >>> latlon_point_1.is_equal_to(latlon_point_2, constraints=True)
        False
        """
        # Compare.
        err_lines = []
        for field_name, self_val in self._init_kwargs.items():
            if not constraints and field_name == "constraints":
                continue
            other_val = getattr(other, field_name)
            if self_val != other_val:
                if not error:
                    return False
                err_lines.append(f"  {field_name!r} values differ:")
                err_lines.append(f"    {self_val!r} vs. {other_val!r}")
        if err_lines:
            raise TypeError("\n" + "\n".join(err_lines))
        return True

    @classmethod
    @_functools.cache
    def is_lps_based(cls):
        """
        Whether the coordinate is based in the LPS system.

        Returns
        -------
        is_lps_based : bool
            Whether the coordinate is based in the LPS system.

        Raises
        ------
        TypeError
            If instance is a `LatLonPoint`.

        See Also
        --------
        is_ltm_based : Counterpart for the LTM system.

        Examples
        --------
        >>> lps_lgrs_box = LpsLgrsBox.from_string("AZS1359008480")
        >>> lps_lgrs_box.is_lps_based()
        True
        >>> LpsLgrsBox.is_lps_based()  # Can call on a class, too.
        True
        >>> ltm_acc_box = LtmAccBox.from_string("29TCVK738P376")
        >>> ltm_acc_box.is_lps_based()
        False
        """
        return cls._is_x_based("Lps")

    @classmethod
    @_functools.cache
    def is_ltm_based(cls):
        """
        Whether the coordinate is based in the LTM system.

        Returns
        -------
        is_ltm_based : bool
            Whether the coordinate is based in the LTM system.

        Raises
        ------
        TypeError
            If instance is a `LatLonPoint`.

        See Also
        --------
        is_lps_based : Counterpart for the LPS system.

        Examples
        --------
        >>> ltm_acc_box = LtmAccBox.from_string("29TCVK738P376")
        >>> ltm_acc_box.is_ltm_based()
        True
        >>> LtmAccBox.is_ltm_based()  # Can call on a class, too.
        True
        >>> lps_lgrs_box = LpsLgrsBox.from_string("AZS1359008480")
        >>> lps_lgrs_box.is_ltm_based()
        False
        """
        return cls._is_x_based("Ltm")

    # TODO: Un-skip doctest once complete validation is implemented.
    def replace(
        self,
        constraints: Constraints | None = None,
        *,
        validate: bool = True,
        copy: bool = False,
        **overrides,
    ) -> _typing.Self:
        """
        Get instance with modified values and/or constraints.

        The new instance will have the same values and constraints as `self`,
        except where explicitly overridden by `overrides` and `constraints`,
        respectively.

        Parameters
        ----------
        constraints : Constraints, optional
            The constraints for `replaced`. If not specified, `replaced` has
            the same constraints as `self`.
        validate : bool, default=True
            Whether to validate `replaced`. Honored even if `self` is returned.
        copy : bool, default=False
            Whether to ensure that `replaced` is not `self` and is not cached
            in association with `self`. If `False` and all `overrides` have the
            same values as `self`, `self` is returned.
        **overrides
            Keyword arguments specifying initialization parameters (values) for
            the new instance.

        Returns
        -------
        replaced : typing.Self
            The new instance, or possibly `self` if `copy` is `False`.

        Raises
        ------
        lgrs.Exceptions.MalformedCoordinate
            If `replaced` would be invalid and `validate` is `True`.

        Examples
        --------
        >>> latlon_point_1 = LatLonPoint(0, 0)
        >>> latlon_point_2 = latlon_point_1.replace(longitude=1)
        >>> latlon_point_2 == LatLonPoint(0, 1)
        True

        >>> extended_ltm = Constraints(extended_ltm=True)
        >>> geo_point = LatLonPoint(81, 0, constraints=extended_ltm)
        >>> ltm_point = geo_point.to_lps_or_ltm()
        >>> isinstance(ltm_point, LtmPoint)
        True
        >>> illegal_point = ltm_point.replace(Constraints())  # doctest: +SKIP
        Traceback (most recent call last):
          ...
        lgrs.exceptions.MalformedCoordinate:
          ...
        """  # noqa: E501
        # Resolve constraints and initialization kwargs for `replaced`.
        if constraints is None:
            constraints = self.constraints  # *REASSIGNMENT*
        cur_init_kwargs_no_constraints = self._init_kwargs.copy()
        del cur_init_kwargs_no_constraints["constraints"]
        new_init_kwargs_no_constraints = cur_init_kwargs_no_constraints.copy()
        new_init_kwargs_no_constraints.update(overrides)

        # Fetch from cache, if possible and allowed.
        has_no_true_overrides = (
            new_init_kwargs_no_constraints == cur_init_kwargs_no_constraints
        )
        if not copy and has_no_true_overrides:
            cached = self._get_cached_cousin(
                type(self), constraints=constraints, precision=self._precision
            )
            if cached is not None:
                if validate:
                    cached.validate()
                return cached

        # Construct new instance and possibly register as a cousin.
        replaced = type(self)(
            **new_init_kwargs_no_constraints,
            constraints=constraints,
            validate=validate,
        )
        if not copy and has_no_true_overrides:
            self._register_cousin(replaced)
        return replaced

    # * COORDINATE TRANSFORMATION. ────────────────────────────────────
    def _force_type_or_error(
        self,
        bound_method: _collections.abc.Callable,
        targ_typ: type[BaseCoordinate],
        constraints_list: list[Constraints],
        *,
        validate: bool | None,
    ) -> BaseCoordinate:
        for constraints in constraints_list:
            cand = bound_method(constraints=constraints, validate=validate)
            if isinstance(cand, targ_typ):
                return cand
        raise _exceptions.MalformedCoordinate(
            f"Location is not compatible with `{targ_typ.__name__}`, "
            f"given `{constraints_list[0]!r}`: {self!r}"
        )

    def _get_cached_or_create[T](
        self,
        func: _collections.abc.Callable[..., T],
        *,
        constraints: Constraints | None,
        validate: bool | None,
        **kwargs,
    ) -> T:
        """
        Get suitable coordinate instance from cache or create one.

        A "suitable coordinate instance" is termed a "cousin". A "cousin" is
        any `BaseCoordinate` whose location on the Moon and constraints are
        the same as those of `self`. (Note that this definition includes the
        trivial case: `self` is its own cousin.) Cousins are often generated
        during intermediate calculations, whether internal or external
        (i.e., by the user), so caching them into cousin groups improves
        efficiency. Note that a cousin group is only guaranteed to include
        those cousins generated by a transformation chain from a common
        root. Therefore, cousins that are wholly independently instantiated
        may not be grouped together.

        Parameters
        ----------
        func : bound method
            If no cached cousin is found, a new one is created by calling
            `func`, which must be a bound `._to_*()` method of
            `BaseCoordinate`.
        constraints : Constraints, optional
            The constraints to apply to this transformation. If not specified
            (or `None`), `self.constraints` is used.
        validate : bool, optional
            Whether to fully validate the transformed coordinate. If `False`,
            no validation is performed. If not specified (or `None`), whatever
            validation is deemed necessary (if any) is performed. Note that if
            `coord` was created earlier (i.e., is from the cache) and was
            already validated, it is not re-validated.
        **kwargs
            Any additional keyword arguments (such as `precision`) are passed
            to `func`.

        Returns
        -------
        coord : BaseCoordinate
            A cousin of `self`, which may be `self`.
        """

        # Resolve some essential parameters.
        targ_types = _resolve_out_types(func.__func__)
        if constraints is None:
            constraints = self.constraints  # *REASSIGNMENT*
        precision = self._resolve_precision(
            kwargs.get("precision"), targ_type=targ_types[0]
        )
        if "precision" in kwargs:
            kwargs["precision"] = precision

        # Attempt to retrieve from cache. Upon failure, create.
        cached = self._get_cached_cousin(
            *targ_types, constraints=constraints, precision=precision
        )
        if cached is None:
            if constraints != self.constraints:
                # Note: Must restart transformation chain from
                # geographic, to ensure that new constraints are
                # properly applied (or trigger an error).
                if isinstance(self, LatLonPoint):
                    src = self.replace(constraints=constraints, validate=False)
                else:
                    src = self.to_latlon()
                # *REASSIGNMENT*
                func = getattr(src, func.__name__.lstrip("_"))
            final = func(constraints=constraints, validate=validate, **kwargs)
        else:
            final = cached

        # Perform any requested validation and return.
        # Note: Special `validate=None` case must be treated by `func`.
        if validate:
            final.validate()
        return final

    @staticmethod
    @_functools.cache
    def _get_conversion_sequence(
        targ_type: type[BaseCoordinate],
    ) -> tuple[_ToMethod | None, _ToMethod]:
        if targ_type is LatLonPoint:
            return (None, BaseCoordinate.to_latlon)
        if targ_type in (LpsPoint, LtmPoint):
            convert = BaseCoordinate.to_lps_or_ltm
        elif targ_type in (LpsLgrsBox, LtmLgrsBox):
            convert = BaseCoordinate.to_lgrs
        elif targ_type in (LpsAccBox, LtmAccBox):
            convert = BaseCoordinate.to_acc
        else:
            BaseCoordinate._raise_unexpected()
        if targ_type.is_lps_based():
            force_system = BaseCoordinate.to_lps
        elif targ_type.is_ltm_based():
            force_system = BaseCoordinate.to_ltm
        else:
            BaseCoordinate._raise_unexpected()
        return (force_system, convert)

    def _resolve_precision(
        self,
        required_precision: float | None,
        *,
        targ_type: type[BaseCoordinate],
        error: bool = True,
    ) -> int | None:
        # Note: Errors raised by this function use `precision` rather
        # than `required_precision` because only the former is used
        # in public functions.
        if required_precision is None:
            if issubclass(targ_type, PointCoordinate):
                precision = 0
            elif isinstance(self, BoxCoordinate):
                precision = self.precision
            else:
                precision = 1
        elif error and required_precision < self._precision:
            raise TypeError(
                "The requested `precision` is finer than `self.precision`: "
                f"{required_precision!r} < {self.precision!r}"
            )
        else:
            precision = self._resolve_precision_static(required_precision)
        return precision

    @staticmethod
    def _resolve_precision_static(required_precision: float) -> int:
        if required_precision < 1:
            raise TypeError(
                "`precision` must be >=1, not: " f"{required_precision!r}"
            )
        elif 1 <= required_precision < 10:
            precision = 1
        elif 10 <= required_precision < 100:
            precision = 10
        elif 100 <= required_precision < 1000:
            precision = 100
        elif 1000 <= required_precision < 25_000:
            precision = 1000
        else:
            precision = 25_000
        return precision

    def to(
        self,
        typ: type[BaseCoordinate],
        constraints: Constraints | None = None,
        *,
        any_system: bool = False,
        search: bool = False,
        validate: bool | None = None,
    ) -> BaseCoordinate:
        """
        Transform `self` to the specified coordinate type.

        This is a convenience function to call one or two `.to_*()`s in
        series. See Examples.

        Parameters
        ----------
        typ : a BaseCoordinate subclass
            The coordinate type to which `self` should be converted.
        constraints : Constraints, optional
            The constraints to apply to this transformation. If not specified
            (or `None`), `self.constraints` is used.
        any_system : bool, default=False
            Whether to allow the output coordinate to be from either system
            (LPS or LTM). If `False`, `.to_lps()` or `.to_ltm()` is called,
            if necessary, with `search=search`.
        search : bool, default=False
            The `search` argument passed to `.to_lps()` or `.to_ltm()`. Ignored
            if `any_system` is `True`.
        validate : bool, optional
            Whether to fully validate the transformed coordinate. If `False`,
            no validation is performed. If not specified (or `None`), whatever
            validation is deemed necessary (if any) is performed. Note that if
            `out` was created earlier (i.e., is from the cache) and was already
            validated, it is not re-validated.

        Returns
        -------
        out : BaseCoordinate (specifically, `typ`)
            The transformed coordinate. If `self` is compatible, `self` is
            returned. If caching is enabled, a cached instance may be returned.

        Raises
        ------
        lgrs.Exceptions.MalformedCoordinate
            If `any_system=False` and the system of `typ` is incompatible with
            `self`.

        Examples
        --------
        >>> latlon_point = LatLonPoint(80, 0)
        >>> box_1 = latlon_point.to(LpsLgrsBox)  # Transform 1
        >>> isinstance(box_1, LpsLgrsBox)
        True

        You can also relax system requirements. Note that the target `typ`
        changes in Transform 2 relative to Transform 1.

        >>> box_2 = latlon_point.to(LtmLgrsBox, any_system=True)  # Transform 2
        >>> isinstance(box_2, LpsLgrsBox)
        True

        Alternatively, you can attempt to force transformation to the target
        `typ`.

        >>> box_3 = latlon_point.to(LtmLgrsBox, search=True)  # Transform 3
        >>> isinstance(box_3, LtmLgrsBox)
        True

        Transform 1 is equivalent to::

            latlon_point.to_lps().to_lgrs()

        Transform 2 is equivalent to::

            latlon_point.to_lgrs()

        Transform 3 is equivalent to::

            latlon_point.to_ltm(search=True).to_lgrs()

        Note that boxes of either system are not supported everywhere, even
        with `search=True`.

        >>> latlon_point_2 = LatLonPoint(0, 0)
        >>> bad_box = latlon_point_2.to(LpsLgrsBox, search=True)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        lgrs.exceptions.MalformedCoordinate:
          ...
        """  # noqa: E501
        force_system, convert = self._get_conversion_sequence(typ)
        if (
            not any_system
            and force_system is not None
            and (
                isinstance(self, LatLonPoint)
                or self.is_lps_based() != typ.is_lps_based()
            )
        ):
            basis = force_system(self, search=search)
        else:
            basis = self
        return convert(basis, constraints=constraints, validate=validate)

    # TODO: Decide whether default for `precision` should always be 1.
    #  If so, how do we handle when a box tries to reduce precision?
    #  Also, should we error when the (hidden) bookkeeping indicates
    #  that precision < precision origin? (If so, should we expand
    #  bookkeeping to cover all cases, even copying?)
    def to_acc(
        self,
        *,
        constraints: Constraints | None = None,
        precision: float | None = None,
        validate: bool | None = None,
    ) -> LpsAccBox | LtmAccBox:
        """
        Transform coordinate to `LpsAccBox` or `LtmAccBox`.

        The type of `out` is determined by the combination of
        `self.constraints` and the location of `self` on the Moon.

        `out` is not validated with this call but should be valid if `self` is
        valid.

        Parameters
        ----------
        constraints : Constraints, optional
            The constraints to apply to this transformation. If not specified
            (or `None`), `self.constraints` is used.
        precision : float, optional
            The maximum allowed value of `out.precision`. If not specified,
            defaults to 1 if `self` is a point else `self.precision`.
        validate : bool, optional
            Whether to fully validate the transformed coordinate. If `False`,
            no validation is performed. If not specified (or `None`), whatever
            validation is deemed necessary (if any) is performed. Note that if
            `out` was created earlier (i.e., is from the cache) and was already
            validated, it is not re-validated.

        Returns
        -------
        out : LpsAccBox or LtmAccBox
            The transformed coordinate. If `self` is compatible, `self` is
            returned. If caching is enabled, a cached instance may be returned.
        """
        return self._get_cached_or_create(
            self._to_acc,
            constraints=constraints,
            precision=precision,
            validate=validate,
        )

    def to_latlon(
        self,
        *,
        constraints: Constraints | None = None,
        validate: bool | None = None,
    ) -> LatLonPoint:
        """
        Transform coordinate to `LatLonPoint`.

        `out` is not validated with this call but should be valid if `self` is
        valid.

        Parameters
        ----------
        constraints : Constraints, optional
            The constraints to apply to this transformation. If not specified
            (or `None`), `self.constraints` is used.
        validate : bool, optional
            Whether to fully validate the transformed coordinate. If `False`,
            no validation is performed. If not specified (or `None`), whatever
            validation is deemed necessary (if any) is performed. Note that if
            `out` was created earlier (i.e., is from the cache) and was already
            validated, it is not re-validated.

        Returns
        -------
        out : LatLonPoint
            The transformed coordinate. If `self` is compatible, `self` is
            returned. If caching is enabled, a cached instance may be returned.
        """
        return self._get_cached_or_create(
            self._to_latlon,
            constraints=constraints,
            validate=validate,
        )

    def to_lgrs(
        self,
        *,
        constraints: Constraints | None = None,
        precision: float | None = None,
        validate: bool | None = None,
    ) -> LpsLgrsBox | LtmLgrsBox:
        """
        Transform coordinate to `LpsLgrsBox` or `LtmLgrsBox`.

        The type of `out` is determined by the combination of
        `self.constraints` and the location of `self` on the Moon.

        `out` is not validated with this call but should be valid if `self` is
        valid.

        Parameters
        ----------
        constraints : Constraints, optional
            The constraints to apply to this transformation. If not specified
            (or `None`), `self.constraints` is used.
        precision : float, optional
            The maximum allowed value of `out.precision`. If not specified,
            defaults to 1 if `self` is a point else `self.precision`.
        validate : bool, optional
            Whether to fully validate the transformed coordinate. If `False`,
            no validation is performed. If not specified (or `None`), whatever
            validation is deemed necessary (if any) is performed. Note that if
            `out` was created earlier (i.e., is from the cache) and was already
            validated, it is not re-validated.

        Returns
        -------
        out : LpsLgrsBox or LtmLgrsBox
            The transformed coordinate. If `self` is compatible, `self` is
            returned. If caching is enabled, a cached instance may be returned.
        """
        return self._get_cached_or_create(
            self._to_lgrs,
            constraints=constraints,
            precision=precision,
            validate=validate,
        )

    def to_lps(
        self,
        *,
        constraints: Constraints | None = None,
        validate: bool | None = None,
        search: bool = False,
    ) -> LpsPoint:
        """
        Transform coordinate to `LpsPoint`.

        This method is most commonly used to explicitly declare the expected
        output type, unlike the ambiguity of `.to_lps_or_ltm()` (which it calls
        internally). Alternatively, this method can be used (with
        `search=True`) to force transformation to `LpsPoint` by inferring
        appropriate constraints.

        Note that the transformation from `LatLonPoint` to `LpsPoint` or
        `LtmPoint` is the foundation that determines the system (LPS or LTM) of
        all later transformation to `*LgrsBox` and `*AccBox`.

        Parameters
        ----------
        constraints : Constraints, optional
            The (preferred) constraints to apply to this transformation. If not
            specified (or `None`), `self.constraints` is used.
        validate : bool, optional
            Whether to fully validate the transformed coordinate. If `False`,
            no validation is performed. If not specified (or `None`), whatever
            validation is deemed necessary (if any) is performed. Note that if
            `out` was created earlier (i.e., is from the cache) and was
            already validated, it is not re-validated.
        search : bool, default=False
            If `constraints` is not sufficient to produce an `LpsPoint` output,
            whether to search (success guaranteed) for a constraints
            configuration that achieves this. An effort is made not to diverge
            further from `constraints` than necessary.

        Returns
        -------
        out : LpsPoint
            The transformed coordinate. If `self` is compatible, `self` is
            returned. If caching is enabled, a cached instance may be returned.

        Raises
        ------
        lgrs.Exceptions.MalformedCoordinate
            If `constraints` are incompatible with `LpsPoint` for this
            location, and `search` is `False`.

        See Also
        --------
        .to : Transformation to any specified coordinate type
        """
        # Determine preferred order of `Constraints` instances.
        if constraints is None:
            constraints = self.constraints  # *REASSIGNMENT*
        constraints_list = [constraints]
        if search:
            if constraints.extended_ltm:
                # Note: Since `extended_ltm=True` is preferred, attempt to
                # retain that constraint if possible.
                constraints_list.extend(
                    (
                        Constraints(extended_ltm=True, prefer_lps=True),
                        Constraints(extended_ltm=False, prefer_lps=False),
                    )
                )
            constraints_list.extend(
                (
                    Constraints(extended_ltm=False, prefer_lps=True),
                    Constraints(global_lps=True),
                )
            )

        # Convert to `LpsPoint`.
        lps_point = self._force_type_or_error(
            self.to_lps_or_ltm,
            LpsPoint,
            constraints_list,
            validate=validate,
        )
        return lps_point

    def to_lps_or_ltm(
        self,
        *,
        constraints: Constraints | None = None,
        validate: bool | None = None,
    ) -> LpsPoint | LtmPoint:
        """
        Transform coordinate to `LpsPoint` or `LtmPoint`.

        The type of `out` is determined by the combination of
        `self.constraints` and the location of `self` on the Moon.

        `out` is not validated with this call but should be valid if `self` is
        valid.

        Parameters
        ----------
        constraints : Constraints, optional
            The constraints to apply to this transformation. If not specified
            (or `None`), `self.constraints` is used.
        validate : bool, optional
            Whether to fully validate the transformed coordinate. If `False`,
            no validation is performed. If not specified (or `None`), whatever
            validation is deemed necessary (if any) is performed. Note that if
            `out` was created earlier (i.e., is from the cache) and was already
            validated, it is not re-validated.

        Returns
        -------
        out : LpsPoint or LtmPoint
            The transformed coordinate. If `self` is compatible, `self` is
            returned. If caching is enabled, a cached instance may be returned.

        See Also
        --------
        .to_lps : Transformation to `LpsPoint` specifically
        .to_ltm : Transformation to `LtmPoint` specifically
        """
        return self._get_cached_or_create(
            self._to_lps_or_ltm,
            constraints=constraints,
            validate=validate,
        )

    def to_ltm(
        self,
        *,
        constraints: Constraints | None = None,
        validate: bool | None = None,
        search: bool = False,
    ) -> LtmPoint:
        """
        Transform coordinate to `LtmPoint`.

        This method is most commonly used to explicitly declare the expected
        output type, unlike the ambiguity of `.to_lps_or_ltm()` (which it calls
        internally). Alternatively, this method can be used (with
        `search=True`) to force transformation to `LtmPoint` by inferring
        appropriate constraints.

        Note that the transformation from `LatLonPoint` to `LpsPoint` or
        `LtmPoint` is the foundation that determines the system (LPS or LTM) of
        all later transformation to `*LgrsBox` and `*AccBox`.

        Parameters
        ----------
        constraints : Constraints, optional
            The (preferred) constraints to apply to this transformation. If not
            specified (or `None`), `self.constraints` is used.
        validate : bool, optional
            Whether to fully validate the transformed coordinate. If `False`,
            no validation is performed. If not specified (or `None`), whatever
            validation is deemed necessary (if any) is performed. Note that if
            `out` was created earlier (i.e., is from the cache) and was
            already validated, it is not re-validated.
        search : bool, default=False
            If `constraints` is not sufficient to produce an `LtmPoint` output,
            whether to search (success guaranteed) for a constraints
            configuration that achieves this. An effort is made not to diverge
            further from `constraints` than necessary.

        Returns
        -------
        out : LtmPoint
            The transformed coordinate. If `self` is compatible, `self` is
            returned. If caching is enabled, a cached instance may be returned.

        Raises
        ------
        lgrs.Exceptions.MalformedCoordinate
            If `constraints` are incompatible with `LtmPoint` for this
            location, and `search` is `False`.

        See Also
        --------
        .to : Transformation to any specified coordinate type
        """
        # Determine preferred order of `Constraints` instances.
        if constraints is None:
            constraints = self.constraints
        constraints_list = [constraints]
        if search:
            kwargs = {"preferred_ltm_zone": constraints.preferred_ltm_zone}
            if not constraints.extended_ltm:
                # Note: Since `extended_ltm=False` is preferred, attempt
                # to retain that constraint if possible.
                constraints_list.extend(
                    (
                        Constraints(
                            extended_ltm=False, prefer_ltm=True, **kwargs
                        ),
                        Constraints(
                            extended_ltm=True, prefer_ltm=False, **kwargs
                        ),
                    )
                )
            constraints_list.extend(
                (
                    Constraints(extended_ltm=True, prefer_ltm=True, **kwargs),
                    Constraints(global_ltm=True, **kwargs),
                )
            )

        # Convert to `LtmPoint`.
        ltm_point = self._force_type_or_error(
            self.to_lps_or_ltm,
            LtmPoint,
            constraints_list,
            validate=validate,
        )
        return ltm_point

    # Note: The following four methods permit `._to_*()` methods to be
    # defined in subclasses for just one step in each direction.
    def _raise_type_not_supported(self) -> _typing.NoReturn:
        raise TypeError(f"Type not supported: {self!r}")

    def _to_acc(self, *, precision: int, **kwargs) -> LpsAccBox | LtmAccBox:
        match self:
            case LpsPoint() | LtmPoint():
                lps_or_ltm_point = self
            case LatLonPoint():
                lps_or_ltm_point = self._to_lps_or_ltm(**kwargs)
            case _:
                self._raise_type_not_supported()
        lgrs_box = lps_or_ltm_point._to_lgrs(precision=1, **kwargs)
        acc_box = lgrs_box._to_acc(precision=precision, **kwargs)
        return acc_box

    def _to_latlon(self, **kwargs) -> LatLonPoint:
        match self:
            case LpsLgrsBox() | LtmLgrsBox():
                lgrs_box = self
            case LpsAccBox() | LtmAccBox():
                lgrs_box = self._to_lgrs(precision=self.precision, **kwargs)
            case _:
                self._raise_type_not_supported()
        lps_or_ltm_point = lgrs_box._to_lps_or_ltm(**kwargs)
        latlon_point = lps_or_ltm_point._to_latlon(**kwargs)
        return latlon_point

    def _to_lgrs(self, *, precision: int, **kwargs) -> LpsLgrsBox | LtmLgrsBox:
        if not isinstance(self, LatLonPoint):
            self._raise_type_not_supported()
        lps_or_ltm_point = self._to_lps_or_ltm(**kwargs)
        lgrs_box = lps_or_ltm_point._to_lgrs(precision=precision, **kwargs)
        return lgrs_box

    def _to_lps_or_ltm(self, **kwargs) -> LpsPoint | LtmPoint:
        if not isinstance(self, (LpsAccBox, LtmAccBox)):
            self._raise_type_not_supported()
        lgrs_box = self._to_lgrs(precision=self.precision, **kwargs)
        lps_or_ltm_point = lgrs_box._to_lps_or_ltm(**kwargs)
        return lps_or_ltm_point

    # * UTILITIES. ────────────────────────────────────────────────────
    def _iter_value_strings(self) -> _collections.abc.Iterator[str]:
        for value in self:
            match value:
                case str():
                    yield value
                case Constraints() | None:
                    continue
                case int() | float():
                    yield repr(value)
                case _:
                    self._raise_unexpected()


# endregion
###############################################################################
# region> POINT COORDINATE TYPES
###############################################################################
class PointCoordinate(BaseCoordinate):
    """The base class for all point coordinates."""

    # * TRANSFORMATION CACHING. ───────────────────────────────────────
    _precision: int = 0  # True by definition.
    _precision_origin: int = 0  # Default.

    # * COORDINATE TRANSFORMATION. ────────────────────────────────────
    @staticmethod
    @_caching._optionally_cache
    def _get_transformer(
        *, to_geographic: bool, proj_crs: _srs.CRS
    ) -> _pyproj.Transformer:
        geo_crs = _srs.make_lunar_crs()
        if to_geographic:
            crs_from = proj_crs
            crs_to = geo_crs
        else:
            crs_from = geo_crs
            crs_to = proj_crs
        transformer = _srs.get_transformer(crs_from, crs_to, always_xy=False)
        return transformer

    # * OVERLAPPING BOXES. ────────────────────────────────────────────
    def _calc_min_dist_to_meridian(
        self, latlon_point: LatLonPoint, meridian: float
    ) -> float:
        # Note: The naive calculation below is a modest overestimate,
        # but after scaling, is a lower limit even for measurements at
        # 84° latitude across 24° of longitude. Trailing commented block
        # gives unused exact calculation.
        ref_latlon_point = LatLonPoint(latlon_point.latitude, meridian)
        naive_dist = latlon_point.distance_to(ref_latlon_point)
        return 0.978 * naive_dist

        # Calculations below are for cross-track distance, which use
        # a starting point at the same latitude as `latlon_point` but on
        # the meridian and an implicit end point that is due north on
        # that meridian.
        # Source:https://www.movable-type.co.uk/scripts/latlong.html
        # start_latlon_point = LatLonPoint(latlon_point.latitude, meridian)
        # init_bearing_from_start_to_end_in_rads = 0  # Due north.
        # ang_dist_from_start_to_targ_in_rads = (
        #     latlon_point.distance_to(start_latlon_point) / _wkt.LUNAR_RADIUS
        # )
        # geod = _get_geod()
        # init_bearing_from_start_to_targ_in_degs, _, _ = geod.inv(
        #     start_latlon_point.longitude,
        #     start_latlon_point.latitude,
        #     latlon_point.longitude,
        #     latlon_point.latitude,
        # )
        # signed_dist = _wkt.LUNAR_RADIUS * _math.asin(
        #     _math.sin(ang_dist_from_start_to_targ_in_rads)
        #     * _math.sin(
        #         _math.radians(init_bearing_from_start_to_targ_in_degs)
        #         - init_bearing_from_start_to_end_in_rads
        #     )
        # )
        # dist = abs(signed_dist)

    def _get_ltm_zone_num_to_cached_lgrs_box(
        self, *, extended_ltm: bool, precision: int
    ) -> dict[int | None, LpsLgrsBox | LtmLgrsBox]:
        # If caching is disabled, return empty `dict`.
        if not _caching._CACHING_IS_ENABLED:
            return {}

        # Mine cache for all relevant cousins and score each.
        scored_cousins = []
        count = _itertools.count()
        for cousins in self._cache_key_to_cousins.values():
            for cousin in cousins:
                if not isinstance(cousin, BoxCoordinate):
                    continue
                if cousin._precision_origin > precision:
                    continue
                if cousin.constraints.extended_ltm != extended_ltm:
                    continue
                type_score = isinstance(cousin, (LpsLgrsBox, LtmLgrsBox))
                precision_score = cousin.precision == precision
                tiebreaker_score = next(count)
                scored_cousins.append(
                    ((type_score, precision_score, tiebreaker_score), cousin)
                )

        # Identify the best cousin for each CRS.
        scored_cousins.sort()
        ltm_zone_num_to_cousin = {
            (
                None
                if cousin.crs.ltm_zone is None
                else int(cousin.crs.ltm_zone[:-1])
            ): cousin
            for score, cousin in scored_cousins
        }

        # Convert each cousin, as necessary, to conform to type and
        # precision expectations, and return mapping.
        for ltm_zone_num, cousin in ltm_zone_num_to_cousin.items():
            if not isinstance(cousin, (LpsLgrsBox, LtmLgrsBox)):
                final_cousin = cousin.to_lgrs(precision=precision)
            elif cousin.precision != precision:
                final_cousin = cousin.with_precision(precision)
            else:
                continue
            ltm_zone_num_to_cousin[ltm_zone_num] = final_cousin
        return ltm_zone_num_to_cousin

    @_functools.cached_property
    def _may_have_25k_lps_box(self) -> bool:
        latlon_point = self.to_latlon()
        lps_favoring_constraints = Constraints(
            extended_ltm=self.constraints.extended_ltm, prefer_lps=True
        )
        may_be_in_lps_region = (
            abs(latlon_point.latitude)
            > lps_favoring_constraints._min_abs_lps_lat_with_preference
        )
        return may_be_in_lps_region

    @_functools.cached_property
    def _may_have_25k_ltm_box(self) -> bool:
        latlon_point = self.to_latlon()
        ltm_favoring_constraints = Constraints(
            extended_ltm=self.constraints.extended_ltm, prefer_ltm=True
        )
        may_be_in_ltm_region = (
            abs(latlon_point.latitude)
            < ltm_favoring_constraints._max_abs_ltm_lat_with_preference
        )
        return may_be_in_ltm_region

    @_functools.cached_property
    def _potential_ltm_zone_nums(self) -> tuple[int, ...]:
        if not self._may_have_25k_ltm_box:
            return ()
        latlon_point = self.to_latlon()
        _, nom_ltm_zone_num = _database._calculate_ltm_zone_number(
            latlon_point.longitude
        )
        zone_nums = [nom_ltm_zone_num]
        for sign, attr_name in (
            (-1, "maximum_longitude"),
            (+1, "minimum_longitude"),
        ):
            for i in range(1, 4):
                test_ltm_zone_num = nom_ltm_zone_num + (sign * i)
                if test_ltm_zone_num > 45:
                    test_ltm_zone_num -= 45  # 46 -> 1, 47 -> 2, etc.
                elif test_ltm_zone_num < 1:
                    test_ltm_zone_num += 45  # 0 -> 45, -1 -> 44, etc.
                # Note: Hemisphere is irrelevant but must be specified.
                test_ltm_zone = _wkt.LtmZone(
                    number=test_ltm_zone_num, hemisphere="N"
                )
                test_lon = getattr(test_ltm_zone, attr_name)
                min_dist_to_zone = self._calc_min_dist_to_meridian(
                    latlon_point, test_lon
                )
                if (
                    min_dist_to_zone
                    < self.constraints._max_geod_length_of_25km_box_diag
                ):
                    zone_nums.append(test_ltm_zone_num)
                else:
                    break
            else:
                # Note: This error should never be raised. Check is
                # required to ensure that
                # `._calc_min_dist_to_meridian()` is guaranteed to be
                # lower limit.
                raise TypeError(
                    "Potential LTM zone count exceeds supported maximum."
                )
        zone_nums.sort()
        return tuple(zone_nums)

    def to_all_acc(
        self,
        *,
        extended_ltm: bool | None = None,
        precision: float = 1,
        validate: bool | None = None,
    ) -> tuple[LpsAccBox | LtmAccBox, ...]:
        """
        Get all ACC boxes that include the point `self`.

        For documentation, see `.to_all_lgrs()`.

        Returns
        -------
        boxes : tuple of ACC boxes
            All valid ACC boxes that overlap `self`, subject to `extended_ltm`.
        """
        lgrs_box_tup = self.to_all_lgrs(
            extended_ltm=extended_ltm, precision=precision
        )
        acc_box_tup = tuple(
            lgrs_box.to_acc(validate=validate) for lgrs_box in lgrs_box_tup
        )
        return acc_box_tup

    def to_all_lgrs(
        self,
        *,
        extended_ltm: bool | None = None,
        precision: float = 1,
        validate: bool | None = None,
    ) -> tuple[LpsLgrsBox | LtmLgrsBox, ...]:
        """
        Get all LGRS boxes that include the point `self`.

        Multiple valid LGRS boxes (`LpsLgrsBox` and `LtmLgrsBox`) may overlap a
        given point near the following boundaries:
          (1) The latitudinal LPS/LTM boundary. (See `extended_ltm` argument.)
          (2) The longitudinal boundary between neighboring LTM zones.
        When using `.to_lgrs()`, the single box returned is determined by the
        `constraints` argument. The current method returns all possible boxes
        for any `constraints`, subject to `extended_ltm`.

        Parameters
        ----------
        extended_ltm : bool | None, default=None
            Whether to use the extended LTM region. If `True`, the nominal
            poleward extent of the LTM region is 82° N/S instead of 80° N/S.
            If `None`, `self.constraints.extended_ltm` is used.
        precision : float, default=1
            The maximum allowed value of `out.precision`.
        validate : bool | None
            Whether to fully validate each box in `boxes`. If `False`, no
            validation is performed. If not specified (or `None`), whatever
            validation is deemed necessary (if any) is performed. Note that if
            any box was created earlier (i.e., is from the cache) and was
            already validated, it is not re-validated.

        Returns
        -------
        boxes : tuple of LGRS boxes
            All valid LGRS boxes that overlap `self`, subject to
            `extended_ltm`. The maximum length of `boxes` is 3, and it may
            contain, at most, 1 `LpsLgrsBox` and 2 `LtmLgrsBox` instances. The
            `LpsLgrsBox` instance, if present, is ``boxes[0]``.

        Examples
        --------
        In the simplest and most common case, only one valid LGRS box overlaps
        a point.

        >>> point_1 = LatLonPoint(0, 0)
        >>> nominal_lgrs_box_1 = point_1.to_lgrs()
        >>> all_lgrs_boxes_1 = point_1.to_all_lgrs()
        >>> len(all_lgrs_boxes_1)
        1
        >>> nominal_lgrs_box_1 == all_lgrs_boxes_1[0]
        True

        In other cases, as many as 3 valid LGRS boxes may overlap a point.

        >>> point_2 = LatLonPoint(80, 4)
        >>> nominal_lgrs_box_2 = point_2.to_lgrs()
        >>> all_lgrs_boxes_2 = point_2.to_all_lgrs()
        >>> len(all_lgrs_boxes_2)
        3
        >>> nominal_lgrs_box_2 in all_lgrs_boxes_2
        True
        """
        # Create generic constraints and corresponding `LatLonPoint`.
        # Note: This helps ensure reuse of some results in future calls.
        if extended_ltm is None:
            extended_ltm = self.constraints.extended_ltm  # *REASSIGNMENT*
        generic_constraints = Constraints(extended_ltm=extended_ltm)
        version: LatLonPoint = self.to_latlon(constraints=generic_constraints)
        del self  # Avoid accidental use.

        # Mine the cache for relevant LGRS cousins.
        # *REASSIGNMENT*
        precision = version._resolve_precision(precision, targ_type=LpsLgrsBox)
        ltm_zone_num_to_lgrs_box = (
            version._get_ltm_zone_num_to_cached_lgrs_box(
                extended_ltm=extended_ltm, precision=precision
            )
        )

        # Check for any missing cousin and attempt to create it.
        if (
            version._may_have_25k_lps_box
            and None not in ltm_zone_num_to_lgrs_box
        ):
            lps_favoring_constraints = Constraints(
                extended_ltm=extended_ltm, prefer_lps=True
            )
            this_version = version.replace(lps_favoring_constraints)
            crs, new_cousins = lps_favoring_constraints._test_forced_lgrs_box(
                this_version, target_lps=True
            )
            if crs is not None:
                for new_cousin in new_cousins:
                    this_version._register_cousin(new_cousin)
                ltm_zone_num_to_lgrs_box[None] = new_cousins[0].with_precision(
                    precision
                )
        for ltm_zone_num in version._potential_ltm_zone_nums:
            if ltm_zone_num in ltm_zone_num_to_lgrs_box:
                continue
            ltm_zone_favoring_constraints = Constraints(
                extended_ltm=extended_ltm,
                preferred_ltm_zone=ltm_zone_num,
            )
            this_version = version.replace(ltm_zone_favoring_constraints)
            crs, new_cousins = (
                ltm_zone_favoring_constraints._test_forced_lgrs_box(
                    this_version, ltm_zone_number=ltm_zone_num
                )
            )
            if crs is not None:
                for new_cousin in new_cousins:
                    this_version._register_cousin(new_cousin)
                ltm_zone_num_to_lgrs_box[ltm_zone_num] = new_cousins[
                    0
                ].with_precision(precision)

        # Record LPS and LTM results for potential use by a different
        # `precision`.
        has_lps = None in ltm_zone_num_to_lgrs_box
        object.__setattr__(version, "_may_have_25k_lps_box", has_lps)
        ltm_zone_nums = tuple(
            ltm_zone_num
            for ltm_zone_num in ltm_zone_num_to_lgrs_box
            if ltm_zone_num is not None
        )
        object.__setattr__(version, "_potential_ltm_zone_nums", ltm_zone_nums)

        # Create sorted `tuple` of LGRS boxes.
        scored_lgrs_boxes = [
            (-1 if ltm_zone_num is None else ltm_zone_num, box)
            for ltm_zone_num, box in ltm_zone_num_to_lgrs_box.items()
        ]
        scored_lgrs_boxes.sort()
        lgrs_box_tup = tuple(box for score, box in scored_lgrs_boxes)

        # Optionally validate, then return.
        if validate:
            for box in lgrs_box_tup:
                box.validate()
        return lgrs_box_tup


# TODO: Un-skip Example 3 once complete validation is implemented.
@_dataclasses.dataclass(frozen=True, repr=False)
class LatLonPoint(PointCoordinate):
    """
    Create an instance representing a latitude-longitude point.

    Parameters
    ----------
    latitude : float
        The latitude of `new`, in decimal degrees.
    longitude : float
        The longitude of `new`, in decimal degrees.
    constraints : Constraints, default=Constraints()
        The constraints together determine whether the location is assigned
        to the Lunar Polar Stereographic (LPS) or Lunar Transverse Mercator
        (LTM) systems and, in the latter case, to which LTM zone the
        location is assigned. See `Constraints` for additional
        documentation. Although these constraints do not directly apply to
        `LatLonPoint`, they are honored in all future transformations of
        this instance.
    validate : bool, default=True
        Whether to validate that the coordinate's values are supported,
        subject to the constraints. This validation also conforms any
        values, where appropriate. See Example 5.

    Raises
    ------
    lgrs.Exceptions.MalformedCoordinate
        If the instance is invalid. Both values and constraints are
        considered.

    See Also
    --------
    Constraints : Additional documentation on constraints.

    Examples
    --------
    >>> point = LatLonPoint(0, 0)

    Constraints are remembered and honored by all derived coordinate
    instances (except where explicitly overridden). Thus, even though the
    `extended_ltm` constraint is irrelevant to `geo_point` (below), that
    constraint is remembered and determines that `proj_point` belongs to the
    extended LTM region rather than the LPS region.

    >>> extended_ltm = Constraints(extended_ltm=True)
    >>> geo_point = LatLonPoint(81, 0, constraints=extended_ltm)
    >>> proj_point = geo_point.to_lps_or_ltm()  # Example 1
    >>> isinstance(proj_point, LtmPoint)
    True

    A coordinate may be invalid because its values are disallowed
    universally (Example 2) or because its type or values are disallowed by
    the applied constraints (Example 3).

    >>> LatLonPoint(1000, -1000)  # Example 2  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    lgrs.exceptions.MalformedCoordinate:
      ...
    >>> lps_point = geo_point.to_ltm()
    >>> lps_point.replace(constraints=extended_ltm)  # Example 3  # doctest: +SKIP
    Traceback (most recent call last):
      ...
    lgrs.exceptions.MalformedCoordinate:
      ...

    Finally, validation may conform values where those can be confidently
    interpreted.

    >>> latlon_point = LatLonPoint(45, 182)  # Example 4
    >>> latlon_point.longitude == -178  # Conformed.
    True
    """  # noqa: E501

    # * FIELDS AND VALIDATION. ────────────────────────────────────────
    latitude: float
    longitude: float

    def _template(self) -> str:
        if self.latitude >= 0:
            n_or_s = "N"
        else:
            n_or_s = "S"
        if self.longitude >= 0:
            e_or_w = "E"
        else:
            e_or_w = "W"
        return (
            f"{abs(self.latitude)!r}°{n_or_s} "
            f"{abs(self.longitude)!r}°{e_or_w}"
        )

    def _validate(self) -> None:
        if not (0 <= self.latitude <= 90):
            conformed_lat = _database._conform_latitude(self.latitude)
            object.__setattr__(self, "latitude", conformed_lat)
        if not (-180 <= self.longitude < 180):
            conformed_lon = _database._conform_longitude(self.longitude)
            object.__setattr__(self, "longitude", conformed_lon)
        self._register_validation()

    # * COORDINATE TRANSFORMATION. ────────────────────────────────────
    _get_crs_name = _return_none

    @_cache_new_cousin
    def _to_lps_or_ltm(
        self,
        *,
        proj_crs: _srs.CRS | None = None,
        constraints: Constraints | None = None,
        validate: bool | None,
    ) -> LpsPoint | LtmPoint:
        # Find projected CRS, which depends on constraints.
        if proj_crs is None:
            assert constraints is not None
            proj_crs, new_cousins = constraints._get_proj_crs_and_new_cousins(
                self
            )
            if new_cousins:
                for cousin in new_cousins:
                    self._register_cousin(cousin)
                if isinstance(cousin, (LpsPoint, LtmPoint)):
                    return cousin

        # Transform.
        transformer = self._get_transformer(
            to_geographic=False, proj_crs=proj_crs
        )
        e, n = transformer.transform(self.latitude, self.longitude)

        # Create and return instance.
        if proj_crs.ltm_zone is None:
            lps_point = LpsPoint(
                hemisphere=proj_crs.lps_hemisphere,
                easting=e,
                northing=n,
                constraints=self.constraints,
                validate=False,
            )
            return lps_point
        else:
            # TODO: Let Mark know that Table 2 is missing zones 24 and
            #  25.
            zone = int(proj_crs.ltm_zone[:-1])
            hemi = proj_crs.ltm_zone[-1]
            ltm = LtmPoint(
                zone_number=zone,
                hemisphere=hemi,
                easting=e,
                northing=n,
                constraints=self.constraints,
                validate=False,
            )
            return ltm


@_dataclasses.dataclass(frozen=True, repr=False)
class LpsPoint(PointCoordinate):
    """
    Create an instance representing a Lunar Polar Stereographic (LPS) point.

    Parameters
    ----------
    hemisphere : {"N", "S"}
        The point's hemisphere.
    easting : float
        The point's easting (meters).
    northing : float
        The point's northing (meters).
    constraints : Constraints, default=Constraints()
        See `LatLonPoint` documentation.
    validate : bool, default=True
        See `LatLonPoint` documentation.

    Raises
    ------
    lgrs.Exceptions.MalformedCoordinate
        If the instance is invalid. Both values and constraints are
        considered.

    Examples
    --------
    >>> point = LpsPoint("N", 500_000, 500_000)
    """

    # * FIELDS AND VALIDATION. ────────────────────────────────────────
    _template = "{hemisphere}{easting!r}E{northing!r}N"
    hemisphere: str
    easting: float
    northing: float

    # Note: `._validate_hemisphere()` is defined on base class.

    # * COORDINATE TRANSFORMATION. ────────────────────────────────────
    def _get_crs_name(self) -> str | None:
        return self.hemisphere

    def _get_transformer(self, *, to_geographic: bool) -> _pyproj.Transformer:
        transformer = LatLonPoint._get_transformer(
            to_geographic=to_geographic, proj_crs=self.crs
        )
        return transformer

    @_cache_new_cousin
    def _to_latlon(
        self,
        *,
        constraints: Constraints | None = None,
        validate: bool | None,
    ) -> LatLonPoint:
        transformer = self._get_transformer(to_geographic=True)
        lat, lon = transformer.transform(self.easting, self.northing)
        latlon = LatLonPoint(
            latitude=lat,
            longitude=lon,
            constraints=self.constraints,
            validate=False,
        )
        return latlon

    @_cache_new_cousin
    def _to_lgrs(
        self,
        *,
        constraints: Constraints | None = None,
        precision: int,
        validate: bool | None,
    ) -> LpsLgrsBox:
        if validate or validate is None:
            LpsLgrsBox._validate_that_constraints_are_nonglobal(constraints)
        is_in_west_half = self.easting < _wkt.LPS_FALSE_EASTING
        match (self.hemisphere, is_in_west_half):
            case ("S", True):  # Eq. 100
                lon_band = "A"
            case ("S", False):  # Eq. 101
                lon_band = "B"
            case ("N", True):  # Eq. 100
                lon_band = "Y"
            case ("N", False):  # Eq. 101
                lon_band = "Z"
            case _:
                self._raise_unexpected(self._validate_hemisphere)
        e_adj = self.easting - _wkt.LPS_FALSE_EASTING  # Eq. 109
        n_adj = self.northing - _wkt.LPS_FALSE_NORTHING  # Eq. 110
        if is_in_west_half:
            # TODO: Check with Mark that abs() should instead be around
            #  around e_adj in Eq. 103, as it is on line 1646 of
            #  reference code.
            # TODO: Let Mark know that Eq. 103 treats Table 13 as 1-
            #  indexed but Eq. 102 treats it as 0-indexed.
            # Note: Eq. 103 uses "24" but "23" used here since our Table
            # 13 equivalent starts at 1, not 0.
            ea_idx = 23 - _floor(abs(e_adj) // 25_000)  # Eq. 103
        else:
            ea_idx = _floor(e_adj // 25_000)  # Eq. 102
        ea = LpsLgrsBox._easting_area_chars[ea_idx]  # Tables 13, 14
        na_idx = _floor(n_adj // 25_000) + 13  # Eq. 104
        na = LpsLgrsBox._northing_area_chars[na_idx]  # Tables 15, 16
        if is_in_west_half:
            e = 25_000 - (abs(e_adj) % 25_000)  # Eq. 105
        else:
            e = e_adj % 25_000  # Eq. 106
        n = n_adj % 25_000
        lps_lrgs = LpsLgrsBox(
            longitudinal_band=lon_band,
            easting_area=ea,
            northing_area=na,
            easting=_format_as_five_digit_int(e),
            northing=_format_as_five_digit_int(n),
            constraints=self.constraints,
            validate=False,
        )
        return lps_lrgs.with_precision(precision)


@_dataclasses.dataclass(frozen=True, repr=False)
class LtmPoint(PointCoordinate):
    """
    Create an instance representing a Lunar Transverse Mercator (LTM) point.

    Parameters
    ----------
    zone_number : int
        The LTM zone number, between 1 and 45 (inclusive).
    hemisphere : {"N", "S"}
        The point's hemisphere.
    easting : float
        The point's easting (meters).
    northing : float
        The point's northing (meters).
    constraints : Constraints, default=Constraints()
        See `LatLonPoint` documentation.
    validate : bool, default=True
        See `LatLonPoint` documentation.

    Raises
    ------
    lgrs.Exceptions.MalformedCoordinate
        If the instance is invalid. Both values and constraints are
        considered.

    Examples
    --------
    >>> point = LtmPoint(23, "N", 250_000, 250_000)
    """

    # * FIELDS AND VALIDATION. ────────────────────────────────────────
    _template = "{zone_number}{hemisphere}{easting!r}E{northing!r}N"
    zone_number: int
    hemisphere: str
    easting: float
    northing: float

    def _validate_zone_number(self) -> None:
        return self._validate_against_closed_interval(
            attr_name="zone_number", minimum=1, maximum=45
        )

    # Note: `._validate_hemisphere()` is defined on base class.

    # * COORDINATE TRANSFORMATION. ────────────────────────────────────
    def _get_crs_name(self) -> str | None:
        return f"{self.zone_number}{self.hemisphere}"

    _get_transformer = LpsPoint._get_transformer

    _to_latlon = LpsPoint._to_latlon

    @_cache_new_cousin
    def _to_lgrs(
        self,
        *,
        constraints: Constraints | None = None,
        precision: int,
        validate: bool | None,
    ) -> LtmLgrsBox:
        if validate or validate is None:
            LtmLgrsBox._validate_that_constraints_are_nonglobal(constraints)
        lon_band = self.zone_number
        latlon_point = self.to_latlon()
        lat_band_idx = _floor(latlon_point.latitude // 8)  # Eq. 81
        # Note: "+ 11" adjusts for indices in Table 6, which start at
        # -11.
        # Table 6
        lat_band = LtmLgrsBox._latitudinal_band_chars[lat_band_idx + 11]
        ea_idx = _floor(self.easting // 25_000) - 5  # Eq. 82
        ea = LtmLgrsBox._easting_area_chars[ea_idx]  # Table 7
        na_letterset = _calc_na_letterset(self.zone_number)  # Eq. 83
        na_idx = _floor(self.northing // 25_000) % 20  # Eq. 84
        na = LtmLgrsBox._northing_area__letterset_to_chars[na_letterset][
            na_idx
        ]  # Tables 8, 9, 10
        e = self.easting % 25_000  # Eq. 85
        n = self.northing % 25_000  # Eq. 86
        ltm_lgrs = LtmLgrsBox(
            longitudinal_band=lon_band,
            latitudinal_band=lat_band,
            easting_area=ea,
            northing_area=na,
            easting=_format_as_five_digit_int(e),
            northing=_format_as_five_digit_int(n),
            constraints=self.constraints,
            validate=False,
        )
        return ltm_lgrs.with_precision(precision)


# endregion
###############################################################################
# region> BOX COORDINATE BASE TYPES
###############################################################################
class BoxCoordinate(BaseCoordinate):
    """The base class for all gridded box coordinates."""

    # * FIELDS AND VALIDATION. ────────────────────────────────────────
    easting: str | None
    northing: str | None

    def _validate(self) -> bool:
        # First, attempt inherited validation.
        if super()._validate(raise_fallback=False):
            return True

        # Instance is invalid, but try to diagnose cause for user.
        try:
            self._validate_against_pattern(self.string)
        except _exceptions.MalformedCoordinate:
            raise
        except Exception:
            pass
        self._raise_fallback_exception()

    @classmethod
    def _validate_against_pattern(cls, string: str) -> _regex.Match:
        match = cls._pattern.search(string)
        if match:
            return match
        simple_pattern = cls._get_simple_pattern()
        if simple_pattern.search(string):
            if "I" in string or "O" in string:
                raise _exceptions.MalformedCoordinate(
                    "`.string` contains the letters 'I' or 'O', which are "
                    "not used by LGRS"
                )
            else:
                # Note: This line should never be seen but is included
                # for compleness.
                failed_pattern = cls._pattern
        else:
            failed_pattern = simple_pattern
        raise _exceptions.MalformedCoordinate(
            f"`.string` does not have the form: {failed_pattern.pattern!r}"
        )

    def _validate_constraints(self) -> None:
        return self._validate_that_constraints_are_nonglobal(self.constraints)

    @classmethod
    def _validate_that_constraints_are_nonglobal(
        cls, constraints: Constraints
    ) -> None:
        for name in ("global_lps", "global_ltm", "global_crs"):
            if not getattr(constraints, name):
                continue
            raise _exceptions.MalformedCoordinate(
                "Global constraints are not compatible with "
                f"`{cls.__name__}`, including: `{name}`"
            )

    # * TRANSFORMATION CACHING. ───────────────────────────────────────
    @_functools.cached_property
    def _precision(self) -> int:
        return self.precision

    # Note: This is only the default value and may be overridden.
    @_functools.cached_property
    def _precision_origin(self) -> int:
        return self._precision

    # * UTILITIES. ────────────────────────────────────────────────────
    @staticmethod
    def _as_int(string: str | None, *, nom_length: int) -> int:
        if string is None:
            return 0
        else:
            return int(f"{string}000"[:nom_length])

    # * INSTANTIATION FROM STRING. ────────────────────────────────────
    _pattern: _regex.Pattern

    @classmethod
    @_functools.cache
    def _get_simple_pattern(cls) -> _regex.Pattern:
        match = _regex.search(r"\(\?# *(?P<s>.*)\)$", cls._pattern.pattern)
        orig_pattern = match.group("s")
        unescaped = orig_pattern.replace("\\", "")
        simple_pattern = _regex.sub(r"\(\?P<.+?>(.*?)\)", r"\1", unescaped)
        return _regex.compile(simple_pattern)

    # TODO: Test why `LpsLgrsBox.from_string("YZ+")` doesn't work.
    @classmethod
    def from_string(
        cls,
        string: str,
        *,
        constraints: Constraints = _default_constraints,
        validate: bool = True,
    ) -> _typing.Self:
        """
        Create a box coordinate instance from a string.

        Parameters
        ----------
        string : str
            The string form of the box coordinate, equivalent to `new.string`.
        constraints : Constraints, default=Constraints()
            See `LatLonPoint` documentation.
        validate : bool, default=True
            Whether to validate `new`.

        Returns
        -------
        new : BoxCoordinate
            The new box coordinate instance. The type is determined by the
            call. See Examples.

        Examples
        --------
        When called the `BoxCoordinate` base class, an instance of the
        appropriate type is returned.

        >>> box_1 = BoxCoordinate.from_string("42SAM2468910101")
        >>> isinstance(box_1, LtmLgrsBox)
        True

        When called from any other class (or instance), an instance of the same
        type is returned, if possible, or an error is raised.

        >>> box_2 = LtmLgrsBox.from_string("42SAM2468910101")
        >>> box_1 == box_2
        True
        >>> box_3 = LpsLgrsBox.from_string("42SAM2468910101")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        lgrs.exceptions.MalformedCoordinate:
          ...
        """  # noqa: E501
        # Support call from `BoxCoordinate` itself.
        if cls is BoxCoordinate:
            for typ in (LpsLgrsBox, LpsAccBox, LtmLgrsBox, LtmAccBox):
                try:
                    new = typ.from_string(string)
                except _exceptions.MalformedCoordinate:
                    continue
                else:
                    return new
            raise _exceptions.MalformedCoordinate(
                f"`string` is not in a supported format: {string!r}"
            )

        # Match to pattern.
        match = cls._validate_against_pattern(string)
        match_dict = match.groupdict()

        # Coerce each argument to the correct type.
        # TODO: Approach below allows 0-prefixing of integers. The only
        #  pattern that allows an ambiguity is for the first few
        #  characters of `Ltm*Box`. For example, should both "01N" and
        #  "1N" be allowed? The former has the benefit of ensuring that
        #  all strings have the same length, but `.string` uses the
        #  latter, which I think is Mark's intent. The reference code
        #  allows "1N", "01N", "001N", etc.
        field_name_to_type = cls._get_field_name_to_type()
        init_kwargs = {
            name: field_name_to_type[name](value_string)
            for name, value_string in match_dict.items()
            if value_string is not None
        }
        return cls(**init_kwargs, constraints=constraints, validate=validate)

    # * COORDINATE TRANSFORMATION. ────────────────────────────────────
    def _get_crs_name(self) -> str:
        return self.to_lps_or_ltm()._get_crs_name()

    # * REFERENCE POINTS. ─────────────────────────────────────────────
    _global_lps = Constraints(global_lps=True)

    @_functools.cached_property
    def _corners(self) -> ProjectedCorners:
        return ProjectedCorners(*self._sample_boundary(1, use_cache=False))

    def _make_parallel_marching_iter(
        self, count_per_side: int
    ) -> _typing.Iterator[tuple[int, int]]:
        step_size = self.precision / count_per_side
        deltas = _itertools.count(0, step_size)
        for delta in deltas:
            if delta == self.precision:
                break
            yield (delta, 0)
            yield (self.precision, delta)
            yield (self.precision - delta, self.precision)
            yield (0, self.precision - delta)

    def _make_reference_point(
        self,
        easting_delta: float,
        northing_delta: float,
        *,
        as_latlon: bool = False,
        preserve_constraints: bool = False,
    ) -> LpsPoint | LtmPoint | LatLonPoint:
        lps_or_ltm_point = self.to_lps_or_ltm()
        # Note: Set `constraints` such that coordinate is guaranteed
        # valid after application of deltas.
        if easting_delta == 0 and northing_delta == 0:
            constraints = lps_or_ltm_point.constraints
        else:
            constraints = Constraints(global_crs=self.crs_nominal)
        proj_point = lps_or_ltm_point.replace(
            easting=lps_or_ltm_point.easting + easting_delta,
            northing=lps_or_ltm_point.northing + northing_delta,
            constraints=constraints,
            validate=False,  # For efficiency only. Known to be valid.
        )
        if as_latlon:
            new = proj_point.to_latlon()
            if preserve_constraints:
                # Note: More useful for public exposure.
                return new.replace(self.constraints)
            else:
                return new
        return proj_point

    def _sample_boundary(
        self,
        count_per_side: int,
        *,
        as_latlon: bool = False,
        serial: bool = False,
        preserve_constraints: bool = False,
        use_cache: bool = True,
    ) -> _collections.abc.Iterator[LpsPoint | LtmPoint | LatLonPoint]:
        # Cache if special "corners" case.
        # Note: `serial` is irrelevant in this case.
        if use_cache and count_per_side == 1:
            if as_latlon:
                points = self.corners_latlon
            else:
                points = self._corners
            for point in points:
                yield point
            return

        # Iterate.
        parallel_iter = self._make_parallel_marching_iter(count_per_side)
        if serial:
            deltas_iter = _itertools.chain(
                *zip(*_itertools.batched(parallel_iter, 4))
            )
        else:
            deltas_iter = parallel_iter
        for easting_delta, northing_delta in deltas_iter:
            point = self._make_reference_point(
                easting_delta,
                northing_delta,
                as_latlon=as_latlon,
                preserve_constraints=preserve_constraints,
            )
            yield point

    @_functools.cached_property
    def bounds(self) -> _bounds.ProjectedBounds:
        """
        Box's bounds as a named tuple of coordinates in the underlying CRS.
        """
        (x_sw, y_sw), (x_se, y_se), (x_ne, y_ne), (x_nw, y_nw) = (
            (point.easting, point.northing) for point in self._corners
        )
        bounds = _bounds.ProjectedBounds(
            min_easting=min(x_nw, x_sw),
            min_northing=min(y_se, y_sw),
            max_easting=max(x_ne, x_se),
            max_northing=max(y_ne, y_nw),
            crs_hint=self.crs_nominal,
        )
        return bounds

    @_functools.cached_property
    def center_latlon(self) -> LatLonPoint:
        """The grid center as a `LatLonPoint`."""
        half_precision = 0.5 * self.precision
        center = self._make_reference_point(
            +half_precision,
            +half_precision,
            as_latlon=True,
            preserve_constraints=True,
        )
        return center

    @_functools.cached_property
    def corners_latlon(self) -> GeographicCorners:
        """
        Box's bounds as a named tuple of coordinates in the underlying CRS.
        """
        return GeographicCorners(
            *(
                point.to_latlon(constraints=self.constraints)
                for point in self._corners
            )
        )

    # * OUTPUT SUPPORT. ───────────────────────────────────────────────
    _extra_field_names: tuple[str, ...]
    _field_data: FieldData

    @_functools.cached_property
    def default_field_data(self) -> FieldData:
        """
        The default (read-only) mapping for `.field_data`.
        """
        field_data = self._init_kwargs.copy()
        del field_data["constraints"]
        for field_name in self._extra_field_names:
            field_data[field_name] = getattr(self, field_name)
        return _types.MappingProxyType(field_data)

    @property
    def field_data(self) -> FieldData:
        """
        The currently registered mapping for field data.
        """
        try:
            return self._field_data
        except AttributeError:
            self.set_field_data()
            return self._field_data

    @_functools.cached_property
    def geometry(self) -> _shapely.Polygon:
        """The shapely polygon form of the box."""
        return self.bounds.geometry

    def set_field_data(
        self,
        field_data: FieldData | None = None,
    ) -> None:
        """
        Set field data (`.field_data`) for this box.

        To reset `.field_data` to a writable copy of its default, use::

            box.set_field_data()

        which is equivalent to::

            box.set_field_data(dict(box.default_field_data))

        Parameters
        ----------
        field_data : a mapping with string keys, optional
            The field data to assign to this box.

        See Also
        --------
        .field_data : The stored (or default) field data for this box.
        """
        if field_data is None:
            field_data = dict(self.default_field_data)
        object.__setattr__(self, "_field_data", field_data)

    # * PUBLIC DATA AND METHODS. ──────────────────────────────────────
    precision: int

    def contains(
        self,
        other: BaseCoordinate,
        *,
        logical_only: bool = False,
        same_crs_only: bool = False,
        tolerance: float = 0.001,
        error: bool = True,
    ) -> bool:
        """
        Test whether the areal extent of `self` includes another coordinate.

        More precisely, `self` contains `other` if no part of the interior of
        `other` is in the exterior of `self`. Therefore, If `self` and `other`
        are equivalent, each is considered to contain the other. If `self` and
        `other` are boxes from the same LTM zone or LPS region (that is, the
        same CRS), a logical test is performed.

        Parameters
        ----------
        other : BaseCoordinate
            The possibly contained coordinate.
        same_crs_only : bool, default=False
            Whether to consider cross-CRS containment. If `False` and `other`
            is from a different nominal CRS (`.crs_nominal`) than `self`,
            containment testing is aborted.
        logical_only : bool, default=False
            Whether to require logical containment, that is, only test whether
            `self` and `other` are both boxes in the same CRS. If `True`, and
            `other` is either not a box coordinate or from a different
            nominal CRS (`.crs_nominal`), containment testing is aborted.
        tolerance : float, default=0.001
            If `other` is within this tolerance (meters) of being contained by
            `self`, `True` is returned. For cross-CRS tests, the underlying
            transformation calculations may not be sufficiently precise to
            provide the correct result unless `tolerance` is nonzero. This
            value may be negative, which makes tests more restrictive.
            `tolerance` is ignored in logical tests.
        error : bool, default=True
            Whether to raise a description exception rather than return `False`
            when `logical_only=True` or `same_crs_only=True` and that
            requirement is violated, aborting containment testing.

        Returns
        -------
        is_contained : bool
            Whether `other` is contained within `self` (or equivalent to
            `self`).

        Raises
        ------
        TypeError
            If `error` is `True` and `logical_only` or `same_crs_only`
            requirements are violated.
        """
        # Honor restrictive arguments.
        other_is_box = isinstance(other, BoxCoordinate)
        if logical_only and not other_is_box:
            if error:
                raise TypeError(f"`other` is not a `BoxCoordinate`: {other!r}")
            else:
                return False
        is_cross_crs = self.crs_nominal != other.crs_nominal
        if (logical_only or same_crs_only) and is_cross_crs:
            if error:
                raise TypeError(
                    f"`other` is not from the same (nominal) CRS: {other!r}"
                )
            else:
                return False

        # Perform logical test, if supported.
        if other_is_box and not is_cross_crs:
            is_child = self.string.startswith(other.string)
            return is_child

        # Rule out containment cheaply, if possible.
        if (
            self.distance_to(other)
            > (_values.SAFETY_FACTOR * self.diagonal) + tolerance
        ):
            return False

        # Perform spatial (non-logical) test.
        if other_is_box:
            # TODO: Determine what sampling density is necessary. The
            #  value 21 is used by `pyproj` for the conceptually similar
            #  `densify_pts` argument of `Transformer.transform_bounds`.
            test_points = other._sample_boundary(21)
        else:
            test_points = (other,)
        (
            self_min_easting,
            self_min_northing,
            self_max_easting,
            self_max_northing,
        ) = self.bounds
        constraints = Constraints(global_crs=self.to_lps_or_ltm().crs)
        for test_point in test_points:
            same_sys_test_point = test_point.to_lps_or_ltm(
                constraints=constraints
            )
            if (
                self_min_easting - tolerance
                <= same_sys_test_point.easting
                <= self_max_easting + tolerance
            ):
                if (
                    self_min_northing - tolerance
                    <= same_sys_test_point.northing
                    <= self_max_northing + tolerance
                ):
                    continue
            return False
        return True

    @_functools.cached_property
    def diagonal(self) -> float:
        """
        The length of the box's diagonal, in meters.

        Strictly, this length is expressed in grid meters and therefore
        inherits the distortion of the underlying CRS.
        """
        return _values.calculate_diagonal_length(self.precision, safe_up=False)

    def with_precision(
        self,
        precision: float,
        *,
        copy: bool = False,
        error: bool = True,
        validate: bool = False,
    ) -> _typing.Self:
        """
        Get a version with the specified precision or better.

        The respective lengths of the relevant easting and northing strings
        will be truncated so that `out.precision` is no greater than
        `precision`. The final lengths of those strings will be no longer than
        what is strictly necessary to satisfy `precision`.

        Parameters
        ----------
        precision : float
             The maximum allowed value of `out.precision`.
        copy : bool, default=False
            Whether to ensure that `out` is not `self`. If `False` and `self`
            is suitable, it is returned as `out`.
        error : bool, default=True
            Whether to raise an error if `precision` is better (smaller) than
            `self.precision`. If `False` and such a precision is specified,
            easting and northing strings will be appended with zeros to satisfy
            `precision` and `out` will be nested within `self`, sharing its
            reference (lower-left, grid-southwest) corner. This is rarely what
            you want.
        validate : bool, default=False
            Whether to validate the `our`. The default is `False` because it's
            assumed that either `self` was validated or intentionally not
            validated, because its values are known to be valid.

        Returns
        -------
        out : typing.Self
            A version of `self` that satisfies `precision`.

        Examples
        --------
        >>> acc_box = LatLonPoint(0, 0).to_acc()
        >>> truncated_acc_box = acc_box.with_precision(10)
        >>> acc_box.string
        '23NFF-000-000'
        >>> truncated_acc_box.string
        '23NFF-00-00'
        """
        # Resolve final precision, optionally raising error if not
        # truncating.
        final_precision = self._resolve_precision(
            precision, targ_type=type(self), error=error
        )

        # Fetch from cache, if possible and allowed.
        if not copy:
            cached = self._get_cached_cousin(
                type(self),
                constraints=self.constraints,
                precision=final_precision,
                truncation_ok=False,  # Avoid infinite recursion.
            )
            if cached is not None:
                if validate:
                    cached.validate()
                return cached

        # Determine `*LgrsBox` easting and northing character count.
        match final_precision:
            case 1:
                lgrs_char_count = 5
            case 10:
                lgrs_char_count = 4
            case 100:
                lgrs_char_count = 3
            case 1_000:
                lgrs_char_count = 2
            case 25_000:
                lgrs_char_count = 0
            case _:
                self._raise_unexpected()

        # Create and return instance with new precision.
        self_lgrs_box = self.to_lgrs()
        init_kwargs = self_lgrs_box._init_kwargs.copy()
        if lgrs_char_count:
            easting = _as_str(self_lgrs_box.easting)
            northing = _as_str(self_lgrs_box.northing)
            init_kwargs["easting"] = f"{easting}00000"[:lgrs_char_count]
            init_kwargs["northing"] = f"{northing}00000"[:lgrs_char_count]
        else:
            init_kwargs["easting"] = None
            init_kwargs["northing"] = None
        # TODO: Consider how to handle the possibility that a truncated
        #  LPS-based coordinate now plots outside the `prefer_lps=False`
        #  zone. Simplest solution would be to assign `prefer_lps=True`
        #  for any LPS-based coordinate upon truncation, but that might
        #  not be what the user expects.
        new_lgrs_box = type(self_lgrs_box)(**init_kwargs, validate=validate)
        if not copy:
            self._register_cousin(new_lgrs_box)
        if isinstance(self, (LpsAccBox, LtmAccBox)):
            new_acc_box = new_lgrs_box.to(type(self), validate=validate)
            return new_acc_box
        else:
            return new_lgrs_box


class _BaseAccBox(BoxCoordinate):
    _condensed_prefix_template: str
    _extra_field_names = (
        "precision",
        "string",
        "condensed",
        "condensed_prefix",
    )

    easting_1k: str | None = None

    @_functools.cached_property
    def _easting_int(self) -> int:
        return self._as_int(self.easting, nom_length=3)

    @_functools.cached_property
    def _northing_int(self) -> int:
        return self._as_int(self.northing, nom_length=3)

    @_functools.cached_property
    def condensed(self) -> str:
        """The condensed string form of the coordinate."""
        return self.string.removeprefix(self.condensed_prefix)

    @_functools.cached_property
    def condensed_prefix(self) -> str:
        """The prefix removed from `.string` to generate `.condensed`."""
        prefix = self._condensed_prefix_template.format(**self._init_kwargs)
        return prefix

    @_functools.cached_property
    def precision(self) -> int:
        """
        The precision of the coordinate, in meters.

        Strictly, this precision is expressed in grid meters and therefore
        inherits the distortion of the underlying CRS.
        """
        # Table 18
        if self.easting_1k is None:
            return 25_000
        elif self.easting is None:
            return 1000
        match len(self.easting):
            case 3:
                return 1
            case 2:
                return 10
            case 1:
                return 100
            case _:
                self._raise_unexpected()


class _BaseLgrsBox(BoxCoordinate):
    _extra_field_names = ("precision", "string")

    @_functools.cached_property
    def _easting_int(self) -> int:
        return self._as_int(self.easting, nom_length=5)

    @_functools.cached_property
    def _northing_int(self) -> int:
        return self._as_int(self.northing, nom_length=5)

    @_functools.cached_property
    def precision(self) -> int:
        """
        The precision of the coordinate, in meters.

        Strictly, this precision is expressed in grid meters and therefore
        inherits the distortion of the underlying CRS.
        """
        # Table 11
        if self.easting is None:
            return 25_000
        match len(self.easting):
            case 5:
                return 1
            case 4:
                return 10
            case 3:
                return 100
            case 2:
                return 1000
            case _:
                self._raise_unexpected()


# endregion
###############################################################################
# region> BOX COORDINATE TYPES
###############################################################################
# TODO: Think about what best field names are, e.g., `easting_area`,
#  `easting_25k`, `easting_25km`, `easting_25k_area`, or
#  `easting_25km_area`.
@_dataclasses.dataclass(frozen=True, repr=False)
class LpsAccBox(_BaseAccBox):
    """
    Create an instance representing an LPS Artemis Condensed Coordinate box.

    Note that each instance represents a square area in LPS space, referenced
    to its lower-left (grid-southwest) corner.

    Except for `easting` and `northing`, each string argument is a single
    character.

    Parameters
    ----------
    longitudinal_band : {"A", "B", "Y", "Z"}
        The polar zone band, which subdivides each polar zone into an east and
        west area.
    easting_area : str
        The point's 25-kilometer-grid easting area designator.
    northing_area : str
        The point's 25-kilometer-grid northing area designator.
    easting_1k : str, optional
        The point's 1-kilometer-grid easting area designator.
    easting : str, optional
        The point's easting (meters).
    northing_1k : str, optional
        The point's 1-kilometer-grid northing area designator.
    northing : str, optional
        The point's northing (meters).
    constraints : Constraints, default=Constraints()
        See `LatLonPoint` documentation.
    validate : bool, default=True
        See `LatLonPoint` documentation.

    Raises
    ------
    lgrs.Exceptions.MalformedCoordinate
        If the instance is invalid. Both values and constraints are
        considered.

    Examples
    --------
    >>> box_1 = LpsAccBox(
    ...     longitudinal_band='B', easting_area='A', northing_area='N',
    ...     easting_1k='-', easting='000', northing_1k='-', northing='000'
    ... )

    You may find it simpler to instantiate from a string.

    >>> box_2 = LpsAccBox.from_string("BAN-000-000")
    >>> box_1 == box_2
    True
    """

    _condensed_prefix_template = (
        "{longitudinal_band}{easting_area}{northing_area}"
    )

    # * FIELDS AND VALIDATION. ────────────────────────────────────────
    _pattern = _compile_regex_without_i_and_o(
        "^"
        "(?P<longitudinal_band>[ABYZ])"
        "(?P<easting_area>[A-Z])"
        "(?P<northing_area>[-A-Z+])"
        "((?P<easting_1k>[-A-Z])"
        "(?P<easting>[0-9]{1,3})?"
        "(?P<northing_1k>[-A-Z])"
        "(?P<northing>[0-9]{1,3})?)?"
        "$"
    )
    longitudinal_band: str
    easting_area: str
    northing_area: str
    easting_1k: str | None = None
    easting: str | None = None
    northing_1k: str | None = None
    northing: str | None = None

    def _validate_easting_area(self) -> None:
        match self.longitudinal_band:
            case "A" | "Y":
                minimum = "M"
                maximum = "Z"
            case "B" | "Z":
                minimum = "A"
                maximum = "N"
            case _:
                self._raise_unexpected()
        self._validate_against_closed_interval(
            attr_name="easting_area",
            minimum=minimum,
            maximum=maximum,
            if_attr_name="longitudinal_band",
        )

    def _validate_easting(self) -> None:
        if (self.easting is None) != (self.northing is None):
            raise _exceptions.MalformedCoordinate(
                "`easting` and `northing` must both be specified "
                "or both be `None`."
            )

    # * COORDINATE TRANSFORMATION. ────────────────────────────────────
    # Tables 13, 14
    _easting_area_chars = _extract_chars_from_pattern(_pattern, "easting_area")
    # Tables 15, 16
    _northing_area_chars = _extract_chars_from_pattern(
        _pattern, "northing_area"
    )
    # Table 17
    _easting_1k_chars = _extract_chars_from_pattern(_pattern, "easting_1k")
    _northing_1k_chars = _easting_1k_chars

    @_cache_new_cousin
    def _to_lgrs(
        self,
        *,
        constraints: Constraints | None = None,
        precision: int,
        validate: bool | None,
    ) -> LpsLgrsBox | LtmLgrsBox:
        if precision < self.precision:
            # Note: Raise error.
            self.with_precision(precision)
        if self.easting_1k is None:
            easting = None
            northing = None
        else:
            # Eqs. 91, 121, 122
            easting = f"{self._easting_1k_chars.index(self.easting_1k):02}"
            northing = f"{self._northing_1k_chars.index(self.northing_1k):02}"
            if self.easting is not None:
                easting += self.easting  # Eq. 123
                northing += self.northing  # Eq. 124
        init_kwargs = {
            "longitudinal_band": self.longitudinal_band,
            "easting_area": self.easting_area,
            "northing_area": self.northing_area,
            "easting": easting,
            "northing": northing,
        }
        if isinstance(self, LpsAccBox):
            lgrs_type = LpsLgrsBox
        else:
            lgrs_type = LtmLgrsBox
            init_kwargs["latitudinal_band"] = self.latitudinal_band
        lgrs = lgrs_type(
            **init_kwargs, constraints=self.constraints, validate=False
        )
        return lgrs.with_precision(precision)


@_dataclasses.dataclass(frozen=True, repr=False)
class LpsLgrsBox(_BaseLgrsBox):
    """
    Create an instance representing an LPS Lunar Grid Reference System box.

    Note that each instance represents a square area in LPS space, referenced
    to its lower-left (grid-southwest) corner.

    Except for `easting` and `northing`, each string argument is a single
    character.

    Parameters
    ----------
    longitudinal_band : {"A", "B", "Y", "Z"}
        The polar zone band, which subdivides each polar zone into an east and
        west area.
    easting_area : str
        The point's 25-kilometer-grid easting area designator.
    northing_area : str
        The point's 25-kilometer-grid northing area designator.
    easting : str, optional
        The point's easting (meters).
    northing : str, optional
        The point's northing (meters).
    constraints : Constraints, default=Constraints()
        See `LatLonPoint` documentation.
    validate : bool, default=True
        See `LatLonPoint` documentation.

    Raises
    ------
    lgrs.Exceptions.MalformedCoordinate
        If the instance is invalid. Both values and constraints are
        considered.

    Examples
    --------
    >>> box_1 = LpsLgrsBox(
    ...     longitudinal_band='Z', easting_area='A', northing_area='B',
    ...     easting='12345', northing='12345'
    ... )

    You may find it simpler to instantiate from a string.

    >>> box_2 = LpsLgrsBox.from_string("ZAB1234512345")
    >>> box_1 == box_2
    True
    """

    # * FIELDS AND VALIDATION. ────────────────────────────────────────
    _pattern = _compile_regex_without_i_and_o(
        "^"
        "(?P<longitudinal_band>[ABYZ])"
        "(?P<easting_area>[A-Z])"
        "(?P<northing_area>[-A-Z+])"
        f"({_make_en_pattern(5, 4, 3, 2)})?"
        "$"
    )
    longitudinal_band: str
    easting_area: str
    northing_area: str
    easting: str | None = None
    northing: str | None = None

    _validate_easting_area = LpsAccBox._validate_easting_area

    # * COORDINATE TRANSFORMATION. ────────────────────────────────────
    _easting_area_chars = LpsAccBox._easting_area_chars
    _northing_area_chars = LpsAccBox._northing_area_chars

    @_cache_new_cousin
    def _to_acc(
        self,
        *,
        constraints: Constraints | None = None,
        precision: int,
        validate: bool | None,
    ) -> LpsAccBox | LtmAccBox:
        if precision < self.precision:
            # Note: Raise error.
            self.with_precision(precision)
        init_kwargs = {
            "longitudinal_band": self.longitudinal_band,
            "easting_area": self.easting_area,
            "northing_area": self.northing_area,
        }
        if self.easting is not None:
            init_kwargs["easting_1k"] = LpsAccBox._easting_1k_chars[
                int(self.easting[:2])
            ]
            init_kwargs["northing_1k"] = LpsAccBox._northing_1k_chars[
                int(self.northing[:2])
            ]
            if len(self.easting) > 2:
                init_kwargs["easting"] = self.easting[2:]
                init_kwargs["northing"] = self.northing[2:]
        if isinstance(self, LpsLgrsBox):
            acc_type = LpsAccBox
        else:
            acc_type = LtmAccBox
            init_kwargs["latitudinal_band"] = self.latitudinal_band
        acc = acc_type(
            **init_kwargs, constraints=self.constraints, validate=False
        )
        return acc.with_precision(precision)

    @_cache_new_cousin
    def _to_lps_or_ltm(
        self,
        *,
        constraints: Constraints | None = None,
        validate: bool | None,
    ) -> LpsPoint:
        # Determine hemisphere and whether in the western half.
        # p. 92 (parags. 1, 3)
        match self.longitudinal_band:
            case "A":
                hemi = "S"
                is_in_west_half = True
            case "B":
                hemi = "S"
                is_in_west_half = False
            case "Y":
                hemi = "N"
                is_in_west_half = True
            case "Z":
                hemi = "N"
                is_in_west_half = False
            case _:
                self._raise_unexpected()

        # Calculate easting and northing.
        # Tables 13 + 14
        ea_idx = self._easting_area_chars.index(self.easting_area)
        if is_in_west_half:
            # Note: `self._easting_area_chars` is 0-indexed but Table 7
            # is 1-indexed, so "+ 1" in Eq. 112 is dropped here.
            ea_val = -25_000 * (24 - ea_idx)  # Eq. 112
        else:
            # TODO: Let Mark know.
            # Note: Although `self._easting_area_chars` is 0-indexed and
            # Table 7 is 1-indexed, Eq. 113 is exactly reproduced here.
            ea_val = 25_000 * ea_idx  # Eq. 113
        # Eq. 115
        easting = ea_val + self._easting_int + _wkt.LPS_FALSE_EASTING
        # Tables 15, 16
        na_idx = self._northing_area_chars.index(self.northing_area)
        na_val = 25_000 * (na_idx - 13)  # Eq. 114
        # Eq. 116
        northing = na_val + self._northing_int + _wkt.LPS_FALSE_NORTHING

        # Create and return instance.
        lps = LpsPoint(
            hemisphere=hemi,
            easting=easting,
            northing=northing,
            constraints=self.constraints,
            validate=False,
        )
        return lps


@_dataclasses.dataclass(frozen=True, repr=False)
class LtmAccBox(_BaseAccBox):
    """
    Create an instance representing an LTM Artemis Condensed Coordinate box.

    Note that each instance represents a square area in LTM space, referenced
    to its lower-left (grid-southwest) corner.

    Except for `easting` and `northing`, each string argument is a single
    character.

    Parameters
    ----------
    longitudinal_band : int
        The LTM zone number, between 1 and 45 (inclusive).
    latitudinal_band : str
        The latitudinal band.
    easting_area : str
        The point's 25-kilometer-grid easting area designator.
    northing_area : str
        The point's 25-kilometer-grid northing area designator.
    easting_1k : str, optional
        The point's 1-kilometer-grid easting area designator.
    easting : str, optional
        The point's easting (meters).
    northing_1k : str, optional
        The point's 1-kilometer-grid northing area designator.
    northing : str, optional
        The point's northing (meters).
    constraints : Constraints, default=Constraints()
        See `LatLonPoint` documentation.
    validate : bool, default=True
        See `LatLonPoint` documentation.

    Raises
    ------
    lgrs.Exceptions.MalformedCoordinate
        If the instance is invalid. Both values and constraints are
        considered.

    Examples
    --------
    >>> box_1 = LtmAccBox(
    ...     longitudinal_band=23, latitudinal_band='N',
    ...     easting_area='F', northing_area='F',
    ...     easting_1k='-', easting='000', northing_1k='-', northing='000'
    ... )

    You may find it simpler to instantiate from a string.

    >>> box_2 = LtmAccBox.from_string("23NFF-000-000")
    >>> box_1 == box_2
    True
    """

    _condensed_prefix_template = (
        "{longitudinal_band}{latitudinal_band}{easting_area}{northing_area}"
    )

    # * FIELDS AND VALIDATION. ────────────────────────────────────────
    _pattern = _compile_regex_without_i_and_o(
        "^"
        "(?P<longitudinal_band>[0-9]{1,2})"
        "(?P<latitudinal_band>[C-X])"
        "(?P<easting_area>[A-K])"
        "(?P<northing_area>[A-V])"
        "((?P<easting_1k>[-A-Z])"
        "(?P<easting>[0-9]{1,3})?"
        "(?P<northing_1k>[-A-Z])"
        "(?P<northing>[0-9]{1,3})?)?"
        "$"
    )
    longitudinal_band: int  # LTM zone
    latitudinal_band: str
    easting_area: str
    northing_area: str
    easting_1k: str | None = None
    easting: str | None = None
    northing_1k: str | None = None
    northing: str | None = None

    def _validate_longitudinal_band(self) -> None:
        return self._validate_against_closed_interval(
            attr_name="longitudinal_band", minimum=1, maximum=45
        )

    def _validate_northing_area(self) -> None:
        na_letterset = _calc_na_letterset(self.longitudinal_band)  # Eq. 83
        na_chars = LtmLgrsBox._northing_area__letterset_to_chars[na_letterset]
        self._validate_against_sequence(
            attr_name="easting_area",
            sequence=na_chars,
            if_attr_name="longitudinal_band",
        )

    @property
    def zone_number(self) -> int:
        return self.longitudinal_band

    # * Coordinate transformation. ────────────────────────────────────
    # Table 6
    _latitudinal_band_chars = _extract_chars_from_pattern(
        _pattern, "latitudinal_band", pre="C", post="X"
    )
    # Table 7
    _easting_area_chars = _extract_chars_from_pattern(_pattern, "easting_area")
    # Tables 8-10
    _northing_area__letterset_to_chars = [
        "ABCDEFGHJKLMNPQRSTUV",
        "FGHJKLMNPQRSTUVABCDE",
        "LMNPQRSTUVABCDEFGHJK",
    ]
    _easting_1k_chars = LpsAccBox._easting_1k_chars
    _northing_1k_chars = LpsAccBox._northing_1k_chars

    _to_lgrs = LpsAccBox._to_lgrs


@_dataclasses.dataclass(frozen=True, repr=False)
class LtmLgrsBox(_BaseLgrsBox):
    """
    Create an instance representing an LTM Lunar Grid Reference System box.

    Note that each instance represents a square area in LTM space, referenced
    to its lower-left (grid-southwest) corner.

    Except for `easting` and `northing`, each string argument is a single
    character.

    Parameters
    ----------
    longitudinal_band : int
        The LTM zone number, between 1 and 45 (inclusive).
    latitudinal_band : str
        The latitudinal band.
    easting_area : str
        The point's 25-kilometer-grid easting area designator.
    northing_area : str
        The point's 25-kilometer-grid northing area designator.
    easting : str, optional
        The point's easting (meters).
    northing : str, optional
        The point's northing (meters).
    constraints : Constraints, default=Constraints()
        See `LatLonPoint` documentation.
    validate : bool, default=True
        See `LatLonPoint` documentation.

    Raises
    ------
    lgrs.Exceptions.MalformedCoordinate
        If the instance is invalid. Both values and constraints are
        considered.

    Examples
    --------
    >>> box_1 = LtmLgrsBox(
    ...     longitudinal_band=42, latitudinal_band='S',
    ...     easting_area='A', northing_area='M',
    ...     easting='24689', northing='10101'
    ... )

    You may find it simpler to instantiate from a string.

    >>> box_2 = LtmLgrsBox.from_string("42SAM2468910101")
    >>> box_1 == box_2
    True
    """

    # * Fields and validation. ────────────────────────────────────────
    _pattern = _compile_regex_without_i_and_o(
        "^"
        "(?P<longitudinal_band>[0-9]{1,2})"
        "(?P<latitudinal_band>[C-X])"
        "(?P<easting_area>[A-K])"
        "(?P<northing_area>[A-V])"
        f"({_make_en_pattern(5, 4, 3, 2)})?"
        "$"
    )
    longitudinal_band: int  # LTM zone
    latitudinal_band: str
    easting_area: str
    northing_area: str
    easting: str | None = None
    northing: str | None = None

    _validate_longitudinal_band = LtmAccBox._validate_longitudinal_band
    _validate_northing_area = LtmAccBox._validate_northing_area

    zone_number = LtmAccBox.zone_number

    # * Coordinate transformation. ────────────────────────────────────
    _latitudinal_band_chars = LtmAccBox._latitudinal_band_chars
    _easting_area_chars = LtmAccBox._easting_area_chars
    _northing_area__letterset_to_chars = (
        LtmAccBox._northing_area__letterset_to_chars
    )

    _latitudinal_band_n_idx = _latitudinal_band_chars.index("N")

    @staticmethod
    @_functools.lru_cache(maxsize=5)  # `maxsize` is small but arbitrary.
    def _calc_n_band(lat_band_min: int) -> int:
        # Note: Longitude is arbitrary.
        temp_latlon = LatLonPoint(
            latitude=lat_band_min, longitude=0, validate=False
        )
        nband_float = temp_latlon.to_ltm(search=True).northing
        nband = _floor(nband_float // 25_000) * 25_000  # Eq. 96
        return nband

    _to_acc = LpsLgrsBox._to_acc

    @_cache_new_cousin
    def _to_lps_or_ltm(
        self,
        *,
        constraints: Constraints | None = None,
        validate: bool | None,
    ) -> LtmPoint:
        # Determine hemisphere.
        # Eq. 92 (also Fig. 15)
        lat_band_idx = self._latitudinal_band_chars.index(
            self.latitudinal_band
        )
        if lat_band_idx >= self._latitudinal_band_n_idx:
            hemi = "N"
        else:
            hemi = "S"

        # Calculate easting and northing.
        ea_idx = self._easting_area_chars.index(self.easting_area)  # Table 7
        # TODO: Let Mark know.
        # Note: Although `self._easting_area_chars` is 0-indexed and
        # Table 7 is 1-indexed, Eq. 93 is exactly reproduced here.
        # TODO: Based on ref code (lines 1728-9), the parentheses are
        #  assumed to be around the first two values, unlike the order
        #  of operations in Eq. 93. Now confirmed. Let Mark know.
        ea_val = (5 + ea_idx) * 25_000  # Eq. 93
        easting = ea_val + self._easting_int  # Eq. 98
        na_letterset = _calc_na_letterset(self.longitudinal_band)  # Eq. 83
        # Tables 8-10
        na_idx = self._northing_area__letterset_to_chars[na_letterset].index(
            self.northing_area
        )
        na_val_rel = na_idx * 25_000  # Eq. 94
        # Table 6
        # TODO: Same comment as above about parentheses.
        # Eq. 95
        lat_band_min = (
            self._latitudinal_band_chars.index(self.latitudinal_band) - 11
        ) * 8
        nband = self._calc_n_band(lat_band_min)  # Eq. 96, etc.
        # Eqs. 97, 99
        na_val = 0  # Initialize.
        while True:
            northing = na_val + na_val_rel + self._northing_int
            if northing >= nband:
                break
            na_val += 500_000

        # Create and return instance.
        ltm = LtmPoint(
            zone_number=self.longitudinal_band,
            hemisphere=hemi,
            easting=easting,
            northing=northing,
            validate=False,
        )
        return ltm


# endregion
