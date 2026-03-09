"""Top-level package for lgrs."""

__author__ = """lgrs Developers"""
__email__ = "rbeyer@seti.org"  # TODO: Decide which, both?
__version__ = "0.1.0"

# Note: Analogous to `pyproj`:
from lgrs.srs.srs import BaseSRS, CRS, GRS
from lgrs.transformer import BaseTransformer, GriddedTransformer

# Note: Unlike in `pyproj`:
from lgrs.caching import enable_caching
from lgrs.database import query_lps_and_ltm_crs_info