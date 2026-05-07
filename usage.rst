===========================
lgrs Usage and Examples
===========================

We are actively developing the *lgrs* Python library to support working with
the Lunar Grid Reference System (LGRS) and its two forms of coordinates: LGRS
and Artemis Condensed Coordinates (ACC).

The code snippets below are examples of how you can perform various operations.

Since we are still in development, not everything is working yet, but you can
check back on this file to see what's ready for playing with.

We will also note that since we are not yet at version 1.0, the call signatures
and even names for these objects and functions may still change.


Coordinate Transformations
--------------------------

The *lgrs* library provides the ability convert between multiple kinds of
point coordinates and grid boxes. You're probably familiar with point
coordinates like latitude/longitude or easting/northing, but the LGRS uses the
concept of a grid of boxes, and the conversions *lgrs* provides allow a user
a user to start with a point coordinate and find out what LGRS (or ACC) grid box
that point falls within.

Likewise, if you have the name of an LGRS or ACC grid box, and want to know the
coordinates of its reference (lower-left) point, this can be easily obtained.


Convenience functions for LPS and LTM
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The *lgrs* library provides some convenience functions for converting lat/lon
coordinates easily into Lunar Polar Stereographic (LPS) or Lunar Transverse
Mercator (LTM) coordinates (although that can also just be done with
`pyproj <https://pyproj4.github.io/pyproj/stable/>`__).

How would you do it via *pyproj*?  Like this::

    >>> from pyproj import CRS, Transformer

    # Set up the CRS objects:
    >>> lonlat_crs = CRS.from_proj4("+proj=longlat +R=1737400")
    >>> ltm_crs = CRS.from_proj4("+proj=tmerc +R=1737400 +lon_0=0 +lat_0=0 +k_0=0.999 +x_0=250000")
    >>> lps_south_crs = CRS.from_proj4(
    ...    "+proj=stere +R=1737400 +lat_0=-90 +k_0=0.994 +x_0=500000 +y_0=500000"
    ... )

    # Create the transformers:
    >>> lonlat_to_ltm = Transformer.from_crs(lonlat_crs, ltm_crs)
    >>> lonlat_to_lps = Transformer.from_crs(lonlat_crs, lps_south_crs)

    # Convert:
    >>> lonlat_to_ltm.transform(2, 1)
    (310589.1246840328, 30311.488262646784)
    
    >>> lonlat_to_ltm.transform(2, -85)
    (255279.36655697995, -2574999.102429298)

    # Inversely, take an LPS coordinate and convert to lon/lat:
    >>> lps_to_lonlat = Transformer.from_crs(lps_south_crs, lonlat_crs)
    >>> lps_to_lonlat.transform(500000, 500000)
    (0.0, -90.0)

We hope to get the LPS and LTM definitions into the *PROJ* database, so that
when using *pyproj* in the future, you might just be able to do the following
to create LTM and LPS CRSes::

    ltm_crs = CRS.from_proj4("+proj=ltm +zone=2")
    lps_south_crs = CRS.from_proj4("+proj=lps +south")

In the meantime, the *lgrs* library provides these convenience functions via
creating a coordinate object::

    >>> from lgrs.coords import LatLonPoint, LpsPoint, LtmPoint

    >>> geo_point = LatLonPoint(longitude=2, latitude=1)

    # The ``lgrs`` library will determine whether the lat/lon you provide should
    # be placed into the LPS or LTM systems.
    >>> converted = geo_point.to_lps_or_ltm()
    >>> converted
    LtmPoint(zone_number=23, hemisphere='N', easting=310589.1246840328, northing=30311.488262646784, prefer_lps=False, extended_ltm=False, polar_ltm=False)

    # Lots of ways to get at the returned information:
    >>> str(converted)
    '23N310589.1246840328E30311.488262646784N'
    >>> list(converted)
    [23, 'N', 310589.1246840328, 30311.488262646784, False, False, False]
    >>> print(converted.easting)
    310589.1246840328

    >>> south_geo_point = LatLonPoint(longitude=2, latitude=-85)

    # We know this is in LPS, so the .to_lps() function can be used, if
    # preferred.
    >>> south_converted = south_geo_point.to_lps()
    >>> south_converted
    LpsPoint(hemisphere='S', easting=505262.9406400493, northing=650710.9011814011, prefer_lps=False, extended_ltm=False, polar_ltm=False)

    # Inversely, take an LPS coordinate and convert to lat/lon:
    >>> lps_coord = LpsPoint(hemisphere="S", easting=500000, northing=500000)
    >>> lps_coord.to_latlon()
    LatLonPoint(latitude=-90.0, longitude=0.0, prefer_lps=False, extended_ltm=False, polar_ltm=False)

Remember that the default polar stereographic projection that is used by the
LOLA and LROC PDS data, and in lots of data that is derived from those data, is
different from LPS.  The *lgrs* library provides some convenience functions to
help with those kinds of conversions with *pyproj*::

    >>> from pyproj import CRS, Transformer
    >>> from lgrs import make_lunar_crs

    >>> polar_stereographic_crs = CRS.from_proj4("+proj=stere +R=1737400 +lat_0=-90")
    >>> lps_crs = make_lunar_crs("S")

    >>> polar_to_lps = Transformer.from_crs(polar_stereographic_crs, lps_crs)
    >>> polar_to_lps.transform(0, 0)
    (500000.0, 500000.0)

The ``make_lunar_crs()`` function can make *pyproj* CRSes for north and south
LPS, as well as all the zones of LTM, and more.


Conversion of points to grid boxes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To convert a lon/lat coordinate to an LGRS grid box::

    >>> from lgrs.coords import LatLonPoint

    >>> geo_point = LatLonPoint(latitude=-30.13048481, longitude=96.48515138)
    >>> grid_converted = geo_point.to_lgrs()
    >>> grid_converted
    LtmLgrsBox(longitudinal_band=35, latitudinal_band='J', easting_area='F', northing_area='J', easting='12711', northing='12229', prefer_lps=False, extended_ltm=False, polar_ltm=False)

    >>> str(grid_converted)
    '35JFJ1271112229'

The above coordinate happened to be in the LTM area, so an LTM LGRS was output.
Here's a polar coordinate::

    >>> polar_geo_point = LatLonPoint(latitude=-86, longitude=30)
    >>> polar_grid_converted = polar_geo_point.to_lgrs()
    >>> polar_grid_converted
    LpsLgrsBox(longitudinal_band='B', easting_area='C', northing_area='S', easting='10307', northing='04455', prefer_lps=False, extended_ltm=False, polar_ltm=False)

    >>> str(polar_grid_converted)
    'BCS1030704455'

There are some areas where the LPS and LTM systems overlap so that a point can
validly use either LPS (and thus LPS LGRS grids) or LTM (and thus LTM LGRS
grids).

By default, this coordinate falls in the LPS zone, but if you use
``extended_ltm=True``, you can force an LTM zone::

    >>> overlap_geo_point = LatLonPoint(latitude=-81.13048481, longitude=96.48515138)
    >>> overlap_geo_point.to_lgrs()
    LpsLgrsBox(longitudinal_band='B', easting_area='L', northing_area='L', easting='16160', northing='19744', prefer_lps=False, extended_ltm=False, polar_ltm=False)

    >>> constrained_geo_point = overlap_geo_point.with_constraints(extended_ltm=True)
    >>> constrained_geo_point.to_lgrs()
    LtmLgrsBox(longitudinal_band=35, latitudinal_band='C', easting_area='F', northing_area='G', easting='02265', northing='17302', prefer_lps=False, extended_ltm=True, polar_ltm=False)

And all of these LGRS grids can be converted to the ACC shorthand (or you could
go there directly)::

    >>> grid_converted.to_acc()
    LtmAccBox(longitudinal_band=35, latitudinal_band='J', easting_area='F', northing_area='J', easting_1k='M', easting='711', northing_1k='M', northing='229', prefer_lps=False, extended_ltm=False, polar_ltm=False)

    >>> str(geo_point.to_acc())  # Straight from a lat/lon coordinate, but same result as above.
    '35JFJM711M229'

    >>> polar_grid_converted.to_acc()
    LpsAccBox(longitudinal_band='B', easting_area='C', northing_area='S', easting_1k='K', easting='307', northing_1k='D', northing='455', prefer_lps=False, extended_ltm=False, polar_ltm=False)

    >>> str(polar_geo_point.to_acc())
    'BCSK307D455'

Conversion of grid boxes to points
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have a grid box, and want to convert it back to a point, do the
following::

    >>> from lgrs.coords import LpsLgrsBox

    >>> lgrs_box = LpsLgrsBox.from_string("BCS1030704455")
    >>> lgrs_box.to_latlon()
    LatLonPoint(latitude=-86.0000149160353, longitude=29.9999496588117, prefer_lps=False, extended_ltm=False, polar_ltm=False)


Working with Grid Boxes
-----------------------
The *lgrs* library also supports convenient access to information and
operations specific to grid boxes::

    # Create an ACC box.
    >>> acc_box = polar_geo_point.to_acc()
    >>> str(acc_box)
    'BCSK307D455'

    # Get its precision, in meters.
    >>> acc_box.precision
    1

    # Get the box's parent grid box, in which `acc_box` is nested.
    >>> parent_acc_box = acc_box.truncate(min_precision=10)
    >>> str(parent_acc_box)
    'BCSK30D45'

    # Format this parent in true ACC shorthand, which excludes the leading
    # characters.
    # (Those characters determine the general (25 km x 25 km) region for the
    # box, but they may be unnecessary if you already know that information.)
    >>> parent_acc_box.condensed
    'K30D45'


Not yet implemented
-------------------

Coming soon!

- Creation of LGRS and ACC grids.

- Output of LGRS and ACC grids (as boxes, lines, or points) in standard formats (GeoPackage, Shapefile, GeoJSON, etc.)

- An lgrs command line program (for easy command line access).
