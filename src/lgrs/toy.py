# -*- coding: utf-8 -*-
"""
Toy exploration code following
    McClernan et al. (2025), "Lunar Grid Systems, Coordinate Systems, 
      and Map Projections for the Artemis Missions and Lunar Surface 
      Navigation"
      
For brevity, this paper is referred to as M2025 hereinafter.
"""



##############################################################################
# region> IMPORT
##############################################################################
# External.
from __future__ import annotations
import abc as _abc
import dataclasses as _dataclasses
import functools as _functools
import math as _math
import typing as _typing
from osgeo import osr as _osr
import re as _re
import pathlib

# endregion






##############################################################################
# region> UTILITY
##############################################################################
_zone_hint_pattern = _re.compile(
    "(?i)^(?P<zone_num>[0-9]+)?(?P<hemi>[N|S])?$"
)

def conform_latitude(latitude: float) -> float:
    if abs(latitude) > 90:
        raise TypeError("latitude must be in [-90, 90] interval")
    return latitude

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
        ) -> _osr.SpatialReference:
    # Validate and conform coordinates.
    latitude = conform_latitude(latitude)  # *REASSIGNMENT*
    # Below: Required by Eq. 13 of M2025 and by WKT.
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
        # TODO: Determine whether solution should be permanent.
        # Below: As a temporary solution, and a deviation from M2025,
        # including the LTM zone in the projection name.
        proj_wkt = f"""
PROJCRS["Moon (2015) - Sphere / Ocentric / Transverse Mercator / LTM zone {ltm_zone.number}{ltm_zone.hemisphere}",
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
    BBOX[{ltm_zone.minimum_latitude},{ltm_zone.minimum_longitude},{ltm_zone.maximum_latitude},{ltm_zone.maximum_longitude}]]]
""".strip()
    if not bound:
        # *REASSIGNMENT*
        proj_wkt, sub_count = _re.subn(r",\s*BBOX\[.+?\]", "", proj_wkt)
        assert (sub_count == 1)
    
    # Create and return projection instance.
    sr = _osr.SpatialReference()
    if sr.ImportFromWkt(proj_wkt):
        raise TypeError("WKT could not be parsed")
    return sr

def parse_zone_hint(
        zone_hint: int | str | None
) -> tuple[int | None, str | None]:
    hemi: str | None = None  # Default.
    zone_num: int | None = None  # Default.
    zone_hint_is_ok: bool = True  # Default.
    match zone_hint:
        case None:
            pass
        case int():
            zone_num = zone_hint
        case str():
            zone_hint_match = _zone_hint_pattern.search(zone_hint)
            if zone_hint_match:
                parsed_zone_num = zone_hint_match.group("zone_num")
                if parsed_zone_num:
                    zone_num = int(zone_hint_match.group("zone_num"))
                hemi = zone_hint_match.group("hemi")
            else:
                zone_hint_is_ok = False
        case _:
            zone_hint_is_ok = False
    if not zone_hint_is_ok:
        raise TypeError(f"`zone_hint` not recognized: {zone_hint!r}")
    return (zone_num, hemi)

# def resolve_zone_number_and_hemisphere(
#         *, zone_number: int | None = None, hemisphere: str | None = None,
#         latitude: float | None = None, longitude: float | None = None,
#         extend_ltm: bool = False
# ) -> tuple[int | None, str]:
#     if hemisphere is None:
#         if latitude is None:
#             raise TypeError("If `hemisphere` is not specified, "
#                             "`latitude` must be specified.")
#         hemisphere = "N" if latitude >= 0 else "S"
#     if zone_number is None:
#         if latitude is None:
#             raise TypeError("If `zone_number` is not specified, "
#                             "`latitude` must be specified.")
#         if extend_ltm:
#             ltm_max_abs_lat = LTM_UNEXTENDED_MAX_ABSOLUTE_LATITUDE
#         else:
#             ltm_max_abs_lat = LTM_EXTENDED_MAX_ABSOLUTE_LATITUDE
#         # TODO: Compare to behavior of original code.
#         use_lps = (abs(latitude) > ltm_max_abs_lat)
#         if not use_lps:
#             if longitude is None:
#                 raise TypeError("To resolve LTM zone, "
#                                 "`longitude` must be specified.")
#             # Below: Eq. 13 of M2025. Zones are 1-indexed.
#             zone_number = (
#                     _math.floor((longitude + 180)
#                                 / (2 * LTM_ZONE_HALF_WIDTH))
#                     + 1
#             )
#     return (zone_number, hemisphere)

# endregion



##############################################################################
# region> AREAS
##############################################################################




##############################################################################
# region> CONVERSION FUNCTIONS
##############################################################################
# def compare_ltm_or_lps(string1: str, string2: str) -> float:
#     for string in (string1, string2):
#         parts = string.split(" ")
#         if len(parts) != 4:
#             raise TypeError("each string must have a non-condensed format, "
#                             "with four parts delimited by spaces: "
#                             "<zone_number> <hemisphere> <easting> <northing>")

# endregion
    


##############################################################################
# region> DEMO CODE
##############################################################################
# if __name__ == "__main__":
#     result = convert_to_ltm_or_lps(latitude=-2.0, longitude=-3.0, 
#                                    as_string=True)

# endregion