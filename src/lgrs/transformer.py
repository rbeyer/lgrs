# Copyright 2026, Ethan I. Schafer (eschaefer@seti.org)
#
# Reuse is permitted under the terms of the license.
# The AUTHORS file and the LICENSE file are at the
# top level of this library.

##############################################################################
# region> IMPORT
##############################################################################
# External.
import abc as _abc
import numpy as _np
import pyproj as _pyproj
from pyproj import aoi as _pyproj_aoi
import typing as _typing

# Internal.
import lgrs.srs.srs as _lgrs_srs
import lgrs.exceptions as _lgrs_exceptions



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
        # `NonGriddedError`.
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
            Input x coordinate(s) or xy grid string(s), as appropriate for
            `.source_srs`.
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
    source_srs: _pyproj.CRS | _lgrs_srs.GRS
    target_srs: _pyproj.CRS | _lgrs_srs.GRS

    def has_inverse(self) -> bool:
        ...

    def is_exact_same(self, other: _typing.Any) -> bool:
        ...

    @staticmethod
    def to_wkt() -> _typing.NoReturn:
        raise _lgrs_exceptions.NonGriddedError(
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
            cls, srs_from: _typing.Any, srs_to: _typing.Any,
            *args, **kwargs
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