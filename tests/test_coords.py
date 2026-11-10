"""Tests for boundary cases in `lgrs.coords` conversions."""

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.

###############################################################################
# region> IMPORT
###############################################################################
# Standard.
import math
import unittest

# Internal.
import lgrs.database as database
from lgrs.coords import LatLonPoint, LpsPoint


# endregion
###############################################################################
# region> TESTS
###############################################################################
class TestLpsWestHalfAreaEdges(unittest.TestCase):
    def test_exact_25km_multiple_is_west_edge_of_next_area(self) -> None:
        for hemisphere, band in (("S", "A"), ("N", "Y")):
            with self.subTest(hemisphere=hemisphere):
                point = LpsPoint(hemisphere, 475_000.0, 510_000.0)
                self.assertEqual(
                    point.to_lgrs(precision=1).string, f"{band}ZN0000010000"
                )
                self.assertEqual(
                    point.to_acc(precision=10).string, f"{band}ZN-00K00"
                )

    def test_neighbors_of_exact_multiple_are_unchanged(self) -> None:
        self.assertEqual(
            LpsPoint("S", 474_999.0, 510_000.0).to_lgrs(precision=1).string,
            "AYN2499910000",
        )
        self.assertEqual(
            LpsPoint("S", 475_001.0, 510_000.0).to_lgrs(precision=1).string,
            "AZN0000110000",
        )

    def test_every_west_half_area_edge(self) -> None:
        for i in range(1, 10):
            easting = 500_000.0 - 25_000 * i
            with self.subTest(easting=easting):
                lgrs = LpsPoint("S", easting, 510_000.0).to_lgrs(precision=1)
                self.assertEqual(lgrs.string[3:8], "00000")
                # Must not raise.
                LpsPoint("S", easting, 510_000.0).to_acc(precision=10)


class TestLpsAntimeridian(unittest.TestCase):
    def test_points_on_180_meridian_are_valid(self) -> None:
        for hemisphere, northing in (("S", 400_000.0), ("N", 600_000.0)):
            with self.subTest(hemisphere=hemisphere):
                point = LpsPoint(hemisphere, 500_000.0, northing)
                self.assertEqual(point.to_latlon().longitude, -180.0)


class TestLtmZoneNumber(unittest.TestCase):
    def test_largest_longitude_below_180_is_zone_45(self) -> None:
        lon = math.nextafter(180.0, 0.0)
        self.assertEqual(database._calculate_ltm_zone_number(lon)[1], 45)
        self.assertEqual(
            LatLonPoint(0.0, lon).to_lgrs(precision=10).string,
            "45NKL21270000",
        )

    def test_zone_edges_unchanged(self) -> None:
        self.assertEqual(database._calculate_ltm_zone_number(-180.0), (1.0, 1))
        self.assertEqual(
            database._calculate_ltm_zone_number(172.0), (45.0, 45)
        )


# endregion
if __name__ == "__main__":
    unittest.main()
