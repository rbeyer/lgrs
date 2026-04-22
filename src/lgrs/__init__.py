"""Top-level package for `lgrs` library."""

# Copyright © 2026, Ethan I. Schafer (eschaefer@seti.org) and
# Ross A. Beyer (rbeyer@seti.org)
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

__author__ = """lgrs Developers"""
__email__ = "rbeyer@seti.org"  # TODO: Decide which, both?
__version__ = "0.1.0"

# Note: Analogous to `pyproj`:
from lgrs.srs.srs import CRS, GRS, make_lunar_crs

# Note: Unlike in `pyproj`:
from lgrs.caching import enable_caching
from lgrs.database import query_lunar_crs_info
from lgrs.easy import from_gridded, from_geographic, from_lps_or_ltm