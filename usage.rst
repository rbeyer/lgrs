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
to start with a point coordinate and find out what LGRS (or ACC) grid box
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
    >>> ltm_crs = CRS.from_proj4(
    ...    "+proj=tmerc +R=1737400 +lon_0=0 +lat_0=0 +k_0=0.999 +x_0=250000"
    ... )
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

    >>> from lgrs.coords import Constraints, LatLonPoint, LpsPoint, LtmPoint

    >>> geo_point = LatLonPoint(longitude=2, latitude=1)

    # The ``lgrs`` library will determine whether the lat/lon you provide should
    # be placed into the LPS or LTM systems.
    >>> converted = geo_point.to_lps_or_ltm()
    >>> converted
    LtmPoint(zone_number=23, hemisphere='N', easting=310_589.1246840328, northing=30_311.488262646784, constraints=Constraints())

    # Lots of ways to get at the returned information:
    >>> str(converted)
    '23N 310589.1246840328 30311.488262646784'
    >>> list(converted)
    [23, 'N', 310589.1246840328, 30311.488262646784]
    >>> print(converted.easting)
    310589.1246840328

    >>> south_geo_point = LatLonPoint(longitude=2, latitude=-85)

    # We know this is in LPS, so the .to_lps() function can be used, if
    # preferred.
    >>> south_converted = south_geo_point.to_lps()
    >>> south_converted
    LpsPoint(hemisphere='S', easting=505_262.9406400493, northing=650_710.9011814011, constraints=Constraints())

    # Inversely, take an LPS coordinate and convert to lat/lon:
    >>> lps_coord = LpsPoint(hemisphere="S", easting=500000, northing=500000)
    >>> lps_coord.to_latlon()
    LatLonPoint(latitude=-90.0, longitude=0.0, constraints=Constraints())

Remember that the default polar stereographic projection that is used by the
LOLA and LROC PDS data, and in lots of data that is derived from those data, is
different from LPS.  The *lgrs* library provides some convenience functions to
help with those kinds of conversions with *pyproj*::

    >>> from pyproj import CRS, Transformer
    >>> from lgrs import make_lunar_crs

    # The IAU_2015 authority in the PROJ database defines this polar
    # stereographic CRS (code 30135 is south; 30130 is north).
    >>> polar_stereographic_crs = CRS.from_user_input("IAU_2015:30135")
    >>> lps_crs = make_lunar_crs("S")

    >>> polar_to_lps = Transformer.from_crs(polar_stereographic_crs, lps_crs)
    >>> polar_to_lps.transform(0, 0)
    (500000.0, 500000.0)

If you would rather see the projection parameters, the same CRS can be written
as a PROJ string, and it gives the same result::

    >>> proj_string_crs = CRS.from_proj4("+proj=stere +R=1737400 +lat_0=-90")
    >>> proj_string_to_lps = Transformer.from_crs(proj_string_crs, lps_crs)
    >>> from_proj_string = proj_string_to_lps.transform(1000, 2000)
    >>> from_authority = polar_to_lps.transform(1000, 2000)
    >>> from_proj_string == from_authority
    True

The ``make_lunar_crs()`` function can make *pyproj* CRSes for north and south
LPS, as well as all the zones of LTM, and more. To get the *WKT* definition of
any of these CRSes (for example, to hand to software that does not use
*pyproj*), use ``make_lunar_wkt()``, which takes the same arguments::

    >>> from lgrs import make_lunar_wkt

    >>> wkt = make_lunar_wkt("S")
    >>> wkt.splitlines()[0]
    'PROJCRS["Moon (2015) - Sphere / Ocentric / LPS South",'
    >>> make_lunar_wkt("23N").splitlines()[0]
    'PROJCRS["Moon (2015) - Sphere / Ocentric / LTM 23N",'


Finding the CRS for a location
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have a location and want to know which LPS region or LTM zone contains
it, use ``query_lunar_crs_info()``. It returns a list of information objects,
one per matching CRS::

    >>> from lgrs import query_lunar_crs_info

    >>> infos = query_lunar_crs_info(latitude=-86, longitude=30)
    >>> [info.name for info in infos]
    ['IAU_2015:30100 / LPS South']

    # The ``hint`` is the short name that ``make_lunar_crs()`` also accepts,
    # so it can be used to make the CRS itself.
    >>> [info.hint for info in infos]
    ['S']
    >>> infos[0].get_crs().equals(make_lunar_crs(infos[0].hint))
    True

    # By default, each location matches exactly one CRS. Along the boundary
    # between LPS and LTM (here at 80 degrees N), ``inclusive_bounds=True``
    # returns both.
    >>> boundary_infos = query_lunar_crs_info(
    ...     latitude=80, longitude=0, inclusive_bounds=True
    ... )
    >>> [info.hint for info in boundary_infos]
    ['N', '23N']

    # Without any location, the query returns every CRS, which is a quick way
    # to see how many LPS regions and LTM zones there are.
    >>> len(query_lunar_crs_info())
    92


Conversion of points to grid boxes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To convert a lon/lat coordinate to an LGRS grid box::

    >>> from lgrs.coords import LatLonPoint

    >>> geo_point = LatLonPoint(latitude=-30.13048481, longitude=96.48515138)
    >>> grid_converted = geo_point.to_lgrs()
    >>> grid_converted
    LtmLgrsBox(longitudinal_band=35, latitudinal_band='J', easting_area='F', northing_area='J', easting='12711', northing='12229', constraints=Constraints())

    >>> str(grid_converted)
    '35JFJ1271112229'

The above coordinate happened to be in the LTM area, so an LTM LGRS was output.
Here's a polar coordinate::

    >>> polar_geo_point = LatLonPoint(latitude=-86, longitude=30)
    >>> polar_grid_converted = polar_geo_point.to_lgrs()
    >>> polar_grid_converted
    LpsLgrsBox(longitudinal_band='B', easting_area='C', northing_area='S', easting='10307', northing='04455', constraints=Constraints())

    >>> str(polar_grid_converted)
    'BCS1030704455'

There are some areas where the LPS and LTM systems overlap so that a point can
validly use either LPS (and thus LPS LGRS grids) or LTM (and thus LTM LGRS
grids).

By default, this coordinate falls in the LPS zone, but if you use
``extended_ltm=True``, you can force an LTM zone::

    >>> overlap_geo_point = LatLonPoint(
    ...     latitude=-81.13048481, longitude=96.48515138
    ... )
    >>> overlap_geo_point.to_lgrs()
    LpsLgrsBox(longitudinal_band='B', easting_area='L', northing_area='L', easting='16160', northing='19744', constraints=Constraints())

    >>> constrained_geo_point = overlap_geo_point.replace(
    ...     constraints=Constraints(extended_ltm=True)
    ... )
    >>> constrained_geo_point.to_lgrs()
    LtmLgrsBox(longitudinal_band=35, latitudinal_band='C', easting_area='F', northing_area='G', easting='02265', northing='17302', constraints=Constraints(extended_ltm=True))

And all of these LGRS grids can be converted to the ACC shorthand (or you could
go there directly)::

    >>> grid_converted.to_acc()
    LtmAccBox(longitudinal_band=35, latitudinal_band='J', easting_area='F', northing_area='J', easting_1k='M', easting='711', northing_1k='M', northing='229', constraints=Constraints())

    # Straight from a lat/lon coordinate, but same result as above.
    >>> str(geo_point.to_acc())
    '35JFJM711M229'

    >>> polar_grid_converted.to_acc()
    LpsAccBox(longitudinal_band='B', easting_area='C', northing_area='S', easting_1k='K', easting='307', northing_1k='D', northing='455', constraints=Constraints())

    >>> str(polar_geo_point.to_acc())
    'BCSK307D455'

Conversion of grid boxes to points
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have a grid box, and want to convert it back to a point, do the
following::

    >>> from lgrs.coords import LpsLgrsBox

    >>> lgrs_box = LpsLgrsBox.from_string("BCS1030704455")
    >>> lgrs_box.to_latlon()
    LatLonPoint(latitude=-86.0000149160353, longitude=29.9999496588117, constraints=Constraints())


Converting a coordinate every way at once
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The examples above call one conversion at a time. If you would rather hand
over any point or box (as a string, if you like) and pick out whichever
results you need, use ``lgrs.easy.convert_coordinate()``::

    >>> from lgrs.easy import convert_coordinate

    # The input string is parsed for you, so no coordinate class is needed.
    >>> convert_coordinate("80 N, 0 E", precision=1, target="latlon")
    LatLonPoint(latitude=80, longitude=0, constraints=Constraints())

    # The LGRS box (here 1 m wide) that contains the point:
    >>> convert_coordinate("80 N, 0 E", precision=1, target="nominal.lgrs.string")
    'ZA-0000022818'

    # Each ``target`` is a chain of attributes on a ``GeoRelatives`` object,
    # which you can also request whole (by omitting ``target``) and explore.
    >>> relatives = convert_coordinate("80 N, 0 E", precision=1)
    >>> relatives.nominal.acc.string
    'ZA--000X818'

    # Not every coordinate has every relative. A point at exactly 80 degrees N
    # is valid in both LPS and LTM, but not in a second LTM zone. A chain that
    # runs into such a gap returns ``None`` rather than raising an error.
    >>> relatives.lps is not None and relatives.ltm_1 is not None
    True
    >>> relatives.get("ltm_2.lgrs.string") is None
    True


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
    >>> parent_acc_box = acc_box.with_precision(10)
    >>> str(parent_acc_box)
    'BCSK30D45'

    # Format this parent in true ACC shorthand, which excludes the leading
    # characters.
    # (Those characters determine the general (25 km x 25 km) region for the
    # box, but they may be unnecessary if you already know that information.)
    >>> parent_acc_box.condensed
    'K30D45'


Generating LGRS and ACC grids
-----------------------------

To generate a grid of LGRS or ACC boxes::

    # Create a global grid of 25-km ACC boxes.
    >>> from lgrs import GeographicBounds, write_grid
    >>> global_bounds = GeographicBounds(-180, -90, 180, 90)  # doctest: +SKIP
    >>> write_grid(
    ...     global_bounds, 25_000, "~/grids/global.gpkg|layer={}", acc=True
    ... )  # doctest: +SKIP

    # Specifically, the above example writes out a single GeoPackage (.gpkg
    # file) with 92 layers, each of which represents an LTM zone or LPS polar
    # region and has an automatically generated, unique layer name in place of
    # the "{}" placeholder. To instead write the same grids to Esri shapefiles,
    # each with the prefix "global":
    >>> write_grid(
    ...     global_bounds, 25_000, "~/grids/global_{}.shp", acc=True
    ... )  # doctest: +SKIP


For your convenience, the *lgrs* library provides several ways to define the
bounds of the grid::

    # Imagine that you want to generate 100-m LGRS boxes that cover the
    # footprint of a GeoTiff called "crater.tif" and output the grid as one or
    # more GeoJSON files (one per CRS).
    >>> write_grid(
    ...     r"C:\geotiffs\crater.tif", 100, r"C:\grids\crater_{}.json"
    ... )  # doctest: +SKIP

    # The process is similar for using the footprint of vector data.
    >>> write_grid(
    ...     "~/vector/sites.gpkg|layer=shackleton",
    ...     100,
    ...     "~/grids/shackleton.gpkg|layer=new_{}",
    ... )  # doctest: +SKIP

    # You can also generate boxes across an entire LPS region or LTM zone. For
    # example, to generate 25-km ACC boxes across the south polar region:
    >>> write_grid("S", 25_000, "~/grids/{}.shp", acc=True)  # doctest: +SKIP

    # When specifying bounds by an LPS region or LTM zone, you are guaranteed to
    # get just one CRS, and therefore exactly one output file. You can therefore
    # skip the placeholder without risking a name collision.
    >>> write_grid("23N", 25_000, "~/grids/23N_grid.gpkg")  # doctest: +SKIP


If you need finer control, you can use the lower-level ``grid`` module::

    >>> from lgrs import grid
    >>> aoi = GeographicBounds(120.0000, 81.0000, 120.0002, 81.0002)
    >>> boxes = grid.make_box_grid(aoi, precision=1, extended_ltm=True)
    >>> poi = LatLonPoint(81.00014637, 120.00012975)
    >>> for box in boxes:
    ...     # Calculate the geodesic distance from the center of ``box``
    ...     # to your point of interest ``poi``.
    ...     dist_to_poi = box.center_latlon.distance_to(poi)
    ...     # Extend the default field data.
    ...     # (These data will be included in each ``GeoDataFrame``.)
    ...     assert box.field_data["precision"] == 1  # Example contents.
    ...     box.field_data["dist_to_poi"] = dist_to_poi
    >>> gdfs = grid.make_gdfs(boxes)
    >>> if len(gdfs) == 1:
    ...     gdf, = gdfs
    ...     gdf.to_file("~/grids/aoi.gpkg")  # doctest: +SKIP
    ... else:
    ...     for gdf in gdfs:
    ...         gdf.to_file(
    ...             f"~/grids/aoi.gpkg|layer={gdf.name_hint}"
    ...         )  # doctest: +SKIP


Command line
------------

The most common operations are also available from a terminal, through the
``lgrs`` program. (These commands are not automatically tested, unlike the
Python examples above, so please report any that fail.) A bare ``lgrs`` lists
the available commands, and ``--help`` after any command describes its
arguments::

    $ lgrs convert-coordinate "80 N, 0 E" 1 --target nominal.lgrs.string
    ZA-0000022818

    $ lgrs make-lunar-wkt --name "LTM 23N"

    $ lgrs write-grid "(3, 4, 5, 6)" 1000 "~/grids/grid_1.gpkg|layer={}" --acc

These correspond to ``convert_coordinate()``, ``make_lunar_wkt()``, and
``write_grid()`` above.


Not yet implemented
-------------------

Coming soon!

- Output of LGRS and ACC grids as lines or points.
