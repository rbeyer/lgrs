"""Tests for the closed-form spherical LTM transform in `lgrs.srs.srs`."""

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
import lgrs.srs.srs as srs
from lgrs.coords import LatLonPoint

# External.
import pyproj

# endregion
###############################################################################
# region> TESTS
###############################################################################
R = 1_737_400.0
K0 = 0.999


def _reference(lat: float, lon: float, lon0: float, y0: float):
    phi, dlam = math.radians(lat), math.radians(lon - lon0)
    e = K0 * R * math.atanh(math.cos(phi) * math.sin(dlam)) + 250_000
    n = K0 * R * math.atan2(math.tan(phi), math.cos(dlam)) + y0
    return e, n


class TestExactSphericalLtm(unittest.TestCase):
    def setUp(self) -> None:
        self.geo = srs.make_lunar_crs()

    def test_ltm_transformer_is_exact_closed_form(self) -> None:
        crs = srs.make_lunar_crs("23S")
        transformer = srs.get_transformer(self.geo, crs, always_xy=False)
        for lat in (-1e-9, -1e-7, -1e-6, -0.5, -45.0, -79.9):
            for lon in (-4.0, -1e-6, 0.0, 2.5, 3.9):
                with self.subTest(lat=lat, lon=lon):
                    e, n = transformer.transform(lat, lon)
                    e_ref, n_ref = _reference(lat, lon, 0.0, 2_500_000)
                    self.assertAlmostEqual(e, e_ref, delta=1e-6)
                    self.assertAlmostEqual(n, n_ref, delta=1e-6)

    def test_round_trip(self) -> None:
        crs = srs.make_lunar_crs("45N")
        fwd = srs.get_transformer(self.geo, crs, always_xy=False)
        inv = srs.get_transformer(crs, self.geo, always_xy=False)
        for lat, lon in ((1e-8, 176.0), (30.0, 173.5), (81.9, 179.9)):
            with self.subTest(lat=lat, lon=lon):
                back = inv.transform(*fwd.transform(lat, lon))
                self.assertAlmostEqual(back[0], lat, delta=1e-12)
                self.assertAlmostEqual(back[1], lon, delta=1e-12)

    def test_always_xy_axis_order(self) -> None:
        crs = srs.make_lunar_crs("23S")
        lat_first = srs.get_transformer(self.geo, crs, always_xy=False)
        lon_first = srs.get_transformer(self.geo, crs, always_xy=True)
        self.assertEqual(
            lat_first.transform(-12.0, 1.5), lon_first.transform(1.5, -12.0)
        )

    def test_agrees_with_proj_away_from_equator(self) -> None:
        crs = srs.make_lunar_crs("12N")
        ours = srs.get_transformer(self.geo, crs, always_xy=False)
        proj = pyproj.Transformer.from_crs(self.geo, crs, always_xy=False)
        lon0 = -180 + 8 * 11 + 4
        for lat in (0.5, 10.0, 45.0, 79.0):
            for dlon in (-3.9, 0.0, 3.9):
                e1, n1 = ours.transform(lat, lon0 + dlon)
                e2, n2 = proj.transform(lat, lon0 + dlon)
                self.assertLess(math.hypot(e1 - e2, n1 - n2), 1e-4)

    def test_non_ltm_transformer_is_unchanged(self) -> None:
        crs = srs.make_lunar_crs("S")  # LPS
        transformer = srs.get_transformer(self.geo, crs, always_xy=False)
        self.assertIsInstance(transformer, pyproj.Transformer)

    def test_point_just_south_of_equator(self) -> None:
        # Previously `23MKFT234-000`, the box north of the equator.
        self.assertEqual(
            LatLonPoint(-1e-7, 3.9).to_acc(precision=1).string,
            "23MKET234Z999",
        )


# endregion
if __name__ == "__main__":
    unittest.main()
