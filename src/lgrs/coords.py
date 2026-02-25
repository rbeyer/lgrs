##############################################################################
# region> IMPORT
##############################################################################
# External.
from __future__ import annotations
import functools as _functools
import dataclasses as _dataclasses
import math as _math
import typing as _typing

# Internal.
import lgrs.bases as _bases
import lgrs.util as _util

# endregion



##############################################################################
# region> CLASSES
##############################################################################
@_dataclasses.dataclass(kw_only=True, frozen=True)
class BaseGridCoordinates(_bases.AbstractGridCoordinates):
    easting: float
    northing: float

    zone: _bases.AbstractBaseZone = _util.ExpectedAttribute()

    def calculate_grid_distance_to(self, other: BaseGridCoordinates) -> float:
        if not self.zone.is_compatible_with(other.zone):
            raise TypeError("Zones are not compatible: "
                            f"{self.zone!r}, {other!r}")
        dist = _math.dist((self.easting, self.northing),
                          (other.easting, other.northing))
        return dist

    # TODO: Next two methods added in a rush. Revisit.
    @_functools.cached_property
    def latitude(self) -> float:
        geo = self.to_geographic()
        return geo.latitude

    @_functools.cached_property
    def longitude(self) -> float:
        geo = self.to_geographic()
        return geo.longitude

    # TODO: Probably cache this.
    def to_geographic(self) -> GeographicCoordinates:
        # TODO: Fix inheritance. Maybe move
        #  `._make_osgeo_transformation()` to `bases`?
        coord_transform = self.zone._make_osgeo_transformation(
            to_geographic=True
        )
        latitude, longitude, elevation = coord_transform.TransformPoint(
                self.easting, self.northing
            )
        new = GeographicCoordinates(latitude=latitude, longitude=longitude)
        return new

@_dataclasses.dataclass(kw_only=True, frozen=True)
class GeographicCoordinates(_bases.AbstractGeographicCoordinates):
    latitude: float
    longitude: float

    @classmethod
    def from_string(cls, string: str) -> _typing.Self:
        parts = cls._parse_string(string,
                                  form=(float | int, float | int))
        latitude, longitude = parts
        new = cls(latitude=latitude, longitude=longitude)

    def to_lps_or_ltm(
            self, *,
            extended_ltm: bool = False,
            zone: _bases.AbstractBaseZone | None = None
    ) -> LpsCoordinates | LtmCoordinates:
        # Resolve target zone.
        import lgrs.areal as areal  # Lazy import, to avoid circular import.
        if zone is None:
            # *REASSIGNMENT*
            zone = areal.BaseZone.from_coordinates(self,
                                                   extended_ltm=extended_ltm)

        # Create and return coordinates instance.
        new = zone.transform_coordinates_into(self)
        return new

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LtmCoordinates(BaseGridCoordinates):
    zone: _bases.AbstractBaseZone

    @classmethod
    def from_string(
            cls, string: str, *,
            extended_ltm: bool = False, is_global: bool = False
    ) -> _typing.Self:
        parts = cls._parse_string(string,
                                  form=(int, str, float | int, float | int))
        zone_num, hemi, easting, northing = parts
        import lgrs.areal as areal  # Lazy import, to avoid circular import.
        zone = areal.LtmZone(number=zone_num, hemisphere=hemi,
                             extended_ltm=extended_ltm, is_global=is_global)
        new = cls(easting=easting, northing=northing, zone=zone)
        return new

    # TODO: Revisit this method, to sync with refactor.
    def as_string(self, *,
                  truncation_meters: int = 1, condensed: bool = True) -> str:
        # Extract and optionally truncate easting and northing.
        if truncation_meters:
            if not _math.log10(truncation_meters).is_integer():
                # Below: Similar error in 7.2 code.
                raise TypeError("`truncation_meters` must be 10 to a positive "
                                "integer power")
            easting = (_math.floor(self.easting / truncation_meters)
                       * truncation_meters)
            northing = (_math.floor(self.northing / truncation_meters)
                        * truncation_meters)
        else:
            easting = self.easting
            northing = self.northing

        # Format and return string.
        string = (f"{self.zone_number} {self.hemisphere} "
                  f"{easting!r} {northing!r}")
        if condensed:
            string = string.replace(" ", "")  # *REASSIGNMENT*
        return string

@_dataclasses.dataclass(kw_only=True, frozen=True)
class LpsCoordinates(BaseGridCoordinates):
    zone: _bases.AbstractBaseZone

    @classmethod
    def from_string(
            cls, string: str, *,
            extended_ltm: bool = False, is_global: bool = False
    ) -> _typing.Self:
        parts = cls._parse_string(string,
                                  form=(str, float | int, float | int))
        hemi, easting, northing = parts
        import lgrs.areal as areal  # Lazy import, to avoid circular import.
        zone = areal.LpsZone(hemisphere=hemi, extended_ltm=extended_ltm,
                             is_global=is_global)
        new = cls(easting=easting, northing=northing, zone=zone)
        return new

# endregion
