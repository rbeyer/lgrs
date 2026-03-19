# !/bin/env python3
#* Original file name: LGRS_Coordinate_Conversion_mk7.2.py
#* Version: 7.2
# =====================================================================
''' PROGRAM INFORMATION
Program:  LGRS_Coordinate_Conversion_mk7.py 
Language: Python 3.11.4
Author:   Mark T. McClernan
Created:  March, 2023   (Python 3.6.5)
Modified: February, 2024 (Python 3.11.4)
IDE:      Visual Studio Code (v1.18.1 x86)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
PROGRAM DESCRIPTION:
    This program performs forward and inverse conversions from
    lunar planetocentric latitude and longitude to each of the
    following lunar coordinate systems:
        1. Lunar Transverse Mercator (LTM) system, 8° zones;
        2. Lunar Polar Stereographic (LPS);
        3. Lunar Grid Reference System (LGRS);
        4. LGRS in Artemis Condensed Coordinate Format (ACC)
        and
        5. LGRS ACC coordinates limited to 6 characters.

    Algorithms are modified for lunar use and provided from Karney
    (2010), Snyder (1987), and NGA (2014). See References.

    Main modifications to projection and equations from references:
        1. Change flattening value to zero to support a lunar spheroid.
        2. Utilizing 8° transverse Mercator zone.
        3. Map projection parameters are all updated to support Lunar use
        4. Grid systems use 25km and 1km.

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
HOW TO USE THIS CODE:

    This software is designed to run via the command line, where an
    input coordinate is provided to the software and the converted 
    format is returned in the specified format. 

    The program is called from the command line with the sample 
    command

    ./LGRS_Coordinate_Conversion_mk7.py {form_in}2{form_out} {Coordinate} 

    Warnings and argument checks are included to make sure the converted 
    format is correct and will terminate the program if the conversion
    is not able to take place. 

    form_in can be LatLon, LTM, LPS, LGRS, PolarLGRS, LGRS_ACC, and PolarLGRS_ACC
    form_out can be  LatLon, LTM, LPS, LGRS, PolarLGRS, LGRS_ACC, PolarLGRS_ACC,
                    ACC or Polar_ACC

    The coordinate variable has two input modes, condensed and noncondensed.
        If not condensed the coordinate needs to be spaced out for each 
        coordinate component, the program is looking for a specific number
        of coordinates and if the correct number is not met the program will 
        terminate. 

        LPS: H, E, N
        LTM: Z, H, E, N
        PolarLGRS: latBand, 25kmE, 25kmN, E, N
        LGRS: lonBand, latBand, 25kmE, 25kmN, E, N
        PolarLGRS_ACC: latBand, 25kmE, 25kmN, 1kmE, 1kmN E, N
        LGRS_ACC: lonBand, latBand, 25kmE, 25kmN, 1kmE, 1kmN E, N

        Easting and northing values do not need to be truncated and can be
        submitted as floating point values. A space is required between each
        coordinate value, no special delimiters are to be used. 

        If condensed the input coordinate must be truncated to at least 1m and
        written with no spaces. A delimiter of (E) for easting and (N) for
        northing is required to input an LTM or LPS coordinate.
        LTM: 23S250000E1894139N
        LPS: S500000E741523N

        LGRS and LGRS coordinates do not require an easting or northing 
        delimiter in condensed mode. Additionally, this import format is
        not available for latitude and longitude inputs.

    The condensed condition is set via a boolean value at the beginning of 
    the program
        condensed = True or condensed = False

    The condensed variable also changes the output, if condensed is specified,
    a condensed argument will be returned. If not condensed the output 
    coordinate will be spaced out depending on the number of variables of the
    final coordinate. 

    Two other variables can be set to change the program's processing 
    behavior. trunc_val specifies the degree at which the coordinate
    is truncated to. 1 for one place, 10 for tens, etc... this value must be
    a multiple of 10 or the program will terminate. If trunc_val is 0
    no truncation will occur and a floating point is returned. 

    The info returns processing errors and the processing time of the
    conversion has taken

    Example program calls: # settings following after hash, 
    Note round-off error from truncation

    LTM 1:
        in 
            ./LGRS_Coordinate_Conversion_mk7.py LatLon2LTM 20.0 0.0 
            # trunc_val=1, condensed=True
        out
            23N250000E0605860N

    LTM 2:
        in 
            ./LGRS_Coordinate_Conversion_mk7.py LatLon2LTM 20.0 0.0 
            # trunc_val=0, condensed=False
        out
            23 N 250000.0 605860.5414745066

    LPS 1:
        in
            ./LGRS_Coordinate_Conversion_mk7.py LatLon2LPS -80.0 -135.0 
            # trunc_val=1, condensed=True
        out 
        S286325E286325N

    LPS 2:
        in
            ./LGRS_Coordinate_Conversion_mk7.py LatLon2LPS -80.0 -135.0 
             # trunc_val=0, condensed=False
        out
            S 286325.3596121004 286325.3596121003        


    LGRS 1: 
        in 
            ./LGRS_Coordinate_Conversion_mk7.py LTM2LGRS 23N250000E0605860N
            # trunc_val=1, condensed=True
        out 
            23QFK0000005860
        
    LTM 3: 
        in 
            ./LGRS_Coordinate_Conversion_mk7.py LGRS2LTM 23QFK0000005860
            # trunc_val=1, condensed=True

        out 
            23N250000.0E605860.0N
        
    Polar LGRS 1: 
        in 
            ./LGRS_Coordinate_Conversion_mk7.py LatLon2PolarLGRS -80.0 -135.0
            # trunc_val=1, condensed=True

        out 
            ATF0421604216

        LatLon 4: 
        in 
            ./LGRS_Coordinate_Conversion_mk7.py PolarLGRS2LatLon ATF0421604216
            # trunc_val=1, condensed=True
        out 
            -81.99995863117528°-135.0° (Round off error)
        
    LGRS_ACC 1:
        in
            ./LGRS_Coordinate_Conversion_mk7.py LTM2LGRS_ACC 23N250000E0605860N
        out 
            23QFK-000E860

    LTM 4: 
        in
            ./LGRS_Coordinate_Conversion_mk7.py LGRS_ACC2LTM 23QFK-000E860
        out 
            23N250000.0E605860.0N 

    PolarLGRS_ACC 1: 
        in
            ./LGRS_Coordinate_Conversion_mk7.py LatLon2PolarLGRS_ACC -82.0 -135.0  
            # trunc_val=1, condensed=True
        out   
            ATFD216D216

    LatLon 5: 
        in
            ./LGRS_Coordinate_Conversion_mk7.py PolarLGRS_ACC2LatLon ATFD216D216
        out 
            -81.99995863117528°-135.0° (Round off error)
    
    To produce the ACC grid for lunar surface navigation set trunc_val to
    10 or specify ACC or Polar_ACC. There is no inverse conversion, as the
    coordinate is relative and truncated to report in a 25km grid zone
    to a precision of 10m. 

    Polar_ACC 1
        in
            ./LGRS_Coordinate_Conversion_mk7.py LatLon2Polar_ACC -82.0 -135.0
        out 
            D21D21

    Polar_ACC
        in 
            ./LGRS_Coordinate_Conversion_mk7.py LTM2ACC 23N250000E0605860N
        out
            -00E86

    See the testing script for more examples.

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
PROGRAM SECTIONS (can search for each using "SECTION #"):
    SECTION 0: INITIALIZE PROGRAM AND CALL EXTERNAL LIBRARIES
    SECTION 1: REFERENCE SURFACE PARAMETERS
        SECTION 1.1:   parameters needed for conversion equations
            SECTION 1.1.1: parameters needed for Karney-Kruger (2010)
                        based Lunar Transverse Mercator (LTM) system.
            SECTION 1.1.2: parameters needed for Snynder (1987) and the Lunar
                        Polar Stereographic System
            SECTION 1.1.3: Parameters Needed for Lunar Grid Reference
                        System (LGRS)
            SECTION 1.1.4: parameters needed for LGRS in Artemis
                        Condensed Coordinate (ACC) Format
            SECTION 1.1.5: Patterns needed to read in condensed coordinates

    SECTION 2: FUNCTION LIBRARY
        SECTION 2.1: Convert to LTM from planetocentric Lat and Lon
        SECTION 2.2: Convert to planetocentric Lat and Lon from LTM
        SECTION 2.3: Calculate meridional radius of curvature
        SECTION 2.4: Calculate distance from pole to latitude parallel
        SECTION 2.5: Calculate polar stereographic ellipsoidal X coordinate
        SECTION 2.6: Calculate polar stereographic ellipsoidal Y coordinate
        SECTION 2.7: Calculate polar stereographic spherical scale error
        SECTION 2.8: Calculate polar stereographic spherical X coordinate
        SECTION 2.9: Calculate polar stereographic spherical Y coordinate
        SECTION 2.10: Convert to LPS from planetocentric Lat and Lon
        SECTION 2.11: Inverse calculate meridional radius of curvature
        SECTION 2.12: Calculate conformal latitude
        SECTION 2.13: Recover Latitude on an ellipsoid without iteration
        SECTION 2.14: Recover Longitude on an ellipsoid
        SECTION 2.15: Calculate distance from projection pole to parallel
        SECTION 2.16: Calculate great circle distance from pole to parallel
        SECTION 2.17: Recover latitude on a sphere
        SECTION 2.18: Recover longitude on a sphere
        SECTION 2.19: Convert to planetocentric Lat and Lon from LPS
        SECTION 2.20: Convert to LGRS from LTM
        SECTION 2.21: Convert to LGRS from LPS
        SECTION 2.22: Convert to LTM from LGRS
        SECTION 2.23: Convert to LPS from LGRS
        SECTION 2.24: Convert to LGRS in ACC format from LTM
        SECTION 2.25: Convert to LGRS in ACC format from LPS
        SECTION 2.26: Convert to LTM form LGRS in ACC format
        SECTION 2.27: Convert to LPS from LGRS in ACC format
        SECTION 2.28: Convert planetocentric latitude to colatitude
        SECTION 2.29: Convert planetocentric colatitude to latitude
        SECTION 2.30: Convert planetocentric longitude to colongitude
        SECTION 2.31: Convert planetocentric colongitude to longitude
        SECTION 2.32: Convert degrees to decimal minutes
        SECTION 2.33: Convert decimal minutes to degrees
        SECTION 2.34: Convert degrees to decimal seconds
        SECTION 2.35: Convert decimal seconds to degrees
        SECTION 2.36: Formula to truncate coordinates

        SECTION 3: MAIN PROGRAM
            SECTION 3.1: Importing system variables for processing
            SECTION 3.2: Converting Coordinates
            SECTION 3.2.1: LATLON CONVERSIONS
                SECTION 3.2.2:LTM CONVERSIONS
                SECTION 3.2.3: LPS CONVERSIONS
                SECTION 3.2.4: LGRS CONVERSIONS
                SECTION 3.2.4: LGRS ACC CONVERSIONS
            SECTION 3.3: Exporting data
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# References

Karney, C.F.F. (2010), Transverse Mercator with an accuracy of a few
    nanometers Journal of Geodesy, 85(8), 475–485,
    https://doi.org/10.48550/arXiv.1002.1417.

NGA (2014), The Universal Grids and the Transverse Mercator and Polar
    Stereographic Map Projections, in National Geospatial-Intelligence
    Agency (NGA) Standardization Document, NGA.SIG.0012_2.0.0_UTMUPS.

Snyder, J. P. (1987). Map Projections: A Working Manual, U.S.
    Geological Survey Professional Paper 1395, Washington, DC: United
    States Government Printing Office,
    https://pubs.usgs.gov/pp/1395/report.pdf.
'''
# =====================================================================
# SECTION 0: INITIALIZE PROGRAM AND CALL EXTERNAL LIBRARIES


import os                   # used as system utilities
import sys
                                            # os -> Python 3.11.4
                                            # sys 3.11.4

import numpy as np          # To perform mathematical calculations
                                            # np 1.25.2

import datetime             # To perform time monitoring
                                            # datetime -> Python 3.11.4

import re                   # for input coordinate parsing
                            # re -> '2.2.1'

ProgName = "LGRS_Coordinate_Conversion_mk7"

# =====================================================================
# SECTION 1: REFERENCE SURFACE PARAMETERS
# Geodetic function constants for the Moon, note all projection origins
#     are determined in their associated function



def initialize_LGRS_function_globals():

    global FalseEasting, FalseNorthing, FalseEasting_polar
    global FalseNorthing_polar, k0, k0_polar, ZoneWidth, a, f, b, e

    # Map projection False Origins
    # False Origins for LTM

    FalseEasting = 250E3
    FalseNorthing = 2500E3

    # False Origins for LPS
    FalseEasting_polar = 500E3
    FalseNorthing_polar = 500E3

    # map projection scale factors
    k0 = .999         # transverse Mercator (LTM)
    k0_polar = .994   # polar stereographic (LPS)

    # Transverse Mercator zone width from the central meridian
    ZoneWidth = 4.

    # Lunar spheroid parameters
    a = 1737400       # Semi-major radius
    f = 0             # Geometric flattening
    b = a * (1 - f)        # Semi-minor radius
    e = (f * (2 - f))**.5  # First eccentricity

    # Ensure a full double is processed and printed
    np.set_printoptions(precision=20)

# ---------------------------------------------------------------------
# SECTION 1.1: parameters needed for conversion equations

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# SECTION 1.1.1: Parameters needed for Karney-Kruger (2010) based Lunar
#                Transverse Mercator (LTM) system.

    # 3rd ellipsoidal flattening
    global n, n2, n3, n4, n5, n6

    n = f / (2 - f)       # can use n = (a - b)/(a + b).

    # construct powers of n to order 6
    n2 = n*n
    n3 = n*n2
    n4 = n*n3
    n5 = n*n4
    n6 = n*n5

    # rectifying radius of conformal spheres to order 6
    global A
    A = a/(1 + n) * (1 + (1/4)*n2 + (1/64)*n4 + (1/256)*n6)

    # construct alpha coefficients (order 6) for forward conversion
    global ap2, ap4, ap6, ap8, ap10, ap12

    ap2 = (1/2)*n - (2/3)*n2 + (5/16)*n3 + (41/180)*n4 - (127/288)*n5 \
                  + (7891/37800)*n6
    ap4 = (13/48)*n2 - (3/5)*n3 + (557/1440)*n4 + (281/630)*n5 \
                     - (1983433/1935360)*n6
    ap6 = (61/240)*n3 - (103/140)*n4 + (15061/26880)*n5 + (167603/181440)*n6
    ap8 = (49561/161280)*n4 - (179/168)*n5 + (6601661/7257600)*n6
    ap10 = (34729/80640)*n5 - (3418889/1995840)*n6
    ap12 = (212378941/319334400)*n6

    # construct beta coefficients (order 6) for inverse conversion
    global bt2, bt4, bt6, bt8, bt10, bt12

    bt2 = (1/2)*n - (2/3)*n2 + (37/96)*n3 - (1/360)*n4 - (81/512)*n5 \
                  + (96199/604800)*n6
    bt4 = (1/48)*n2 + (1/15)*n3 - (437/1440)*n4 + (46/105)*n5 \
                    - (1118711/3870720)*n6
    bt6 = (17/480)*n3 - (37/840)*n4 - (209/4480)*n5 + (5569/90720)*n6
    bt8 = (4397/161280)*n4 - (11/504)*n5 - (830251/7257600)*n6
    bt10 = (4583/161280)*n5 - (108847/3991680)*n6
    bt12 = (20648693/638668800)*n6


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# SECTION 1.1.2: parameters needed for Snyder (1987) Lunar Polar
#                Stereographic

# coefficients needed for iteration during the inverse transform
# see Snyder (1987)

    global e2, e4, e6, e8

    e2 = e*e
    e4 = e2*e2
    e6 = e4*e2
    e8 = e6*e2

    global C2, C4, C6, C8

    C2 = e2/2 + 5*e4/24 + e6/12 + 13*e8/360
    C4 = 7*e4/48 + 29*e6/240 + 811*e8/11520
    C6 = 7*e6/120 + 81*e8/1120
    C8 = 4279*e8/161280

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# SECTION 1.1.3: parameters needed for Lunar Grid Reference System (LGRS)

    global latBands, e25kLetters, n25kLetters, e25kLetters_polar, \
        n25kLetters_polar
    # Latitude bands C..X 8° each, covering 88°S to 88°N
    # letters duplicated for oversized zones
    latBands = 'CCDEFGHJKLMNPQRSTUVWXX'

    # Letters used for the 25km LGRS in the LTM portion
    e25kLetters = ['ABCDEFGHJK']
    n25kLetters = ['ABCDEFGHJKLMNPQRSTUV', 'FGHJKLMNPQRSTUVABCDE',
                   'LMNPQRSTUVABCDEFGHJK']

    # Letters used for the 25km LGRS in the LPS portion
    e25kLetters_polar = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
    n25kLetters_polar = 'ABCDEFGHJKLMNPQRSTUVWXYZ'

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# SECTION 1.1.4: Parameters needed for LGRS in Artemis Condensed
#                Coordinate (ACC) Format
    global e1kmLetters, n1kmLetters

    # Letters used for the 1km grid used in LGRS in condensed format
    e1kmLetters = '-ABCDEFGHJKLMNPQRSTUVWXYZ'  # "-" is a zero character
    n1kmLetters = '-ABCDEFGHJKLMNPQRSTUVWXYZ'

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# SECTION 1.1.5: Patterns needed to read in condensed coordinates
    global LTM_pattern, LPS_pattern, LGRS_pattern
    global PolarLGRS_pattern, LGRS_ACC_pattern, PolarLGRS_ACC_pattern

    # supports floating or truncated integer values
    LTM_pattern = r'(\d+)([NS]{1})(\d+(?:\.\d+)?|\.\d+)(E)(\d+(?:\.\d+)?|\.\d+)(N)'
    LPS_pattern = r'([NS]{1})(\d+(?:\.\d+)?|\.\d+)(E)(\d+(?:\.\d+)?|\.\d+)(N)'

    # supports only truncated values (this is ok; non-compressed
    # Coordinates can be read in as a full floating point)
    LGRS_pattern = r'(\d+)([A-Z]{1})([A-Z]{1})([A-Z]{1})(\d{5})(\d{5})'
    PolarLGRS_pattern = r'([A-Z]{1})([A-Z]{1})([A-Z]{1})(\d{5})(\d{5})'
    LGRS_ACC_pattern = r'(\d+)([A-Z]{1})([A-Z]{1})([A-Z]{1})(.{1})(\d+)(.{1})(\d+)'
    PolarLGRS_ACC_pattern = r'([A-Z]{1})([A-Z]{1})([A-Z]{1})(.{1})(\d+)(.{1})(\d+)'

# =====================================================================
# SECTION 2: FUNCTION LIBRARY
    # SECTION 2.1: Convert to LTM from planetocentric Lat and Lon
    # SECTION 2.2: Convert to planetocentric Lat and Lon from LTM
    # SECTION 2.3: Calculate meridional radius of curvature
    # SECTION 2.4: Calculate distance from pole to latitude parallel
    # SECTION 2.5: Calculate polar stereographic ellipsoidal X coordinate
    # SECTION 2.6: Calculate polar stereographic ellipsoidal Y coordinate
    # SECTION 2.7: Calculate polar stereographic spherical scale error
    # SECTION 2.8: Calculate polar stereographic spherical X coordinate
    # SECTION 2.9: Calculate polar stereographic spherical Y coordinate
    # SECTION 2.10: Convert to LPS from planetocentric Lat and Lon
    # SECTION 2.11: Inverse calculate meridional radius of curvature
    # SECTION 2.12: Calculate conformal latitude
    # SECTION 2.13: Recover Latitude on an ellipsoid without iteration
    # SECTION 2.14: Recover Longitude on an ellipsoid
    # SECTION 2.15: Calculate distance from projection pole to parallel
    # SECTION 2.16: Calculate great circle distance from pole to parallel
    # SECTION 2.17: Recover latitude on a sphere
    # SECTION 2.18: Recover longitude on a sphere
    # SECTION 2.19: Convert to planetocentric Lat and Lon from LPS
    # SECTION 2.20: Convert to LGRS from LTM
    # SECTION 2.21: Convert to LGRS from LPS
    # SECTION 2.22: Convert to LTM from LGRS
    # SECTION 2.23: Convert to LPS from LGRS
    # SECTION 2.24: Convert to LGRS in ACC format from LTM
    # SECTION 2.25: Convert to LGRS in ACC format from LPS
    # SECTION 2.26: Convert to LTM form LGRS in ACC format
    # SECTION 2.27: Convert to LPS from LGRS in ACC format
    # SECTION 2.28: Convert planetocentric latitude to colatitude
    # SECTION 2.29: Convert planetocentric colatitude to latitude
    # SECTION 2.30: Convert planetocentric longitude to colongitude
    # SECTION 2.31: Convert planetocentric colongitude to longitude
    # SECTION 2.32: Convert degrees to decimal minutes
    # SECTION 2.33: Convert decimal minutes to degrees
    # SECTION 2.34: Convert degrees to decimal seconds
    # SECTION 2.35: Convert decimal seconds to degrees
    # SECTION 2.36: Formula to truncate coordinates

# ---------------------------------------------------------------------
# SECTION 2.1: Convert to LTM from planetocentric Lat and Lon


def toLTM(lon, lat, zone=None, trunc_val=1, process_errors=True):
    """Converts Planetocentric LatLon degree values to LTM easting
       and northing coordinates. Latitude and Longitude are the only
       Inputs required. Optionally, the zone does not have to be
       specified. If specified the central meridian will be
       calculated for the specified zone. An option is available to
       truncate the coordinates. 1 m is the default needed for LTM
       coordinates specifically; however, there will be round off with
       inverse conversion or additional conversions to other coordinate
       systems. For grid systems set to 0 for no truncation.

    Parameters:
    lon             Longitude               (float): degrees
    lat             Latitude                (float): degrees
    zone            LTM Zone                (int,float,NoneType),scaler
    lam0            Central Meridian to Zone(float): degrees
    trunc_val       Coordinate Precision    (int,float): meters
    process_errors  Processing flag         (logical): boolean

    Returns:
    zone            LTM zone                (int) scaler
    h               hemisphere              (str) unitless
    E               Eastings                (float,str) meters
    N               Northings               (float,str) meters

    Raises:
    ValueError: If coordinates are not within a latitude 90 -90,
                    longitude -180-180 range.
                User challenged if value is in the extended range"""
    if process_errors:
        if lat > 90:
            raise ValueError("Operation aborted: Latitude exceeds 90°.")
        elif lat < -90:
            raise ValueError("Operation aborted: Latitude less than -90°.")
        elif lon > 180:
            raise ValueError("Operation aborted: Longitude exceeds 180° "
                             " Try converting from 0°-360° to "
                             "-180°-180° longitude range.")
        elif lon < -180:
            raise ValueError("Operation aborted: Longitude is less than 180°")
        elif (lat >= -90 and lat < -82) or (lat <= 90 and lat > 82):
            choice = input("Latitude is in the extended between +-82° "
                           "and +-90° degrees. Do you wish to force the "
                           "conversion? LGRS is not supported in this region."
                           "(y/n): ")
            if choice.lower() != 'y':
                raise ValueError("Operation aborted: Latitude outside of "
                                 "LTM projection areas")
        elif (lat >= -82 and lat < -80) or (lat <= 82 and lat > 80):
            choice = input("Latitude is in the extended between +-80° "
                           "and +-82° degrees. Do you wish to continue the "
                           "conversion? (y/n): ")
            if choice.lower() != 'y':
                raise ValueError("Operation aborted: Latitude outside of "
                                 "LTM projections areas")

    # determine correct hemisphere for coordinate and processing
    if lat >= 0.:
        h = 'N'
    else:
        h = 'S'

    # determine LTM zone if none is given
    if zone == None:    # if no zone is given

        # longitudinal zone
        zone = np.floor((np.mean(lon) + 180)/(ZoneWidth * 2)) + 1

        if zone > 45:  # 180° values sometimes come up as 46. 
                       # We assign it back to zone 1
            zone -= 45

    # longitude of central meridian
    lam0 = np.deg2rad((zone - 1) * (ZoneWidth * 2) - 180. + (ZoneWidth))

    # convert from degrees to radians
    phi = np.deg2rad(lat)  # latitude from equator
    lam = np.deg2rad(lon) - lam0  # longitude ± from central meridian

    # precompute simple longitude values for speed
    coslam = np.cos(lam)
    sinlam = np.sin(lam)
    tanlam = np.tan(lam)

    # precompute latitude values
    tanphi = np.tan(phi)  # prime (_p) indicates angles on the conformal sphere

    # Compute conformal latitude
    sigma = np.sinh(e*np.arctanh(e*tanphi / (1 + tanphi**2)**.5))
    T_p = tanphi * (1 + sigma*sigma)**.5 - sigma * (1 + tanphi*tanphi)**.5

    # compute Gauss Schreiber coordinates
    E_p = np.arctan2(T_p, coslam)
    N_p = np.arcsinh(sinlam / (T_p*T_p + coslam*coslam)**.5)

    # Compute unscaled X,Y coordinates
    Ecoordonate = (E_p
                  + ap2 * np.sin(2*E_p) * np.cosh(2*N_p)
                  + ap4 * np.sin(4*E_p) * np.cosh(4*N_p)
                  + ap6 * np.sin(6*E_p) * np.cosh(6*N_p)
                  + ap8 * np.sin(8*E_p) * np.cosh(8*N_p)
                  + ap10 * np.sin(10*E_p) * np.cosh(10*N_p)
                  + ap12 * np.sin(12*E_p) * np.cosh(12*N_p))

    Ncoordonate = (N_p
                  + ap2 * (np.cos(2*E_p)) * (np.sinh(2*N_p))
                  + ap4 * (np.cos(4*E_p)) * (np.sinh(4*N_p))
                  + ap6 * (np.cos(6*E_p)) * (np.sinh(6*N_p))
                  + ap8 * (np.cos(8*E_p)) * (np.sinh(8*N_p))
                  + ap10 * (np.cos(10*E_p)) * (np.sinh(10*N_p))
                  + ap12 * (np.cos(12*E_p)) * (np.sinh(12*N_p)))

    # solve for X and Y with adjustment for UTM scale factor
    X = k0 * A * Ncoordonate
    Y = k0 * A * Ecoordonate

    # The following are not needed to complete the coordinate
    # system conversion but are provided for completeness

    # # compute p and q values
    # p_p=1.+2*ap2*(np.cos(2*E_p))*(np.cosh(2*N_p)) + \
    #     4*ap4*(np.cos(4*E_p))*(np.cosh(4*N_p)) + \
    #     6*ap6*(np.cos(6*E_p))*(np.cosh(6*N_p)) + \
    #     8*ap8*(np.cos(8*E_p))*(np.cosh(8*N_p)) + \
    #     10*ap10*(np.cos(10*E_p))*(np.cosh(10*N_p)) + \
    #     12*ap12*(np.cos(12*E_p))*(np.cosh(12*N_p))


    # q_p=2*ap2*(np.sin(2*E_p))*(np.sinh(2*N_p)) + \
    #     4*ap4*(np.sin(4*E_p))*(np.sinh(4*N_p)) + \
    #     6*ap6*(np.sin(6*E_p))*(np.sinh(6*N_p)) + \
    #     8*ap8*(np.sin(8*E_p))*(np.sinh(8*N_p)) + \
    #     10*ap10*(np.sin(10*E_p))*(np.sinh(10*N_p)) + \
    #     12*ap12*(np.sin(12*E_p))*(np.sinh(12*N_p))

    # # calculate convergence
    # gamma_p=np.arctan((T_p*tanlam)/(((1+T_p*T_p)**.5)))
    # gamma_pp=np.arctan2(q_p,p_p)
    # gamma=gamma_p+gamma_pp

    # # Calculate scale factor
    # sinphi=np.sin(phi)
    # k_p=(1-e*e*sinphi*sinphi)**.5*(1+tanphi*tanphi)**.5 / \
    # (T_p*T_p+coslam*coslam)**.5
    # k_pp=A/a*np.sqrt(p_p*p_p+q_p*q_p)
    # k=k0*k_p*k_pp

    # shift x/y to false origins
    E=X+FalseEasting

    if np.all(h == 'S'):
        N = Y + FalseNorthing  # y in southern hemisphere relative false
                              # northing
    else:
        N = Y

    if trunc_val == 0:
        E = trunc(E, trunc_val)  # x relative to false easting
        N = trunc(N, trunc_val)

    elif trunc_val != None:
        E = trunc(E, trunc_val)  # x relative to false easting
        N = trunc(N, trunc_val)

        # add zero padding
        E = "{:06.0f}".format(E)
        N = "{:07.0f}".format(N)

    return int(zone), h, E, N

# ---------------------------------------------------------------------
# SECTION 2.2: Convert to planetocentric Lat and Lon from LTM


def toLatLon(E, N, zone, h, process_errors=True):
    """Converts LTM easting and northing coordinates to Planetocentric
       LatLon degree values. Eastings, Northings, Zone, and hemisphere
       are needed inputs to complete the inverse conversion. Zone and
       hemisphere must be specified; however, this is to the user to
       specify; This allows forced processing of an adjacent zone.

    Parameters:
    zone            LTM zone                (int,float) scaler
    h               hemisphere              (str) unitless
    E               Eastings                (float,str) meters
    N               Northings               (float,str) meters
    process_errors  Processing flag         (logical): boolean

    Returns:
    lam             Longitude               (float): degrees
    phi             Latitude                (float): degrees

    Raises:
    ValueError: If coordinates are not within the proper LTM range of,
                125,000m ≤ E < 375,000m
                0m ≤ N < 2,500,000m
                The program terminates if latitude is not in
                coverage area.
                """

    if isinstance(E, str):
        E = float(E)
        N = float(N)

    if process_errors:
        if E > 375000:
            raise ValueError("Operation aborted: Easting less than 375km.")
        elif E < 125000:
            raise ValueError("Operation aborted: Easting less than 125km.")
        elif N > 2500000:
            raise ValueError("Operation aborted: Northing exceeds 2,500km")
        elif N < 0:
            raise ValueError("Operation aborted: Northing negative")

    # subtract false origins for the easting and northing values
    X = E - FalseEasting

    if h == 'S':
        Y = N - FalseNorthing  # if in the southern hemisphere
    else:
        Y = N

    # Calculate Unscaled transverse Mercator ratios
    N = X / (k0*A)
    E = Y / (k0*A)

    # Compute the Gauss-Schreiber ratios using Clenshaw summation
    E_p = (E
        - bt2 * np.sin(2*E) * np.cosh(2*N)
        - bt4 * np.sin(4*E) * np.cosh(4*N)
        - bt6 * np.sin(6*E) * np.cosh(6*N)
        - bt8 * np.sin(8*E) * np.cosh(8*N)
        - bt10 * np.sin(10*E) * np.cosh(10*N)
        - bt12 * np.sin(12*E) * np.cosh(12*N))

    N_p = (N
        - bt2 * (np.cos(2*E)) * (np.sinh(2*N))
        - bt4 * (np.cos(4*E)) * (np.sinh(4*N))
        - bt6 * (np.cos(6*E)) * (np.sinh(6*N))
        - bt8 * (np.cos(8*E)) * (np.sinh(8*N))
        - bt10 * (np.cos(10*E)) * (np.sinh(10*N))
        - bt12 * (np.cos(12*E)) * (np.sinh(12*N)))

    sinhN_p = np.sinh(N_p)
    sinE_p = np.sin(E_p)
    cosE_p = np.cos(E_p)

    # Use Newton-Raphson iteration values to solve for Latitude
    T_p = sinE_p / np.sqrt(sinhN_p*sinhN_p + cosE_p*cosE_p)

    dTi = 1.
    Ti = np.zeros(T_p.shape)
    Ti = np.array(T_p)  # deeps copy of array!!

    # For i in range(0,Ti.shape[0])
    i = 0

    while np.abs(dTi) > 1E-12:
        sigmai = np.sinh(e * np.arctanh(e*Ti / np.sqrt(1 + Ti*Ti)))

        Ti_p = Ti * np.sqrt(1 + sigmai*sigmai) - sigmai*np.sqrt(1 + Ti*Ti)

        dTi = ((T_p - Ti_p) / np.sqrt(1 + Ti_p*Ti_p)
                * (1 + (1 - e*e)*Ti*Ti) / ((1 - e*e)*np.sqrt(1 + Ti*Ti)))
        Ti += dTi

        # break
        if i > 50:
            raise ValueError("Operation aborted: latitude iteration "
                             "did not converge")
        i += 1

    T = Ti
    phi = np.arctan(T)

    lam = np.arctan2(sinhN_p, cosE_p)

    # equations are provided for completeness but not required to
    # complete the conversion

    # # convergence: Karney 2011 Eq 26, 27
    # p=1.-2*bt2*(np.cos(2*E))*(np.cosh(2*N)) - \
    #      4*bt4*(np.cos(4*E))*(np.cosh(4*N)) - \
    #      6*bt6*(np.cos(6*E))*(np.cosh(6*N)) - \
    #      8*bt8*(np.cos(8*E))*(np.cosh(8*N)) - \
    #      10*bt10*(np.cos(10*E))*(np.cosh(10*N)) - \
    #      12*bt12*(np.cos(12*E))*(np.cosh(12*N))


    # q=2*bt2*(np.sin(2*E))*(np.sinh(2*N)) + \
    #   4*bt4*(np.sin(4*E))*(np.sinh(4*N)) + \
    #   6*bt6*(np.sin(6*E))*(np.sinh(6*N)) + \
    #   8*bt8*(np.sin(8*E))*(np.sinh(8*N)) + \
    #   10*bt10*(np.sin(10*E))*(np.sinh(10*N)) + \
    #   12*bt12*(np.sin(12*E))*(np.sinh(12*N))

    # gamma_p=np.arctan(np.tan(E_p)*np.tanh(N_p))
    # gamma_pp=np.arctan2(q,p)
    # gamma=gamma_p+gamma_pp

    # # scale: Karney 2011 Eq 28
    # sinphi=np.sin(phi)
    # k_p=(1.-e*e*sinphi*sinphi)**.5*(1 + T*T)**.5\
    #     *(sinhN_p*sinhN_p+ cosE_p*cosE_p)**.5
    # k_pp=A/a/(p*p + q*q)**.5
    # k=k0*k_p*k_pp

    # redetermine the central meridian from the zone provided
    lam0 = np.deg2rad((zone - 1) * (ZoneWidth*2) - 180 + ZoneWidth)
    lam += lam0  # adjust longitude from zonal to global coordinates

    return np.rad2deg(lam), np.rad2deg(phi)  # convert back to degrees

# ---------------------------------------------------------------------
# SECTION 2.3: Calculate meridional radius of curvature


def meridional_radius_of_curvature(phi, phi1, e):
    """Calculates curvature needed to support an ellipsoid for a polar
   stereographic map projection.
    Parameters:
    phi     latitude (float): degrees
    phi1    projection longitudinal reference (float): degrees
    e       ellipsoid eccentricity (float): unitless

    Returns:
    t     (float): Unitless, curvature"""
    pi2 = np.pi/2.
    pi4 = pi2/2.

    if phi1 == np.deg2rad(-90.):  # sign is flipped
        t = np.tan(pi4 - (-phi/2)) / (((1 - e*np.sin(-phi)) / (1 + e*np.sin(-phi)))**(e/2))
    else:
        t = np.tan(pi4 - (phi/2)) / (((1 - e*np.sin(phi)) / (1 + e*np.sin(phi)))**(e/2))
    return t

# ---------------------------------------------------------------------
# SECTION 2.4: Calculate distance from pole to latitude parallel


def ellipsoidal_polar_arc_distance(a, k_0, e, t):
    """Calculates the distance from the pole to the points latitude
    Parameters:
    a       reference surface radius (float): meters
    k0      projection central scale factor (float): unitless
    e       ellipsoid eccentricity (float): unitless
    t       ellipsoid eccentricity (float): unitless

    Returns:
    Rho     (float): meters, Distance from pole to points"""
    pe = (1 + e)
    me = (1 - e)
    ang = np.sqrt((pe**pe) * (me**me))
    rho = 2*a*k_0*t/ang
    return rho

# ---------------------------------------------------------------------
# SECTION 2.5: Calculate polar stereographic ellipsoidal X coordinate


def ellipsoidal_stereographic_map_x(A, phiX, phiX1, lam, lam0, rho=0):
    """Determine the X coordinate for a stereographic map projection.
    Reduced equations are provided for the polar stereographic maps
    as was done in the reference material. See Snyder (1987) for more
    information.

    map projection from a ellipsoid reference surface.
    Parameters:
    A          Gaussian Radius of curvature (float): meters
    phiX       Conformal latitude (float): degrees
    phiX1      Conformal Projection origin latitude (float): degrees
    lam        longitude (float): degrees
    lam0       Projection origin latitude (float): degrees
    rho        Radius from center for projection at {phiX1,lam0}
                (float): unitless

    Returns:
    map_X float: grid Coordinate (float) meters"""

    if phiX1 == np.deg2rad(90.):
        map_x = rho*np.sin(lam - lam0)


    elif phiX1 == np.deg2rad(-90):
        map_x = rho*np.sin(lam - lam0)


    else:
        map_x = A*np.cos(phiX)*np.sin(lam - lam0)

    return map_x

# ---------------------------------------------------------------------
# SECTION 2.6: Calculate polar stereographic ellipsoidal Y coordinate


def ellipsoidal_stereographic_map_y(A, phiX, phiX1, lam, lam0, rho=0):
    """Determines the Y coordinate for a stereographic map projection.
    Reduced equations are provided for the polar stereographic maps
    as was done in the reference material. See Snyder (1987) for more
    information.

    map projection from a ellipsoidal reference surface.
    Parameters:
    A          Gaussian Radius of curvature (float): meters
    phiX       Conformal latitude (float): degrees
    phiX1      Conformal Projection origin latitude (float): degrees
    lam        longitude (float): degrees
    lam0       Projection origin latitude (float): degrees
    rho        Radius from center for projection at {phiX1,lam0}
                (float): unitless

    Returns:
    map_Y float: grid Coordinate (float) meters"""
    # Map Y coordinate

    if phiX1 == 0.:  # equation for equatorial center
        y = A*np.sin(phiX)

    elif phiX1 == np.deg2rad(90.):
        map_y = -rho*np.cos(lam - lam0)

    elif phiX1 == np.deg2rad(-90):
        map_y = rho*np.cos(-lam - lam0)

    else:  # oblique aspects
        ang = np.cos(phiX1)*np.sin(phiX) - np.sin(phiX1)*np.cos(phiX)*np.cos(lam - lam0)
        map_y = A*ang
    return map_y

# ---------------------------------------------------------------------
# SECTION 2.7: Calculate polar stereographic spherical scale error


def polar_stereographic_spherical_scale_err(phi, phi_1, lam, lam0, k_0):
    #scale error in azimuthal projection
    """Determines the map point scale error for a polar stereographic
    map projection from a spheroidal reference surface.
    Parameters:
    phi         latitude (float): degrees
    phi_1       Projection origin latitude (float): degrees
    lam         longitude (float): degrees
    lam0        Projection origin latitude (float): degrees
    k0          Central scale factor, located at {phi_1,lam0}
                (float): unitless

    Returns:
    k float,int: point scale error."""

    if phi_1 == -90:  # South polar stereographic specific function
        k = (2*k_0) / (1 - np.sin(phi))

    elif phi_1 == 90:  # North pole specific function
        k = (2*k_0) / (1 + np.sin(phi))

    # Process all other areas (function can be used for oblique stereographic)
    else:
        k = (2*k_0) / (1 + np.sin(phi_1)*np.sin(phi) + np.cos(phi_1)*np.cos(phi)*np.cos(lam - lam0))
    return k

# ---------------------------------------------------------------------
# SECTION 2.8: Calculate polar stereographic spherical X coordinate


def spherical_stereographic_map_x(phi, phi_1, lam, lam0, R, k):
    """Determines the X coordinate for a stereographic map projection.
    Reduced equations are provided for the polar stereographic maps
    as was done in the reference material. See Snyder (1987) for more
    information.

    map projection from a spheroidal reference surface.
    Parameters:
    phi         latitude (float): degrees
    phi_1       Projection origin latitude (float): degrees
    lam         longitude (float): degrees
    lam0        Projection origin latitude (float): degrees
    R           reference surface radius (float): meters
    k           point scale factor, located at {phi_1,lam0}
                (float): unitless

    Returns:
    map_X float: grid Coordinate."""

    if phi_1 == -90: # south polar stereographic specific function
        map_x = 2*R*k0_polar*np.tan(np.pi/4 + phi/2)*np.sin(lam - lam0)

    elif phi_1==90: # north pole specific function
        map_x = 2*R*k0_polar*np.tan(np.pi/4 - phi/2)*np.sin(lam - lam0)

    else: # Process all other areas
        map_x = R*k*np.cos(phi)*np.sin(lam - lam0)
    return map_x

# ---------------------------------------------------------------------
# SECTION 2.9: Calculate polar stereographic spherical Y coordinate


def spherical_stereographic_map_y(phi, phi_1, lam, lam0, R, k):  # Map Y coordinate
    """Determines the Y coordinate for a stereographic map projection.
    Reduced equations are provided for the polar stereographic maps
    as was done in the reference material. See Snyder (1987) for more
    information.

    map projection from a spheroidal reference surface.
    Parameters:
    phi         latitude (float): degrees
    phi_1       Projection origin latitude (float): degrees
    lam         longitude (float): degrees
    lam0        Projection origin latitude (float): degrees
    R           reference surface radius (float): meters
    k           point scale factor, located at {phi_1,lam0}
                (float): unitless

    Returns:
    map_Y float: grid Coordinate."""

    if phi_1 == -90: # south polar stereographic specific function
        map_y = 2*R*k0_polar*np.tan(np.pi/4 + phi/2)*np.cos(lam - lam0)

    elif phi_1 == 90: # north pole specific function
        map_y = 2*R*k0_polar*np.tan(np.pi/4 - phi/2)*np.cos(lam - lam0)

    else: # Process all other areas 
        ang = np.cos(phi_1)*np.sin(phi) - np.sin(phi_1)*np.cos(phi)\
           * np.cos(lam - lam0)
        map_y = R*k*ang

    return map_y

# ---------------------------------------------------------------------
# SECTION 2.10: Convert to LPS from planetocentric Lat and Lon


def toLPS(lam, phi, trunc_val=1, eqs="Spherical", process_errors=True):
    """Converts Planetocentric LatLon degree values to LPS Easting
       and Northing Coordinates. Latitude and Longitude are the only
       Inputs required. The LPS zone/ hemisphere does not have to be
       specified as a simple test on the coordinates can determine
       the hemisphere. An option is available to truncate the
       coordinates. 1m is the default needed for LPS coordinates
       specifically; however, there will be round off with inverse
       conversions or additional conversions to other coordinates.
       For conversion to a grid systems value, set to 0 for no 
       truncation.

    Parameters:
    lam             Longitude               (float): degrees
    phi             Latitude                (float): degrees
    equations       ellipsoidal or spherical (str): unitless
    trunc_val       Coordinate Precision    (int,float): degrees
    process_errors  Processing flag         (logical): boolean

    Returns:
    h               LTM zone/hemisphere     (str) unitless
    E               Eastings                (float,str) meters
    N               Northings               (float,str) meters

    Raises:
    ValueError: If coordinates are not within a latitude range
                80 to 90 if h=="N" or if
                -90 to -80 if h=="S" or if,
                longitude is not in the -180-180 range.
                Program will terminate if no projection method is
                Specified"""
    
    if process_errors:

        if phi > 90:
            raise ValueError("Operation aborted: Latitude exceeds 90°.")
        elif phi < -90:
            raise ValueError("Operation aborted: Latitude less than -90°.")
        elif lam > 180:
            raise ValueError("Operation aborted: Longitude exceeds 180° "
                             " Try converting from 0°-360° to "
                             "-180°-180° longitude range.")
        
        elif lam < -180:
            raise ValueError("Operation aborted: Longitude is less than 180°")
        elif (phi < 80 and phi > -80):
                raise ValueError("Operation aborted: Latitude outside of "
                                 "LPS Polar projection areas")

    # force -180 to 180. Fixes East West Naming differences in LGRS polar
    # geometrically this is the same point.

    if lam == -180:
        lam = 180

    # Determine the LPS Zone/hemisphere for processing
    if phi >= 80.:
        h = 'N'                 # north hemisphere
        phi1 = np.deg2rad(90.)  # projection origin latitude

    elif phi <= -80.:
        h = 'S'                  # south hemisphere
        phi1 = np.deg2rad(-90.)  # projection origin latitude

    else:
        raise ValueError("Hemisphere could not be determined")

    lam0 = np.deg2rad(0.)  # projection origin longitude

    # Convert degrees to radians
    phi = np.deg2rad(phi)
    lam = np.deg2rad(lam)

    # Snyder (1987) equations for converting to and from
    # polar stereographic. Two methods were provided from Snyder.
    # both are provided here to support a more complex lunar shape
    # if needed in the future. 
    if eqs == "Spherical":    # Snyder (1987) spherical equations
        k = polar_stereographic_spherical_scale_err(phi, phi1, lam, lam0, k0_polar)  # calculate scale factor
        StereoX = spherical_stereographic_map_x(phi, phi1, lam, lam0, a, k)  # determine grid X value
        StereoY = spherical_stereographic_map_y(phi, phi1, lam, lam0, a, k)  # determine grid Y value

    elif eqs == "Ellipsoidal":    # Snyder (1987) ellipsoidal equations
        t = meridional_radius_of_curvature(phi, phi1, e)  # calculate radial curvature
        rho = ellipsoidal_polar_arc_distance(a, k0_polar, e, t)  # calculate distance from center to point
        StereoX = ellipsoidal_stereographic_map_x(a, phi, phi1, lam, lam0, rho)  # determine grid X value
        StereoY = ellipsoidal_stereographic_map_y(a, phi, phi1, lam, lam0, rho)  # determine grid Y value

    else:
        raise ValueError("Operation aborted: Conversion method not "
                         "specified")


    # Add false Eastings and Northings
    StereoX += FalseEasting_polar
    StereoY += FalseNorthing_polar

    if trunc_val == 0:
        StereoX = trunc(StereoX, trunc_val)  # x relative to false easting
        StereoY = trunc(StereoY, trunc_val)

    elif trunc_val != None:
        StereoX = trunc(StereoX, trunc_val)  # x relative to false easting
        StereoY = trunc(StereoY, trunc_val)

        # add zero padding 
        StereoX="{:06.0f}".format(StereoX)
        StereoY="{:06.0f}".format(StereoY)
    # zone is set to an empty value as it is not needed for LPS
    # zone=None

    # Return LPS coordinates to the user.
    return h, StereoX, StereoY

# ---------------------------------------------------------------------
# SECTION 2.11: Inverse calculate meridional radius of curvature


def inv_meridional_radius_of_curvature(rho, e, a, k0, phi1):
    """Calculates curvature needed to support an ellipsoid for a polar
    stereographic map projection
    Parameters:
    rho     distance between pole and point (float): meters
    e       eccentricity (float): unitless
    a       Reference surface semi major radius (float): meters
    k0      map projection central scale factor
    phi1    projection latitude reference (float): degrees

    Returns:
    t     (float): Unitless, curvature"""

    pe = (1 + e)
    me = (1 - e)

    if phi1 == np.deg2rad(-90) or phi1 == np.deg2rad(90):
        t = rho * np.sqrt((pe**pe) * (me**me)) / (2*a*k0)

    else: 
        # requires additional functions beyond the scope of LPS
        raise ValueError("Operation aborted: ellipsoidal curvature "
                         "Not be determined.")
    return t

# ---------------------------------------------------------------------
# SECTION 2.12: Calculate conformal latitude


def ellipsoidal_stereographic_conformal_latitude(phi, e, phi1=0, t=None):
    """Calculates conformal latitude on the ellipsoid from a polar
    stereographic map projection points

    Parameters:
    phi     latitude (float): degrees
    e       eccentricity (float): unitless
    phi1    projection latitude reference (float): degrees

    Function has two states, one for polar and one for oblique
    orientations. 

    Returns:
    X     conformal latitude (float): Unitless"""
    pi2 = np.pi/2.
    pi4 = pi2/2.

    # polar regions phi not needed
    if phi1 == np.deg2rad(90) or phi1 == np.deg2rad(-90):
        X = pi2 - 2*np.arctan(t)

    # equatorial projection regions, phi needed but t is.
    else:
        ang = np.tan(pi4 + (phi/2))*(((1 - e*np.sin(phi))/(1 + e*np.sin(phi)))**(e/2))
        X = 2*np.arctan(ang) - pi2
    return X

# ---------------------------------------------------------------------
# SECTION 2.13: Recover Latitude on an ellipsoid without iteration


def ellipsoidal_stereographic_latitude(phiX, e, phi1X):
    """Recovers latitude on the ellipsoid from a polar 
    stereographic map projection points. Program uses an approximation
    described in Snyder (1987), to avoid iteration. 

    Parameters:
    phiX    conformal latitude (float): degrees
    e       eccentricity (float): unitless
    phi1X   Conformal projection latitude reference (float): degrees

    Returns:
    phi     latitude (float): degrees"""

    phi=(phiX
        + C2*np.sin(2*phiX)
        + C4*np.sin(4*phiX)
        + C6*np.sin(6*phiX)
        + C8*np.sin(8*phiX))

    # assign correct hemispheric location based on map projection
    if phi1X == np.deg2rad(-90):
        return phi * -1
    else:
        return phi

# ---------------------------------------------------------------------
# SECTION 2.14: Recover Longitude on an ellipsoid 


def ellipsoidal_stereographic_longitude(x, y, C_e, rho, phi1X, lam0):  
    """Recovers longitude on the ellipsoid from a polar
    stereographic map projection points. 

    Parameters:
    x       grid coordinate (float): meters
    y       grid coordinate (float): meters
    C_e     Simplified angular distance (float): see Snyder (1987)
            Not needed for polar areas.
    rho     Radius from center for projection at {phiX1,lam0}
                (float): unitless
    phi1X   Conformal projection latitude reference (float): degrees
    lam0    projection longitudinal reference (float): degrees

    Returns:
    lam     longitude (float): degrees"""

    if phi1X == np.deg2rad(-90):
        lam = -lam0+np.arctan2(x, -y)
        lam = np.deg2rad(planetocentric_lon_degrees(
                                    np.rad2deg(-lam + np.deg2rad(180))))

    elif phi1X==np.deg2rad(90): # this needs to be checked
        lam = lam0 + np.arctan2(x, y)
        lam = np.deg2rad(planetocentric_lon_degrees(
                                    np.rad2deg(-lam - np.deg2rad(180))))
    else:
        ang = (x*np.sin(C_e))/\
        (rho*np.cos(phi1X)*np.cos(C_e) - y*np.sin(phi1X)*np.sin(C_e))
        lam = lam0 + np.arctan(ang)

    return lam

# ---------------------------------------------------------------------
# SECTION 2.15: Calculate distance from projection pole to parallel


def Euclidean_distance2D(x, y):
    """Calculates the distance from the pole to the points latitude
    Parameters:
    X      Polar stereographic X coordinate (float): meters
    Y      Polar stereographic Y coordinate (float): meters

    As coordinates are Cartesian, Euclidean distance works here.

    Returns:
    Rho     (float): meters, Distance from pole to points"""

    return (x**2 + y**2)**.5

# ---------------------------------------------------------------------
# SECTION 2.16: Calculate great circle distance from pole to parallel


def polar_stereographic_great_cicle_arc(rho, R, k0):
    """Calculates the distance from the pole to the points latitude
    Parameters:
    Rho     (float): meters, Distance from pole to points
    R       (float): reference surface radius
    k0      Central scale factor, located at {phi_1,lam0}
                (float): unitless
    As coordinates are Cartesian Euclidean distance works here.

    Returns:
    c       (float) great circle arc distance on a sphere"""

    return 2 * np.arctan2(rho, (2*R*k0))

# ---------------------------------------------------------------------
# SECTION 2.17: Recover latitude on a sphere


def spherical_polar_latitude(c, phi_1, y, rho):
    """Determines the longitude from a stereographic map projection.
    Coordinates must be in polar stereographic topocentric coordinates
    See Snyder (1987) for more information.

    map projection inverse conversion for a spherical reference surface.
    Parameters:
    c          great circle distance (float): meters
    phi_1      Projection origin latitude (float): degrees
    y          grid coordinate (float): meters
    rho        distance from the pole to the points latitude {phiX1,lam0}
                (float): unitless

    Returns:
    phi  latitude  (float) degrees"""

    if rho == 0. and c == 0.:
        phi=phi_1
    else:
        ang = ((np.cos(c)*np.sin(phi_1)) + ((y*np.sin(c)*np.cos(phi_1))/rho))
        phi = np.arcsin(ang)

    # this is a logical check to see if the point is the same as the
    # map projection origin. If so then we assign the origin point
    # explicitly
    if np.isnan(phi): 
        phi = phi_1

    return phi

# ---------------------------------------------------------------------
# SECTION 2.18: Recover longitude on a sphere


def spherical_polar_longitude(x, c, rho, phi_1, y, lam0): 
    """Determines the longitude from a stereographic map projection.
    Coordinates must be in polar stereographic topocentric coordinates
    See Snyder (1987) for more information.

    map projection inverse conversion for a spherical reference surface.
    Parameters:
    x           grid Coordinate (float): meters
    c           great circle distance (float): meters
    rho         distance from the pole to the points latitude {phiX1,lam0}
                (float): unitless
    phi_1       Projection origin latitude (float): degrees
    y           grid Coordinate (float): meters
    lam0        Projection origin longitude (float): degrees

    Returns:
    lam  longitude  (float) degrees"""

    if phi_1 == np.deg2rad(90.): # process north pole
        lam = lam0 + np.arctan2(x, (-1*y))

    elif phi_1 == np.deg2rad(-90.):# process south pole
        lam = lam0 + np.arctan2(x,y)

    else: # process all other areas
        ang = np.arctan2((x*np.sin(c)),
            (rho*np.cos(phi_1)*np.cos(c) - y*np.sin(phi_1)*np.sin(c)))
        lam = lam0 + ang

    return lam

# ---------------------------------------------------------------------
# SECTION 2.19: Convert to planetocentric Lat and Lon from LPS


def toLatLon_Polar(E, N, h, eqs="Spherical", process_errors=True):
    """Converts LPS hemisphere, Easting, Northing Coordinates to
       Planetocentric LatLon degree values. Eastings, Northings, Zone,
       and hemisphere. Zone is not needed as the hemisphere is used.

    Parameters:
    zone            LTM zone                (int,float) scaler
    h               hemisphere              (str) unitless
    E               Eastings                (float,str) meters
    N               Northings               (float,str) meters
    process_errors  Processing flag         (logical): boolean

    Returns:
    lon             Longitude               (float): degrees
    lat             Latitude                (float): degrees

    Raises:
    ValueError: If coordinates are not within a proper LPS range of,
                197,000m ≤ E < 805000m
                197,000m ≤ N < 805000m
                Program terminates if latitude does not converge
                """

    if isinstance(E,str):
        E=float(E)
        N=float(N)

    if process_errors:
        if E > 805000:
            raise ValueError("Operation aborted: Easting outside of value range.")
        elif E < 197000:
            raise ValueError("Operation aborted: Easting outside of value range.")
        elif N > 805000:
            raise ValueError("Operation aborted: Northing outside of value range.")
        elif N < 197000:
            raise ValueError("Operation aborted: Northing outside of value range")

    # Determine the LPS Zone/hemisphere for processing, hemisphere is a
    # required argument for processing so we use it here
    if h == 'N': # north polar
        phi1=np.deg2rad(90) # projection reference latitude
    elif h == 'S': # south polar
        phi1 = np.deg2rad(-90) 

    lam0 = np.deg2rad(0.) # projection reference longitude

    # remove false origins
    X = E - FalseEasting_polar
    Y = N - FalseNorthing_polar

    # Snyder (1987) Spherical Equations
    if eqs == "Spherical":
        Rho = Euclidean_distance2D(X, Y) # determine distance from pole to points
        C = polar_stereographic_great_cicle_arc(Rho, a, k0_polar) # calculate arc distance
        phi = spherical_polar_latitude(C, phi1, Y, Rho) # determine latitude
        lam = spherical_polar_longitude(X, C, Rho, phi1, Y, lam0) # determine longitude

    # Snyder (1987) ellipsoidal equations
    elif eqs == "Ellipsoidal":
        rho = Euclidean_distance2D(X, Y) # determine distance from pole to points
        t = inv_meridional_radius_of_curvature(rho, e, a, k0_polar, phi1)
        phiX = ellipsoidal_stereographic_conformal_latitude(None, e, phi1, t)
        phi = ellipsoidal_stereographic_latitude(phiX, e, phi1)
        lam = ellipsoidal_stereographic_longitude(X, Y, 0, rho, phi1, lam0)

    else:
        raise ValueError("Operation aborted: Conversion method not "
                         "specified")

    if lam == -np.pi:
        lam = np.pi

    return np.rad2deg(lam), np.rad2deg(phi)

# ---------------------------------------------------------------------
# SECTION 2.20: Convert to LGRS from LTM


def toLGRS(X, Y, lonBand, h, trunc_val=1 ,process_errors=True):
    """Converts LTM Easting and Northing Coordinates to LGRS coordinate
    of longitude band (LTM zone),latitude band, 25km easting grid letter,
    25km northing grid letter, Easting in 25km grid zone, and Northing
    in 25km grid zone. All LTM coordinates are required for proper
    output. 
    If coordinate is truncated then the coordinate is zero padded
    to the proper string length. if not truncated, the final coordinate
    is left as a floating point.

    Parameters:
    X               LTM Eastings            (float,int) meters
    Y               LTM Northings           (float,int) meters
    lonBand         LTM zone                (int,float) scaler
    h               hemisphere              (str) unitless
    trunc_val       precision               (int,float): meters
    process_errors  Processing flag         (logical): boolean

    Returns:
    lonBand         LGRS zone (LTM zone)    (float) scaler
    latBand         C-X 8° latitude reference (str)
    e25k            25km grid zone easting letter (str)
    n25k            25km grid zone northing letter (str)
    E               25km grid zone easting (str,float) meters
    N               25km grid zone northing (str,float) meters

    Raises:
    ValueError: If coordinates are not within a the proper LTM range of,
                125,000m ≤ E < 375,000m
                0m ≤ N < 2,500,000m
                or has the correct zone
                """
    if process_errors:
        if X > 375000:
            raise ValueError("Operation aborted: Easting less than 375km.")
        elif X < 125000:
            raise ValueError("Operation aborted: Easting less than 125km.")
        elif Y > 2500000:
            raise ValueError("Operation aborted: Northing exceeds 2,500km")
        elif Y < 0:
            raise ValueError("Operation aborted: Northing negative")
        elif lonBand < 1:
            raise ValueError("Operation aborted: Incorrect LTM zone formatting")
        elif lonBand > 45:
            raise ValueError("Operation aborted: Incorrect LTM zone formatting")
    # letter set for latitude zones and 25km grid zones 
    # determined above.
   
    # number of unique letter sets for LGRS
    cols=1
    rows=3

    # global values | false easting and northing values must be applied

    # convert LTM to LatLon to get latitude to determine the correct band
    _,lat=toLatLon(X,Y,lonBand,h,'Lunar')
 
    # grid zones are 8°/10° tall, at 0° N is 10th band: only works w/ 8°
    latBand = latBands[int(np.floor(lat/(2*ZoneWidth) + len(latBands)/2))]
  
    # 25km zones
    col=int(np.floor(X/25E3)) # determine Easting letter index
    row = int(np.floor(Y/25E3) % 20) # determine Northing letter index

    # assign Easting letter by index. Five is subtracted to center the
    # letter reference
    e25k = e25kLetters[int((lonBand-1)%cols)][col-5]

    # assign Northing letter by index
    # rows in zones are A-V, F-E, or L-K.
    n25k = n25kLetters[int((lonBand-1)%rows)][row]

    # truncate easting/northing to within 25km grid square
    E = X % 25E3
    N = Y % 25E3
   
    # truncate to format final output
    if trunc_val != None:
        E = trunc(E,trunc_val,process_errors=True)
        N = trunc(N,trunc_val,process_errors=True)

        # add zero padding to value. Convert to strings to retain vals
        if trunc_val != 0:
            E = "{:05.0f}".format(E)
            N = "{:05.0f}".format(N)

    return lonBand, latBand, e25k, n25k, E, N

# ---------------------------------------------------------------------
# SECTION 2.21: Convert to LGRS from LPS


def toLGRS_polar(E, N, h, trunc_val=1, process_errors=True):
    """Converts LTM Easting and Northing Coordinates to LGRS coordinate
    of longitude band (LTM zone),latitude band, 25km easting grid letter,
    25k northing grid letter, Easting in 25km grid zone, and Northing
    in 25km grid zone on polar regions. All LTM coordinates are required
    for proper output. 
    If coordinate is truncated then the coordinate is zero padded
    to the proper string length. if not truncated, the final coordinate
    is left as a floating point.

    Parameters:
    X               LPS Eastings            (float,str) meters
    Y               LPS Northings           (float,str) meters
    h               hemisphere               (str) unitless
    trunc_val       precision               (int,float): meters
    process_errors  Processing flag         (logical): boolean

    Returns:
    lonBand         LGRS zone A,B,Y,Z    (str) scaler
    e25k            25km grid zone easting letter (str)
    n25k            25km grid zone northing letter (str)
    E               25km grid zone easting (str,float) meters
    N               25km grid zone northing (str,float) meters

    Raises:
    ValueError: If coordinates are not within a proper LPS range of,
                197,000m ≤ E < 805000m
                197,000m ≤ N < 805000m
                Program terminates if coordinates are in the wrong zone
                """
    if isinstance(E,str):
        E=float(E)
        N=float(N)

    if process_errors:
        if E > 805000:
            raise ValueError("Operation aborted: Easting outside of value range.")
        elif E < 197000:
            raise ValueError("Operation aborted: Easting outside of value range.")
        elif N > 805000:
            raise ValueError("Operation aborted: Northing outside of value range.")
        elif N < 197000:
            raise ValueError("Operation aborted: Northing outside of value range")
        elif h not in ["S", "N"]:
            raise ValueError("Operation aborted: Wrong hemisphere provided")

    # lat_band
    # there is no latitude band on the poles 

    # lon_Band
    # determine the longitudinal LGRS zone with logical checks
    if h == 'S':
        if E < FalseEasting_polar :
            lonBand = 'A'
        elif E >= FalseEasting_polar:
            lonBand = 'B'
    elif h == 'N':
        if E < FalseEasting_polar:
            lonBand = 'Y'
        elif E >= FalseEasting_polar:
            lonBand = 'Z'  

    # letter set for 25km grid zones determined above.
    # e25kLetters_polar
    # n25kLetters_polar

    # make coordinates relative to false northing or easting
    X = E - FalseEasting_polar
    Y = N - FalseNorthing_polar
    
    # determine center index value
    centX = (len(e25kLetters_polar) - 1)//2 # this is index 13
    centY = (len(n25kLetters_polar) - 1)//2 # 

    # shift increases from A to the East. Decrements from Z to west
    if lonBand == 'A' or lonBand == 'Y':
        col = int((len(n25kLetters_polar) - 1) - (np.floor(np.abs(X)/25E3)))
        # E-=25E3
    else:
        col = int((np.floor(X/25E3)))
    e25k = e25kLetters_polar[col]

    # add half the letter width to the index to correct position
    # done b/c everything is relative to the center 
    row = int(np.floor(Y/25E3) + centY) + 1

    # added extended range characters
    if row < 0:
        n25k = '-'
    elif row > len(n25kLetters_polar) - 1:
        n25k = '+'
    else:
        n25k = n25kLetters_polar[row]

    # truncate easting/northing to within 25km grid square

    if lonBand == 'A' or lonBand == 'Y':
        E = 25E3-np.abs(X) % 25E3
    else:
        E = np.abs(X) % 25E3
    N = Y % 25E3

    # truncate to format final output
    if trunc_val != None:
        E = trunc(E, trunc_val, process_errors=True)
        N = trunc(N, trunc_val, process_errors=True)

    # add zero padding to value. Convert to strings to retain vals
        if trunc_val != 0:
            E = "{:05.0f}".format(E)
            N = "{:05.0f}".format(N)

    return lonBand, e25k, n25k, E, N

# ---------------------------------------------------------------------
# SECTION 2.22: Convert to LTM from LGRS


def LGRStoLTM(latBand, lonBand, e25k, n25k, E, N, process_errors=True):
    """Converts LGRS coordinate of longitude band (LTM zone),latitude
    band, 25km easting grid letter, 25k northing grid letter, Easting
    in 25km grid zone , and Northing in 25km grid zone to LTM Easting
    and Northing Coordinates. All LGRS coordinates are required for proper
    output. 
    If coordinate is truncated previously there will be some precision
    loss when converting back to LatLon.
    Conversion requires 2LTM function.

    Parameters:

    lonBand         LGRS zone (LTM zone)    (float) scaler
    latBand         C-X 8° latitude reference (str)
    e25k            25km grid zone easting letter (str)
    n25k            25km grid zone northing letter (str)
    E               25km grid zone easting (str,float) meters
    N               25km grid zone northing (str,float) meters

    Returns:
    lonBand         LTM zone                (int,float) scaler
    h               hemisphere              (str) unitless
    X               LTM Eastings            (float,int) meters
    Y               LTM Northings           (float,int) meters

    Raises:
    ValueError: If coordinates are in polar regions or not in 25km range"""

    # convert to float is value was zero padded
    if isinstance(E, str):
        E = float(E)
        N = float(N)

    if process_errors:
        if E > 25000:
            raise ValueError("Operation aborted: Easting greater than 25km.")
        elif E < 0:
            raise ValueError("Operation aborted: Easting grid coordinate negative.")
        elif N > 25000:
            raise ValueError("Operation aborted: Northing greater than 25km")
        elif N < 0:
            raise ValueError("Operation aborted: Northing grid coordinate negative")
        elif lonBand < 1:
            raise ValueError("Operation aborted: Incorrect LTM zone formatting")
        elif lonBand > 45:
            raise ValueError("Operation aborted: Incorrect LTM zone formatting")
        elif latBand in ["A","B","Y","Z"]:
            raise ValueError("Operation aborted: LGRS coordinate is polar")

    # letter set for latitude zones and 25km grid zones 
    # determined above.
   
    # number of unique letter sets for LGRS
    cols = 1
    rows = 3 

    # recover the hemisphere
    h = 'N' if latBand > 'N' else 'S' # ternary argument assignment to
                                  # determine the hemisphere

    # recover easting specified by e25k | +5 To center the letter reference
    col = e25kLetters[int((lonBand-1)%cols)].index(e25k) + 5
    e25kNum = col * 25E3 # add back 25k to easting in meters

    # recover northing specified by n25k
    row = n25kLetters[int((lonBand-1)%rows)].index(n25k)
    n25kNum = row * 25E3 # add back n25k in meters

    # get bottom of latitude band
    latBand = (latBands.index(latBand)-11)*8 # converts to degrees

    # get northing off of bottom of band
    nBand=np.floor(toLTM(ZoneWidth,latBand,zone=None,trunc_val=0)[3]/25E3)*25E3

    # 25km grid square row letters repeat every 500km heading north.
    # Iteratively add back grid letter blocks to scale data to correct position
    n2M = 0 
    while (n2M + n25kNum + N < nBand):
        n2M += 500E3

    # reconstruct positional values
    E=e25kNum + E
    N=n2M + n25kNum + N

    return lonBand, h, E, N

# ---------------------------------------------------------------------
# SECTION 2.23:  Convert to LPS from LGRS


def LGRStoLPS(lonBand, e25k, n25k, E, N, process_errors=True):
    """Converts LGRS coordinate of longitude band (LTM zone),latitude
    band, 25km easting grid letter, 25km northing grid letter, Easting
    in 25km grid zone, and Northing in 25km grid zone to LTM Easting
    and Northing Coordinates. All LGRS coordinates are required for proper
    output. 
    If coordinate is truncated previously there will be some precision
    loss when converting back to LatLon.

    Parameters:

    lonBand         LGRS polar zone (A,B,Y,Z)     (str)
    e25k            25km grid zone easting letter (str)
    n25k            25km grid zone northing letter (str)
    E               25km grid zone easting (str,float) meters
    N               25km grid zone northing (str,float) meters

    Returns:
    h               hemisphere               (str) unitless
    X               LPS Eastings            (float,int) meters
    Y               LPS Northings           (float,int) meters

    Raises:
    ValueError: If coordinates are in polar regions or not in 25km range"""

    # convert to float if value was zero padded
    if isinstance(E, str):
        E = float(E)
        N = float(N)

    if process_errors:
        if E > 25000:
            raise ValueError("Operation aborted: Easting greater than 25km.")
        elif E < 0:
            raise ValueError("Operation aborted: Easting grid coordinate negative.")
        elif N > 25000:
            raise ValueError("Operation aborted: Northing greater than 25km")
        elif N < 0:
            raise ValueError("Operation aborted: Northing grid coordinate negative")
        elif lonBand not in ["A","B","Y","Z"]:
            raise ValueError("Operation aborted: LGRS coordinate is not polar")

    # recover hemisphere
    if lonBand == 'A' or lonBand == 'B':
        h = 'S'
    elif lonBand == 'Y' or lonBand =='Z':
        h = 'N'
    else:
        raise ValueError("Operation aborted: LGRS hemisphere not correct")

    # recover location of 25km grid square lower left corner
    # shifted increases from A to the East. Decrements from Z to west
    if lonBand=='A' or lonBand=='Y':

        # this is the member of cells between center 
        # and the cell in question
        col=(len(e25kLetters_polar)-1)-e25kLetters_polar.index(e25k)+1
        e25kNum = -1*col * 25E3 # add back 25km to easting in meters
        # E=25E3-E
    else:
        col = e25kLetters_polar.index(e25k)
        e25kNum = col * 25E3 # add back 25km to easting in meters

    # recover northing specified by n25k

    # added for extended range characters
    if n25k=='-':
        row=-1-(len(n25kLetters_polar)-1)//2-1
    elif n25k=='+':
        row=len(n25kLetters_polar)-(len(n25kLetters_polar)-1)//2-1
    else:
        # n25k = n25kLetters_polar[row]
        row = n25kLetters_polar.index(n25k)-(len(n25kLetters_polar)-1)//2-1

    n25kNum = row * 25E3 #add back n25k in meters

    # reconstruct relative positional values and add back false origin
    E = e25kNum + E + FalseEasting_polar
    N = n25kNum + N + FalseNorthing_polar

    return h, E, N

# ---------------------------------------------------------------------
# SECTION 2.24: Convert to LGRS in ACC format from LTM


def toLGRS_ACC(X, Y, lonBand, h, trunc_val=10, ACC=True, process_errors=True):
    """Converts LTM Easting and Northing Coordinates to LGRS
    in Artemis Condensed Coordinate (ACC) format. Coordinates are
    a longitude band (LTM zone),latitude band, 25km easting grid letter,
    25k northing grid letter, 1km easting grid letter, 1 km northing
    grid letter, Easting in 1km grid zone truncated to 10m, and
    Northing in 1km grid zone truncated to 10m.
    All LTM coordinates are required for proper output.
    As the coordinate is truncated to 10m the coordinate will
    express some round off during the inverse conversions.
    ACC does not have to be truncated, however, the coordinate
    length will be larger than 6 characters.

    Parameters:
    X               LTM Eastings            (float,int) meters
    Y               LTM Northings           (float,int) meters
    lonBand         LTM zone                (int,float) scaler
    h               hemisphere              (str) unitless
    trunc_val       precision               (int,float): meters
    process_errors  Processing flag         (logical): boolean

    Returns:
    lonBand         LGRS zone (LTM zone)    (float) scaler
    latBand         C-X 8° latitude reference (str)
    e25k            25km grid zone easting letter (str)
    n25k            25km grid zone northing letter (str)
    e1k             1km grid zone easting letter (str)
    n1k             1km grid zone easting letter (str)
    E               1km grid zone easting (str) meters
    N               1km grid zone northing (str) meters

    Raises:
    ValueError: If coordinates are not within a the proper LTM range of,
                125,000m ≤ E < 375,000m
                0m ≤ N < 2,500,000m
                or has the correct zone or if coordinate ACC truncation
                value is not correct
                """

    if process_errors:
        if X > 375000:
            raise ValueError("Operation aborted: Easting less than 375km.")
        elif X < 125000:
            raise ValueError("Operation aborted: Easting less than 125km.")
        elif Y > 2500000:
            raise ValueError("Operation aborted: Northing exceeds 2,500km")
        elif Y < 0:
            raise ValueError("Operation aborted: Northing negative")
        elif lonBand < 1:
            raise ValueError("Operation aborted: Incorrect LTM zone formatting")
        elif lonBand > 45:
            raise ValueError("Operation aborted: Incorrect LTM zone formatting")
        elif ACC == True and trunc_val != 10:
            raise ValueError("Operation aborted: ACC truncation precision "
                             "incorrect. Change to 10m.")

    # letter set for latitude zones, 25km, and 1km grid zones 
    # determined above.
   
    # number of unique letter sets for LGRS
    cols = 1
    rows = 3 

    # global values | false easting and northing values must be applied

    # convert UTM to LatLon to get latitude to determine the correct band
    _,lat = toLatLon(X,Y,lonBand,h,'Lunar')
 
    # grid zones are 8° tall, at 0° N is 10th band: only works w/ 8°
    latBand = latBands[int(np.floor(lat/(2*ZoneWidth)+len(latBands)/2))] 
  
    # 25km zones
    col = int(np.floor(X/25E3)) # determine Easting letter index
    row = int(np.floor(Y/25E3) % 20) # determine Northing letter index

    # assign Easting letter by index. Five is subtracted to center the 
    # letter reference
    e25k = e25kLetters[int((lonBand-1)%cols)][col-5]

    # assign Northing letter by index
    # rows in zones are A-V, F-E, or L-K.
    n25k = n25kLetters[int((lonBand-1)%rows)][row]

    # truncate easting/northing to within 25km grid square
    E = X % 25E3
    N = Y % 25E3

    # generate 1k lettering
    ACC_col = int(np.floor(E/1E3)%25)
    e1k = e1kmLetters[ACC_col]

    # generate 1k lettering
    ACC_row = int(np.floor(N/1E3)%25)
    n1k = n1kmLetters[ACC_row]

    # truncate final easting/northing to within 1km grid square
    E %= 1E3
    N %= 1E3

    # add zero padding to value. Convert to strings to retain vals
    if trunc_val != None:

        if ACC and trunc_val==10: # apply ACC formatting

            # truncate value to 10m
            E = trunc(E, trunc_val, process_errors=True)
            N = trunc(N, trunc_val, process_errors=True)

            # convert to string and apply zero padding
            E = "{:05.0f}".format(E)
            N = "{:05.0f}".format(N)

            # remove last value
            E = E[2:-1]
            N = N[2:-1]

            return e1k, E, n1k, N

        else:
            # truncate to format final output
            E = trunc(E, trunc_val, process_errors=True)
            N = trunc(N, trunc_val, process_errors=True)

            # add zero padding
            if trunc_val!=0:
                E = "{:03.0f}".format(E)
                N = "{:03.0f}".format(N)


        return lonBand, latBand, e25k, n25k, e1k, E, n1k, N

# ---------------------------------------------------------------------
# SECTION 2.25: Convert to LGRS in ACC format from LPS


def toLGRS_polar_ACC(E, N, h, trunc_val=10, ACC=True, process_errors=True):
    """Converts LTM Easting and Northing Coordinates to LGRS coordinate
    in ACC format. Coordinates are a longitude band, 25k easting
    grid letter, 25k northing grid letter, 1km easting grid letter,
    1km northing grid letter, Easting in 1km grid zone truncated to 10m,
    and Northing in 1km grid zone truncated to 10m.

    If coordinate is truncated then the coordinate is zero padded
    to the proper string length. If not truncated, the final coordinate
    is left as a floating point.

    Parameters:
    E               LPS Eastings            (float,int) meters
    N               LPS Northings           (float,int) meters
    h               hemisphere               (str) unitless
    trunc_val       precision               (int,float): meters
    process_errors  Processing flag         (logical): boolean

    Returns:
    lonBand         LGRS zone A,B,Y,Z    (str) scaler
    e25k            25km grid zone easting letter (str)
    n25k            25km grid zone northing letter (str)
    e1k             1km grid zone easting letter (str)
    n1k             1km grid zone northing letter (str)
    E               1km grid zone easting (str,float) meters
    N               1km grid zone northing (str,float) meters

    Raises:
    ValueError: If coordinates are not within a the proper LPS range of,
                197,000m ≤ E < 805000m
                197,000m ≤ N < 805000m
                Program terminates if coordinates are in the wrong zone
                or if the precision for ACC format is not correct.
                """
    if process_errors:
        if E > 805000:
            raise ValueError("Operation aborted: Easting outside of value range.")
        elif E < 197000:
            raise ValueError("Operation aborted: Easting outside of value range.")
        elif N > 805000:
            raise ValueError("Operation aborted: Northing outside of value range.")
        elif N < 197000:
            raise ValueError("Operation aborted: Northing outside of value range")
        elif h not in ["S", "N"]:
            raise ValueError("Operation aborted: Wrong hemisphere provided")
        elif ACC == True and trunc_val != 10:
            raise ValueError("Operation aborted: ACC truncation precision "
                             "incorrect. Change to 10m.")
    # lat_band
    # there is no latitude band on the poles 

    # lon_Band
    # determine the longitudinal LGRS zone with logical checks
    if h == 'S':
        if E < FalseEasting_polar:
            lonBand = 'A'
        elif E >= FalseEasting_polar:
            lonBand = 'B'
    elif h == 'N':
        if E < FalseEasting_polar:
            lonBand = 'Y'
        elif E >= FalseEasting_polar:
            lonBand = 'Z'

    # letter set for 25km and 1km grid zones determined above.

    # make coordinates relative to false northing or easting
    X = E - FalseEasting_polar
    Y = N - FalseNorthing_polar

    # determine number for letter index center
    centX = (len(e25kLetters_polar) - 1)//2 # this is index 13
    centY = (len(n25kLetters_polar) - 1)//2 # 

    # shifted increases from A to the East. Decrements from Z to west
    if lonBand == 'A' or lonBand == 'Y':
        col = int((len(n25kLetters_polar) - 1) - (np.floor(np.abs(X)/25E3)))
    else:
        col = int((np.floor(X/25E3)))
    e25k = e25kLetters_polar[col]

    # add half the letter width to the index to correct position
    # done b/c everything is relative to the center 
    row = int(np.floor(Y/25E3) + centY) + 1

    # added extended range characters
    if row < 0:
        n25k = '-'
    elif row > len(n25kLetters_polar) - 1:
        n25k = '+'
    else:
        n25k = n25kLetters_polar[row]

    # truncate easting/northing to within 25km grid square
    # values are reassigned here
    E = np.abs(X) % 25E3
    N = Y % 25E3

    # Adjustment to the easting at the 1km level
    if lonBand == 'A' or lonBand == 'Y':
        LGRS_col = int((np.floor((25E3 - np.abs(E))/1E3))%25)
    else:
        LGRS_col = int(np.floor((E/1E3)%25))

    e1k = e1kmLetters[LGRS_col]

    # generate 1km northing lettering
    LGRS_row = int((((np.floor(N/1E3)))))
    n1k = n1kmLetters[LGRS_row]

    if lonBand == 'A' or lonBand == 'Y':
        E = (25E3 - np.abs(E))%1E3
    else:
        E %= 1E3
    N %= 1E3

    if trunc_val!=None:
        if ACC and trunc_val == 10: # apply ACC formatting

            # truncate value to 10m
            E = trunc(E, trunc_val, process_errors=True)
            N = trunc(N, trunc_val, process_errors=True)

            # convert to string and apply zero padding
            E = "{:05.0f}".format(E)
            N = "{:05.0f}".format(N)

            # remove last value
            E = E[2:-1]
            N = N[2:-1]
            
            return e1k, E, n1k, N

        else:
            # truncate to format final output
            E = trunc(E, trunc_val, process_errors=True)
            N = trunc(N, trunc_val, process_errors=True)

            # add zero padding
            if trunc_val != 0:
                E = "{:03.0f}".format(E)
                N = "{:03.0f}".format(N)
        # print(lonBand, e25k, n25k, e1k, E, n1k, N)
        return lonBand, e25k, n25k, e1k, E, n1k, N

# ---------------------------------------------------------------------
# SECTION 2.26: Convert to LTM form LGRS in ACC format


def LGRS_ACCtoLTM(latBand, lonBand, e25k, n25k, e1k, E, n1k, N,
                                            ACC=True,process_errors=True):
    """Converts LGRS in ACC format of longitude band (LTM zone),latitude 
    band, 25k easting grid letter, 25k northing grid letter, 
    1k easting grid letter, 1k northing grid letter, Easting in 1km grid zone,
    and Northing in 1km grid zone to LTM Easting and Northing Coordinates.

    All LGRS coordinates are required for proper output.
    If coordinate is truncated previously there will be some precision
    loss when converting back to LatLon.
    Conversion requires 2LTM function.

    Parameters:
    lonBand         LGRS zone (LTM zone)    (float) scaler
    latBand         C-X 8° latitude reference (str)
    e25k            25km grid zone easting letter (str)
    n25k            25km grid zone northing letter (str)
    e1k             1km grid zone easting letter (str)
    n1k             1km grid zone easting letter (str)
    E               1km grid easting (str) meters
    N               1km grid northing (str) meters

    Returns:
    X               LTM Eastings            (float,int) meters
    N               LTM Northings           (float,int) meters
    lonBand         LTM zone                (int,float) scaler
    h               hemisphere              (str) unitless
    trunc_val       precision               (int,float): meters
    process_errors  Processing flag         (logical): boolean

    Raises:
    ValueError: If coordinates are in polar regions or not in 25km range,
                or grid area."""

    # convert to float is value was zero padded or in ACC format
    if ACC:
        E = float(E + "0") # add back ones position and convert to float
        N = float(N + "0") # for processing

    elif isinstance(E, str):
        E = float(E)
        N = float(N)

    if process_errors:
        if E > 25000:
            raise ValueError("Operation aborted: Easting greater than 25km.")
        elif E < 0:
            raise ValueError("Operation aborted: Easting grid coordinate negative.")
        elif N > 25000:
            raise ValueError("Operation aborted: Northing greater than 25km")
        elif N < 0:
            raise ValueError("Operation aborted: Northing grid coordinate negative")
        elif lonBand < 1:
            raise ValueError("Operation aborted: Incorrect LTM zone formatting")
        elif lonBand > 45:
            raise ValueError("Operation aborted: Incorrect LTM zone formatting")
        elif latBand in ["A","B","Y","Z"]:
            raise ValueError("Operation aborted: LGRS coordinate is polar")

    # letter set for latitude zones, 25km, and 1km grid zones 
    # determined above.
   
    # number of unique letter sets for LGRS
    cols = 1
    rows = 3

    # recover the hemisphere
    h = 'N' if latBand > 'N' else 'S' # ternary argument assignment to
                                  # determine the hemisphere
    # recover 1km grid spacing
    AGRS_col = e1kmLetters.index(e1k)
    e1kNum = AGRS_col*1E3

    AGRS_row = n1kmLetters.index(n1k)
    n1kNum = AGRS_row*1E3

    # recover easting specified by e25k | +5 To center the letter reference
    col = e25kLetters[int((lonBand-1)%cols)].index(e25k) + 5 
    e25kNum = col * 25E3 # add back 25k to easting in meters

    # recover northing specified by n25k
    row = n25kLetters[int((lonBand - 1)%rows)].index(n25k)
    n25kNum = row * 25E3 # add back n25k in meters

    # get bottom of latitude band
    latBand = (latBands.index(latBand) - 11)*8 # converts to degrees

    # get northing off of bottom of band,
    nBand=np.floor(toLTM(ZoneWidth,latBand,zone=None,trunc_val=0,process_errors=False)[3]/25E3)*25E3

    # 25km grid square, row letters repeat every 500km heading north.
    # iteratively add back grid letter blocks to scale data to correct position
    n2M = 0 
    while (n2M + n25kNum + N < nBand):
        n2M += 500E3

    # reconstruct positional values
    E = e25kNum + e1kNum + E
    N = n2M + n25kNum + n1kNum + N

    return lonBand, h, E, N

# ---------------------------------------------------------------------
# SECTION 2.27: Convert to LPS from LGRS in ACC format


def LGRS_ACCtoLPS(lonBand, e25k, n25k, e1k, E, n1k, N,
                                            ACC=True, process_errors=True):
    """Converts LGRS ACC formatted grid coordinates to LPS coordinates.

    If coordinate is truncated previously there will be some precision
    loss when converting back to LatLon.

    Parameters:
    lonBand         LGRS zone A,B,Y,Z    (str) scaler
    e25k            25km grid zone easting letter (str)
    n25k            25km grid zone northing letter (str)
    e1k             1km grid zone easting letter (str)
    n1k             1km grid zone northing letter (str)
    E               1km grid zone easting (str,float) meters
    N               1km grid zone northing (str,float) meters

    Returns:
    E               LPS Eastings            (float,int) meters
    N               LPS Northings           (float,int) meters
    h               hemisphere               (str) unitless
    trunc_val       precision               (int,float): meters
    process_errors  Processing flag         (logical): boolean

    Raises:
    ValueError: If coordinates are in polar regions or not in 25km range"""

    # convert to float is value was zero padded
    if ACC:
        E = float(E + "0") # add back ones position and convert to float
        N = float(N + "0") # for processing

    elif isinstance(E, str):
        E = float(E)
        N = float(N)

    if process_errors:
        if E > 25000:
            raise ValueError("Operation aborted: Easting greater than 25km.")
        elif E < 0:
            raise ValueError("Operation aborted: Easting grid coordinate negative.")
        elif N > 25000:
            raise ValueError("Operation aborted: Northing greater than 25km")
        elif N < 0:
            raise ValueError("Operation aborted: Northing grid coordinate negative")
        elif lonBand not in ["A","B","Y","Z"]:
            raise ValueError("Operation aborted: LGRS coordinate is not polar")

    # recover hemisphere
    if lonBand == 'A'or lonBand == 'B':
        h = 'S'
    elif lonBand == 'Y'or lonBand == 'Z':
        h = 'N'
    else:
        raise ValueError("Operation aborted: LGRS hemisphere not correct")

    # recover location of 25km grid square lower left corner
    # shifted increases from A to the East. Decrements from Z to west

    centX = (len(e25kLetters_polar) - 1)//2 
    centY = (len(n25kLetters_polar) - 1)//2 

    # recover location of 25km grid square lower left corner
    # shifted increases from A to the East. Decrements from Z to west
    if lonBand=='A' or lonBand=='Y':

        # this is the member of cells between center 
        # and the cell in question
        col = (len(e25kLetters_polar) - 1) - e25kLetters_polar.index(e25k) + 1
        e25kNum = -1*col * 25E3 # add back 25km to easting in meters
        # E=25E3-E
    else:
        col = e25kLetters_polar.index(e25k)
        e25kNum = col * 25E3 # add back 25km to easting in meters

    # added for extended range characters
    if n25k == '-':
        row = -1 - (len(n25kLetters_polar) -1 )//2 -1
    elif n25k=='+':
        row=len(n25kLetters_polar) - (len(n25kLetters_polar) - 1)//2 -1
    else:
        row = n25kLetters_polar.index(n25k) - (len(n25kLetters_polar) - 1)//2 -1

    n25kNum = row * 25E3 #add back n25k in meters

    # determine 1km spacing from letters
    LGRS_col = e1kmLetters.index(e1k)
    e1kNum = LGRS_col*1E3

    LGRS_row = n1kmLetters.index(n1k)
    n1kNum = LGRS_row*1E3

    # reconstruct relative positional values and  add back false origins
    E = e25kNum + e1kNum + E + FalseEasting_polar
    N = n25kNum + n1kNum + N + FalseNorthing_polar

    return h, E, N

# ---------------------------------------------------------------------
# SECTION 2.28: Convert planetocentric latitude to colatitude


def planetocentric_lat_degrees(colat):
    """convert points from colatitude 0-180 to 90--90 degrees.
    Parameters
    colat   0-180 longitude (float): degrees 

    Returns 
    lat  -90-90 latitude (float): degrees

    """
    return 90. - colat

# ---------------------------------------------------------------------
# SECTION 2.29: Convert planetocentric colatitude to latitude
def planetocentric_colat_degrees(lat):
    """convert points from colatitude 90--90 to 0-180 degrees.
    Parameters 
    colat 0-180 longitude (float): degrees

    Returns 
    lat  -90-90 latitude (float): degrees
    """
    return -1*(lat - 90.)

# ---------------------------------------------------------------------
# SECTION 2.30: Convert planetocentric longitude to colongitude


def planetocentric_colon_degrees(lon): # 0-360
    """convert points from -180 to 180 to 0-360 degrees.
    Parameters 
    lon   -180-180 longitude (float): degrees

    Returns 
    colon   0-360 longitude (float): degrees
    """
    return (lon) % 360.

# ---------------------------------------------------------------------
# SECTION 2.31: Convert planetocentric colongitude to longitude


def planetocentric_lon_degrees(colon): # -180 - 180
    """convert points from 0-360 degrees to -180 to 180.
    Parameters 
    colon   0-360 longitude (float): degrees
    """
    return ((colon + 540.)%360) - 180.

# ---------------------------------------------------------------------
# SECTION 2.32: Convert degrees to decimal minutes


def degrees_to_decimal_minutes(degrees):
    """converts degrees to decimal minutes:
    Parameters:
    degrees       (float,int): degrees

    Returns:
    degrees       (float,int): decimal degrees
    minutes       (float,int): degrees(min)"""

    # Extract the integer part (deg) and the fractional part (min)
    deg = int(degrees)
    minutes = (degrees - deg) * 60

    return deg, minutes

# ---------------------------------------------------------------------
# SECTION 2.33: Convert decimal minutes to degrees


def decimal_minutes_to_degrees(degrees, minutes):
    """converts decimal minutes to degrees:
    Parameters:
    degrees       (float,int): decimal degrees
    minutes       (float,int): degrees(min)

    Returns:
    degrees       (float,int): degrees"""

    # Calculate the degrees in decimal format
    degrees_decimal = degrees + minutes / 60

    return degrees_decimal

# ---------------------------------------------------------------------
# SECTION 2.34: Convert degrees to decimal seconds


def degrees_to_decimal_seconds(degrees):
    """converts  degrees to decimal seconds :
    Parameters:
    degrees (float): decimal degrees

    Returns:
    degrees       (float,int): degrees
    minutes       (float,int): degrees(min)
    seconds       (float): degrees(sec)"""

    # Extract the integer part (deg) and the fractional part (min)
    deg = int(degrees)
    minutes_decimal = (degrees - deg) * 60

    # Extract the integer part (min) and the fractional part (sec)
    minutes = int(minutes_decimal)
    seconds = (minutes_decimal - minutes) * 60

    return deg, minutes, seconds

# ---------------------------------------------------------------------
# SECTION 2.35: Convert decimal seconds to degrees


def decimal_seconds_to_degrees(degrees, minutes, seconds):
    """converts decimal seconds to degrees:
    degrees       (float,int): degrees
    minutes       (float,int): degrees(min)
    seconds       (float,int): degrees(sec)

    Returns:
    float: decimal degrees"""

    # Calculate the degrees in decimal format
    degrees_decimal = degrees + minutes / 60 + seconds / 3600

    return degrees_decimal

# ---------------------------------------------------------------------
# SECTION 2.36: Formula to truncate coordinates
# If difference between coordinate and nearest whole number is less than
# 1mm, ie .001 or .999 we round


def check_decimal_round(value, tolerance=0.001):
    """Assists the truncation function on the south pole.
    often the truncation value forces a round down because of the
    roundoff error. This dependence forces a round if the coordinate
    is within 1mm of the nearest whole value coordinate. 
    Parameters:
    val       (float,int): meters
    tolerance (float,int): meters

    Returns:
    val, (float): The result of rounding if within 1mm
    """
    rounded_value = round(value)
    if abs(value - rounded_value) < tolerance:
        return round(value)
    else:
        return value

def trunc(val, precision,process_errors=True):
    """Truncates value to the desired precision
    Parameters:
    val       (float,int): meters
    precision (float,int): meters

    Returns:
    float,int: The result of the truncation operation.
               Value not processed if precision is 0

    Raises:
    ValueError: If the precision is not a multiple of 10."""

    if process_errors:
        if precision not in [0,1,10,100,1000,10000,
                                100000,1000000,10000000]:
            raise ValueError("Operation Aborted: Truncation is only "
                             "allowed for multiples of 10.")

    if precision == 0:
        return val
    else:
        val=check_decimal_round(val, tolerance=0.001)
        return float(int(val/precision)*precision)


# =====================================================================
# SECTION 3: MAIN PROGRAM 
    # SECTION 3.1: Importing system variables for processing
    # SECTION 3.2: Converting Coordinates
    # SECTION 3.2.1: LATLON CONVERSIONS 
        # SECTION 3.2.2:LTM CONVERSIONS
        # SECTION 3.2.3: LPS CONVERSIONS
        # SECTION 3.2.4: LGRS CONVERSIONS
        # SECTION 3.2.4: LGRS ACC CONVERSIONS
    # SECTION 3.3: Exporting data

# ---------------------------------------------------------------------
# SECTION 3.1: Importing system variables for processing


def main(switch, trunc_val, condensed=True):
    """ Complete conversions between LTM, LPS, LGRS, LGRS in ACC, and
        LatLon. This function is designed to accommodate shell scripting,
        All other equations should be able to be utilized in Python. 
        Specify switch statement variable to continue:\n"LatLon2LTM\n"
        "LatLon2LPS\n""LatLon2LGRS\n""LatLon2PolarLGRS\n"
        "LatLon2LGRS_ACC\n""LatLon2PolarLGRS_ACC\n""LatLon2ACC\n"
        "LatLon2Polar_ACC\n""LTM2LatLon\n""LTM2LGRS\n""LTM2LGRS_ACC\n"
        "LTM2ACC\n""LPS2LatLon\n""LPS2PolarLGRS\n""LPS2PolarLGRS_ACC\n"
        "LPS2ACC\n""LGRS2LTM\n""PolarLGRS2LPS\n""LGRS2LatLon\n"
        "PolarLGRS2LatLon\n""LGRS_ACC2LatLon\n""PolarLGRS_ACC2LatLon\n"
        "LGRS_ACC2LTM\n""PolarLGRS_ACC2LPS\n")"""

    #  argument formats
    form_in = switch.split("2")[0] #input argument format
    form_out = switch.split("2")[1] # output argument format

    # input coordinates
    try:
        if condensed:
            if  form_in == "LatLon":
                if len(sys.argv)-1 == 3:
                    lat = float(sys.argv[2])
                    lon = float(sys.argv[3])
                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                    "Input for LatLon:\nLat\nLon")

            # LTM:        zone,h,E,N,
            elif form_in == "LTM":
                if len(sys.argv)-1 == 2:
                    zone, h, E, _, N, _ = list(re.findall(LTM_pattern,sys.argv[2])[0])
                    zone = int(zone)
                    h = str(h)
                    E = float(E)
                    N = float(N)

                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                    "Input for Condensed LTM: "
                                    "\nzone\{1-45\}\nh\{N|S\}\n00000E\n00000N.")
            # LPS:        h,E,N
            elif form_in == "LPS":
                if len(sys.argv)-1 == 2:
                    h, E, _, N, _ = list(re.findall(LPS_pattern,sys.argv[2])[0])
                    h = str(h)
                    E = float(E)
                    N = float(N)

                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                    "Input for Condensed LPS:"
                                    "\nh\{N|S\}\n00000E\n00000N.")

            # LGRS:       lonBand,latBand,e25k,n25k,E,N
            elif form_in=="LGRS":
                if len(sys.argv)-1 == 2:
                    lonBand, latBand, e25k, n25k, E, N = list(re.findall(LGRS_pattern,sys.argv[2])[0])
                    lonBand = int(lonBand)
                    latBand = str(latBand)
                    e25k = str(e25k)
                    n25k = str(n25k)
                    E = float(E)
                    N = float(N)
                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                "Input for Condensed LGRS: "
                                "\nlonBand\{1-45\}\nlatBand\{N|S\}\n"
                                "e25k\{A-Z\}\nn25k\{A-Z\}\nE{00000}\nN{00000}")
            # Polar_LGRS  lonBand,e25k,n25k,E,N
            elif form_in == "PolarLGRS":
                if len(sys.argv)-1 == 2:
                    lonBand, e25k, n25k, E, N = list(re.findall(PolarLGRS_pattern,sys.argv[2])[0])

                    lonBand = str(lonBand)
                    e25k = str(e25k)
                    n25k = str(n25k)
                    E = float(E)
                    N = float(N)

                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                    "Input for Condensed Polar LGRS: "
                                "\nlatBand\{N|S\}\ne25k\{A-Z\}\nn25k\{A-Z\}"
                                "\nE{00000}\nN{00000}")
            # LGRS_ACC:         lonBand,latBand,e25k,n25k,e1k,E,n1k,N
            elif form_in == "LGRS_ACC":
                if len(sys.argv)-1 == 2:
                    lonBand, latBand, e25k, n25k, e1k, E, n1k, N=list(re.findall(LGRS_ACC_pattern,sys.argv[2])[0])

                    lonBand = int(lonBand)
                    latBand = str(latBand)
                    e25k = str(e25k)
                    n25k = str(n25k)
                    e1k = str(e1k)
                    E = float(E)
                    n1k = str(n1k)
                    N = float(N)
                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                     "Input for Condensed LGRS_ACC: "
                                "\nlonBand\{1-45\}\nlatBand\{N|S\}\n"
                                "e25k\{A-Z\}\nn25k\{A-Z\}\nE{00000}\nN{00000}"
                    "Input for LGRS_ACC:\nlonBand\nlatBand\ne25k\nn25k\ne1k\nn1k\nE\nN")

            elif form_in == "PolarLGRS_ACC":
                if len(sys.argv)-1 == 2:
                    lonBand, e25k, n25k, e1k, E, n1k, N=list(re.findall(PolarLGRS_ACC_pattern,sys.argv[2])[0])

                    lonBand=str(lonBand)
                    e25k=str(e25k)
                    n25k=str(n25k)
                    e1k=str(e1k)
                    E=float(E)
                    n1k=str(n1k)
                    N=float(N)
                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                    "Input for PolarLGRS_ACC:\nlonBand\ne25k\nn25k\ne1k\nn1k\nE\nN")
            else:
                raise IndexError("Operation aborted: Input failed")

        elif not condensed:
            # LatLon:     lon,lat,
            if  form_in == "LatLon":
                if len(sys.argv)-1 == 3:
                    lat=float(sys.argv[2])
                    lon=float(sys.argv[3])
                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                    "Input for LatLon:\nLat\nLon")
            # LTM:        zone,h,E,N,
            elif form_in == "LTM":
                if len(sys.argv)-1 == 5:
                    zone = int(sys.argv[2])
                    h = str(sys.argv[3])
                    E = float(sys.argv[4])
                    N = float(sys.argv[5])
                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                    "Input for LTM:\nzone\nh\nE\nN")
            # LPS:        h,E,N
            elif form_in == "LPS":
                if len(sys.argv)-1 == 4:
                    h = str(sys.argv[2])
                    E = float(sys.argv[3])
                    N = float(sys.argv[4])
                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                    "Input for LPS:\nh\nE\nN")
            # LGRS:       lonBand,latBand,e25k,n25k,E,N
            elif form_in == "LGRS":
                if len(sys.argv)-1 == 7:
                    lonBand = int(sys.argv[2])
                    latBand = str(sys.argv[3])
                    e25k = str(sys.argv[4])
                    n25k = str(sys.argv[5])
                    E = float(sys.argv[6])
                    N = float(sys.argv[7])
                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                "Input for LGRS:\nlonBand\nlatBand\ne25k\nn25k\nE\nN")
            # Polar_LGRS  lonBand,e25k,n25k,E,N
            elif form_in == "PolarLGRS":
                if len(sys.argv)-1 == 6:
                    lonBand = str(sys.argv[2])
                    e25k = str(sys.argv[3])
                    n25k = str(sys.argv[4])
                    E = float(sys.argv[5])
                    N = float(sys.argv[6])
                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                                "Input for PolarLGRS:\nlonBand\ne25k\nn25k\nE\nN")
            # LGRS_ACC:         lonBand,latBand,e25k,n25k,e1k,E,n1k,N
            elif form_in == "LGRS_ACC":
                if len(sys.argv)-1 == 9:
                    lonBand = int(sys.argv[2])
                    latBand = str(sys.argv[3])
                    e25k = str(sys.argv[4])
                    n25k = str(sys.argv[5])
                    e1k = str(sys.argv[6])
                    E = float(sys.argv[7])
                    n1k = str(sys.argv[8])
                    N = float(sys.argv[9])
                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                    "Input for LGRS_ACC:\nlonBand\nlatBand\ne25k\nn25k\ne1k\nn1k\nE\nN")
            elif form_in == "PolarLGRS_ACC":
                if len(sys.argv)-1 == 8:
                    lonBand = str(sys.argv[2])
                    e25k = str(sys.argv[3])
                    n25k = str(sys.argv[4])
                    e1k = str(sys.argv[5])
                    E = float(sys.argv[6])
                    n1k = str(sys.argv[7])
                    N = float(sys.argv[8])

                else:
                    raise IndexError("Operation aborted: Number of inputs not correct."
                    "Input for PolarLGRS_ACC:\nlonBand\ne25k\nn25k\ne1k\nn1k\nE\nN")
            else:
                raise IndexError("Operation aborted: Input failed")
        else:
            raise IndexError("Coordinate style could not be determined."
                             "Please specify if coordinates are condensed "
                             "or not. (Note this is not ACC formatting).")

    except IndexError as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        print(e)
        exit(1)



# ---------------------------------------------------------------------
# SECTION 3.2: Converting Coordinates

    try:
        # SECTION 3.2.1: LATLON CONVERSIONS
        # Convert Planetocentric LatLon to LTM
        if switch == "LatLon2LTM":

            zone, h, E, N = toLTM(lon, lat,
                            zone=None,
                            trunc_val=trunc_val,
                            process_errors=True)

        # Convert Planetocentric LatLon to LPS
        elif switch == "LatLon2LPS":

            h, E, N = toLPS(lon, lat,
                        trunc_val=trunc_val,
                        eqs="Spherical",
                        process_errors=True)

        # Convert Planetocentric LatLon to LGRS
        elif switch == "LatLon2LGRS":

            zone, h, E1, N1 = toLTM(lon, lat,
                                zone=None,
                                trunc_val=0,
                                process_errors=True)

            lonBand, latBand, e25k, n25k, E, N=toLGRS(E1, N1, zone, h,
                                                    trunc_val=trunc_val,
                                                    process_errors=True)

        # Convert Planetocentric LatLon to Polar LGRS
        elif switch == "LatLon2PolarLGRS":

            h, E1, N1 = toLPS(lon, lat,
                            trunc_val=0,
                            eqs="Spherical",
                            process_errors=True)

            lonBand, e25k, n25k, E, N=toLGRS_polar(E1, N1, h,
                                                trunc_val=trunc_val,
                                                process_errors=True)

        # Convert Planetocentric LatLon to LGRS in ACC
        elif switch == "LatLon2LGRS_ACC":

            zone, h, E1, N1 = toLTM(lon, lat,
                                zone=None,
                                trunc_val=0,
                                process_errors=True)

            lonBand, latBand, e25k, n25k, e1k, E, n1k, N = toLGRS_ACC(E1, N1, zone, h,
                                                                trunc_val=trunc_val,
                                                                ACC=False,
                                                                process_errors=True)

        # Convert Planetocentric LatLon to Polar LGRS in ACC
        elif switch == "LatLon2PolarLGRS_ACC":

            h, E1, N1 = toLPS(lon, lat,
                            trunc_val=0,
                            eqs="Spherical",
                            process_errors=True)

            lonBand, e25k, n25k, e1k, E, n1k, N = toLGRS_polar_ACC(E1, N1, h,
                                                            trunc_val=trunc_val,
                                                            ACC=False,
                                                            process_errors=True)

        # Convert Planetocentric LatLon to ACC
        elif switch == "LatLon2ACC":

            zone, h, E1, N1 = toLTM(lon, lat,
                                zone=None,
                                trunc_val=0,
                                process_errors=True)

            e1k, E, n1k, N = toLGRS_ACC(E1, N1, zone, h,
                                    trunc_val=10,
                                    ACC=True,
                                    process_errors=True)

        # Convert Planetocentric LatLon to Polar ACC
        elif switch == "LatLon2Polar_ACC":

            # ACC formatted only
            h, E1, N1 = toLPS(lon, lat,
                            trunc_val=0,
                            eqs="Spherical",
                            process_errors=True)

            e1k, E, n1k, N = toLGRS_polar_ACC(E1, N1, h,
                            trunc_val=10,
                            ACC=True,
                            process_errors=True)

        #SECTION 3.2.2:LTM CONVERSIONS
        # Convert LTM to Planetocentric LatLon
        elif switch == "LTM2LatLon":

            lon, lat = toLatLon(E, N, zone, h,
                                process_errors=True)

        # LTM to LGRS
        elif switch == "LTM2LGRS":

            lonBand, latBand, e25k, n25k, E, N = toLGRS(E, N, zone, h,
                                                    trunc_val=trunc_val,
                                                    process_errors=True)

        # LTM to ACC LGRS 
        elif switch == "LTM2LGRS_ACC":

            lonBand, latBand, e25k, n25k, e1k, E, n1k, N = toLGRS_ACC(E, N, zone, h,
                                                                trunc_val=trunc_val,
                                                                ACC=False,
                                                                process_errors=True)

        # LTM to ACC  
        elif switch == "LTM2ACC":

            e1k, E, n1k, N = toLGRS_ACC(E, N, zone, h,
                                    trunc_val=10,
                                    ACC=True,
                                    process_errors=True)

        # SECTION 3.2.3: LPS CONVERSIONS
        # Convert LPS to Planetocentric LatLon
        elif switch == "LPS2LatLon":

            lon, lat = toLatLon_Polar(E, N, h,
                                    eqs="Spherical",
                                    process_errors=True)

        # LPS to LGRS
        elif switch == "LPS2PolarLGRS":

            lonBand, e25k, n25k, E, N = toLGRS_polar(E, N, h,
                                                trunc_val=trunc_val,
                                                process_errors=True)

        # LPS to LGRS ACC
        elif switch == "LPS2PolarLGRS_ACC":

            # ACC formatted
            lonBand, e25k, n25k, e1k, E, n1k, N = toLGRS_polar_ACC(E, N, h,
                                                            trunc_val=trunc_val,
                                                            ACC=False,
                                                            process_errors=True)

        # LPS to ACC  
        elif switch == "LPS2ACC":

            # ACC formatted
            e1k, E, n1k, N = toLGRS_polar_ACC(E, N, h,
                                            trunc_val=10,
                                            ACC=True,
                                            process_errors=True)

        # SECTION 3.2.4: LGRS CONVERSIONS
        # LGRS to Convert Planetocentric LatLon
        elif switch == "LGRS2LatLon":

            zone, h, E, N = LGRStoLTM(latBand, lonBand, e25k, n25k, E, N)

            lon, lat = toLatLon(E, N, zone, h, process_errors=True)

        # LGRS to LTM
        elif switch == "LGRS2LTM":

            zone, h, E, N = LGRStoLTM(latBand, lonBand, e25k, n25k, E, N)

        # LGRS to LPS
        elif switch == "PolarLGRS2LPS":

            h, E, N = LGRStoLPS(lonBand, e25k, n25k, E, N, process_errors=True)

        #Convert Polar LGRS to  Planetocentric polar LatLon
        elif switch == "PolarLGRS2LatLon":

            h, E1, N1 = LGRStoLPS(lonBand, e25k, n25k, E, N, process_errors=True)

            lon, lat =toLatLon_Polar(E1, N1, h, 
                                    eqs="Spherical", 
                                    process_errors=True)

        elif switch == "LGRS2LGRS_ACC":

            zone, h, E1, N1 = LGRStoLTM(latBand, lonBand, e25k, n25k, E, N)

            lonBand, latBand, e25k, n25k, e1k, E, n1k, N = toLGRS_ACC(E1, N1, zone, h,
                                                                trunc_val=trunc_val,
                                                                ACC=False,
                                                                process_errors=True)

        elif switch == "LGRS2ACC":

            zone, h, E1, N1 = LGRStoLTM(latBand, lonBand, e25k, n25k, E, N)

            e1k, E, n1k, N = toLGRS_polar_ACC(E1, N1, h,
                                            trunc_val=10,
                                            ACC=True,
                                            process_errors=True)

        elif switch == "PolarLGRS2Polar_ACC":

            h, E1, N1 = LGRStoLPS(lonBand, e25k, n25k, E, N, process_errors=True)

            e1k, E, n1k, N = toLGRS_polar_ACC(E1, N1, h,
                                            trunc_val=10,
                                            ACC=True,
                                            process_errors=True)

        elif switch == "PolarLGRS2PolarLGRS_ACC":

            h,E1,N1 = LGRStoLPS(lonBand, e25k, n25k, E, N, process_errors=True)
            lonBand,e25k,n25k,e1k,E,n1k,N = toLGRS_polar_ACC(E1, N1, h, 
                                                            trunc_val=trunc_val,
                                                            ACC=False,
                                                            process_errors=True)

        #SECTION 3.2.4: LGRS ACC CONVERSIONS
        # LGRS ACC to Convert Planetocentric LatLon
        elif switch == "LGRS_ACC2LatLon":

            zone, h, E1, N1 = LGRS_ACCtoLTM(latBand, lonBand, e25k, n25k, e1k, E, n1k, N,
                                        ACC=False,
                                        process_errors=True)

            lon, lat = toLatLon(E1, N1, zone, h, process_errors=True)

        #  Convert Polar LGRS ACC to Planetocentric LatLon 
        elif switch == "PolarLGRS_ACC2LatLon":
            h, E, N = LGRS_ACCtoLPS(lonBand, e25k, n25k, e1k, E, n1k, N,
                                ACC=False,
                                process_errors=True)
            lon, lat = toLatLon_Polar(E, N, h, 
                                    eqs="Spherical",
                                    process_errors=True)

        #  ACC LGRS to LTM 
        elif switch == "LGRS_ACC2LTM":
            zone, h, E, N = LGRS_ACCtoLTM(latBand, lonBand, e25k, n25k, e1k, E, n1k, N,
                                        ACC=False,
                                        process_errors=True)

        elif switch == "LGRS_ACC2LGRS":

            zone, h, E1, N1 = LGRS_ACCtoLTM(latBand, lonBand, e25k, n25k, e1k, E, n1k, N, 
                                        ACC=False,
                                        process_errors=True)

            lonBand, latBand, e25k, n25k, E, N = toLGRS(E1, N1, zone, h,
                                                trunc_val=trunc_val,
                                                process_errors=True)

        # LGRS ACC to LPS 
        elif switch == "PolarLGRS_ACC2LPS":

            h, E, N=LGRS_ACCtoLPS(lonBand, e25k, n25k, e1k, E, n1k ,N,
                                ACC=False,
                                process_errors=True) 

        elif switch == "PolarLGRS_ACC2PolarLGRS":

            h, E1, N1 = LGRS_ACCtoLPS(lonBand, e25k, n25k, e1k, E, n1k, N,
                                    ACC=False,
                                    process_errors=True) 

            lonBand, e25k, n25k, E, N = toLGRS_polar(E1, N1, h,
                                                trunc_val=trunc_val,
                                                process_errors=True)

        # flag warnings 
        else:
            raise ValueError("Operation aborted: Forward Conversion Method Not Specified.")

    # print faults
    except ValueError as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        print(e)
        exit(1)


# ---------------------------------------------------------------------
# SECTION 3.3: Exporting data

    try:
        if condensed:
            if  form_out == "LatLon":
                Coordinate_out = '{}°{}°'.format(lat, lon)
            elif form_out == "LTM":
                Coordinate_out = '{}{}{}E{}N'.format(zone, h, E, N)
            elif form_out == "LPS":
                Coordinate_out = '{}{}E{}N'.format(h, E, N)
            elif form_out == "LGRS":
                Coordinate_out = '{}{}{}{}{}{}'.format(lonBand, latBand, e25k, n25k,
                                                        E, N)
            elif form_out == "PolarLGRS":
                Coordinate_out = '{}{}{}{}{}'.format(lonBand, e25k, n25k, E, N)
            elif form_out == "LGRS_ACC":
                Coordinate_out = '{}{}{}{}{}{}{}{}'.format(lonBand, latBand,
                                                        e25k, n25k, e1k, E, n1k, N)
            elif form_out == "PolarLGRS_ACC":
                Coordinate_out = '{}{}{}{}{}{}{}'.format(lonBand, e25k, n25k, e1k, E,
                                                        n1k, N)
            elif form_out == "ACC" or form_out == "Polar_ACC":
                Coordinate_out = '{}{}{}{}'.format(e1k, E, n1k, N)
            else:
                raise ValueError("Operation aborted: output failed")
        else:
            if  form_out == "LatLon":
                Coordinate_out = '{} {}'.format(lat, lon)
            elif form_out == "LTM":
                Coordinate_out = '{} {} {} {}'.format(zone, h, E, N)
            elif form_out == "LPS":
                Coordinate_out = '{} {} {}'.format(h, E, N)
            elif form_out == "LGRS":
                Coordinate_out = '{} {} {} {} {} {}'.format(lonBand, latBand, e25k, 
                                                                n25k, E, N)
            elif form_out == "PolarLGRS":
                Coordinate_out = '{} {} {} {} {}'.format(lonBand, e25k, n25k, E, N)
            elif form_out == "LGRS_ACC":
                Coordinate_out = '{} {} {} {} {} {} {} {}'.format(lonBand, latBand, 
                                                e25k, n25k, e1k, E, n1k, N)
            elif form_out == "PolarLGRS_ACC":
                Coordinate_out = '{} {} {} {} {} {} {}'.format(lonBand,
                                                e25k, n25k, e1k, E, n1k, N)
            elif form_out == "ACC" or form_out == "Polar_ACC":
                Coordinate_out = '{} {} {} {}'.format(e1k, E, n1k, N)
            else:
                raise ValueError("Operation aborted: output failed")

        print(Coordinate_out)

    except ValueError as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        print(e)
        exit(1)


# ---------------------------------------------------------------------
# Print program timing and elapsed time
    if info:
        EndTime = datetime.datetime.now()
        print('\n', ProgName, 'execution time')
        print('    Start Time:', StartTime)
        print('    End Time:  ', EndTime)
        print('    Run Time:  ', EndTime - StartTime)


# =====================================================================
# Run main program

# determine input argument format

info = False
trunc_val = 1
condensed = True

if info:
    StartTime = datetime.datetime.now()
    print('Program:', ProgName)

try:
    Method = sys.argv[1]
except IndexError:
    Method = None
    if info:
        print("No conversion method provided.")


# run conversion
try:
    if Method in ["LatLon2LTM",
                  "LatLon2LPS",
                  "LatLon2LGRS",
                  "LatLon2PolarLGRS",
                  "LatLon2LGRS_ACC",
                  "LatLon2PolarLGRS_ACC",
                  "LatLon2ACC",
                  "LatLon2Polar_ACC",
                  "LTM2LatLon",
                  "LTM2LGRS",
                  "LTM2LGRS_ACC",
                  "LTM2ACC",
                  "LPS2LatLon",
                  "LPS2PolarLGRS",
                  "LPS2PolarLGRS_ACC",
                  "LPS2ACC",
                  "LGRS2LTM",
                  "PolarLGRS2LPS",
                  "LGRS2LatLon",
                  "PolarLGRS2LatLon",
                  "LGRS_ACC2LatLon",
                  "PolarLGRS_ACC2LatLon",
                  "LGRS_ACC2LTM",
                  "PolarLGRS_ACC2LPS",
                  "LGRS2LGRS_ACC",
                  "PolarLGRS2PolarLGRS_ACC",
                  "LGRS2ACC",
                  "PolarLGRS2Polar_ACC",
                  "LGRS_ACC2LGRS",
                  "PolarLGRS_ACC2PolarLGRS"]:

        initialize_LGRS_function_globals()
        main(Method, trunc_val, condensed)

    else:
        raise ValueError("Operation aborted: Conversion Method Not Specified "
                         "Correctly.\n Select one of the following:\n"
                         "LatLon2LTM\n"
                         "LatLon2LPS\n"
                         "LatLon2LGRS\n"
                         "LatLon2PolarLGRS\n"
                         "LatLon2LGRS_ACC\n"
                         "LatLon2PolarLGRS_ACC\n"
                         "LatLon2ACC\n"
                         "LatLon2Polar_ACC\n"
                         "LTM2LatLon\n"
                         "LTM2LGRS\n"
                         "LTM2LGRS_ACC\n"
                         "LTM2ACC\n"
                         "LPS2LatLon\n"
                         "LPS2PolarLGRS\n"
                         "LPS2PolarLGRS_ACC\n"
                         "LPS2ACC\n"
                         "LGRS2LTM\n"
                         "LGRS2LatLon\n"
                         "LGRS_ACC2LTM\n"
                         "LGRS2LGRS_ACC\n"
                         "LGRS2ACC\n"
                         "PolarLGRS2LatLon\n"
                         "PolarLGRS2LPS\n"
                         "PolarLGRS2PolarLGRS_ACC\n"
                         "PolarLGRS2Polar_ACC\n"
                         "LGRS_ACC2LatLon\n"
                         "LGRS_ACC2LGRS\n"
                         "PolarLGRS_ACC2LatLon\n"
                         "PolarLGRS_ACC2LPS\n"
                         "PolarLGRS_ACC2\n")

except ValueError as e:
    if info:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        print(e)

# =====================================================================
