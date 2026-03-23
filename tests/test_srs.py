"""Tests for `lgrs.srs.srs` module."""

# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

###############################################################################
# region> IMPORT
###############################################################################
# External.
import pyproj
import pyproj.crs.crs as crs
import unittest

# Internal.
import lgrs.caching as caching
import lgrs.srs.srs as srs



# endregion
###############################################################################
# region> TESTS
###############################################################################
class TestDirectCrsGeneration(unittest.TestCase):

    def setUp(self):
        caching.enable_caching(False, clear=True)

    def check_crs_generation(
            self, *, proj_crs: crs.CRS,
            north: float, south: float, east: float, west: float,
            method_name_part: str
    ) -> None:
        self.assertIsInstance(proj_crs, crs.CRS)
        self.assertEqual(proj_crs.area_of_use.north, north)
        self.assertEqual(proj_crs.area_of_use.south, south)
        self.assertEqual(proj_crs.area_of_use.east, east)
        self.assertEqual(proj_crs.area_of_use.west, west)
        # TODO: Change string to `wkt.DATUM_NAME`.
        iau_datum = crs.Datum.from_authority(*"IAU_2015:30100".split(":"))
        self.assertEqual(proj_crs.datum, iau_datum)
        # Note: Ultimately, this merely tests against the text of the
        # input WKT.
        self.assertTrue(
            method_name_part in proj_crs.coordinate_operation.method_name
        )

    def test_lps_generation(self):
        lps_n = srs.make_lunar_crs("N")
        self.check_crs_generation(
            proj_crs=lps_n,
            north=90.,
            south=80.,
            east=180.,
            west=-180.,
            method_name_part="Stereographic"
        )

    def test_ltm_generation(self):
        ltm_1s = srs.make_lunar_crs("1S")
        self.check_crs_generation(
            proj_crs=ltm_1s,
            north=0.,
            south=-80.,
            east=-172.,
            west=-180.,
            method_name_part="transverse Mercator"
        )

class TestDirectCrsInterconversion(unittest.TestCase):

    def setUp(self):
        caching.enable_caching(False, clear=True)

    def check_interconversion(
            self, *, proj_crs: crs.CRS, in_lat: float, in_lon: float,
            in_easting: float, in_northing: float
    ) -> None:
        geo_crs = proj_crs.geodetic_crs
        transformer_from_geo = pyproj.Transformer.from_crs(geo_crs, proj_crs)
        transformer_to_geo = pyproj.Transformer.from_crs(proj_crs, geo_crs)
        out_easting, out_northing = transformer_from_geo.transform(in_lat, in_lon)
        # Note: Expected disparity is "very small" but precise
        # magnitudes of `very_small_projected` and `very_small_geo` are
        # not rigorous.
        very_small_projected = 1e-9
        self.assertTrue(abs(out_easting - in_easting) < very_small_projected)
        self.assertTrue(abs(out_northing - in_northing) < very_small_projected)
        out_lat, out_lon = transformer_to_geo.transform(in_easting, in_northing)
        very_small_geo = 1e-12
        self.assertTrue(abs(out_lat - in_lat) < very_small_geo)
        self.assertTrue(abs(out_lon - in_lon) < very_small_geo)

    def test_lps_interconversion(self):
        lps_s = srs.make_lunar_crs("S")
        # Note: `in_easting` and `in_northing` from run of 7.2 code with
        # `in_lat` and `in_lon` as inputs.
        self.check_interconversion(
            proj_crs=lps_s,
            in_lat=-87.6, in_lon=54.3,
            in_easting=558754.2137973069,
            in_northing=542219.1855347467
        )

    def test_ltm_interconversion(self):
        ltm_45n = srs.make_lunar_crs("45N")
        # Note: `in_easting` and `in_northing` from run of 7.2 code with
        # `in_lat` and `in_lon` as inputs.
        self.check_interconversion(
            proj_crs=ltm_45n,
            in_lat=45.6, in_lon=178.9,
            in_easting=311464.70966367936,
            in_northing=1382473.8696073617
        )

class TestCrsCaching(unittest.TestCase):

    def setUp(self):
        caching.enable_caching(True, clear=True)

    def tearDown(self):
        caching.enable_caching(False, clear=True)

    def test_crs_caching(self):
        lps_s_core = srs.make_lunar_crs("S", extended_ltm=True)
        also_lps_s_core = srs.make_lunar_crs(
            proj="LPS", south=True, extended_ltm=True
        )
        self.assertIs(lps_s_core, also_lps_s_core)
        ltm_23s = srs.make_lunar_crs("23S")
        also_ltm_23s = srs.make_lunar_crs(proj="LTM", zone=23, south=True)
        self.assertIs(ltm_23s, also_ltm_23s)



# endregion

if __name__ == "__main__":
    unittest.main()