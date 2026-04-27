"""Tests for `lgrs.database` module."""

# Copyright © 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

###############################################################################
# region> IMPORT
###############################################################################
# External.
import itertools
import numpy as np
import pyproj.aoi
import unittest

# Internal.
import lgrs.database as database



# endregion
###############################################################################
# region> TESTS
###############################################################################
class TestQueryDatabase(unittest.TestCase):
    default_kwargs = {
        "contains": False,
        "primary_ltm": True, "extended_ltm": False, "polar_ltm": False,
        "inclusive_bounds": False,
    }

    def check_query(self, *, expected_long_names: list[str], **kwargs) -> None:
        full_kwargs = self.default_kwargs.copy()
        full_kwargs.update(kwargs)
        infos = database.query_lunar_crs_info(**full_kwargs)
        actual_long_names = [info._long_name for info in infos]
        self.assertEqual(actual_long_names, expected_long_names)

    def test_ltm_zone_center(self) -> None:
        self.check_query(
            latitude=40, longitude=0, inclusive_bounds=True,
            expected_long_names=["23N"]
        )

    def test_ltm_zone_equator_side(self) -> None:
        self.check_query(
            latitude=0, longitude=-176, inclusive_bounds=False,
            expected_long_names=["01N"]
        )
        self.check_query(
            latitude=0, longitude=-176, inclusive_bounds=True,
            expected_long_names=["01N", "01S"]
        )

    def test_ltm_zone_equator_corner(self) -> None:
        self.check_query(
            latitude=0, longitude=-180, inclusive_bounds=True,
            expected_long_names=["01N", "45N", "01S", "45S"]
        )
        self.check_query(
            latitude=0, longitude=-180, inclusive_bounds=True,
            contains=True,
            expected_long_names=["01N", "45N", "01S", "45S"]
        )
        self.check_query(
            latitude=[0, 0], longitude=[-180, -172], inclusive_bounds=True,
            contains=True,
            expected_long_names=["01N", "01S"]
        )
        self.check_query(
            latitude=0, longitude=180, inclusive_bounds=True,
            expected_long_names=["01N", "45N", "01S", "45S"]
        )
        self.check_query(
            latitude=0, longitude=-180, inclusive_bounds=True,
            contains=True,
            expected_long_names=["01N", "45N", "01S", "45S"]
        )

    def test_ltm_zone_lps_corner(self) -> None:
        self.check_query(
            latitude=-80, longitude=-180, inclusive_bounds=True,
            expected_long_names=["S", "01S", "45S"]
        )

    def test_ltm_extensions(self) -> None:
        # 81 degrees.
        self.check_query(
            latitude=81, longitude=0,
            expected_long_names=["N"]
        )
        self.check_query(
            latitude=81, longitude=0, extended_ltm=True,
            expected_long_names=["N", "23N*"]
        )
        self.check_query(
            latitude=81, longitude=0, extended_ltm=True, polar_ltm=True,
            expected_long_names=["N", "23N*", "23N**"]
        )
        self.check_query(
            latitude=81, longitude=0, extended_ltm=False, polar_ltm=True,
            expected_long_names=["N", "23N**"]
        )
        self.check_query(
            latitude=81, longitude=0,
            primary_ltm=False, extended_ltm=False, polar_ltm=True,
            expected_long_names=["23N**"]
        )

        # 83 degrees.
        self.check_query(
            latitude=83, longitude=0,
            expected_long_names=["N"]
        )
        self.check_query(
            latitude=83, longitude=0, extended_ltm=True,
            expected_long_names=["N", "N*"]
        )
        self.check_query(
            latitude=83, longitude=0, extended_ltm=True, polar_ltm=True,
            expected_long_names=["N", "N*", "23N**"]
        )
        self.check_query(
            latitude=83, longitude=0, extended_ltm=False, polar_ltm=True,
            expected_long_names=["N", "23N**"]
        )
        self.check_query(
            latitude=83, longitude=0,
            primary_ltm=False, extended_ltm=False, polar_ltm=True,
            expected_long_names=["23N**"]
        )

        # 90 degrees.
        self.check_query(
            latitude=90, longitude=0, extended_ltm=True, polar_ltm=True,
            expected_long_names=["N", "N*", "23N**"]
        )
        self.check_query(
            latitude=-90, longitude=0, extended_ltm=True, polar_ltm=True,
            expected_long_names=["S", "S*", "23S**"]
        )
        long_name_formatters = [f"{i:02}{{}}**".format
                                  for i in range(1, 46)]
        long_name_formatters[:0] = ["{}".format, "{}*".format]
        north_pole_long_names = [formatter("N")
                                  for formatter in long_name_formatters]
        self.check_query(
            latitude=90, longitude=0, extended_ltm=True, polar_ltm=True,
            inclusive_bounds=True,
            expected_long_names=north_pole_long_names
        )
        south_pole_long_names = [formatter("S")
                                  for formatter in long_name_formatters]
        self.check_query(
            latitude=-90, longitude=0, extended_ltm=True, polar_ltm=True,
            inclusive_bounds=True,
            expected_long_names=south_pole_long_names
        )
        both_pole_long_names = (
            north_pole_long_names[:2]
            + south_pole_long_names[:2]
            + north_pole_long_names[2:]
            + south_pole_long_names[2:]
        )
        self.check_query(
            latitude=[-90, 90], longitude=[0, 0],
            extended_ltm=True, polar_ltm=True,
            inclusive_bounds=True,
            expected_long_names=both_pole_long_names
        )

    def test_contains(self) -> None:
        self.check_query(
            latitude=[0, 0, 82, 82], longitude=[-4, 4, 4, -4],
            extended_ltm=True,
            inclusive_bounds=True, contains=True,
            expected_long_names=["23N*"]
        )
        self.check_query(
            latitude=[0, 0], longitude=[-180, -171],
            contains=True,
            expected_long_names=[]
        )
        self.check_query(
            latitude=[0, 0], longitude=[-180, -171],
            inclusive_bounds=True, contains=True,
            expected_long_names=[]
        )
        self.check_query(
            latitude=[-90, 90], longitude=[0, 0],
            extended_ltm=True, polar_ltm=True,
            inclusive_bounds=True, contains=True,
            expected_long_names=[]
        )
        self.check_query(
            latitude=[-90, 90], longitude=[0, 0],
            extended_ltm=True, polar_ltm=True,
            inclusive_bounds=True, contains=True,
            expected_long_names=[]
        )

    def test_aoi(self) -> None:
        # Test `inclusive_bounds=True`.
        self.check_query(
            area_of_interest=pyproj.aoi.AreaOfInterest(
                west_lon_degree=-4, east_lon_degree=4,
                south_lat_degree=0, north_lat_degree=80,
            ),
            inclusive_bounds=True,
            expected_long_names=["N", "22N", "23N", "24N", "22S", "23S", "24S"]
        )
        self.check_query(
            area_of_interest=pyproj.aoi.AreaOfInterest(
                west_lon_degree=-4, east_lon_degree=4,
                south_lat_degree=0, north_lat_degree=80,
            ),
            inclusive_bounds=True, contains=True,
            expected_long_names=["23N"]
        )

    # TODO: Decide how we plan to deal with this test.
    @unittest.skip("expensive")
    def test_aoi_expensive(self) -> None:
        # Test latitudinal sampling.
        # Note: Internally, `lgrs.database.query_lunar_crs_info()`
        # converts `area_of_interest` to a non-uniform grid. The
        # logic for the longitudinal spacing of that grid is self-
        # evident but the logic for the latitudinal sampling is not.
        # Therefore, the following tests test for consistency between
        # the results when a densified grid covering the
        # `area_of_interest` is passed to results when a grid is
        # generated internally by
        # `lgrs.database.query_lunar_crs_info()`.
        crit_lats = np.arange(-90, 90.1, step=0.25).tolist()
        for s_lat, n_lat in itertools.combinations(crit_lats, 2):
            aoi = pyproj.aoi.AreaOfInterest(
                west_lon_degree=-3, east_lon_degree=3,
                south_lat_degree=s_lat, north_lat_degree=n_lat
            )
            dense_lats, dense_lons = database._grid_sample(
                latitudes=(s_lat, n_lat), longitudes=(-3, 3),
                lat_sample=0.25, lon_sample=2
            )
            aoi_crs_list = database.query_lunar_crs_info(
                area_of_interest=aoi,
                extended_ltm=True, polar_ltm=True,
            )
            aoi_long_names = [crs._long_name
                               for crs in aoi_crs_list]
            self.check_query(
                latitude=dense_lats, longitude=dense_lons,
                extended_ltm=True, polar_ltm=True,
                expected_long_names=aoi_long_names
            )



# endregion