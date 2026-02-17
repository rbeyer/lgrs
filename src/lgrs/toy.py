# -*- coding: utf-8 -*-
"""
Toy exploration code following
    McClernan et al. (2025), "Lunar Grid Systems, Coordinate Systems, 
      and Map Projections for the Artemis Missions and Lunar Surface 
      Navigation"
      
For brevity, this paper is referred to as M2025 hereinafter.
"""



##############################################################################
#%% IMPORT
##############################################################################
# External.
from __future__ import annotations
import dataclasses
import functools
import math
import osgeo.osr
import re
import pathlib



##############################################################################
#%% CONFIGURATION
##############################################################################
#---- LTM --------------------------------------------------------------------
# Note: See Table 4 of M2025 for most of these variables.
# Note: If any of these variables are modified from their M2025 values,
# additional changes to the code will likely be necessary.

# Boundaries.
LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE = 82  # (degrees)
LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE = 80  # (degrees)

# False northing and easting.
LTM_FALSE_EASTING = 250_000  # `F_E` in M2025 (meters)
LTM_N_FALSE_NORTHING = 0  # `F_N` in M2025 (meters)
LTM_S_FALSE_NORTHING = 2_500_000  # `F_N` in M2025 (meters)

# Shape paramters.
ELLIPSOIDAL_FLATTENING = 0  # `f` in M2025 (unitless)
# Note: `e` in M2025 (unitless).
ECCENTRICITY = (ELLIPSOIDAL_FLATTENING * (2 - ELLIPSOIDAL_FLATTENING))**0.5
LUNAR_RADIUS = 1_737_400  # `a` in M2025 (meters)
# Note: `n` in M2025 (unitless).
THIRD_FLATTENING = ELLIPSOIDAL_FLATTENING / (2 - ELLIPSOIDAL_FLATTENING)

# Other parameters.
LTM_CENTRAL_SCALE_FACTOR = 0.999  # `k_0` in M2025 (exact,  unitless)
LTM_LATITUDE_OF_PROJECTION_AXIS = 0  # `phi_0` in M2025 (degrees)
LTM_ZONE_HALF_WIDTH = 4  # `W` in M2025 (degrees)



##############################################################################
#%% UTILITY
##############################################################################
def conform_longitude(longitude: float, *, fudge: bool = False) -> float:
    # Conform longitude to expected range, [-180, 180).
    # TODO: Determine whether accepted range is reasonable.
    if abs(longitude) > 360:
        raise TypeError("`longitude` must be in [-360, 360] interval")    
    longitude %= 360  # Conforms to [0, 360) interval.
    if longitude >= 180:
        longitude -= 360  # Conforms to [-180, 180) interval.
        
    # Optionally fudge longitude, if necessary.
    # TODO: Delete code and argument if `fudge` is no longer needed.
    if fudge:
        zone = LtmZone.from_geographic(latitude=0, longitude=longitude)
        for border_lon in (zone.minimum_longitude, zone.maximum_longitude):
            if abs(border_lon - longitude) < 1e-11:
                # Note: Fudge inward, so that zone of longitude does not
                # change.
                if border_lon is zone.minimum_longitude:
                    fudged_longitude = zone.minimum_longitude + 1e-11
                else:
                    fudged_longitude = zone.maximum_longitude - 1e-11
                return fudged_longitude

    # Return.
    return longitude
    

def make_zone_spatial_reference(
        *, latitude: float, longitude: float, 
        bound: bool = True, extend_ltm: bool = True
        ) -> osgeo.osr.SpatialReference:
    # Validate coordinates.
    if abs(latitude) > 90:
        raise TypeError("latitude must be in [-90, 90] interval")
    # Note: Required by Eq. 13 of M2025 and by WKT.
    longitude = conform_longitude(longitude)  # *REASSIGNMENT*
    
    # Determine whether to use LTM or LPS.
    ltm_zone = LtmZone.from_geographic(latitude=latitude, longitude=longitude,
                                       extend_ltm=extend_ltm, error=False)
    
    # Characterize zone.
    if ltm_zone is None:
        raise NotImplementedError("support for LPS")
        
    # Construct projection WKT.
    # Note: Earlier code completes through Step 3 (p. 18 of M2025).
    # Below, later steps are completed using `osgeo.osr`.
    else:
        if ELLIPSOIDAL_FLATTENING:
            raise NotImplementedError("support for non-spheres")
        # TODO: Compare format below (taken from pp. 23-24 of M2025) to
        # `sr.ExportToPrettyWkt()` and identify any outdated or 
        # otherwise non-preferred formatting.
        # Note: As a temporary solution, and a deviation from M2025,
        # including the LTM zone in the projection namne.
        proj_wkt = f"""
PROJCRS["Moon (2015) - Sphere / Ocentric / Tranverse Mercator / LTM zone {ltm_zone.number}{ltm_zone.hemisphere}",
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
    PARAMETER["Longitude of natural origin",{ltm_zone.center_longitude},
      ANGLEUNIT["degree",0.0174532925199433],
      ID["EPSG",8802]],
    PARAMETER["Scale factor at natural origin",{LTM_CENTRAL_SCALE_FACTOR},
      SCALEUNIT["unity",1],
      ID["EPSG",8805]],
    PARAMETER["False easting",{ltm_zone.false_easting},
      LENGTHUNIT["metre",1],
      ID["EPSG",8806]],
    PARAMETER["False northing",{ltm_zone.false_northing},
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
    SCOPE["Lunar Transverse Mercator Zone LTM_{ltm_zone.number}{ltm_zone.hemisphere}."],
    BBOX[{ltm_zone.maximum_latitude},{ltm_zone.minimum_longitude},{ltm_zone.minimum_latitude},{ltm_zone.maximum_longitude}]]]
""".strip()
    if not bound:
        # *REASSIGNMENT*
        proj_wkt, sub_count = re.subn(r",\s*BBOX\[.+?\]", "", proj_wkt)
        assert (sub_count == 1)
    
    # Create and return projection instance.
    sr = osgeo.osr.SpatialReference()
    if sr.ImportFromWkt(proj_wkt):
        raise TypeError("WKT could not be parsed")
    return sr



##############################################################################
#%% NAMED TUPLES
##############################################################################
@dataclasses.dataclass(kw_only=True, frozen=True)
class BaseGridCoordinates:
    easting: int|float
    northing: int|float

    def grid_distance_to(self, other: BaseGridCoordinates) -> float:
        # Verify compatibility.
        # TODO: Update restrictions as new subclasses are added.
        if type(self) is not type(other):
            raise TypeError(f"Cannot compare mixed types: {self!r}, {other!r}")
        inst_dicts = []
        for instance in (self, other):
            inst_dict = dataclasses.asdict(instance)
            del inst_dict["easting"]
            del inst_dict["northing"]
            inst_dicts.append(inst_dict)
        self_dict, other_dict = inst_dicts
        if self_dict != other_dict:
            for key, self_value in self_dict.items():
                if other_dict[key] != self_value:
                    raise TypeError(f"`{key}` does not match: "
                                    f"{self!r}, {other!r}")
            # Note: This line should never be encountered.
            raise TypeError(f"Not comparable: {self!r}, {other!r}")
            
        # Calculate and return distance.
        dist = math.dist((self.easting, self.northing), 
                         (other.easting, other.northing))
        return dist
                

@dataclasses.dataclass(kw_only=True, frozen=True)
class GeographicCoordinates:
    latitude: float
    longitude: float

    def to_ltm_or_lps(
            self, *, extend_ltm: bool = False
            ) -> LtmCoordinates|LpsCoordinates:
        # Project.
        proj_sr = make_zone_spatial_reference(latitude=self.latitude, 
                                              longitude=self.longitude,
                                              extend_ltm=extend_ltm)
        geo_sr = osgeo.osr.SpatialReference()
        geo_sr.CopyGeogCSFrom(proj_sr)
        coord_transform = osgeo.osr.CoordinateTransformation(geo_sr, proj_sr)
        
        # Create coordinates instance.
        easting, northing, elevation = coord_transform.TransformPoint(
            self.latitude, self.longitude
            )
        _, zone_str = proj_sr.GetName().rsplit(" ", maxsplit=1)
        zone_num_str = zone_str[:-1]
        hemi_str = zone_str[-1]
        if zone_num_str:
            proj_coords = LtmCoordinates(zone_number=int(zone_num_str), 
                                         hemisphere=hemi_str, 
                                         easting=easting, northing=northing)
        else:
            proj_coords = LpsCoordinates(hemisphere=hemi_str,
                                         easting=easting, northing=northing)
        return proj_coords


@dataclasses.dataclass(kw_only=True, frozen=True)
class LtmCoordinates(BaseGridCoordinates):
    zone_number: int
    hemisphere: str
    
    @classmethod
    def from_string(cls, string: str):  # TODO: Add `-> typing.Self`.
        # Parse `string`.
        if " " in string:
            parts = string.split(" ")
            if len(parts) != 4:
                raise TypeError("If non-condensed, `string` must have four "
                                "parts delimited by spaces: <zone_number> "
                                "<hemisphere> <easting> <northing>")
            zone_str, hemisphere, easting_str, northing_str = parts
        elif "." in string:
            raise TypeError("The decimal point is only supported in the non-"
                            "condensed format.")
        else:
            raise NotImplementedError("Support for condensed format.")
            
        # Return new coordinates instance.
        new = cls(zone_number=int(zone_str), hemisphere=hemisphere,
                  easting=float(easting_str), northing=float(northing_str))
        return new

    def as_string(self, *, 
                  truncation_meters: int = 1, condensed: bool = True) -> str:
        # Extract and optionally truncate easting and northing.
        if truncation_meters:
            if not math.log10(truncation_meters).is_integer():
                # Note: Similar error in 7.2 code.
                raise TypeError("`truncation_meters` must be 10 to a positive "
                                "integer power")
            # *REASSIGNMENTS*
            easting = (math.floor(self.easting / truncation_meters) 
                       * truncation_meters)
            northing = (math.floor(self.northing / truncation_meters) 
                        * truncation_meters)
        else:
            easting = self.easting
            northing = self.northing
            
        # Format and return string.
        string = (f"{self.zone_number} {self.hemisphere} "
                  "{easting!r} {northing!r}")
        if condensed:
            string = string.replace(" ", "")  # *REASSIGNMENT*
        return string        
    
    
@dataclasses.dataclass(kw_only=True, frozen=True)
class LpsCoordinates(BaseGridCoordinates):
    hemisphere: str
    
    
@dataclasses.dataclass(kw_only=True, frozen=True)
class LtmZone:
    number: int
    hemisphere: str
    extend_ltm: bool = False
    
    @classmethod
    def from_geographic(
            cls, *, 
            latitude: float, longitude: float, extend_ltm: bool = False,
            error: bool = True
            ):  # TODO: Add `-> typing.Self|None`.
        # Determine whether LTM is supported.
        if extend_ltm:
            ltm_max_abs_lat = LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            ltm_max_abs_lat = LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        # TODO: Compare to behavior of original code.
        if abs(latitude) > ltm_max_abs_lat:
            if error:
                raise TypeError(f"latitude is not supported: {latitude}")
            else:
                return None
            
        # Identify zone number and hemisphere.
        # Note: Eq. 13 of M2025. Zones are 1-indexed.
        zone_num = math.floor((longitude + 180)/(2 * LTM_ZONE_HALF_WIDTH)) + 1        
        # Note: Related to eqs. 14 and 15 of M2025.
        hemi = "N" if latitude >= 0 else "S"
        
        # Create and return instance.
        new = cls(number=zone_num, hemisphere=hemi, extend_ltm=extend_ltm)
        return new
    
    @functools.cached_property
    def center_longitude(self) -> int:
        ctr_lon = ((self.number - 1)
                   * (2 * LTM_ZONE_HALF_WIDTH)
                   - 180
                   + LTM_ZONE_HALF_WIDTH)        
        return ctr_lon

    @functools.cached_property
    def false_easting(self) -> int:
        return LTM_FALSE_EASTING

    @functools.cached_property
    def false_northing(self) -> int:
        match self.hemisphere:
            case "N":
                return LTM_N_FALSE_NORTHING
            case "S":
                return LTM_S_FALSE_NORTHING

    @functools.cached_property
    def maximum_latitude(self) -> int:
        if self.hemisphere == "S":
            return 0
        elif self.extend_ltm:
            return LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            return LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE
    
    @functools.cached_property
    def maximum_longitude(self) -> int:
        return self.center_longitude + LTM_ZONE_HALF_WIDTH
        
    @functools.cached_property
    def minimum_latitude(self) -> int:
        if self.hemisphere == "N":
            return 0
        elif self.extend_ltm:
            return -LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
        else:
            return -LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE
                
    @functools.cached_property
    def minimum_longitude(self) -> int:
        return self.center_longitude - LTM_ZONE_HALF_WIDTH
    
        

##############################################################################
#%% CONVERSION FUNCTIONS
##############################################################################
# def compare_ltm_or_lps(string1: str, string2: str) -> float:
#     for string in (string1, string2):
#         parts = string.split(" ")
#         if len(parts) != 4:
#             raise TypeError("each string must have a non-condensed format, "
#                             "with four parts delimited by spaces: "
#                             "<zone_number> <hemisphere> <easting> <northing>")

    

##############################################################################
#%% DEMO CODE
##############################################################################
# if __name__ == "__main__":
#     result = convert_to_ltm_or_lps(latitude=-2.0, longitude=-3.0, 
#                                    as_string=True)
    