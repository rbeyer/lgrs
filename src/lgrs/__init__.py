"""Top-level package for lgrs."""

__author__ = """lgrs Developers"""
__email__ = "rbeyer@seti.org"  # TODO: Decide which, both?
__version__ = "0.1.0"

# Note: Analogous to `pyproj`:
from lgrs.srs.srs import CRS, GRS, make_lunar_crs

# Note: Unlike in `pyproj`:
from lgrs.caching import enable_caching
from lgrs.database import query_lunar_crs_info
from lgrs.easy import from_gridded, from_geographic, from_lps_or_ltm