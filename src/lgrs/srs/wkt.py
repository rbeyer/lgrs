"""
Support for formatting lunar CRS WKTs.

Specifically, this module supports the Lunar Polar Stereographic (LPS)
and Lunar Transverse Mercator (LTM) projections described by:
    McClernan, M.T., Dennis, M.L., Theriot, I.H., Hare, T.M., Archinal,
        B.A., Ostrach, L.R., Hunter, M.A., Miller, M.J., Beyer, R.A.,
        Annex, A.M., and Lawrence, S.J., 2025, Lunar grid systems,
        coordinate systems, and map projections for the Artemis missions
        and lunar surface navigation: U.S. Geological Survey Techniques
        and Methods, book 11, chap. E1, 308 p.,
        https://doi.org/10.3133/tm11E1

For brevity, this paper is referred to as "M2025" hereinafter.
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
# Standard.
import abc as _abc
import dataclasses as _dataclasses
import functools as _functools
import itertools as _itertools
import re as _re
import typing as _typing

# Internal.
import lgrs.caching as _caching

# endregion
###############################################################################
# region> CONFIGURATION
###############################################################################
# Note: If any of these variables are modified from their M2025 values,
# additional changes to the code will likely be necessary.
# Note: See Tables 4 and 5 of M2025 for most of these variables.
# Note: Integer values should be represented as integers, for
# conventional formatting in WKTs.

# * GENERAL VALUES. ───────────────────────────────────────────────────
# Datum.
DATUM_NAME = "IAU_2015:30100"
DATUM_WKT_ID = 'ID["IAU",30100,2015]'

# Shape parameters.
LUNAR_RADIUS: float = 1_737_400  # `a` in M2025 (meters)

# Other.
REMARK = "Source of projection parameters: https://doi.org/10.3133/tm11E1"

# * LTM VALUES. ───────────────────────────────────────────────────────
# Boundaries.
LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE: float = 82  # (degrees)
LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE: float = 80  # (degrees)

# False easting and northing.
LTM_FALSE_EASTING: float = 250_000  # `F_E` in M2025 (meters)
LTM_N_FALSE_NORTHING: float = 0  # `F_N` in M2025 (meters)
LTM_S_FALSE_NORTHING: float = 2_500_000  # `F_N` in M2025 (meters)

# Other parameters.
LTM_CENTRAL_SCALE_FACTOR: float = 0.999  # `k_0` in M2025 (exact, unitless)
LTM_LATITUDE_OF_PROJECTION_AXIS: float = 0  # `phi_0` in M2025 (degrees)
LTM_ZONE_HALF_WIDTH: float = 4  # `W` in M2025 (degrees)

# * LPS VALUES. ───────────────────────────────────────────────────────
# Projection IDs.
LPS_N_ID = 7190092
LPS_S_ID = 7190091

# False easting and northing.
LPS_FALSE_EASTING: float = 500_000  # `F_E` in M2025 (meters)
LPS_FALSE_NORTHING: float = 500_000  # `F_N` in M2025 (meters)

# Other parameters.
LPS_CENTRAL_SCALE_FACTOR: float = 0.994  # `k_0` in M2025 (exact, unitless)
LPS_N_LATITUDE_OF_PROJECTION_ORIGIN: float = +90  # `phi_0` in M2025 (degrees)
LPS_S_LATITUDE_OF_PROJECTION_ORIGIN: float = -90  # `phi_0` in M2025 (degrees)
LPS_LONGITUDE_OF_PROJECTION_ORIGIN: float = 0  # `lambda_0` in M2025 (degrees)


# endregion
###############################################################################
# region> TEMPLATES
###############################################################################
# Below: Format inspired by p. 36 of M2025 but refined based on the WKT
# standard and common practice. The placeholder `ID["USGS",...]` is also
# removed.
# Note: Keep `_lps_regex` updated in tandem with `CONVERSION`.
_lps_regex = _re.compile("Lunar Polar Stereographic (.)")
_format_lps_wkt = f"""
PROJCRS["Moon (2015) - Sphere / Ocentric / {{prefix}}LPS {{north_or_south}}{{suffix}}",
  BASEGEOGCRS["Moon (2015) - Sphere / Ocentric",
    DATUM["Moon (2015) - Sphere",
      ELLIPSOID["Moon (2015) - Sphere",{LUNAR_RADIUS},0,
        LENGTHUNIT["metre",1]]],
    PRIMEM["Reference Meridian",0,
      ANGLEUNIT["degree",0.0174532925199433]],
    {DATUM_WKT_ID}],
  CONVERSION["{{prefix}}Lunar Polar Stereographic {{north_or_south}}{{suffix}}",
    METHOD["Polar Stereographic (variant A)",
      ID["EPSG",9810]],
    PARAMETER["Latitude of natural origin",{{lat_origin}},
      ANGLEUNIT["degree",0.0174532925199433],
      ID["EPSG",8801]],
    PARAMETER["Longitude of natural origin",{LPS_LONGITUDE_OF_PROJECTION_ORIGIN},
      ANGLEUNIT["degree",0.0174532925199433],
      ID["EPSG",8802]],
    PARAMETER["Scale factor at natural origin",{LPS_CENTRAL_SCALE_FACTOR},
      SCALEUNIT["unity",1],
      ID["EPSG",8805]],
    PARAMETER["False easting",{LPS_FALSE_EASTING},
      LENGTHUNIT["metre",1],
      ID["EPSG",8806]],
    PARAMETER["False northing",{LPS_FALSE_NORTHING},
      LENGTHUNIT["metre",1],
      ID["EPSG",8807]]],
  CS[Cartesian,2],
    AXIS["easting (X)",{{other_north_or_south_lower}},
      MERIDIAN[90,
        ANGLEUNIT["degree",0.0174532925199433]],
      ORDER[1],
      LENGTHUNIT["metre",1]],
    AXIS["northing (Y)",{{other_north_or_south_lower}},
      MERIDIAN[0,
        ANGLEUNIT["degree",0.0174532925199433]],
      ORDER[2],
      LENGTHUNIT["metre",1]],
  USAGE[
    SCOPE["Navigation and mapping."],
    {{area_string}},
    {{bbox_string}}],
  REMARK["{REMARK}"]]
""".strip().format  # noqa: E501

# Below: Format inspired by p. 23 of M2025 but refined based on the WKT
# standard and common practice. The placeholder `ID["USGS",...]` is also
# # removed.
# Note: Keep `_ltm_regex` updated in tandem with `CONVERSION`.
_ltm_regex = _re.compile("Lunar Transverse Mercator Zone ([0-9]+.)")
_format_ltm_wkt = f"""
PROJCRS["Moon (2015) - Sphere / Ocentric / {{prefix}}LTM {{zone_number}}{{hemisphere}}{{suffix}}",
  BASEGEOGCRS["Moon (2015) - Sphere / Ocentric",
    DATUM["Moon (2015) - Sphere",
      ELLIPSOID["Moon (2015) - Sphere",{LUNAR_RADIUS},0,
        LENGTHUNIT["metre",1]]],
    PRIMEM["Reference Meridian",0,
      ANGLEUNIT["degree",0.0174532925199433]],
    {DATUM_WKT_ID}],
  CONVERSION["{{prefix}}Lunar Transverse Mercator Zone {{zone_number}}{{hemisphere}}{{suffix}}",
    METHOD["Transverse Mercator",
      ID["EPSG",9807]],
    PARAMETER["Latitude of natural origin",{LTM_LATITUDE_OF_PROJECTION_AXIS},
      ANGLEUNIT["degree",0.0174532925199433],
      ID["EPSG",8801]],
    PARAMETER["Longitude of natural origin",{{center_longitude}},
      ANGLEUNIT["degree",0.0174532925199433],
      ID["EPSG",8802]],
    PARAMETER["Scale factor at natural origin",{LTM_CENTRAL_SCALE_FACTOR},
      SCALEUNIT["unity",1],
      ID["EPSG",8805]],
    PARAMETER["False easting",{LTM_FALSE_EASTING},
      LENGTHUNIT["metre",1],
      ID["EPSG",8806]],
    PARAMETER["False northing",{{false_northing}},
      LENGTHUNIT["metre",1],
      ID["EPSG",8807]]],
  CS[Cartesian,2],
    AXIS["(E)",east,
      ORDER[1],
      LENGTHUNIT["metre",1]],
    AXIS["(N)",north,
      ORDER[2],
      LENGTHUNIT["metre",1]],
  USAGE[
    SCOPE["Navigation and mapping."],
    {{area_string}},
    {{bbox_string}}],
  REMARK["{REMARK}"]]
""".strip().format  # noqa: E501


# endregion
###############################################################################
# region> UTILITIES
###############################################################################
def _validate_constraints(
    *,
    # Note: `prefer*` arguments are only used outside this module.
    prefer_lps: bool = False,
    prefer_ltm: bool = False,
    preferred_ltm_zone: int | None = None,
    extended_ltm: bool,
    global_lps: bool,
    global_ltm: bool,
    **ignore,
) -> int:
    all_kwargs = locals().copy()
    all_kwargs.update(ignore)
    del all_kwargs["ignore"]
    tot_enabled_count = sum(
        (v not in (False, None)) for v in all_kwargs.values()
    )
    for mutually_exclusive_arg_names in (
        ("prefer_lps", "prefer_ltm"),
        ("extended_ltm", "global_lps", "global_ltm"),
        *_itertools.product(
            ("prefer_lps", "prefer_ltm", "preferred_ltm_zone"),
            ("global_lps", "global_ltm"),
        ),
    ):
        enabled_count = 0
        for arg_name in mutually_exclusive_arg_names:
            if locals()[arg_name] in (False, None):
                continue
            enabled_count += 1
            if enabled_count > 1:
                raise TypeError(
                    "At most one of the following constraints may be enabled: "
                    f"`{'`, `'.join(mutually_exclusive_arg_names)}`"
                )
    return tot_enabled_count


# endregion
###############################################################################
# region> ZONES
###############################################################################
@_dataclasses.dataclass(kw_only=True, frozen=True)
class BaseZone(metaclass=_caching._AbstractMetaMultiton):
    extended_ltm: bool = False
    global_lps: bool = False
    global_ltm: bool = False
    hemisphere: str
    datum_name: str = DATUM_NAME

    def __post_init__(self):
        _validate_constraints(**self.__dict__)

    # * UTILITIES. ────────────────────────────────────────────────────
    @_abc.abstractmethod
    def _get_area_string(self, **kwargs) -> str: ...

    def _get_bbox_string(self) -> str:
        return (
            f"BBOX[{self.minimum_latitude},{self.minimum_longitude},"
            f"{self.maximum_latitude},{self.maximum_longitude}]"
        )

    def _validate_datum_name(self) -> None:
        if self.datum_name != DATUM_NAME:
            raise TypeError(
                f"`datum_name` must be {DATUM_NAME!r}, not: "
                f"{self.datum_name!r}"
            )

    def _validate_hemisphere(self) -> None:
        if self.hemisphere not in ("N", "S"):
            raise TypeError(
                "`hemisphere` must be either 'N' or 'S', not: "
                f"{self.hemisphere!r}"
            )

    # * ATTRIBUTES. ───────────────────────────────────────────────────
    @_functools.cached_property
    def absolute_ltm_limit(self) -> float:
        if self.global_lps:
            return 0
        elif self.global_ltm:
            return 90
        elif self.extended_ltm:
            return LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            return LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE

    @property
    @_abc.abstractmethod
    def maximum_latitude(self) -> float: ...

    @property
    @_abc.abstractmethod
    def maximum_longitude(self) -> float: ...

    @property
    @_abc.abstractmethod
    def minimum_latitude(self) -> float: ...

    @property
    @_abc.abstractmethod
    def minimum_longitude(self) -> float: ...

    @property
    @_abc.abstractmethod
    def name(self) -> str: ...

    @property
    @_abc.abstractmethod
    def wkt(self) -> str: ...


@_dataclasses.dataclass(kw_only=True, frozen=True)
class LpsZone(BaseZone):
    number: None = None  # Ignored, but included to parallel `LtmZone`.

    # * INITIALIZATION. ───────────────────────────────────────────────
    def __post_init__(self) -> None:
        self._validate_datum_name()
        self._validate_hemisphere()

    # * UTILITIES. ────────────────────────────────────────────────────
    def _get_area_string(
        self, lat_sign: str, north_or_south: str, **ignore
    ) -> str:
        polar_region = "polar region"
        if self.absolute_ltm_limit == LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE:
            end = "."
        elif self.absolute_ltm_limit == LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE:
            end = (
                ", though valid from "
                f"{lat_sign}{LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE}° latitude "
                "in the primary range."
            )
        elif self.absolute_ltm_limit == 0:
            end = (
                ", including the non-standard range equatorward of "
                f"{lat_sign}{LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE}° latitude."
            )
            lat_sign = ""  # *REASSIGNMENT*
            polar_region = "hemisphere"  # *REASSIGNMENT*
        else:
            raise TypeError(
                "`.absolute_ltm_limit` is not supported: "
                f"{self.absolute_ltm_limit!r}"
            )
        return (
            f'AREA["'
            f"{north_or_south}ern {polar_region} of the Moon - "
            f"{north_or_south.lower()} of "
            f"{lat_sign}{self.absolute_ltm_limit}° latitude{end}"
            f'"]'
        )

    # * ATTRIBUTES. ───────────────────────────────────────────────────
    maximum_longitude: _typing.ClassVar = 180
    minimum_longitude: _typing.ClassVar = -180

    @_functools.cached_property
    def maximum_latitude(self) -> float:
        if self.hemisphere == "N":
            return 90
        else:
            return -self.absolute_ltm_limit

    @_functools.cached_property
    def minimum_latitude(self) -> float:
        if self.hemisphere == "S":
            return -90
        else:
            return self.absolute_ltm_limit

    @_functools.cached_property
    def name(self) -> str:
        # Note: Format is loosely inspired by PROJ, e.g.,
        # "NAD83 / UTM zone 15N", though PROJ supports no UPS
        # equivalent.
        return f"{DATUM_NAME} / LPS {self.hemisphere}"

    @_functools.cached_property
    def wkt(self) -> str:
        hemisphere = self.hemisphere
        if hemisphere == "S":
            lat_sign = "-"
            north_or_south = "South"
            other_north_or_south = "North"
            lat_origin = LPS_S_LATITUDE_OF_PROJECTION_ORIGIN
            id_num = LPS_S_ID
        else:
            lat_sign = "+"
            north_or_south = "North"
            other_north_or_south = "South"
            lat_origin = LPS_N_LATITUDE_OF_PROJECTION_ORIGIN
            id_num = LPS_N_ID
        other_north_or_south_lower = other_north_or_south.lower()
        area_string = self._get_area_string(
            lat_sign=lat_sign, north_or_south=north_or_south
        )
        bbox_string = self._get_bbox_string()
        prefix = ""
        if self.global_lps:
            suffix = " (unrestricted)"
        elif self.extended_ltm:
            suffix = " (exclusive)"
        else:
            suffix = ""
        wkt = _format_lps_wkt(**locals())
        return wkt


@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmZone(BaseZone):
    number: int

    # * INITIALIZATION. ───────────────────────────────────────────────
    def __post_init__(self) -> None:
        self._validate_datum_name()
        self._validate_hemisphere()
        self._validate_number()

    # * UTILITIES. ────────────────────────────────────────────────────
    def _validate_number(self) -> None:
        if not (1 <= self.number <= 45):
            raise TypeError(
                f"`number` must be in the range [1, 45], not: {self.number!r}"
            )

    # * UTILITIES. ────────────────────────────────────────────────────
    def _get_area_string(
        self, lat_sign: str, north_or_south: str, **ignore
    ) -> str:
        if self.absolute_ltm_limit == LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE:
            end = (
                ", though valid to "
                f"{lat_sign}{LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE}° latitude "
                "in the extended range."
            )
        elif self.absolute_ltm_limit == LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE:
            end = (
                ", including the extended range poleward of "
                f"{lat_sign}{LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE}° latitude."
            )
        elif self.absolute_ltm_limit == 90:
            end = (
                ", including the non-standard range poleward of "
                f"{lat_sign}{LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE}° latitude."
            )
        else:
            raise TypeError(
                "`.absolute_ltm_limit` is not supported: "
                f"{self.absolute_ltm_limit!r}"
            )
        return (
            f'AREA["'
            f"Between {self.minimum_longitude:+}° and "
            f"{self.maximum_longitude:+}° longitude, "
            f"{north_or_south.lower()}ern hemisphere "
            "between the equator and "
            f"{lat_sign}{self.absolute_ltm_limit}° latitude{end}"
            f'"]'
        )

    # * ATTRIBUTES. ───────────────────────────────────────────────────
    @_functools.cached_property
    def center_longitude(self) -> float:
        ctr_lon = (
            (self.number - 1) * (2 * LTM_ZONE_HALF_WIDTH)
            - 180
            + LTM_ZONE_HALF_WIDTH
        )
        return ctr_lon

    @_functools.cached_property
    def false_northing(self) -> float:
        if self.hemisphere == "S":
            return LTM_S_FALSE_NORTHING
        else:
            return LTM_N_FALSE_NORTHING

    @_functools.cached_property
    def maximum_latitude(self) -> float:
        if self.hemisphere == "S":
            return 0
        else:
            return self.absolute_ltm_limit

    @_functools.cached_property
    def maximum_longitude(self) -> float:
        return self.center_longitude + LTM_ZONE_HALF_WIDTH

    @_functools.cached_property
    def minimum_latitude(self) -> float:
        if self.hemisphere == "N":
            return 0
        else:
            return -self.absolute_ltm_limit

    @_functools.cached_property
    def minimum_longitude(self) -> float:
        return self.center_longitude - LTM_ZONE_HALF_WIDTH

    @_functools.cached_property
    def name(self) -> str:
        # Note: Format is inspired by PROJ, e.g.,
        # "NAD83 / UTM zone 15N".
        return f"{DATUM_NAME} / LTM zone {self.number}{self.hemisphere}"

    @_functools.cached_property
    def wkt(self) -> str:
        zone_number = self.number
        hemisphere = self.hemisphere
        center_longitude = self.center_longitude
        false_northing = self.false_northing
        if hemisphere == "S":
            lat_sign = "-"
            north_or_south = "South"
        else:
            lat_sign = "+"
            north_or_south = "North"
        area_string = self._get_area_string(
            lat_sign=lat_sign, north_or_south=north_or_south
        )
        bbox_string = self._get_bbox_string()
        if self.global_ltm:
            prefix = ""
            suffix = " (unrestricted)"
        elif self.extended_ltm:
            prefix = "Extended "
            suffix = ""
        else:
            prefix = ""
            suffix = ""
        wkt = _format_ltm_wkt(**locals())
        return wkt


# endregion
