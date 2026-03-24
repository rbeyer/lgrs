"""This module has tests for the lgrs reference module."""

# Copyright © 2026, Ross A. Beyer (rbeyer@seti.org)
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

import unittest

from unittest.mock import patch

import lgrs.reference.LGRS_Coordinate_Conversion as cconv


class Test_Coord_Conv(unittest.TestCase):

    def setUp(self):
        cconv.initialize_LGRS_function_globals()

    @patch("builtins.print")
    def test_latlon2ltm(self, mock_print):

        with patch("sys.argv", ["test_name", "LatLon2LTM", 1.0, 1.0]):
            cconv.main("LatLon2LTM", 1, True)
            mock_print.assert_called_with("23N280289E0030297N")

        with patch("sys.argv", ["test_name", "LatLon2LTM", 1.0, 1.0]):
            cconv.main("LatLon2LTM", 10, False)
            mock_print.assert_called_with("23 N 280280 0030290")

    @patch("builtins.print")
    def test_latlon2lps(self, mock_print):

        with patch("sys.argv", ["test_name", "LatLon2LPS", 85, 1.0]):
            cconv.main("LatLon2LPS", 1, True)
            mock_print.assert_called_with("N502631E349220N")

        with patch("sys.argv", ["test_name", "LatLon2LPS", 85, 1.0]):
            cconv.main("LatLon2LPS", 10, False)
            mock_print.assert_called_with("N 502630 349220")

    @patch("builtins.print")
    def test_polarlgrs2polarlgrs_acc(self, mock_print):

        with patch(
            "sys.argv",
            ["test_name", "PolarLGRS2PolarLGRS_ACC", "AZS1359008480"],
        ):
            cconv.main("PolarLGRS2PolarLGRS_ACC", 1, True)
            mock_print.assert_called_with("AZSN590H480")

    @patch("builtins.print")
    def test_PolarLGRS2Polar_ACC(self, mock_print):

        with patch(
            "sys.argv",
            ["test_name", "PolarLGRS2Polar_ACC", "AZS1359008480"],
        ):
            cconv.main("PolarLGRS2Polar_ACC", 1, True)
            mock_print.assert_called_with("N59H48")
