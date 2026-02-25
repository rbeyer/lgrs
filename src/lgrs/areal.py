##############################################################################
# region> IMPORT
##############################################################################
# External.
from __future__ import annotations
import abc as _abc
import collections as _collections
import dataclasses as _dataclasses
import functools as _functools
import math as _math
from osgeo import osr as _osr
_osr.UseExceptions()
import re as _re
import textwrap as _textwrap
import typing as _typing

# Internal.
import lgrs.bases as _bases
import lgrs.coords as _coords

# endregion



##############################################################################
# region> CONFIGURATION
##############################################################################
#---- LTM --------------------------------------------------------------------
# Note: See Table 4 of M2025 for most of these variables.
# Note: If any of these variables are modified from their M2025 values,
# additional changes to the code will likely be necessary.

# Boundaries.
LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE: float = 82.  # (degrees)
LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE: float = 80.  # (degrees)

# False northing and easting.
LTM_FALSE_EASTING: float = 250_000.  # `F_E` in M2025 (meters)
LTM_N_FALSE_NORTHING: float = 0.  # `F_N` in M2025 (meters)
LTM_S_FALSE_NORTHING: float = 2_500_000.  # `F_N` in M2025 (meters)

# Shape parameters.
ELLIPSOIDAL_FLATTENING: float = 0.  # `f` in M2025 (unitless)
# Below: `e` in M2025 (unitless).
ECCENTRICITY: float = (ELLIPSOIDAL_FLATTENING
                       * (2 - ELLIPSOIDAL_FLATTENING))**0.5
LUNAR_RADIUS: float = 1_737_400.  # `a` in M2025 (meters)
# Below: `n` in M2025 (unitless).
THIRD_FLATTENING: float = ELLIPSOIDAL_FLATTENING / (2 - ELLIPSOIDAL_FLATTENING)

# Other parameters.
LTM_CENTRAL_SCALE_FACTOR: float = 0.999  # `k_0` in M2025 (exact,  unitless)
LTM_LATITUDE_OF_PROJECTION_AXIS: float = 0.  # `phi_0` in M2025 (degrees)
LTM_ZONE_HALF_WIDTH: float = 4.  # `W` in M2025 (degrees)

# endregion



##############################################################################
# region> UTILITIES
##############################################################################
_zone_name_pattern = _re.compile(
    "(?i)^(?P<zone_num>[0-9]+)?(?P<hemi>[N|S])$"
)

# endregion



##############################################################################
# region> ZONES
##############################################################################
@_dataclasses.dataclass(kw_only=True, frozen=True)
class BaseZone(_bases.AbstractBaseZone):
    number: int | None = None
    hemisphere: str = None
    extended_ltm: bool = False
    is_global: bool = False

    #* INSTANTIATION AND INITIALIZATION. ------------------------------
    def __post_init__(self) -> None:
        # Validate hemisphere.
        if self.hemisphere not in ("N", "S"):
            raise TypeError("`hemisphere` not recognized: "
                            f"{self.hemisphere!r}")

        # Optionally make global.
        if self.is_global:
            self._make_global()

    @classmethod
    def from_name(
            cls, name: str, *,
            extended_ltm: bool = False, is_global: bool = False
    ) -> LpsZone | LtmZone:
        # Parse (and validate) `name`.
        zone_name_match = _zone_name_pattern.search(name)
        if not zone_name_match:
            raise TypeError(f"`name` is not recognized: {name!r}")
        parsed_zone_num = zone_name_match.group("zone_num")
        if parsed_zone_num:
            new_cls = LtmZone
            zone_num = int(parsed_zone_num)
        else:
            new_cls = LpsZone
            zone_num = None
        hemi = zone_name_match.group("hemi")

        # Create and return instance.
        new = new_cls(number=zone_num, hemisphere=hemi,
                      extended_ltm=extended_ltm, is_global=is_global)
        return new

    @classmethod
    def from_coordinates(
            cls, coordinates: _bases.AbstractBaseCoordinates, *,
            extended_ltm: bool = False, is_global: bool = False
    ) -> LpsZone | LtmZone:
        if extended_ltm:
            ltm_max_abs_lat = LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            ltm_max_abs_lat = LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        # Note: Choice of `>` rather than `>=` is arbitrary.
        # TODO: Confirm this arbitrary choice. Alternatively, could add
        #  (ugly) `prefer_ltm` argument or use `cls` as a hint.
        use_lps = (abs(coordinates.latitude) > ltm_max_abs_lat)
        if use_lps:
            new_cls = LpsZone
            zone_num = None
        else:
            new_cls = LtmZone
            # Below: Eq. 13 of M2025. Zones are 1-indexed.
            zone_num = (
                    _math.floor((coordinates.longitude + 180)
                                / (2 * LTM_ZONE_HALF_WIDTH))
                    + 1
            )
        # Note: This inequality is from M2025 code.
        hemi = "N" if coordinates.latitude >= 0 else "S"
        new = new_cls(number=zone_num, hemisphere=hemi,
                      extended_ltm=extended_ltm, is_global=is_global)
        return new

    #* BASIC BEHAVIOR. ------------------------------------------------
    def __contains__(
            self,
            coordinates: _bases.AbstractBaseCoordinates
    ) -> bool:
        if self.minimum_latitude <= coordinates.latitude <= self.maximum_latitude:
            if self.minimum_longitude <= coordinates.longitude <= self.maximum_longitude:
                return True
        return False

    #* UTILITY. -------------------------------------------------------
    def _get_bbox_string(self) -> str:
        return f"BBOX[{self.minimum_latitude},{self.minimum_longitude},{self.maximum_latitude},{self.maximum_longitude}]"

    def _make_global(self) -> None:
        # Note: Instance is a frozen dataclass, so setting attributes
        # must be handled carefully.
        for attr_name, value in (("is_global", True),
                                 ("minimum_latitude", -90),
                                 ("maximum_latitude", 90),
                                 ("minimum_longitude", -180),
                                 ("maximum_longitude", 180)):
            object.__setattr__(self, attr_name, value)
        # Note: Discard cached spatial reference with bounding box, if any.
        self.__dict__.pop("spatial_reference", None)

    def _make_spatial_reference(self, wkt: str) -> _osr.SpatialReference:
        # Perform cursory validation.
        if ELLIPSOIDAL_FLATTENING:
            raise NotImplementedError("Non-spheres are not supported.")

        # Finalize wkt.
        cleaned_wkt = _textwrap.dedent(wkt.strip())
        # TODO: Decide whether removing BBOX attribute is necessary,
        #  since it is already set to global extent.
        if self.is_global:
            final_wkt, sub_count = _re.subn(r",?\s*BBOX\[.+?\]",
                                            "", cleaned_wkt)
            assert (sub_count == 1)
        else:
            final_wkt = cleaned_wkt

        # Create and return projection instance.
        sr = _osr.SpatialReference()
        if sr.ImportFromWkt(final_wkt):
            raise TypeError("WKT could not be parsed.")
        return sr

    #* PROJECTION. ----------------------------------------------------
    @_functools.cache
    def _make_osgeo_transformation(
            self, *, to_geographic: bool
    ) -> _osr.CoordinateTransformation:
        proj_sr = self.spatial_reference
        geo_sr = _osr.SpatialReference()
        geo_sr.CopyGeogCSFrom(proj_sr)
        if to_geographic:
            coord_transform = _osr.CoordinateTransformation(proj_sr,
                                                            geo_sr)
        else:
            coord_transform = _osr.CoordinateTransformation(geo_sr,
                                                            proj_sr)
        return coord_transform

    @_functools.cached_property
    def transform_coordinates_into(
            self,
    ) -> _collections.abc.Callable[[_bases.AbstractBaseCoordinates], _coords.LpsCoordinates | _coords.LtmCoordinates]:
        # Determine coordinates type.
        match self:
            case LpsZone():
                coords_type = _coords.LpsCoordinates
            case LtmZone():
                coords_type = _coords.LtmCoordinates
            case _:
                raise TypeError(f"Unrecognized type: {self!r}")

        # Create `osgeo` coordination transformer.
        coord_transform = self._make_osgeo_transformation(to_geographic=False)

        # Create and return static method.
        def transform_coordinates_into(
                coordinates: _bases.AbstractBaseCoordinates
        ) -> coords_type:
            easting, northing, elevation = coord_transform.TransformPoint(
                coordinates.latitude, coordinates.longitude
            )
            new = coords_type(easting=easting, northing=northing, zone=self)
            return new
        return transform_coordinates_into

    #* ATTRIBUTES. ----------------------------------------------------
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
    def spatial_reference(self) -> _osr.SpatialReference:
        ...

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LpsZone(BaseZone):
    number: None = None

    #* ATTRIBUTES. ----------------------------------------------------
    maximum_longitude: _typing.ClassVar = 180.
    minimum_longitude: _typing.ClassVar = -180.

    @_functools.cached_property
    def maximum_latitude(self) -> float:
        if self.hemisphere == "N":
            return 90.
        elif self.extended_ltm:
            return -LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            return -LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE

    @_functools.cached_property
    def minimum_latitude(self) -> float:
        if self.hemisphere == "S":
            return -90.
        elif self.extended_ltm:
            return LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            return LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE

    @_functools.cached_property
    def name(self) -> str:
        return self.hemisphere

    @_functools.cached_property
    def spatial_reference(self) -> _osr.SpatialReference:
        # TODO: Compare format below (taken from p. 36 of M2025) to
        #  `sr.ExportToPrettyWkt()` and identify any outdated or
        #  otherwise non-preferred formatting.
        # Below: Only deviation from M2025 is the addition of a USAGE
        # attribute, which parallels that for LTM WKT in M2025, except
        # that SCOPE is replaced with AREA.
        if self.hemisphere == "N":
            north_or_south = "North"
            origin = 90
            id_num = 7190092
        else:
            north_or_south = "South"
            origin = -90
            id_num = 7190091
        n_or_s = north_or_south[0]
        wkt = f"""
        PROJCRS[“Moon (2015) - Sphere / Ocentric / {north_or_south} Polar”,
          BASEGEOGCRS[“Moon (2015) - Sphere / Ocentric”,
            DATUM[“Moon (2015) - Sphere”,
              ELLIPSOID[“Moon (2015) - Sphere”,1737400,0,
                LENGTHUNIT[“metre”,1]]],
            PRIMEM[“Reference Meridian”,0,
              ANGLEUNIT[“degree”,0.0174532925199433]],
            ID[“IAU”,30100,2015]],
          CONVERSION[“{north_or_south} Polar”,
            METHOD[“Polar Stereographic (variant A)”,
              ID[“EPSG”,9810]],
            PARAMETER[“Latitude of natural origin”,{origin},
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
            AREA["Lunar Polar Stereographic Zone LPS_{self.hemisphere}."],
            {self._get_bbox_string()}],              
        ID[“USGS”,{id_num},{n_or_s}]]]
        """
        sr = self._make_spatial_reference(wkt)
        return sr

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmZone(BaseZone):
    number: int

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
        if self.hemisphere == "N":
            return LTM_N_FALSE_NORTHING
        else:
            return LTM_S_FALSE_NORTHING

    @_functools.cached_property
    def maximum_latitude(self) -> float:
        if self.hemisphere == "S":
            return 0
        elif self.extended_ltm:
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
        elif self.extended_ltm:
            return -LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            return -LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE

    @_functools.cached_property
    def minimum_longitude(self) -> float:
        return self.center_longitude - LTM_ZONE_HALF_WIDTH

    @_functools.cached_property
    def name(self) -> str:
        return f"{self.hemisphere}{self.number}"

    @_functools.cached_property
    def spatial_reference(self) -> _osr.SpatialReference:
        # Note: This method uses `osgeo.ogr` to execute Step 4 and later
        # from p. 18 of M2025.
        # TODO: Compare format below (taken from pp. 23-24 of M2025) to
        #  `sr.ExportToPrettyWkt()` and identify any outdated or
        #  otherwise non-preferred formatting.
        # Below: Only deviation from M2025 is that SCOPE is replaced
        # with AREA.
        wkt = f"""
        PROJCRS["Moon (2015) - Sphere / Ocentric / Transverse Mercator / LTM zone {self.number}{self.hemisphere}",
          BASEGEOGCRS["Moon (2015) - Sphere / Ocentric",
            DATUM["Moon (2015) - Sphere",
              ELLIPSOID["Moon (2015) - Sphere",{LUNAR_RADIUS},0,
                LENGTHUNIT["metre",1]]],
            PRIMEM["Reference Meridian",0,
              ANGLEUNIT["degree",0.0174532925199433]],
            ID["IAU",30100,2015]],
          CONVERSION["transverse Mercator",
            METHOD["transverse Mercator",
              ID["EPSG",9807]],
            PARAMETER["Latitude of natural origin",{LTM_LATITUDE_OF_PROJECTION_AXIS},
              ANGLEUNIT["degree",0.0174532925199433],
              ID["EPSG",8801]],
            PARAMETER["Longitude of natural origin",{self.center_longitude},
              ANGLEUNIT["degree",0.0174532925199433],
              ID["EPSG",8802]],
            PARAMETER["Scale factor at natural origin",{LTM_CENTRAL_SCALE_FACTOR},
              SCALEUNIT["unity",1],
              ID["EPSG",8805]],
            PARAMETER["False easting",{self.false_easting},
              LENGTHUNIT["metre",1],
              ID["EPSG",8806]],
            PARAMETER["False northing",{self.false_northing},
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
            AREA["Lunar Transverse Mercator Zone LTM_{self.number}{self.hemisphere}."],
            {self._get_bbox_string()}]]
        """
        sr = self._make_spatial_reference(wkt)
        return sr

# endregion


##############################################################################
# region> TEMPORARY TESTING CODE
##############################################################################
# TODO: Consolidate all testing formally.
# y = BaseZone.from_name("23N", is_global=False)
# y.spatial_reference
# z = BaseZone.from_name("N", is_global=True)
# z.spatial_reference

test_geo_coord_1 = _coords.GeographicCoordinates(latitude=1, longitude=2)
test_geo_coord_2 = _coords.GeographicCoordinates(latitude=85, longitude=2)
test_ltm_coord = test_geo_coord_1.to_lps_or_ltm()
test_lps_coord = test_geo_coord_2.to_lps_or_ltm()
