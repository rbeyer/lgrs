# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.
# TODO: Finalize reference. Current form is copied from "Suggested
#  citation" in M2025.
"""
This module handles formatting of lunar CRS WKTs.

Specifically, this module supports the Lunar Polar Stereographic (LPS)
and Lunar Transverse Mercator (LTM) projections described by:
    McClernan, M.T., Dennis, M.L., Theriot, I.H., Hare, T.M., Archinal,
        B.A., Ostrach, L.R., Hunter, M.A., Miller, M.J., Beyer, R.A.,
        Annex, A.M., and Lawrence, S.J., 2025, Lunar grid systems,
        coordinate systems, and map projections for the Artemis missions
        and lunar surface navigation: U.S. Geological Survey Techniques
        and Methods, book 11, chap. E1, 308 p.,
        https://doi.org/10.3133/tm11E1

For brevity, this paper is referred to as M2025 hereinafter.
"""

##############################################################################
# region> IMPORT
##############################################################################
# External.
import abc as _abc
import dataclasses as _dataclasses
import functools as _functools
import typing as _typing

# Internal.
import lgrs.caching as _caching



# endregion
##############################################################################
# region> CONFIGURATION
##############################################################################
# Note: See Table 4 of M2025 for most of these variables.
# Note: If any of these variables are modified from their M2025 values,
# additional changes to the code will likely be necessary.

# Datum.
DATUM_NAME = "IAU_2015:30100"
DATUM_WKT_ID = 'ID[“IAU”,30100,2015]'

# Boundaries.
LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE: float = 82.  # (degrees)
LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE: float = 80.  # (degrees)

# False northing and easting.
LTM_FALSE_EASTING: float = 250_000.  # `F_E` in M2025 (meters)
LTM_N_FALSE_NORTHING: float = 0.  # `F_N` in M2025 (meters)
LTM_S_FALSE_NORTHING: float = 2_500_000.  # `F_N` in M2025 (meters)

# Shape parameters.
LUNAR_RADIUS: float = 1_737_400.  # `a` in M2025 (meters)

# Other parameters.
LTM_CENTRAL_SCALE_FACTOR: float = 0.999  # `k_0` in M2025 (exact,  unitless)
LTM_LATITUDE_OF_PROJECTION_AXIS: float = 0.  # `phi_0` in M2025 (degrees)
LTM_ZONE_HALF_WIDTH: float = 4.  # `W` in M2025 (degrees)



# endregion
##############################################################################
# region> TEMPLATES
##############################################################################
# Below: Format taken from p. 36 of M2025. Only deviation from M2025 is
# the addition of USAGE, which parallels that for the LTM WKT in the
# current module.
_format_lps_wkt = f"""
PROJCRS[“Moon (2015) - Sphere / Ocentric / {{north_or_south}} Polar”,
  BASEGEOGCRS[“Moon (2015) - Sphere / Ocentric”,
    DATUM[“Moon (2015) - Sphere”,
      ELLIPSOID[“Moon (2015) - Sphere”,1737400,0,
        LENGTHUNIT[“metre”,1]]],
    PRIMEM[“Reference Meridian”,0,
      ANGLEUNIT[“degree”,0.0174532925199433]],
    {DATUM_WKT_ID}],
  CONVERSION[“{{north_or_south}} Polar”,
    METHOD[“Polar Stereographic (variant A)”,
      ID[“EPSG”,9810]],
    PARAMETER[“Latitude of natural origin”,{{origin}},
      ANGLEUNIT[“degree”,0.0174532925199433],
      ID[“EPSG”,8801]],
    PARAMETER[“Longitude of natural origin”,0,
      ANGLEUNIT[“degree”,0.0174532925199433],
      ID[“EPSG”,8802]],
    PARAMETER[“Scale factor at natural origin”,.994,
      SCALEUNIT[“unity”,1],
      ID[“EPSG”,8805]],
    PARAMETER[“False easting”,500000,
      LENGTHUNIT[“metre”,1],
      ID[“EPSG”,8806]],
    PARAMETER[“False northing”,500000,
      LENGTHUNIT[“metre”,1],
      ID[“EPSG”,8807]]],
  CS[Cartesian,2],
    AXIS[“(E)”,east,
      ORDER[1],
      LENGTHUNIT[“metre”,1]],
    AXIS[“(N)”,north,
      ORDER[2],
      LENGTHUNIT[“metre”,1]],
  USAGE[
    AREA["Lunar Polar Stereographic Zone LPS_{{hemisphere}}."],
    {{bbox_string}}],              
ID[“USGS”,{{id_num}},{{hemisphere}}]]]
""".strip().format

# Below: Format taken from p. 18 of M2025. Only deviations from M2025
# are that SCOPE is replaced with AREA, which seems better suited for
# the content, and PROJCRS name is extended to include zone number.
_format_ltm_wkt = f"""
PROJCRS["Moon (2015) - Sphere / Ocentric / Transverse Mercator / LTM zone {{zone_number}}{{hemisphere}}",
  BASEGEOGCRS["Moon (2015) - Sphere / Ocentric",
    DATUM["Moon (2015) - Sphere",
      ELLIPSOID["Moon (2015) - Sphere",{LUNAR_RADIUS},0,
        LENGTHUNIT["metre",1]]],
    PRIMEM["Reference Meridian",0,
      ANGLEUNIT["degree",0.0174532925199433]],
    {DATUM_WKT_ID}],
  CONVERSION["transverse Mercator",
    METHOD["transverse Mercator",
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
    PARAMETER["False easting",{{false_easting}},
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
    AREA["Lunar Transverse Mercator Zone LTM_{{zone_number}}{{hemisphere}}."],
    {{bbox_string}}]]
""".strip().format



# endregion
##############################################################################
# region> ZONES
##############################################################################
@_dataclasses.dataclass(kw_only=True, frozen=True)
class BaseZone(metaclass=_caching._AbstractMetaMultiton):
    extend_ltm: bool = False
    hemisphere: str
    datum_name: str = DATUM_NAME

    # * UTILITIES. ----------------------------------------------------
    def _get_bbox_string(self) -> str:
        return f"BBOX[{self.minimum_latitude},{self.minimum_longitude},{self.maximum_latitude},{self.maximum_longitude}]"

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

    # * ATTRIBUTES. ----------------------------------------------------
    @property
    @_abc.abstractmethod
    def maximum_latitude(self) -> float:
        ...

    @property
    @_abc.abstractmethod
    def maximum_longitude(self) -> float:
        ...

    @property
    @_abc.abstractmethod
    def minimum_latitude(self) -> float:
        ...

    @property
    @_abc.abstractmethod
    def minimum_longitude(self) -> float:
        ...

    @property
    @_abc.abstractmethod
    def name(self) -> str:
        ...

    @property
    @_abc.abstractmethod
    def wkt(self) -> str:
        ...

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LpsZone(BaseZone):
    number: None = None  # Ignored, but included to parallel `LtmZone`.

    # * INITIALIZATION. -----------------------------------------------
    def __post_init__(self) -> None:
        self._validate_datum_name()
        self._validate_hemisphere()

    #* ATTRIBUTES. ----------------------------------------------------
    maximum_longitude: _typing.ClassVar = 180.
    minimum_longitude: _typing.ClassVar = -180.

    @_functools.cached_property
    def maximum_latitude(self) -> float:
        if self.hemisphere == "N":
            return 90.
        elif self.extend_ltm:
            return -LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            return -LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE

    @_functools.cached_property
    def minimum_latitude(self) -> float:
        if self.hemisphere == "S":
            return -90.
        elif self.extend_ltm:
            return LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            return LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE

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
            north_or_south = "South"
            origin = -90
            id_num = 7190091
        else:
            north_or_south = "North"
            origin = 90
            id_num = 7190092
        bbox_string = self._get_bbox_string()
        wkt = _format_lps_wkt(**locals())
        return wkt

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmZone(BaseZone):
    number: int

    # * INITIALIZATION. -----------------------------------------------
    def __post_init__(self) -> None:
        self._validate_datum_name()
        self._validate_hemisphere()
        self._validate_number()

    # * UTILITIES. ----------------------------------------------------
    def _validate_number(self) -> None:
        if not (1 <= self.number <= 45):
            raise TypeError(
                f"`number` must be in the range [1, 45], not: {self.number!r}"
            )

    #* ATTRIBUTES. ----------------------------------------------------
    @_functools.cached_property
    def center_longitude(self) -> float:
        ctr_lon = ((self.number - 1)
                   * (2 * LTM_ZONE_HALF_WIDTH)
                   - 180
                   + LTM_ZONE_HALF_WIDTH)
        return ctr_lon

    @_functools.cached_property
    def false_easting(self) -> float:
        return LTM_FALSE_EASTING

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
        elif self.extend_ltm:
            return LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            return LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE

    @_functools.cached_property
    def maximum_longitude(self) -> float:
        return self.center_longitude + LTM_ZONE_HALF_WIDTH

    @_functools.cached_property
    def minimum_latitude(self) -> float:
        if self.hemisphere == "N":
            return 0
        elif self.extend_ltm:
            return -LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            return -LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE

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
        false_easting = self.false_easting
        false_northing = self.false_northing
        bbox_string = self._get_bbox_string()
        wkt = _format_ltm_wkt(**locals())
        return wkt



# endregion