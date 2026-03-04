import abc
import functools
import typing

import pyproj


class BaseRS(abc.ABC):
    ...
BaseRS.register(pyproj.CRS)

class GRS(BaseRS):
    ...

class AnyRS(GRS, pyproj.CRS):
    ...


class BaseTransformer(abc.ABC):
    ...
BaseTransformer.register(pyproj.Transformer)

class GriddedTransformer(BaseTransformer):
    @classmethod
    def from_rs(
            cls, rs_from: typing.Any, rs_to: typing.Any, *args, **kwargs
    ) -> type[typing.Self]:
        ...

class AnyTransformer(GriddedTransformer, pyproj.Transformer):
    @classmethod
    @functools.wraps(pyproj.Transformer.from_crs)
    def from_crs(
            cls, crs_from: typing.Any, crs_to: typing.Any, *args, **kwargs
    ) -> pyproj.Transformer | GriddedTransformer:
        # Note: Returns output of `pyproj.Transformer.from_crs(...) or
        # `GriddedTransformer.from_rs(...)`, as appropriate.
        ...

# The original `pyproj.Transformer` that we all know and love.
normal_transformer = pyproj.Transformer.from_crs(
    "EPSG:4326", "EPSG:26917"
)

# `GriddedTransformer` will support transformations from, to, and
# between GRSs.
# Note: Use of "custom" authorities is explicitly recommended in the
# PROJ docs
# (https://proj.org/en/stable/apps/projinfo.html#cmdoption-projinfo-output-id).
# Note: We could test "LGRS" and "ACC" against
# `pyproj.database.get_authorities()` at startup and issue a warning if
# there is a collision.
gridded_transformer_1 = GriddedTransformer.from_rs(
    "LTM:23N", "LGRS:23JFJ"
)
gridded_transformer_2 = GriddedTransformer.from_rs(
    "LGRS:23JFJ", "LTM:23N",
)

# However, a request for a CRS-to-CRS transformer will raise an error,
# consistent with the scope of `GriddedTransformer`.
nongridded_transformer = GriddedTransformer.from_rs(
    "EPSG:4326", "EPSG:26917"
)

# `AnyTransformer`, on the other hand, will support all CRS and GRS
# mixes. In other words, its functionality is the union of
# `pyproj.Transformer` and `GridedTransformer`, but it does not extend
# GRS support beyond whatever `GridedTransformer` does. The intent is
# that `AnyTransformer` can be a drop-in replacement for
# `pyproj.Transformer` in most code.
normal_transformer_equivalent = AnyTransformer.from_crs(
    "EPSG:4326", "EPSG:26917"
)
# Below: `AnyTransformer.from_crs()` allows misnomer that `crs_to` is
# an LGRS area (rather than a CRS).
gridded_transformer_1_equivalent = AnyTransformer.from_crs(
    "LTM:23N", "LGRS:23JFJ"
)

# One exception to `AnyTransformer`'s "drop-in replacement" suitability
# is type checking, which must instead use `BaseRS`.
# TODO: There is an alternative implementation in which all attributes
#  required by `GriddedTransformer`, *even those not common to
#  `pyproj.Transformer` (e.g., `.from_rs()`), are defined in
#  `BaseTransformer`. That would allow BaseTransformer to be a complete
#  drop-in for `pyproj.Transformer` and `GriddedTransformer` at the
#  mental cost of: (1) the ostensible *base* class having attributes
#  not "inherited" by `pyproj.Transformer`, (2) consolidation of code
#  from `GriddedTransformer` and `AnyTransformer` (in the current
#  implementation) into `BaseTransformer`, making for lengthier, more
#  complex method bodies, and (3) loss of most `pyproj.Transformer`
#  auto-completion in the new drop-in.
isinstance(normal_transformer, AnyTransformer)  # False.
isinstance(gridded_transformer_1, AnyTransformer)  # False.
isinstance(normal_transformer, BaseTransformer)  # True.
isinstance(gridded_transformer_1, BaseTransformer)  # True.