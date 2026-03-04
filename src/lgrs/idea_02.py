##############################################################################
# region> IMPORT
##############################################################################
import abc
import functools
import pyproj
import typing



# endregion
##############################################################################
# region> EXCEPTIONS
##############################################################################
class NonGriddedException(pyproj.exceptions.CRSError):
    pass


# endregion
##############################################################################
# region> REFERENCE SYSTEM CLASSES
##############################################################################
class GRS:
    # Note: Will raise `NonGriddedException`, if appropriate.
    ...

class AnyRS(GRS, pyproj.CRS, abc.ABC):
    # Note: Though not yet fleshed out, the relationship between
    # `AnyRS`, `GRS`, and `pyproj.CRS` is conceptually analogous to the
    # relationship (elaborated further below) between `AnyTransformer`,
    # `GriddedTransformer`, and `pyproj.Transformer`.
    ...

    @classmethod
    def __subclasshook__(cls, other: type) -> bool:
        return issubclass(other, (pyproj.CRS, GRS))



# endregion
##############################################################################
# region> TRANSFORMER CLASSES
##############################################################################
class GriddedTransformer:
    @classmethod
    def from_rs(
            cls, rs_from: typing.Any, rs_to: typing.Any, *args, **kwargs
    ) -> type[typing.Self]:
        # Note: If both `rs_from` and `rs_to` are CRSs, raise
        # `NonGriddedException`. Final code will be much better than
        # this.
        for rs in (rs_from, rs_to):
            try:
                pyproj.CRS.from_user_input(rs)
            except pyproj.exceptions.CRSError:
                return GriddedTransformer()
            else:
                raise NonGriddedException(
                    f"Reference system is not gridded: {rs!r}"
                )

class AnyTransformer(GriddedTransformer, pyproj.Transformer, abc.ABC):
    """
    Abstract base class with extended transformer support.

    Designed to be a drop-in replacement for `pyproj.Transformer` in most
    code, this class has the following features:
        1) Any factory method (`from_*()`) from `pyproj.Transformer` and
           `GriddedTransformer` is supported and returns an instance of the
           corresponding type.
        2) For convenience, `from_crs()` is extended to support equivalent
           calls to `from_rs()`.
        3) This class is an abstract base class to both `pyproj.Transformer`
           and `GriddedTransformer`.
    """
    # Note: Why not call this `BaseTransformer`? While it is an abstract
    # base class, it *also* inherits from its abstract child classes.
    # This makes the code simpler and aids linting/auto-completion, but
    # somewhat blurs the "base" relevance. I'm not opposed to going with
    # "Base" instead of "Any" throughout, if that's preferable. One
    # couterargument is that `AnyTransformer` (even if it is
    # reimplemented to not properly inherit from any preexisting
    # transformer class) will still have methods that are not found on
    # its children, which strikes me as a little confusing.

    @classmethod
    def __subclasshook__(cls, other: type) -> bool:
        return issubclass(other, (pyproj.Transformer, GriddedTransformer))

    @classmethod
    @functools.wraps(pyproj.Transformer.from_crs)
    def from_crs(
            cls, crs_from: typing.Any, crs_to: typing.Any, *args, **kwargs
    ) -> pyproj.Transformer | GriddedTransformer:
        # Note: Returns output of `pyproj.Transformer.from_crs(...) or
        # `GriddedTransformer.from_rs(...)`, as appropriate.
        # Note: In final code, assessment will be optimized.
        try:
            return GriddedTransformer.from_rs(crs_from, crs_to,
                                              *args, **kwargs)
        except NonGriddedException:
            return pyproj.Transformer.from_crs(crs_from, crs_to,
                                               *args, **kwargs)



# endregion
##############################################################################
# region> DEMONSTRATION CODE
##############################################################################
if __name__ == "__main__":
    # Custom authorities are used to signal gridded mode.
    # Note: Use of custom authorities is explicitly recommended in the
    # PROJ docs
    # (https://proj.org/en/stable/apps/projinfo.html#cmdoption-projinfo-output-id).
    # Note: We could test "LGRS" and "ACC" against
    # `pyproj.database.get_authorities()` at startup and issue a warning
    # if there is a collision, as future-proofing precaution.
    gridded_transformer_1 = GriddedTransformer.from_rs(
        "LTM:23N", "LGRS:23JFJ"
    )
    gridded_transformer_2 = GriddedTransformer.from_rs(
        "LGRS:23JFJ", "LTM:23N",
    )
    gridded_transformer_3 = GriddedTransformer.from_rs(
        "ACC:23JFJ", "LTM:23N",
    )

    # An equivalent instance, including type, is returned whether using
    # `pyproj.Transformer`, `GriddedTransformer`, or `AnyTransformer`.
    normal_transformer = pyproj.Transformer.from_crs(
        "EPSG:4326", "EPSG:26917"
    )
    test_normal_transformer = AnyTransformer.from_crs(
        "EPSG:4326", "EPSG:26917"
    )
    assert (test_normal_transformer == normal_transformer)
    assert isinstance(test_normal_transformer, pyproj.Transformer)
    test_gridded_transformer_1 = GriddedTransformer.from_rs(
        "LTM:23N", "LGRS:23JFJ"
    )
    # Below: Commented out because equality testing not yet supported.
    # assert (test_gridded_transformer_1 == gridded_transformer_1)
    assert isinstance(test_gridded_transformer_1, GriddedTransformer)

    # However, a request for a CRS-to-CRS `GriddedTransformer` will
    # raise an error, consistent with the scope of `GriddedTransformer`.
    try:
        nongridded_transformer = GriddedTransformer.from_rs(
            "EPSG:4326", "EPSG:26917"
        )
    except NonGriddedException:
        pass
    else:
        raise TypeError("`NonGriddedException` expected.")

    # Both `pyproj.Transformer` and `GriddedTransformer` instances test
    # as instances of `AnyTransformer`. This allows `AnyTransformer` to
    # be generally used as a drop-in replacement for
    # `pyproj.Transformer`.
    assert isinstance(normal_transformer, AnyTransformer)
    assert isinstance(gridded_transformer_1, AnyTransformer)
    # Note: `AnyTransformer` is abstract and never instantiated.
    assert (type(test_normal_transformer) is pyproj.Transformer)

# endregion