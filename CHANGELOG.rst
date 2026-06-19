=========
Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

When updating this file, please add an entry for your change under
Unreleased_ and one of the following headings:

- Added - for new features.
- Changed - for changes in existing functionality.
- Deprecated - for soon-to-be removed features.
- Removed - for now removed features.
- Fixed - for any bug fixes.
- Security - in case of vulnerabilities.

If the heading does not yet exist under Unreleased_, then add it
as a 3rd level heading, underlined with pluses (see examples below).

When preparing for a public release add a new 2nd level heading,
underlined with dashes under Unreleased_ with the version number
and the release date, in year-month-day format (see examples below).


Unreleased
----------

Added
^^^^^
* Basic support for ``min_zones=True`` option when generating grids
  (``lgrs.grid.make_box_grid()`` and ``lgrs.easy.write_grid()``).
* ``bounds`` module, which includes enhanced versions of ``GeographicBounds``
  (previously hosted by ``lgrs.grid``) and ``ProjectedBounds`` (previously
  hosted by ``lgrs.coords``).
* ``PointCoordinate.is_within_bounds()``.

Changed
^^^^^^^
* The ``bounds`` argument of ``lgrs.grid.make_box_grid()`` and
  ``lgrs.easy.write_grid()`` can now be specified in seven different ways, as
  documented in the docstrings for those functions. Most notably, bounds may now
  be specified in LPS and LTM CRSs, whereas only geographic bounds were
  previously supported.
* For ``lgrs.coords.BaseCoordinate``, ``.to_lps()`` and ``.to_ltm()`` now
  support a ``search`` argument. Documentation has been added to explain its
  functionality. The method ``.to()`` inherits this enhanced functionality. Note
  that the prior implementation of these methods was similar to
  ``search=True`` but ``search`` defaults to ``False``, which may break existing
  code.
* Ambiguous and/or outdated documentation has been updated throughout the
  library, including ``LatLonPoint``, ``BaseCoordinate.copy()``, and
  ``BoxCoordinate.contains()`` in the ``lgrs.coords`` module.
* Some argument defaults have changed, including those for ``same_crs_only`` and
  ``error`` of ``lgrs.coords.BoxCoordinate.contains()``.
* The ``primary`` argument of ``lgrs.database.query_lunar_crs_info()`` is now
  called ``nominal``, to be consistent with use elsewhere in the library.
* ``pyproj.Transformer`` instances are now universally cached for better
  performance.
* ``BaseCoordinate.field_data`` is now a writable ``dict``, by default.

Removed
^^^^^^^
* For ``lgrs.coords.BoxCoordinate``, ``.corners`` is removed. Use
  ``.corners_latlon``, ``.bounds``, or possibly ``.geometry`` instead.

Fixed
^^^^^
* Grid generation (via ``lgrs.grid.make_box_grid()`` and
  ``lgrs.easy.write_grid()``) now handles the margins of the input ``bounds``
  more carefully. Therefore, the footprint of ``bounds`` will be spanned by the
  generated boxes, generally with some excess fringe.
* Constraints are now set with sufficient specificity to guarantee coordinate
  validity when generating box corner coordinates. Consequently, caching now
  remains enabled when using the ``min_overlap=False`` setting of
  ``lgrs.grid.make_box_grid()`` and ``lgrs.easy.write_grid()``, greatly
  improving performance.
* The ``.to_lps()`` and ``.to_ltm()`` methods of ``lgrs.coords.BoxCoordinate``
  now honor their ``validate`` argument.
* The behavior of ``lgrs.coords.BaseCoordinate.is_equal_to()`` now exactly
  follows its documentation.


0.2.0 (2026-06-02)
------------------

Added
^^^^^
Grid generation is now implemented.

* Supports lat/lon bounds specification by (a) explicit bounds, (b) path to
  vector or raster data, or (c) name of LPS region or LTM zone (i.e., CRS).
* All precisions.
* Output is via geopandas, so a wide variety of formats are supported. (I've
  only tested GeoPackage, Esri shapefile, and GeoJSON.)

    * Because a single call may produce grids from multiple CRSes and hence
      multiple files/layers, there is built-in support for generating
      descriptive names that ensure uniqueness.

        * We may ultimately want to support single-layer (common CRS) output
          of boxes soured from multiple CRSes, but that's not ideal and there
          are limits to how usefully that can be expanded to large areas.

* Both LGRS and ACC, with automatically generated field data.
* With or without the extended LTM region.
* With the standard write modes: "x", "w", and "a".
* An option to minimize overlap (min_overlap) near boundries.

    * This works best for <25 km boxes. If you think about it, a maximum
      ~25 km x ~25 km overlap could hypothetically result in >600 million
      1-m boxes overlapping. This setting reduces the overlap to approximately
      what's required to cover an area; boxes closely follow the nominal
      latitudinal and longitudinal boundaries of their respective zones. (It so
      happens to be far more performant, too.)

* There's also an "experimental" option (min_overlap=False) to instead generate
  all boxes across the entire width of the overlap.

    * Due to unresolved caching issues with this specific option, caching is
      disabled when this option is used, dramatically decreasing performance
      (perhaps by 2-3 orders of magnitude).

* Boxes now support user-specified field data. (See last example in usage.rst.)


Changed
^^^^^^^

Constraints and Validation

* Constraints are now packaged in their own class (Constraints) and
  have expanded options.

* Constraints now carefully treat boundaries between LPS and LTM
  regions (latitudinal) and between adjacent LTM zones (longitudinal).
  (See especially: Constraints._get_proj_crs_and_new_cousins().)

    * Specifically, a box is valid if any part of its parent 25-km
      box is within the nominal lat/lon bounds of its zone. This is
      similar to MGRS and was discussed with Mark in the context of
      the polar bounding box.
    * The result is up to ~35 km of overlap (diagonal length of 25-km
      box) near the aforementioned boundaries where multiple, non-aligned
      boxes from different CRSes may all be valid.

	* However, note that this is less overlap that in the reference
	  code, which uses oversized bouding boxes only.

    * Because up to 3 (non-aligned) boxes may overlap a single point,
      PointCoordinate.to_all_lgrs() and PointCoordinate.to_all_acc()
      now exist to query those boxes (rather than leave it to the
      user to brute-force explore constraints-space).

* Coordinate (point and box) validation now follows a multi-tier path:

    * Validation by reconstruction - back-convert to LatLonPoint and
      forward-convert, to confirm that final value matching starting
      value. This proved to be a very general way to test some
      complicated aspects, especially those related to constraints.
      Validation proceeds only if reconstruction fails, and then,
      with the sole purpose of producing a more detailed error.
    * Validation of each field (but not all fields have independent
      validation).
    * Validation against regex pattern (for the strings of boxes
      only).



0.1.0 (2026-05-07)
------------------

* First release.
