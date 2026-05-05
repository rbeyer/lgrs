====
lgrs Usage and Examples
====

The code snippets below are examples of how you can perform various operations.

Since we are still in development, not everything is working yet, but you can check
back on this file to see what's ready for playing with.

We will also note that since we are not at verison 1.0, the call signatures and arguments
for these objects and functions are also in flux and may change.


Coordinate Transformations
--------------------------

The *lgrs* library provides the ability convert between coordinates and grid boxes.
You're probably familiar with coordinates like lon/lat or easting/northing, but the LGRS
system introduces the concept of grids, and the conversions *lgrs* provides allow a user
to have a coordinate and find out what LGRS (or ACC) grid box that coordinate falls within.

Likewise, if you have the name of an LGRS or ACC grid box, and want to know the coordinates
of its corners, that can be easily obtained.


Convenience functions for LPS and LTM
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The *lgrs* library provides some convenience functions for converting lon/lat coordinates
easily into LPS or LTM coordinates (although that can also just be done with *pyproj*)

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

    # Inversely take an LPS coordinate and convert to lon/lat:
    >>> lps_to_lonlat = Transformer.from_crs(lps_south_crs, lonlat_crs)
    >>> lps_to_lonlat.transform(500000, 500000)
    (0.0, -90.0)

We hope to get the LPS and LTM definitions into the *proj* database, so that when using *proj* in the future you might just be able to do the following to create LTM and LPS CRSes::

    ltm_crs = CRS.from_proj4("+proj=ltm +zone=2")
    lps_south_crs = CRS.from_proj4("+proj=lps +south")

In the meantime, the *lgrs* library provides these convenience functions via creating a coordinate object::

    >>> from lgrs.coords import LatLonPoint, LpsPoint, LtmPoint

    >>> ll = LatLonPoint(longitude=2, latitude=1)

    # The *lgrs* library will determine whether the lon/lat you provide should be placed
    # into the  LPS or LTM systems.
    >>> converted = ll.to_lps_or_ltm()
    >>> converted
    LtmPoint(zone_number=23, hemisphere='N', easting=310589.1246840328, northing=30311.488262646784, prefer_lps=False, extended_ltm=False, polar_ltm=False)

    # Lots of ways to get at the returned information:
    >>> str(converted)
    '23N310589.1246840328E30311.488262646784N'
    >>> list(converted)
    [23, 'N', 310589.1246840328, 30311.488262646784, False, False, False]
    >>> print(converted.easting)
    310589.1246840328

    >>> south_ll = LatLonPoint(longitude=2, latitude=-85)

    # We know this is in LPS, so the .to_lps() function can be used.
    >>> south_converted = south_ll.to_lps()
    >>> south_converted
    LpsPoint(hemisphere='S', easting=505262.9406400493, northing=650710.9011814011, prefer_lps=False, extended_ltm=False, polar_ltm=False)

    # Inversely take an LPS coordinate and convert to lon/lat:
    >>> lps_coord = LpsPoint(hemisphere="S", easting=500000, northing=500000)
    >>> lps_coord.to_latlon()
    LatLonPoint(latitude=-90.0, longitude=0.0, prefer_lps=False, extended_ltm=False, polar_ltm=False)


Remember that the default polar stereographic projection that is used by the LOLA and LROC PDS data and lots of data that is derived from it, is different than LPS.  The *lgrs* library provides some convenience functions to help with those kinds of conversions with *pyproj*::

    >>> from pyproj import CRS, Transformer
    >>> from lgrs import make_lunar_crs

    >>> polar_stereographic_crs = CRS.from_proj4("+proj=stere +R=1737400 +lat_0=-90")
    >>> lps_crs = make_lunar_crs("S")

    >>> polar_to_lps= Transformer.from_crs(polar_stereographic_crs, lps_crs)
    >>> polar_to_lps.transform(0, 0)
    (500000.0, 500000.0)

The ``make_lunar_crs()`` function can make *pyproj* CRSes for north and south LPS, as well as all the zones of LTM, and more.



Conversion of coordinates to grids
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To convert a lon/lat coordinate to an LGRS grid::

    >>> from lgrs.coords import LatLonPoint

    >>> ll = LatLonPoint(latitude=-30.13048481, longitude=96.48515138)
    >>> grid_converted = ll.to_lgrs()
    >>> grid_converted
    LtmLgrsBox(longitudinal_band=35, latitudinal_band='J', easting_area='F', northing_area='J', easting='12711', northing='12229', prefer_lps=False, extended_ltm=False, polar_ltm=False)

    >>> str(grid_converted)
    '35JFJ1271112229'

The above coordinate happened to be in the LTM area, so an LTM LGRS was output.  Here's a polar coordinate::

    >>> polar_ll = LatLonPoint(latitude=-86, longitude=30)
    >>> polar_grid_converted = polar_ll.to_lgrs()
    >>> polar_grid_converted
    LpsLgrsBox(longitudinal_band='B', easting_area='B', northing_area='S', easting='10307', northing='04455', prefer_lps=False, extended_ltm=False, polar_ltm=False)

    >>> str(polar_grid_converted)
    'BBS1030704455'

There are some areas that are in the overlap area that could either be represented in LTM (and thus LTM LGRS grids) or in LPS (and thus in LPS LGRS grids).

By default, this coordinate falls in the LPS zone, but if you use ``extended_ltm=True`` you can force an LTM zone::

    >>> overlap_ll = LatLonPoint(latitude=-81.13048481, longitude=96.48515138)
    >>> overlap_ll.to_lgrs()
    LpsLgrsBox(longitudinal_band='B', easting_area='K', northing_area='L', easting='16160', northing='19744', prefer_lps=False, extended_ltm=False, polar_ltm=False)

    >>> constrained_ll = overlap_ll.with_constraints(extended_ltm=True)
    >>> constrained_ll.to_lgrs()
    LtmLgrsBox(longitudinal_band=35, latitudinal_band='C', easting_area='F', northing_area='G', easting='02265', northing='17302', prefer_lps=False, extended_ltm=True, polar_ltm=False)

And all of these LGRS grids can be converted to the ACC shorthand (or you could go there directly)::

    >>> grid_converted.to_acc()
    LtmAccBox(longitudinal_band=35, latitudinal_band='J', easting_area='F', northing_area='J', easting_1k='M', easting='711', northing_1k='M', northing='229', prefer_lps=False, extended_ltm=False, polar_ltm=False)

    >>> str(ll.to_acc())  # straight from a lon/lat coordinate, but same as above
    '35JFJM711M229'

    >>> polar_grid_converted.to_acc()
    LpsAccBox(longitudinal_band='B', easting_area='B', northing_area='S', easting_1k='K', easting='307', northing_1k='D', northing='455', prefer_lps=False, extended_ltm=False, polar_ltm=False)

    >>> str(polar_ll.to_acc())
    'BBSK307D455'


Conversion of Grid Boxes to Coordinates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have a grid box, and want to convert it back to coordinates, do the following::

    >>> from lgrs.coords import LpsLgrsBox

    >>> lgrs_box = LpsLgrsBox.from_string("BBS1030704455")
    >>> lgrs_box.to_latlon()
    LatLonPoint(latitude=-86.34312698089725, longitude=18.67584891760275, prefer_lps=False, extended_ltm=False, polar_ltm=False)





Not yet implemented 
-------------------

Coming soon!

- Conversion of LGRS and ACC grid specifications back to LPS/LTM and lon/lat coordinates.

- Creation of LGRS and ACC geometries.

- Output of LGRS and ACC geometries (boxes, points, lines) in standard formats (GeoPackage, Shapefile, GeoJSON, etc.)

- An lgrs command line program (for easy command line access).
