##############################################################################
# region> IMPORT
##############################################################################
import abc as _abc
import functools as _functools
import typing as _typing

# endregion


##############################################################################
# region> ATTRIBUTE INTENTIONS
##############################################################################
class ExpectedAttribute(_functools.cached_property):

    def __init__(self):
        """
        Construct an expected attribute.

        An inherited `abc.abstractmethod` must be overridden at a class's top
        level or the class cannot be instantiated. When the actual assignment
        of the corresponding attribute occurs elsewhere (e.g., within
        `.__init__()`), use of the current class can express the intent to
        assign the required attribute but still ensure that a descriptive error
        is raised if that assignment does not occur.

        Examples
        --------
        >>> import abc
        >>> class MyBaseClass(abc.ABC):
        ...     @property
        ...     @abc.abstractmethod
        ...     def some_attribute_name(self) -> str:
        ...         ...
        >>> class MyNaiveClass(MyBaseClass):
        ...     pass
        >>> class MyFaultyClass(MyBaseClass):
        ...     some_attribute_name = ExpectedAttribute()
        >>> class MyValidClass(MyBaseClass):
        ...     some_attribute_name = ExpectedAttribute()
        ...
        ...     def __init__(self):
        ...         self.some_attribute_name = "spam"
        >>> naive = MyNaiveClass()  # Fails to instantiate.
        Traceback (most recent call last):
            ...
        TypeError: Can't instantiate abstract class MyNaiveClass without an implementation for abstract method 'some_attribute_name'
        >>> faulty = MyFaultyClass()
        >>> faulty.some_attribute_name  # Raises AttributeError.
        ... # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        AttributeError: Unexpectedly, `.some_attribute_name` was not assigned to: ...
        >>> valid = MyValidClass()  # Fails to instantiate.
        >>> valid.some_attribute_name
        'spam'
        """
        super().__init__(self.func)

    def __set_name__(self, owner: type, name: str) -> None:
        self.owner = owner
        self.name = name
        super().__set_name__(owner, name)

    def func(self, instance: _typing.Any) -> _typing.NoReturn:
        """
        Raise descriptive error if attribute is unassigned.

        Parameters
        ----------
        instance : typing.Any
            The instance to which the attribute should have been assigned.

        Raises
        -------
        AttributeError
            Always raised.
        """
        raise AttributeError(f"Unexpectedly, `.{self.name}` was not "
                             f"assigned to: {instance!r}")

def make_abstract_property():
    @property
    @_abc.abstractmethod
    def attribute(self):
        ...
    return attribute

# endregion