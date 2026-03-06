##############################################################################
# region> IMPORT
##############################################################################
import abc as _abc
import collections as _collections
import functools as _functools
import numpy as _np
import pyproj as _pyproj
from pyproj import database as _pyproj_database
from pyproj import aoi as _pyproj_aoi
import typing as _typing



# endregion
##############################################################################
# region> EXCEPTIONS
##############################################################################
class NonGriddedException(_pyproj.exceptions.CRSError):
    """
    Raised when a non-gridded object is unexpectedly encountered.

    For example, when a `pyproj.CRS` is encountered but a `GRS` is
    expected, or when a `pyproj.Transformer` is encountered but a
    `GriddedTransformer` is expected.
    """
    pass



# endregion
##############################################################################
# region> CACHING
##############################################################################
# Would cache `CRS`, `SRS`, `pyproj.Transformer`, and `GriddedTransformer`
# instances that are created via this library.

_CACHING_IS_ENABLED: bool = True

_cache: dict[tuple[str, _typing.Any], _typing.Any] = {}

def enable_caching(enable: bool = True, clear: bool = False) -> None:
    """
    Enable or disable caching, and optionally clear the cache.

    Parameters
    ----------
    enable : bool, default=True
        Whether to enable caching.
    clear : bool, default=False
        Whether to clear the cache.

    """
    global _CACHING_IS_ENABLED
    _CACHING_IS_ENABLED = enable
    if clear:
        _cache.clear()



# endregion
##############################################################################
# region> SPATIAL REFERENCE SYSTEMS
##############################################################################
# Note: Unfortunately, if we want to replicate
# `pyproj.query_utm_crs_info()` as closely as possible, we'd need to
# implement something like `pyproj.database.CRSInfo` (stub below) and
# `pyproj.database.PJType`, possibly more.
class SRSInfo(_pyproj_database.CRSInfo):
    ...

# Conservative option, nearly identical to
# `pyproj.database.query_utm_crs_info()`. Note the necessary inclusion
# of `extend_ltm` to cover the 80-82 degrees LPS/LTM overlap.
def query_ltm_crs_info(
        datum_name: str | None = "IAU_2015:30100",
        area_of_interest: _pyproj_aoi.AreaOfInterest | None = None,
        contains: bool = False, *,
        extend_ltm: bool = False,
) -> list[SRSInfo]:
    ...

# Preferred option, which extends support to LPS and supports querying
# by point(s), which will be needed to support `GriddedTransform`
# (though `GriddedTransform` might use some intermediate `np.ndarray`
# form, for performance, rather than the final output of this function).
# Note: Might be preferable to instead return some subclass of `list`
# that has useful (but possibly empty) subsets accessible as `.lps`,
# `.ltm`, and `.ltm_extended`.
def query_lps_and_ltm_crs_info(
        datum_name: str | None = "IAU_2015:30100",
        area_of_interest: _pyproj_aoi.AreaOfInterest | None = None,
        contains: bool = False, *,
        extend_ltm: bool = False,
        latitude: float | _collections.abc.Iterable[float] | None = None,
        longitude: float | _collections.abc.Iterable[float] | None = None
) -> list[SRSInfo]:
    """
    Query for LPS and LTM CRS information.

    Parameters
    ----------
    datum_name : str, default="IAU_2015:30100"
        The name of the datum.
    area_of_interest : AreaOfInterest, optional
        Filter `infos` by `area_of_interest`. Not compatible with `latitude`
        and `longitude`.
    contains : bool, default=False
        If `True`, `infos` will only reference a CRS if its area of use entirely
        contains `area_of_interest`. If `False`, `infos` will only reference a
        CRS if its area of use intersects the specified `area_of_interest`.
        Ignored if `area_of_interest` is unspecified.
    extend_ltm : bool, default=False
        Whether to use extended LTM zones, which span from 80 to 82 degrees N
        and S.
    latitude : float or iterable of floats, optional
        The latitude(s) to query. Numpy arrays are preferred.
    longitude : float or array, optional
        The longitudes(s) to query. Numpy arrays are preferred.

    Returns
    -------
    infos : list[SRSInfo]
        List of LPS and/or LTM CRS information instances.

    Raises
    ------
    TypeError
        If the combination of `area_of_interest`, `latitude`, and `longitude`
        are under- or over-specified.

    """
    match (latitude, longitude).count(None):
        case 1:
            raise TypeError(
                "Must specify both `latitude` and `longitude`, or "
                "neither."
            )
        case 2:
            if area_of_interest:
                raise TypeError("Cannot specify both `area_of_interest` and "
                                "`latitude`, `longitude`.")
    ...

class CRS(_pyproj.CRS):
    @_functools.wraps(_pyproj.CRS.__init__)
    def __init__(self, *args, **kwargs) -> None:
        # TODO: Add LTM support equivalent to existing UTM support. The
        #  expectation is that this `CRS` class could be dropped once
        #  LTM gains PROJ support.
        # Example: `CRS("IAU_2015:30100 / LTM zone 23N")
        # Example: `CRS(proj="ltm", zone=23, ellps="IAU_2015:30100")`
        # Note: My ideal would be that LPS would also be supported by
        # this syntactic sugar, but since UPS is not thusly supported,
        # that's probably unrealistic.
        # Fall back to `super().__init__(...)` if not LTM specific.
        ...

class GRS:
    """
    Class for gridded reference systems.
    """
    def __init__(self, *args, **kwargs) -> None:
        # Support instantiation by "LGRS:" and "ACC:", or maybe drop the
        # colons?
        # Note: Use of custom authorities is explicitly recommended in
        # the PROJ docs
        # (https://proj.org/en/stable/apps/projinfo.html#cmdoption-projinfo-output-id).
        # Note: We could test "LGRS" and "ACC" against
        # `pyproj.database.get_authorities()` at startup and issue a
        # warning if there is a collision, as future-proofing
        # precaution.
        ...

class BaseSRS(GRS, _pyproj.CRS, _abc.ABC):
    """
    Abstract base class for spatial reference systems.
    """
    ...
BaseSRS.register(_pyproj.CRS)
BaseSRS.register(GRS)



# endregion
##############################################################################
# region> TRANSFORMERS
##############################################################################
class GriddedTransformer:

    # Begin: `pyproj.Transformer` primary (~required) counterparts.
    @classmethod
    def from_srs(
            cls, srs_from: _typing.Any, srs_to: _typing.Any, *args, **kwargs
    ) -> type[_typing.Self]:
        """
        Make a Transformer to and/or from a gridded reference system (`GRS`).

        Parameters
        ----------
        srs_from : CRS, GRS, or suitable input
            Spatial reference system of input data.
        srs_to : CRS, GRS, or suitable input
            Spatial reference system of output data.
        *args
            Additional positional arguments are the same as those for
            `pyproj.Transformer.from_crs()`.
        **kwargs
            Additional keyword arguments are the same as those for
            `pyproj.Transformer.from_crs()`.

        Returns
        -------
        transformer : GriddedTransformer
            The created transformer.

        Examples
        --------
        >>> gt_1 = GriddedTransformer.from_srs("IAU_2015:30100", "LGRS:")
        >>> gt_2 = GriddedTransformer.from_srs("ACC:", "IAU_2015:30100")
        >>> gt_3 = GriddedTransformer.from_srs("IAU_2015:30100", "LGRS:")
        >>> assert gt_1 is gt_3  # Only if `enable_caching()`.
        """
        # Note: If both `srs_from` and `srs_to` are CRSs, raise
        # `NonGriddedException`.
        ...

    # TODO: We should decide whether to emulate the return type behavior
    #  of `pyproj.Transformer.transform()`, which essentially matches
    #  that of the inputs. This is challenging for us because the
    #  transformation may change dimensionality (e.g.,
    #  grid string --> tuple[float, float]). (This complication results
    #  in a complex return type hint; see below.) The utility of arrays
    #  of strings is also dubious, in my experience. But I think
    #  adapting the relevant `pyproj` utilities (`_copytobuffer()` and
    #  `_convertback()`) wouldn't be too hard.
    def transform(
            self, xx: _typing.Any, yy: _typing.Any = None, *args, **kwargs
    ) -> str | tuple[str, ...] | list[str] | tuple[float | tuple[float, ...] | list[float] |  _np.ndarray, ...] | _np.ndarray:
        """
        Transform points between two spatial reference systems.

        Parameters
        ----------
        xx : scalar, str, or array
            Input x coordinate(s) or xy grid string(s).
        yy : scalar or array, optional
            Input y coordinate(s). If `xx` is specified by string(s), must be
            `None`.
        *args
            Additional positional arguments are the same as those for
            `pyproj.Transformer.transform()`.
        **kwargs
            Additional keyword arguments are the same as those for
            `pyproj.Transformer.transform()`.

        Returns
        -------
        transformed : str, tuple of str, or tuple of float or float sequences
            Return type matches type of `xx` as much as possible.

        Raises
        ------
        TypeError
            If inputs are not compatible with this transformer.

        See Also
        --------
        pyproj.Transformer.transform :
            CRS transformation and additional relevant documentation.

        Examples
        --------
        >>> gt_1 = GriddedTransformer.from_srs("IAU_2015:30100", "LGRS:")
        >>> lgrs_str = gt_1.transform(2., 1.)
        >>> gt_2 = GriddedTransformer.from_srs("ACC:", "IAU_2015:30100")
        >>> lat, lon = gt_2.transform("23NHGK58E31")
        """
        # TODO: Confirm default lat/lon order.
        ...

    # TODO: I'm disinclined to implement `itransform()`, but let me know
    #  your thoughts.

    # End: `pyproj.Transformer` primary (required) counterparts.

    # Begin: `pyproj.Transformer` secondary counterparts.
    # Note: I'm inclined to support at least the "low-hanging fruit"
    # that overlap with `pyproj.Transformer` attributes, to reduce the
    # "mental friction". Perhaps even "support" all attributes /
    # methods, but simply yield a descriptive error for any we don't
    # truly wish to (or can't) implement (e.g., `.to_wkt()` below.) Some
    # examples (incomplete) below.
    accuracy: float
    area_of_use: _pyproj_aoi.AreaOfUse
    description: str
    name: str
    source_srs: _pyproj.CRS | GRS
    target_crs: _pyproj.CRS | GRS

    def has_inverse(self) -> bool:
        ...

    def is_exact_same(self, other: _typing.Any) -> bool:
        ...

    @staticmethod
    def to_wkt() -> _typing.NoReturn:
        raise NonGriddedException(
            "WKT does not support transformations involving gridded "
            "coordinate systems."
        )
    # End: `pyproj.Transformer` secondary counterparts.


class BaseTransformer(_abc.ABC):
    """
    Abstract base class for generating transformers.

    Supports all factory methods (`.from_*()`) from `pyproj.Transformer` and
    `GriddedTransformer`. Each returns an instance of the appropriate type,
    that is, either `pyproj.Transformer` or `GriddedTransformer`. For
    convenience, `.from_srs()` is extended to support equivalent calls to
    `pyproj.Transformer.from_crs()`.
    """
    from_crs = _pyproj.Transformer.from_crs
    from_pipeline = _pyproj.Transformer.from_pipeline
    from_proj = _pyproj.Transformer.from_proj

    @classmethod
    def from_srs(
            cls, srs_from: _typing.Any, srs_to: _typing.Any, *args,
            cache: bool = True, **kwargs
    ) -> GriddedTransformer | _pyproj.Transformer:
        """
        Make a Transformer for any combination of `CRS` and `GRS`.

        Parameters
        ----------
        srs_from : CRS, GRS, or suitable input
            Spatial reference system of input data.
        srs_to : CRS, GRS, or suitable input
            Spatial reference system of output data.
        *args
            Additional positional arguments are the same as those for
            `pyproj.Transformer.from_crs()`.
        **kwargs
            Additional keyword arguments are the same as those for
            `pyproj.Transformer.from_crs()`.

        Returns
        -------
        transformer : pyproj.Transformer | GriddedTransformer
            The created transformer.

        Examples
        --------
        >>> import pyproj
        >>> crs_trans = BaseTransformer.from_srs("EPSG:4326", "EPSG:26917")
        >>> assert isinstance(crs_trans, pyproj.Transformer)
        >>> grid_trans = BaseTransformer.from_srs("IAU_2015:30100", "LGRS:")
        >>> assert isinstance(grid_trans, GriddedTransformer)
        >>> grid_trans_2 = BaseTransformer.from_srs("IAU_2015:30100", "LGRS:")
        >>> assert grid_trans is grid_trans_2  # Only if `enable_caching()`.
        """
        # Note: Allow `crs_from` and `crs_to` as aliases of `srs_from` and
        # `srs_to`.
        ...
BaseTransformer.register(_pyproj.Transformer)
BaseTransformer.register(GriddedTransformer)



# endregion
