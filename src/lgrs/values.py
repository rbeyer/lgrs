"""
Cross-library reference values, sentinels, and related utilities.

In some comments, the following reference is cited as "M2025", for
brevity:
    McClernan, M.T., Dennis, M.L., Theriot, I.H., Hare, T.M., Archinal,
        B.A., Ostrach, L.R., Hunter, M.A., Miller, M.J., Beyer, R.A.,
        Annex, A.M., and Lawrence, S.J., 2025, Lunar grid systems,
        coordinate systems, and map projections for the Artemis missions
        and lunar surface navigation: U.S. Geological Survey Techniques
        and Methods, book 11, chap. E1, 308 p.,
        https://doi.org/10.3133/tm11E1
"""

# Copyright © 2026, Ethan I. Schaefer (eschaefer@seti.org)
#
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
import functools as _functools
import math as _math

# Internal.
import lgrs.srs.wkt as _wkt


# endregion
###############################################################################
# region> UTILITIES
###############################################################################
@_functools.cache
def calculate_diagonal_length(side_length: float, *, safe_up: bool) -> float:
    """
    Calculate the diagonal length of a box given its side length.

    Parameters
    ----------
    side_length : float
        The side length of the box, in projected (LPS/LTM) space.
    safe_up : bool
        Whether the diagonal length should be exaggerated by a `SAFE_FACTOR`.

    Returns
    -------
    diagonal_length : float
        The diagonal length of the box, in projected (LPS/LTM) space.

    Examples
    --------
    >>> approx_sqrt_2 = calculate_diagonal_length(1, safe_up=False)
    >>> abs(approx_sqrt_2 - 2**0.5) < 1e-6
    True
    >>> larger = calculate_diagonal_length(1, safe_up=True)
    >>> larger > approx_sqrt_2
    True
    """
    diag_length = _math.sqrt(2 * side_length**2)
    if safe_up:
        diag_length *= SAFETY_FACTOR
    return diag_length


def calculate_m_per_degree_longitude(latitude: float) -> float:
    """
    Calculate the length of a degree of longitude in meters.

    Parameters
    ----------
    latitude : float
        That latitude at which to calculate.

    Returns
    -------
    longitude_degree_length : float
        The length of a degree of longitude in meters.

    Examples
    --------
    >>> calculate_m_per_degree_longitude(45)
    21441.84671321207
    """
    m_per_deg_lon = (
        LUNAR_CIRCUMFERENCE * _math.cos(_math.radians(latitude)) / 360
    )
    return m_per_deg_lon


# TODO: Delete unused parts of this module when code is mature.
#  Everything geodesic?
def projected_length_to_min_max_geodesic(
    proj_length: float, *, safe: bool
) -> tuple[float, float]:
    min_geod_length = proj_length / MAX_LINEAR_DISTORTION
    max_geod_length = proj_length / MIN_LINEAR_DISTORTION
    if safe:
        min_geod_length /= SAFETY_FACTOR
        max_geod_length *= SAFETY_FACTOR
    return (min_geod_length, max_geod_length)


def geodesic_length_to_min_max_projected(
    geod_length: float, *, safe: bool
) -> tuple[float, float]:
    min_proj_length = MIN_LINEAR_DISTORTION * geod_length
    max_proj_length = MAX_LINEAR_DISTORTION * geod_length
    if safe:
        min_proj_length /= SAFETY_FACTOR
        max_proj_length *= SAFETY_FACTOR
    return (min_proj_length, max_proj_length)


# endregion
###############################################################################
# region> REFERENCE VALUES
###############################################################################
# Lengths.
LUNAR_CIRCUMFERENCE = 2 * _math.pi * _wkt.LUNAR_RADIUS
M_PER_DEGREE_LATITUDE = LUNAR_CIRCUMFERENCE / 360
# Note: Small degree increment that everywhere measures <=1 mm and is
# not lost to floating-point precision in common calculations. Actual
# value could probably be much smaller, but this magnitude suffices for
# our purposes.
DEGREE_EPSILON = 0.001 / M_PER_DEGREE_LATITUDE

# Distortion.
# Note: geodesic_distance = projected_distance / distortion
MIN_LINEAR_DISTORTION: float = 0.994  # At either pole in LPS.
# Note: Described as "just greater than 1.0016" in M2025 for 80° N/S.
# Due to `prefer_lps` constraint, LPS coordinates are used as slightly
# equatorward latitudes, with higher distortion, so instead use maximum
# geodesic side length of a nominal 1 m x 1 m `LpsLgrsBox`.
# TODO: Brute-force calculate this value.
MAX_LINEAR_DISTORTION: float = 1.0017

# Other.
SAFETY_FACTOR = 1.1
# Note: If `SAFETY_FACTOR` far exceeds distortion, distortion effects
# can often be ignored, simplifying calculations.
assert (SAFETY_FACTOR - 1.0) > 10 * (
    max(MIN_LINEAR_DISTORTION**-1, MAX_LINEAR_DISTORTION) - 1.0
)


# endregion
###############################################################################
# region> SENTINELS
###############################################################################
class _DefaultType:
    def __repr__(self):
        return "<DEFAULT>"


DEFAULT = _DefaultType()


# endregion
